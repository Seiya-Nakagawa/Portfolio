"""所有者の追加と既存データの移行（マイグレーション 0021〜0023）のテスト。

移行前の状態（0020）にデータを作成してから最新まで進め、運営者への紐づけを検証する。
"""

from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

AUTH = ("auth", "0012_alter_user_first_name_max_length")
BEFORE = [("portfolio", "0020_all_skills_master"), AUTH]
AFTER = [("portfolio", "0023_owner_required"), AUTH]


class OwnerMigrationTests(TransactionTestCase):
    def tearDown(self):
        # 他のテストのため、最新の状態に戻す。
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _migrate(self, targets):
        """指定した状態までマイグレーションを進め（戻し）、その状態のモデル群を返す。"""
        executor = MigrationExecutor(connection)
        executor.migrate(targets)
        executor = MigrationExecutor(connection)
        return executor.loader.project_state(targets).apps

    def _create_legacy_data(self, apps):
        User = apps.get_model("auth", "User")
        Skill = apps.get_model("portfolio", "Skill")
        Project = apps.get_model("portfolio", "Project")
        Company = apps.get_model("portfolio", "Company")
        Certification = apps.get_model("portfolio", "Certification")
        Work = apps.get_model("portfolio", "Work")
        SiteInfo = apps.get_model("portfolio", "SiteInfo")
        SkillsheetText = apps.get_model("portfolio", "SkillsheetText")

        User.objects.create(
            username="operator", password="pbkdf2$old", email="o@example.com"
        )
        Skill.objects.create(
            skill_id="python",
            category="言語",
            name="Python",
            sort_order=1,
            is_master=True,
        )
        Project.objects.create(
            project_id="p-1", name="案件", start_year_month="2024-01"
        )
        Company.objects.create(name="A社", kind="main", start_year_month="2020-01")
        Certification.objects.create(name="資格", acquired_on=date(2024, 1, 1), org="X")
        Work.objects.create(title="実績", desc_ja="d")
        SiteInfo.objects.create(
            site_info_id=1,
            name="氏名",
            typing_titles=["a"],
            catchphrase="c",
            intro="i",
            birth_date=date(1990, 1, 1),
            job="j",
            education="e",
            location="l",
            hobby="h",
            github_url="https://github.com/x",
            contact_message="m",
            contact_form_url="https://example.com",
            copyright_start_year=2024,
        )
        SkillsheetText.objects.create(
            text_key="summary", body="概要", updated_at=timezone.now()
        )

    def test_既存データが運営者に紐づき_運営者のアカウントが整う(self):
        old_apps = self._migrate(BEFORE)
        self._create_legacy_data(old_apps)

        new_apps = self._migrate(AFTER)
        operator = new_apps.get_model("auth", "User").objects.get(username="operator")
        for name in (
            "Project",
            "Company",
            "Certification",
            "Work",
            "SiteInfo",
            "SkillsheetText",
        ):
            with self.subTest(name):
                row = new_apps.get_model("portfolio", name).objects.get()
                self.assertEqual(row.owner_id, operator.pk)
        # 共通マスタの所有者は空のまま。
        self.assertIsNone(
            new_apps.get_model("portfolio", "Skill").objects.get().owner_id
        )
        # 文章項目は主キーの付け替え後も内容が残る。
        text = new_apps.get_model("portfolio", "SkillsheetText").objects.get()
        self.assertEqual((text.text_key, text.body), ("summary", "概要"))

        self.assertTrue(operator.is_staff)
        self.assertFalse(operator.password.startswith("pbkdf2"))
        self.assertTrue(operator.password.startswith("!"))
        profile = new_apps.get_model("portfolio", "UserProfile").objects.get(
            user=operator
        )
        self.assertTrue(profile.is_public)

    def test_ユーザーが複数いる場合は移行を中止する(self):
        old_apps = self._migrate(BEFORE)
        self._create_legacy_data(old_apps)
        old_apps.get_model("auth", "User").objects.create(username="other")

        with self.assertRaises(RuntimeError):
            self._migrate(AFTER)

        # 後始末で最新まで進められるよう、移行前の状態のまま既存データを消す。
        for name in (
            "ProjectSkill",
            "Project",
            "Company",
            "Certification",
            "Work",
            "SiteInfo",
            "SkillsheetText",
        ):
            old_apps.get_model("portfolio", name).objects.all().delete()
        old_apps.get_model("auth", "User").objects.all().delete()

    def test_データもユーザーもない新規構築では何もせず完了する(self):
        self._migrate(BEFORE)
        new_apps = self._migrate(AFTER)
        self.assertEqual(new_apps.get_model("auth", "User").objects.count(), 0)
