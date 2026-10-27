"""商用化レビューで見送った指摘（Issue #189）の対応のテスト。"""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse

from portfolio import registry, usage
from portfolio.models import (
    Project,
    ProjectSkill,
    Skill,
    SkillCategory,
    UsageDaily,
    Work,
)
from portfolio.tests.helpers import create_user

PASSWORD = "pw-for-test"


def _master(skill_id, category, name):
    return Skill.objects.create(
        skill_id=skill_id,
        category=category,
        name=name,
        sort_order=10,
        is_master=True,
    )


class MergeCustomSkillsTests(TestCase):
    """共通マスタへ同名の項目を追加したとき、独自スキル項目を統合する。"""

    def setUp(self):
        self.operator = create_user("operator", is_staff=True)
        self.user = create_user("user-a")
        SkillCategory.objects.create(name="言語", sort_order=10)
        self.custom = Skill.objects.create(
            skill_id="u-aaaa",
            category="言語",
            name="Rust",
            sort_order=0,
            owner=self.user,
        )
        self.project = Project.objects.create(
            owner=self.user, name="案件", start_year_month="2024-01"
        )
        ProjectSkill.objects.create(
            project=self.project, skill=self.custom, version="1"
        )

    def test_運営者の追加で使用実績が共通マスタへ付け替わる(self):
        registry.save_skill(
            self.operator, {"skill_id": "rust", "category": "言語", "name": "rust"}
        )
        self.assertFalse(Skill.objects.filter(skill_id="u-aaaa").exists())
        usage_rows = ProjectSkill.objects.filter(project=self.project)
        self.assertEqual([r.skill_id for r in usage_rows], ["rust"])
        self.assertEqual(usage_rows[0].version, "1")

    def test_同じ案件に共通マスタの使用実績がある場合は独自の使用実績を削除する(self):
        master = _master("rust", "言語", "Rust")
        ProjectSkill.objects.create(project=self.project, skill=master, version="2")
        registry.merge_custom_skills_into_master(master)
        rows = ProjectSkill.objects.filter(project=self.project)
        self.assertEqual([(r.skill_id, r.version) for r in rows], [("rust", "2")])
        self.assertFalse(Skill.objects.filter(skill_id="u-aaaa").exists())

    def test_種類や名前が異なる独自スキル項目は統合しない(self):
        registry.save_skill(
            self.operator, {"skill_id": "go", "category": "言語", "name": "Go"}
        )
        self.assertTrue(Skill.objects.filter(skill_id="u-aaaa").exists())

    def test_種データの取り込みでも統合する(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "skills_master.json"
            path.write_text(
                json.dumps(
                    {"categories": [{"name": "言語", "skills": [{"name": "Rust"}]}]}
                ),
                encoding="utf-8",
            )
            out = StringIO()
            call_command("import_skill_master", seed_file=path, stdout=out)
        self.assertIn("統合しました", out.getvalue())
        self.assertFalse(Skill.objects.filter(skill_id="u-aaaa").exists())
        self.assertEqual(
            list(ProjectSkill.objects.values_list("skill__name", flat=True)), ["Rust"]
        )


class CategoryLockTests(TestCase):
    def setUp(self):
        self.user = create_user("user-a")
        SkillCategory.objects.create(name="言語", sort_order=10)

    def test_独自スキル項目の保存は種類の行をロックしてから行う(self):
        with mock.patch.object(
            registry, "_lock_categories", wraps=registry._lock_categories
        ) as lock:
            registry.save_skill(self.user, {"category": "言語", "name": "Rust"})
        lock.assert_called_once()

    def test_存在しない種類の独自スキル項目は作成できない(self):
        with self.assertRaises(registry.ValidationFailed):
            registry.save_skill(self.user, {"category": "ない", "name": "Rust"})


class UsageIncrementFailureTests(TestCase):
    def test_加算に失敗しても例外にならず警告を記録する(self):
        with (
            mock.patch("portfolio.usage._increment", side_effect=OperationalError),
            self.assertLogs("portfolio.usage", "WARNING") as logs,
        ):
            usage.increment(UsageDaily.METRIC_SKILLSHEET_PDF)
        self.assertIn("skillsheet_pdf", logs.output[0])

    def test_加算の失敗は呼び出し元のトランザクションを壊さない(self):
        from django.db import transaction

        user = create_user("taro")
        with transaction.atomic():
            with mock.patch(
                "portfolio.usage.UsageDaily.objects.filter",
                side_effect=OperationalError,
            ):
                usage.increment(UsageDaily.METRIC_SIGNUP)
            user.username = "taro2"
            user.save()
        user.refresh_from_db()
        self.assertEqual(user.username, "taro2")

    def test_職務経歴書の生成は加算が失敗しても成功する(self):
        user = create_user("taro")
        self.client.force_login(user)
        with mock.patch("portfolio.usage._increment", side_effect=OperationalError):
            response = self.client.get(reverse("manage-skillsheet-markdown"))
        self.assertEqual(response.status_code, 200)


class MediaDeliveryTests(TestCase):
    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.owner = create_user("owner", public=True, is_staff=True, password=PASSWORD)

    def _put(self, relative):
        path = Path(self._media.name) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG-data")

    def test_画像の応答はキャッシュさせない(self):
        relative = f"users/{self.owner.pk}/works/a.png"
        self._put(relative)
        response = self.client.get(f"/media/{relative}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-cache")

    def test_移行前の旧パスの画像は所有者が公開中なら配信する(self):
        self._put("works/old.png")
        Work.objects.create(
            owner=self.owner, title="実績", desc_ja="d", thumbnail="works/old.png"
        )
        response = self.client.get("/media/works/old.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-cache")

    def test_移行前の旧パスの画像は非公開なら404(self):
        self._put("works/old.png")
        Work.objects.create(
            owner=self.owner, title="実績", desc_ja="d", thumbnail="works/old.png"
        )
        self.owner.profile.is_public = False
        self.owner.profile.save()
        self.assertEqual(self.client.get("/media/works/old.png").status_code, 404)

    def test_参照されていない旧パスの画像は404(self):
        self._put("works/orphan.png")
        self.assertEqual(self.client.get("/media/works/orphan.png").status_code, 404)

    def test_旧パスでもディレクトリを遡るパスは配信しない(self):
        self.assertEqual(
            self.client.get("/media/works/../users/1/works/a.png").status_code, 404
        )
