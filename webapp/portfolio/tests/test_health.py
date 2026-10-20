"""死活監視（ヘルスチェック）と、ログに個人情報を出力しないことのテスト。"""

import logging
from io import StringIO
from unittest import mock

from allauth.socialaccount.models import SocialAccount
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse

from portfolio import health
from portfolio.tests.helpers import create_user


class HealthCheckTests(TestCase):
    def get(self, **extra):
        return self.client.get("/healthz", **extra)

    def test_returns_ok_without_authentication(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_database_failure_returns_503(self):
        with mock.patch.object(health, "database_is_available", return_value=False):
            response = self.get()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"ng")

    def test_database_connection_error_is_detected(self):
        with mock.patch(
            "portfolio.health.connection.cursor", side_effect=OperationalError("down")
        ):
            self.assertFalse(health.database_is_available())

    @override_settings(HEALTH_MAX_SERVER_ERRORS=2)
    def test_too_many_server_errors_return_503(self):
        for _ in range(2):
            health.record_server_error()
        self.assertEqual(self.get().status_code, 200)
        health.record_server_error()
        self.assertEqual(self.get().status_code, 503)

    @override_settings(HEALTH_MAX_SERVER_ERRORS=0)
    def test_old_server_errors_are_ignored(self):
        with mock.patch("portfolio.health.time.time", return_value=1_000_000):
            health.record_server_error()
        self.assertEqual(self.get().status_code, 200)

    def test_response_has_no_internal_information(self):
        health.record_server_error()
        body = self.get().content.decode()
        self.assertNotRegex(body, r"\d")

    def test_post_is_not_allowed(self):
        self.assertEqual(self.client.post("/healthz").status_code, 405)

    def test_healthz_is_not_rate_limited_as_public_page(self):
        with override_settings(RATE_LIMITS={"public": (1, 60), "login": (1, 60)}):
            statuses = {self.get().status_code for _ in range(5)}
        self.assertEqual(statuses, {200})


class ServerErrorCountTests(TestCase):
    def test_5xx_responses_are_counted(self):
        self.client.raise_request_exception = False
        with mock.patch(
            "portfolio.views.services.build_skill_rows", side_effect=RuntimeError
        ):
            user = create_user("taro", public=True)
            self.client.get(f"/u/{user.username}/api/skills")
        self.assertEqual(health.recent_server_errors(), 1)

    def test_health_check_failure_is_not_counted(self):
        with mock.patch.object(health, "database_is_available", return_value=False):
            self.client.get("/healthz")
        self.assertEqual(health.recent_server_errors(), 0)

    def test_4xx_responses_are_not_counted(self):
        self.client.get("/u/nobody/")
        self.assertEqual(health.recent_server_errors(), 0)

    def test_counting_failure_does_not_break_the_response(self):
        with mock.patch(
            "portfolio.health.ratelimit.increment", side_effect=OperationalError
        ):
            health.record_server_error()


class NoPersonalDataInLogsTests(TestCase):
    """ログにメールアドレス等の個人情報が出力されないことを確認する。"""

    EMAIL = "secret-person@example.com"

    def setUp(self):
        self.stream = StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setLevel(logging.DEBUG)
        root = logging.getLogger()
        previous_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.removeHandler, handler)
        self.addCleanup(root.setLevel, previous_level)

    def test_screens_and_errors_do_not_log_email(self):
        user = create_user("taro", public=True, email=self.EMAIL)
        SocialAccount.objects.create(user=user, provider="google", uid="u-1")
        self.client.force_login(user)
        self.client.get(reverse("manage"))
        self.client.get(reverse("manage-skillsheet-markdown"))
        self.client.raise_request_exception = False
        with mock.patch(
            "portfolio.manage_views.export.render_skillsheet", side_effect=RuntimeError
        ):
            self.client.get(reverse("manage-skillsheet-markdown"))
        self.assertNotIn(self.EMAIL, self.stream.getvalue())
