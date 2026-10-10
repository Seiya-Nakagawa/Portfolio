from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone

from portfolio.models import Project, ProjectSkill, Skill, Skillsheet
from portfolio.tests.test_manage import LoggedInTestCase

TODAY = date(2026, 9, 25)

# 架空のダミー本文。実データは含めない。
BODY = """# 職務経歴書

## ■開発経歴

**2000年01月〜2000年02月｜旧案件**（3名体制）

- 案件概要: ダミー

**1999年01月〜現在｜存在しない案件**

## ■テクニカルスキル

置き換え前の内容

## ■自己PR

ダミーの自己PRです。
"""


def _skill(skill_id, category, name, sort_order):
    return Skill.objects.create(
        skill_id=skill_id, category=category, name=name, sort_order=sort_order
    )


class SkillsheetTestCase(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        java = _skill("java", "言語", "Java", 10)
        python = _skill("python", "言語", "Python", 20)
        _skill("cobol", "言語", "COBOL", 30)
        old = Project.objects.create(
            name="旧案件", start_year_month="2023-07", end_year_month="2025-03"
        )
        new = Project.objects.create(name="新案件", start_year_month="2025-04")
        ProjectSkill.objects.create(project=old, skill=java)
        ProjectSkill.objects.create(project=new, skill=python)

    def _save_body(self, body=BODY):
        return Skillsheet.objects.create(body=body, updated_at=timezone.now())

    def _get(self, name):
        with patch("portfolio.manage_views.timezone.localdate", return_value=TODAY):
            return self.call("get", name)


class RenderTests(SkillsheetTestCase):
    def test_スキル表と案件期間を差し替える(self):
        from portfolio import export

        self._save_body()
        rendered = export.render_skillsheet(TODAY)
        self.assertIn("| 言語 | Java | 2023年 | 1年9ヶ月 |", rendered.markdown)
        self.assertNotIn("置き換え前の内容", rendered.markdown)
        self.assertNotIn("COBOL", rendered.markdown)
        self.assertIn(
            "**2023年07月〜2025年03月｜旧案件**（3名体制）", rendered.markdown
        )
        self.assertIn("## ■自己PR", rendered.markdown)

    def test_案件見出しの期間のみ置き換え本文は変更しない(self):
        from portfolio import export

        self._save_body(
            "## ■開発経歴\n\n**2000年01月〜2000年02月｜旧案件**（3名体制）\n\n## ■テクニカルスキル\n"
        )
        rendered = export.render_skillsheet(TODAY)
        self.assertIn(
            "**2023年07月〜2025年03月｜旧案件**（3名体制）", rendered.markdown
        )

    def test_警告(self):
        from portfolio import export

        self._save_body()
        warnings = export.render_skillsheet(TODAY).warnings
        self.assertEqual(warnings.unmatched_projects, ["新案件"])
        self.assertEqual(warnings.unused_skill_count, 1)

    def test_HTMLにスタイルと表が含まれる(self):
        from portfolio import export

        self._save_body()
        html = export.render_skillsheet(TODAY).html
        self.assertIn("Noto Sans CJK JP", html)
        self.assertIn("<table>", html)

    def test_本文未登録はエラー(self):
        from portfolio import export, registry

        with self.assertRaises(registry.ValidationFailed):
            export.render_skillsheet(TODAY)

    def test_スキル見出しが0件や2件以上はエラー(self):
        from portfolio import export, registry

        for body in ("## ■開発経歴\n", BODY + "\n## ■テクニカルスキル\n\nx\n"):
            with self.subTest(body=body[:20]):
                self._save_body(body)
                with self.assertRaises(registry.ValidationFailed):
                    export.render_skillsheet(TODAY)
                Skillsheet.objects.all().delete()


class ApiTests(SkillsheetTestCase):
    def _put(self, body, expected):
        return self.call(
            "put",
            "manage-api-skillsheet",
            {"body": body, "expected_updated_at": expected},
        )

    def test_未登録でも取得でき生成エラーを返す(self):
        data = self._get("manage-api-skillsheet").json()
        self.assertEqual(data["body"], "")
        self.assertIsNone(data["updated_at"])
        self.assertIsNone(data["preview_html"])
        self.assertIn("登録されていません", data["error"])

    def test_初回保存して取得できる(self):
        with patch("portfolio.manage_views.timezone.localdate", return_value=TODAY):
            response = self._put(BODY, None)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["body"], BODY)
        self.assertIsNone(data["error"])
        self.assertIn("<table>", data["preview_html"])
        self.assertEqual(Skillsheet.objects.count(), 1)

    def test_更新日時が一致すれば更新できる(self):
        sheet = self._save_body()
        response = self._put(BODY + "追記\n", sheet.updated_at.isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Skillsheet.objects.get().body.endswith("追記\n"))
        self.assertEqual(Skillsheet.objects.count(), 1)

    def test_更新日時が古い場合は保存しない(self):
        sheet = self._save_body()
        stale = (sheet.updated_at - timedelta(minutes=1)).isoformat()
        response = self._put("## ■テクニカルスキル\n", stale)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Skillsheet.objects.get().body, BODY)

    def test_登録済みなのに更新日時なしでは保存しない(self):
        self._save_body()
        self.assertEqual(self._put(BODY, None).status_code, 400)

    def test_本文が空やスキル見出し不正は保存しない(self):
        for body in ("", "   ", "## ■開発経歴\n"):
            with self.subTest(body=body):
                self.assertEqual(self._put(body, None).status_code, 400)
        self.assertEqual(Skillsheet.objects.count(), 0)

    def test_本文のダウンロード(self):
        self._save_body()
        response = self._get("manage-skillsheet-markdown")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response.content.decode(), BODY)

    def test_本文未登録のダウンロードは404(self):
        self.assertEqual(self._get("manage-skillsheet-markdown").status_code, 404)

    def test_PDFのダウンロード(self):
        self._save_body()
        response = self._get("manage-skillsheet-pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("filename*=UTF-8''", response["Content-Disposition"])
        self.assertIn("%E8%81%B7%E5%8B%99", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_本文未登録のPDFはエラー(self):
        self.assertEqual(self._get("manage-skillsheet-pdf").status_code, 400)
