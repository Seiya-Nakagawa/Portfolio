"""死活監視（ヘルスチェック）と、ログに個人情報を出力しないことのテスト。"""

import logging
from datetime import timedelta
from io import StringIO
from unittest import mock

from allauth.socialaccount.models import SocialAccount
from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portfolio import health
from portfolio.models import JobRun, ReleasedUsername
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

    def test_database_read_error_is_detected(self):
        with mock.patch(
            "portfolio.health.get_user_model", side_effect=OperationalError("down")
        ):
            self.assertFalse(health.database_is_available())

    def test_stale_daily_maintenance_returns_503(self):
        JobRun.objects.filter(job_name=JobRun.JOB_DAILY_MAINTENANCE).update(
            succeeded_at=timezone.now() - timedelta(hours=27)
        )
        self.assertEqual(self.get().status_code, 503)

    def test_recent_daily_maintenance_is_healthy(self):
        JobRun.objects.filter(job_name=JobRun.JOB_DAILY_MAINTENANCE).update(
            succeeded_at=timezone.now() - timedelta(hours=25)
        )
        self.assertEqual(self.get().status_code, 200)

    def test_missing_daily_maintenance_record_returns_503(self):
        JobRun.objects.all().delete()
        self.assertEqual(self.get().status_code, 503)

    def test_migration_initializes_daily_maintenance_record(self):
        self.assertTrue(
            JobRun.objects.filter(job_name=JobRun.JOB_DAILY_MAINTENANCE).exists()
        )

    def test_server_errors_do_not_make_it_unhealthy(self):
        self.client.raise_request_exception = False
        user = create_user("taro", public=True)
        with mock.patch(
            "portfolio.views.services.build_skill_rows", side_effect=RuntimeError
        ):
            for _ in range(20):
                self.client.get(f"/u/{user.username}/api/skills")
        self.assertEqual(self.get().status_code, 200)

    def test_response_has_no_internal_information(self):
        body = self.get().content.decode()
        self.assertNotRegex(body, r"\d")

    def test_post_is_not_allowed(self):
        self.assertEqual(self.client.post("/healthz").status_code, 405)

    def test_healthz_is_not_rate_limited_as_public_page(self):
        with override_settings(RATE_LIMITS={"public": (1, 60), "login": (1, 60)}):
            statuses = {self.get().status_code for _ in range(5)}
        self.assertEqual(statuses, {200})


class DailyMaintenanceTests(TestCase):
    def test_success_records_last_success_time(self):
        JobRun.objects.update(succeeded_at=timezone.now() - timedelta(hours=30))
        call_command("daily_maintenance", stdout=StringIO())
        run = JobRun.objects.get(job_name=JobRun.JOB_DAILY_MAINTENANCE)
        self.assertLess(timezone.now() - run.succeeded_at, timedelta(minutes=1))

    def test_failure_does_not_record_success(self):
        stale = timezone.now() - timedelta(hours=30)
        JobRun.objects.update(succeeded_at=stale)
        with (
            mock.patch(
                "portfolio.management.commands.daily_maintenance.media_files."
                "purge_unreferenced_images",
                side_effect=OSError("disk"),
            ),
            self.assertRaises(OSError),
        ):
            call_command("daily_maintenance", stdout=StringIO())
        run = JobRun.objects.get(job_name=JobRun.JOB_DAILY_MAINTENANCE)
        self.assertEqual(run.succeeded_at, stale)

    def test_expired_username_reservations_are_purged(self):
        now = timezone.now()
        ReleasedUsername.objects.create(
            username="old", released_at=now - timedelta(days=91), released_by=None
        )
        ReleasedUsername.objects.create(
            username="new", released_at=now - timedelta(days=1), released_by=None
        )
        call_command("daily_maintenance", stdout=StringIO())
        self.assertEqual(
            list(ReleasedUsername.objects.values_list("username", flat=True)), ["new"]
        )


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
