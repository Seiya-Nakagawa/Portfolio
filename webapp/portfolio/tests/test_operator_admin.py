"""運営管理（管理サイト）のテスト。"""

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from portfolio.models import Company, Project, UsageDaily
from portfolio.tests.helpers import create_operator, create_user


class OperatorAdminTestCase(TestCase):
    def setUp(self):
        self.operator = create_operator("ops")
        self.user = create_user("taro", public=True, email="taro@example.com")
        self.client.force_login(self.operator)

    def changelist(self):
        return reverse("admin:auth_user_changelist")

    def act(self, action, users):
        return self.client.post(
            self.changelist(),
            {"action": action, "_selected_action": [u.pk for u in users]},
            follow=True,
        )


class AccessTests(OperatorAdminTestCase):
    def test_non_staff_cannot_enter(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_staff_sees_user_counts(self):
        suspended = create_user("hanako")
        suspended.is_active = False
        suspended.save()
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["user_counts"],
            {"total": 3, "suspended": 1, "public": 2},
        )

    def test_usage_rows_come_from_usage_daily(self):
        from django.utils import timezone

        UsageDaily.objects.create(
            usage_date=timezone.localdate(), metric=UsageDaily.METRIC_SIGNUP, count=5
        )
        response = self.client.get(reverse("admin:index"))
        today_row = response.context["usage_rows"][0]
        self.assertIn(5, today_row["values"])

    def test_only_users_are_registered(self):
        from django.contrib import admin

        self.assertEqual(
            list(admin.site._registry),
            [get_user_model()],
        )

    def test_portfolio_data_is_not_exposed(self):
        company = Company.objects.create(owner=self.user, name="SecretCorp")
        Project.objects.create(
            owner=self.user,
            company=company,
            name="SecretProject",
            start_year_month="2024-01",
        )
        index = self.client.get(reverse("admin:index"))
        listing = self.client.get(self.changelist())
        for response in (index, listing):
            self.assertNotContains(response, "SecretCorp")
            self.assertNotContains(response, "SecretProject")
        self.assertEqual(self.client.get("/admin/portfolio/company/").status_code, 404)


class UserManagementTests(OperatorAdminTestCase):
    def test_changelist_lists_users(self):
        response = self.client.get(self.changelist())
        self.assertContains(response, "taro@example.com")

    def test_cannot_add_or_delete(self):
        self.assertEqual(
            self.client.get(reverse("admin:auth_user_add")).status_code, 403
        )
        self.assertEqual(
            self.client.get(
                reverse("admin:auth_user_delete", args=[self.user.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("admin:auth_user_change", args=[self.user.pk]),
                {"username": "changed"},
            ).status_code,
            403,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "taro")

    def test_bulk_delete_is_not_offered(self):
        self.act("delete_selected", [self.user])
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_suspend_and_resume(self):
        self.act("suspend", [self.user])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.act("resume", [self.user])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_cannot_suspend_self(self):
        self.act("suspend", [self.operator, self.user])
        self.operator.refresh_from_db()
        self.user.refresh_from_db()
        self.assertTrue(self.operator.is_active)
        self.assertFalse(self.user.is_active)

    def test_cannot_suspend_other_operator(self):
        other = create_operator("ops2")
        self.act("suspend", [other, self.user])
        other.refresh_from_db()
        self.assertTrue(other.is_active)

    def test_suspend_and_resume_are_recorded_in_history(self):
        self.act("suspend", [self.user])
        self.act("resume", [self.user])
        entries = LogEntry.objects.filter(object_id=str(self.user.pk))
        self.assertEqual(entries.count(), 2)
        self.assertTrue(all(e.user_id == self.operator.pk for e in entries))

    def test_individual_user_page_is_not_viewable(self):
        response = self.client.get(
            reverse("admin:auth_user_change", args=[self.user.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_suspended_user_cannot_log_in(self):
        self.act("suspend", [self.user])
        self.client.logout()
        self.user.refresh_from_db()
        self.user.set_password("pw-for-test")
        self.user.save()
        self.assertFalse(self.client.login(username="taro", password="pw-for-test"))

    def test_changelist_query_count_does_not_grow_with_users(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.client.get(self.changelist())
            return len(queries)

        before = count_queries()
        for i in range(5):
            create_user(f"extra{i}", public=True)
        self.assertEqual(count_queries(), before)


class GenerationCountTests(OperatorAdminTestCase):
    def count(self, metric):
        row = UsageDaily.objects.filter(metric=metric).first()
        return row.count if row else 0

    def test_markdown_generation_is_counted(self):
        self.client.get(reverse("manage-skillsheet-markdown"))
        self.assertEqual(self.count(UsageDaily.METRIC_SKILLSHEET_MD), 1)
