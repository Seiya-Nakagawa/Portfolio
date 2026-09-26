import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from portfolio.models import Certification, Project, ProjectSkill, Skill, Work

TODAY = date(2026, 9, 25)


def _create_skill(skill_id, category, name, level, sort_order, remarks=""):
    return Skill.objects.create(
        skill_id=skill_id,
        category=category,
        name=name,
        level_id=level,
        remarks=remarks,
        sort_order=sort_order,
    )


class SkillsApiTests(TestCase):
    def setUp(self):
        # 表示順の検証のため、カテゴリ名の辞書順と sort_order の順が食い違うよう登録する。
        self.lang_java = _create_skill("java", "言語", "Java", 3, 20)
        self.lang_py = _create_skill("python", "言語", "Python", 4, 10)
        self.os_linux = _create_skill("linux", "OS", "Linux", 3, 30)
        self.unused = _create_skill("cobol", "言語", "COBOL", 1, 40)
        project = Project.objects.create(
            name="案件A", start_year_month="2025-01", end_year_month="2025-12"
        )
        for skill in (self.lang_java, self.lang_py, self.os_linux):
            ProjectSkill.objects.create(project=project, skill=skill)

    def _get(self):
        with patch("portfolio.views.timezone.localdate", return_value=TODAY):
            return self.client.get(reverse("api-skills"))

    def test_レスポンス形式(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["generated_at"], "2026-09-25")
        self.assertEqual(
            body["skills"][0],
            {
                "category": "言語",
                "name": "Python",
                "months": 12,
                "years": "1年",
                "stars": 3,
            },
        )

    def test_案件情報を含まない(self):
        self.assertNotIn("案件A", self._get().content.decode())

    def test_カテゴリはsort_order最小値の順_カテゴリ内はsort_order順(self):
        names = [s["name"] for s in self._get().json()["skills"]]
        self.assertEqual(names, ["Python", "Java", "Linux"])

    def test_使用実績のない項目は出力しない(self):
        names = [s["name"] for s in self._get().json()["skills"]]
        self.assertNotIn("COBOL", names)

    def test_認証不要でGETのみ許可する(self):
        self.assertEqual(self._get().status_code, 200)
        self.assertEqual(self.client.post(reverse("api-skills")).status_code, 405)


class CertificationsApiTests(TestCase):
    def test_sort_order順でキーはname_date_org(self):
        Certification.objects.create(
            name="B", acquired_on="Jul 2024", org="X", sort_order=2
        )
        Certification.objects.create(
            name="A", acquired_on="Sep 2020", org="Y", sort_order=1
        )
        response = self.client.get(reverse("api-certifications"))
        self.assertEqual(
            response.json(),
            [
                {"name": "A", "date": "Sep 2020", "org": "Y"},
                {"name": "B", "date": "Jul 2024", "org": "X"},
            ],
        )


class WorksApiTests(TestCase):
    def test_sort_order順で未設定の任意項目は省略する(self):
        Work.objects.create(title="後", desc_ja="d2", sort_order=2)
        Work.objects.create(
            title="先",
            desc_ja="d1",
            desc_en="e1",
            tags=["Python"],
            thumbnail="img/a.png",
            github_url="https://github.com/x/y",
            sort_order=1,
        )
        body = self.client.get(reverse("api-works")).json()
        self.assertEqual([w["title"] for w in body], ["先", "後"])
        self.assertEqual(
            body[0],
            {
                "title": "先",
                "desc_ja": "d1",
                "desc_en": "e1",
                "tags": ["Python"],
                "thumbnail": "img/a.png",
                "github_url": "https://github.com/x/y",
            },
        )
        self.assertNotIn("thumbnail", body[1])
        self.assertNotIn("live_url", body[1])


class IndexPageTests(TestCase):
    def test_ページ本体が認証なしで表示され_API_URLを渡す(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-api-skills="/api/skills"', html)
        self.assertIn('data-api-works="/api/works"', html)
        self.assertIn("/static/js/main.js", html)


class ImportPortfolioDataTests(TestCase):
    def _seed_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name)
        (path / "certifications.json").write_text(
            json.dumps([{"name": "A", "date": "Jul 2024", "org": "X"}]),
            encoding="utf-8",
        )
        (path / "works.json").write_text(
            json.dumps([{"title": "W", "desc_ja": "d", "tags": ["a"]}]),
            encoding="utf-8",
        )
        return path

    def test_投入し_再実行では二重登録しない(self):
        seed = self._seed_dir()
        call_command("import_portfolio_data", seed_dir=seed, stdout=StringIO())
        call_command("import_portfolio_data", seed_dir=seed, stdout=StringIO())
        self.assertEqual(Certification.objects.get().acquired_on, "Jul 2024")
        self.assertEqual(Work.objects.get().tags, ["a"])

    def test_同梱の投入元を読み込める(self):
        call_command("import_portfolio_data", stdout=StringIO())
        self.assertGreater(Certification.objects.count(), 0)
        self.assertGreater(Work.objects.count(), 0)

    def test_投入元がなければエラー(self):
        with self.assertRaises(CommandError):
            call_command("import_portfolio_data", seed_dir=Path("/nonexistent"))
