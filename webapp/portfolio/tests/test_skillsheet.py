from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone

from portfolio.models import (
    Certification,
    Company,
    Project,
    ProjectSkill,
    Skill,
    SkillsheetText,
)
from portfolio.tests.test_manage import LoggedInTestCase

TODAY = date(2026, 9, 25)

# 架空のダミー文章。実データは含めない。
TEXTS = {
    "full_name": "架空 太郎",
    "summary": "ダミーの職務概要です。",
    "strengths": "- ダミーの強み",
    "self_pr": "**ダミー** の自己PRです。",
}


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
        self.main = Company.objects.create(
            name="架空株式会社",
            department="開発部",
            employment_type="正社員",
            kind="main",
            start_year_month="2023-07",
            capital="200万円",
            founded="2008年5月",
        )
        self.side = Company.objects.create(
            name="副業先",
            kind="side",
            start_year_month="2025-01",
            end_year_month="2025-06",
        )
        self.old = Project.objects.create(
            name="旧案件",
            start_year_month="2023-07",
            end_year_month="2025-03",
            company=self.main,
            team_size="3名体制",
            overview="ダミーの概要",
            tasks="設計\n実装",
            phases="基本設計",
            environment="Java 21",
        )
        self.new = Project.objects.create(
            name="新案件",
            start_year_month="2025-04",
            company=self.main,
            tasks="単一の業務",
        )
        self.side_project = Project.objects.create(
            name="副業案件",
            start_year_month="2025-01",
            end_year_month="2025-06",
            company=self.side,
        )
        ProjectSkill.objects.create(project=self.old, skill=java)
        ProjectSkill.objects.create(project=self.new, skill=python)
        Certification.objects.create(
            name="ダミー資格", acquired_on=date(2020, 5, 1), org="ダミー団体"
        )

    def _save_texts(self, **overrides):
        for key, body in (TEXTS | overrides).items():
            if body is not None:
                SkillsheetText.objects.create(
                    text_key=key, body=body, updated_at=timezone.now()
                )

    def _get(self, name, **kwargs):
        with patch("portfolio.manage_views.timezone.localdate", return_value=TODAY):
            return self.call("get", name, **kwargs)


class RenderTests(SkillsheetTestCase):
    def _render(self):
        from portfolio import export

        return export.render_skillsheet(TODAY)

    def test_構成の順に出力する(self):
        self._save_texts()
        markdown = self._render().markdown
        headings = [line for line in markdown.splitlines() if line.startswith("## ")]
        self.assertEqual(
            headings,
            [
                "## ■職務概要",
                "## ■職務経歴 概略",
                "## ■開発経歴",
                "## ■副業",
                "## ■テクニカルスキル",
                "## ■活かせる経験・得意分野",
                "## ■保有資格",
                "## ■自己PR",
            ],
        )
        self.assertTrue(
            markdown.startswith(
                "# 職務経歴書\n最終更新日: 2026年9月25日\n氏名: 架空 太郎\n"
            )
        )
        self.assertTrue(markdown.endswith("\n\n以上\n"))

    def test_概略は本業の会社のみ(self):
        self._save_texts()
        markdown = self._render().markdown
        self.assertIn("| 2023年07月〜現在 | 架空株式会社 開発部 |", markdown)
        summary = markdown.split("## ■開発経歴")[0]
        self.assertNotIn("副業先", summary)

    def test_会社見出しと会社概要(self):
        self._save_texts()
        markdown = self._render().markdown
        self.assertIn("### 架空株式会社 開発部（正社員） 2023年07月〜現在", markdown)
        self.assertIn("【資本金】200万円\u3000【設立】2008年5月", markdown)
        self.assertIn("### 副業先 2025年01月〜2025年06月", markdown)

    def test_案件は開始年月の降順で詳細を出力する(self):
        self._save_texts()
        markdown = self._render().markdown
        self.assertLess(markdown.index("｜新案件**"), markdown.index("｜旧案件**"))
        self.assertIn("**2025年04月〜現在｜新案件**\n", markdown)
        self.assertIn("- 業務内容: 単一の業務", markdown)
        self.assertIn("**2023年07月〜2025年03月｜旧案件**（3名体制）", markdown)
        self.assertIn("- 案件概要: ダミーの概要", markdown)
        self.assertIn("- 業務内容:\n    - 設計\n    - 実装", markdown)
        self.assertIn("- 担当工程: 基本設計", markdown)
        self.assertIn("- 環境・言語: Java 21", markdown)

    def test_空の詳細は出力しない(self):
        self._save_texts()
        block = self._render().markdown.split("｜新案件**")[1].split("**")[0]
        self.assertNotIn("案件概要", block)
        self.assertNotIn("担当工程", block)
        self.assertNotIn("環境・言語", block)

    def test_スキル表と資格(self):
        self._save_texts()
        markdown = self._render().markdown
        self.assertIn("| 言語 | Java | 2023年 | 1年9ヶ月 |", markdown)
        self.assertNotIn("COBOL", markdown)
        self.assertIn("- ダミー資格（2020年05月）", markdown)

    def test_文章項目は見出しの下に出力する(self):
        self._save_texts()
        markdown = self._render().markdown
        self.assertIn("## ■職務概要\n\nダミーの職務概要です。", markdown)
        self.assertIn("## ■自己PR\n\n**ダミー** の自己PRです。", markdown)

    def test_空の項目は見出しごと出力しない(self):
        from portfolio import export

        markdown, _ = export.build_markdown(TODAY)
        for heading in ("■職務概要", "■活かせる経験・得意分野", "■自己PR"):
            self.assertNotIn(heading, markdown)
        self.assertNotIn("氏名:", markdown)
        Certification.objects.all().delete()
        ProjectSkill.objects.all().delete()
        markdown, _ = export.build_markdown(TODAY)
        self.assertNotIn("■保有資格", markdown)
        self.assertNotIn("■テクニカルスキル", markdown)

    def test_会社がなければ会社関連の見出しを出力しない(self):
        from portfolio import export

        Project.objects.update(company=None)
        Company.objects.all().delete()
        markdown, _ = export.build_markdown(TODAY)
        for heading in ("■職務経歴 概略", "■開発経歴", "■副業"):
            self.assertNotIn(heading, markdown)

    def test_表の区切り文字はエスケープする(self):
        from portfolio import export

        self._save_texts()
        self.main.name = "A|B"
        self.main.save()
        markdown, _ = export.build_markdown(TODAY)
        self.assertIn("| 2023年07月〜現在 | A\\|B 開発部 |", markdown)

    def test_警告は会社未設定の案件と未入力の文章項目(self):
        self._save_texts(summary=None, self_pr=None)
        self.new.company = None
        self.new.save()
        warnings = self._render().warnings
        self.assertEqual(warnings.unassigned_projects, ["新案件"])
        self.assertEqual(warnings.missing_texts, ["職務概要", "自己PR"])
        self.assertNotIn("新案件", self._render().markdown)

    def test_すべて揃っていれば警告なし(self):
        self._save_texts()
        warnings = self._render().warnings
        self.assertEqual(warnings.unassigned_projects, [])
        self.assertEqual(warnings.missing_texts, [])

    def test_HTMLにスタイルと表と入れ子の箇条書きが含まれる(self):
        self._save_texts()
        html = self._render().html
        self.assertIn("IPAexGothic", html)
        self.assertIn("<table>", html)
        self.assertRegex(html, r"業務内容:\s*<ul>\s*<li>設計</li>")


class SkillsheetApiTests(SkillsheetTestCase):
    def _put(self, key, body, expected):
        return self.call(
            "put",
            "manage-api-skillsheet-text",
            {"body": body, "expected_updated_at": expected},
            text_key=key,
        )

    def test_未入力でも取得でき項目が揃う(self):
        data = self._get("manage-api-skillsheet").json()
        self.assertEqual(
            [t["key"] for t in data["texts"]],
            ["full_name", "summary", "strengths", "self_pr"],
        )
        self.assertTrue(all(t["updated_at"] is None for t in data["texts"]))
        self.assertIn("<table>", data["preview_html"])
        self.assertEqual(data["warnings"]["unassigned_projects"], [])
        self.assertEqual(len(data["warnings"]["missing_texts"]), 4)

    def test_初回保存して取得できる(self):
        with patch("portfolio.manage_views.timezone.localdate", return_value=TODAY):
            response = self._put("summary", "新しい職務概要", None)
        self.assertEqual(response.status_code, 200)
        texts = {t["key"]: t for t in response.json()["texts"]}
        self.assertEqual(texts["summary"]["body"], "新しい職務概要")
        self.assertIsNotNone(texts["summary"]["updated_at"])
        self.assertIn("新しい職務概要", response.json()["preview_html"])

    def test_更新日時が一致すれば更新できる(self):
        self._save_texts()
        text = SkillsheetText.objects.get(pk="summary")
        response = self._put("summary", "更新後", text.updated_at.isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SkillsheetText.objects.get(pk="summary").body, "更新後")

    def test_更新日時が古い場合は保存しない(self):
        self._save_texts()
        text = SkillsheetText.objects.get(pk="summary")
        stale = (text.updated_at - timedelta(minutes=1)).isoformat()
        self.assertEqual(self._put("summary", "更新後", stale).status_code, 400)
        self.assertEqual(
            SkillsheetText.objects.get(pk="summary").body, TEXTS["summary"]
        )

    def test_登録済みなのに更新日時なしでは保存しない(self):
        self._save_texts()
        self.assertEqual(self._put("summary", "更新後", None).status_code, 400)

    def test_項目ごとに競合を判定する(self):
        self._save_texts()
        self.assertEqual(self._put("self_pr", "新規", None).status_code, 400)
        SkillsheetText.objects.filter(pk="self_pr").delete()
        self.assertEqual(self._put("self_pr", "新規", None).status_code, 200)

    def test_空の内容や不正な氏名は保存しない(self):
        for key, body in (
            ("summary", ""),
            ("summary", "   "),
            ("summary", None),
            ("full_name", "1行目\n2行目"),
            ("full_name", "あ" * 256),
        ):
            with self.subTest(key=key, body=body):
                self.assertEqual(self._put(key, body, None).status_code, 400)
        self.assertEqual(SkillsheetText.objects.count(), 0)

    def test_氏名は前後の空白を除いて保存する(self):
        self._put("full_name", "  架空 花子  ", None)
        self.assertEqual(SkillsheetText.objects.get().body, "架空 花子")

    def test_存在しない項目は404(self):
        self.assertEqual(self._put("unknown", "x", None).status_code, 404)

    def test_Markdownのダウンロード(self):
        self._save_texts()
        response = self._get("manage-skillsheet-markdown")
        self.assertEqual(response.status_code, 200)
        disposition = response["Content-Disposition"]
        self.assertIn("attachment", disposition)
        self.assertIn("filename*=UTF-8''", disposition)
        self.assertIn("20260925.md", disposition)
        body = response.content.decode()
        self.assertIn("## ■職務概要", body)
        self.assertIn("氏名: 架空 太郎", body)

    def test_未入力でもMarkdownをダウンロードできる(self):
        self.assertEqual(self._get("manage-skillsheet-markdown").status_code, 200)

    def test_PDFのダウンロード(self):
        self._save_texts()
        response = self._get("manage-skillsheet-pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("filename*=UTF-8''", response["Content-Disposition"])
        self.assertIn("%E8%81%B7%E5%8B%99", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))


class PdfSecurityTests(SkillsheetTestCase):
    def test_外部URLとローカルファイルは取得しない(self):
        from portfolio import export

        fetcher = export.build_url_fetcher()
        for url in (
            "file:///etc/passwd",
            "http://127.0.0.1:9/x",
            "https://example.com/",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetcher.fetch(url)

    def test_データURIは取得できる(self):
        from portfolio import export

        response = export.build_url_fetcher().fetch("data:text/plain;base64,YQ==")
        self.assertEqual(response.read(), b"a")

    def test_生HTMLの外部参照を含んでもPDFを生成できる(self):
        from portfolio import export

        html = export.to_html_document('<img src="file:///etc/passwd">\n')
        self.assertTrue(export.build_pdf(html).startswith(b"%PDF"))
