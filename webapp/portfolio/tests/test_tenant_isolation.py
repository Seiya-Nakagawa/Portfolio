"""テナント分離のテスト（基本設計書 4.13）。

2 人のユーザーを用意し、一方が他方のデータを参照・変更・削除できないこと、
集計・職務経歴書の生成・公開データが所有者のデータのみを対象とすることを検証する。
管理画面の API を追加した際は、このテストにも追加する。
"""

import json
from datetime import date

from django.test import TestCase
from django.urls import reverse

from portfolio import export, services
from portfolio.models import (
    Certification,
    Company,
    Project,
    ProjectSkill,
    SiteInfo,
    Skill,
    SkillsheetText,
    Work,
)
from portfolio.tests.helpers import create_operator, create_user

TODAY = date(2026, 9, 25)
PASSWORD = "pw-for-test"


class TwoUsersTestCase(TestCase):
    """ユーザー A（ログイン中）とユーザー B のそれぞれがデータを持つ状態を用意する。"""

    def setUp(self):
        self.user_a = create_user("user-a", password=PASSWORD, is_staff=True)
        self.user_b = create_user("user-b", password=PASSWORD, is_staff=True)
        self.client.login(username="user-a", password=PASSWORD)

        self.company_a = Company.objects.create(
            owner=self.user_a, name="A社", kind="main", start_year_month="2020-01"
        )
        self.company_b = Company.objects.create(
            owner=self.user_b, name="B社", kind="main", start_year_month="2021-01"
        )
        self.project_a = Project.objects.create(
            owner=self.user_a, name="案件A", start_year_month="2024-01"
        )
        self.project_b = Project.objects.create(
            owner=self.user_b,
            name="案件B",
            start_year_month="2024-01",
            end_year_month="2024-12",
            company=self.company_b,
        )
        self.master = Skill.objects.create(
            skill_id="python", category="言語", name="Python", sort_order=10
        )
        self.skill_a = Skill.objects.create(
            skill_id="own-a",
            category="言語",
            name="独自A",
            sort_order=20,
            owner=self.user_a,
        )
        self.skill_b = Skill.objects.create(
            skill_id="own-b",
            category="言語",
            name="独自B",
            sort_order=30,
            owner=self.user_b,
        )
        ProjectSkill.objects.create(project=self.project_a, skill=self.master)
        ProjectSkill.objects.create(project=self.project_b, skill=self.master)
        ProjectSkill.objects.create(project=self.project_b, skill=self.skill_b)
        self.cert_b = Certification.objects.create(
            owner=self.user_b, name="資格B", acquired_on=date(2024, 1, 1), org="X"
        )
        self.work_b = Work.objects.create(owner=self.user_b, title="実績B", desc_ja="d")
        SkillsheetText.objects.create(
            owner=self.user_b,
            text_key="summary",
            body="B の職務概要",
            updated_at=TODAY,
        )

    def call(self, method, name, data=None, **kwargs):
        body = json.dumps(data) if data is not None else None
        return getattr(self.client, method)(
            reverse(name, kwargs=kwargs), data=body, content_type="application/json"
        )


class OtherUsersRowsAreNotFoundTests(TwoUsersTestCase):
    """他のユーザーの行は、存在しないものとして 404 になる。"""

    def test_案件の参照_更新_削除(self):
        kwargs = {"project_id": self.project_b.project_id}
        self.assertEqual(
            self.call("get", "manage-api-project", **kwargs).status_code, 404
        )
        self.assertEqual(
            self.call("delete", "manage-api-project", **kwargs).status_code, 404
        )
        response = self.call(
            "post",
            "manage-api-projects",
            {
                "project_id": self.project_b.project_id,
                "name": "乗っ取り",
                "start_year_month": "2024-01",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.project_b.refresh_from_db()
        self.assertEqual(self.project_b.name, "案件B")

    def test_会社の更新_削除(self):
        payload = {"name": "乗っ取り", "kind": "main", "start_year_month": "2021-01"}
        kwargs = {"company_id": self.company_b.company_id}
        self.assertEqual(
            self.call("put", "manage-api-company", payload, **kwargs).status_code, 404
        )
        self.assertEqual(
            self.call("delete", "manage-api-company", **kwargs).status_code, 404
        )
        self.company_b.refresh_from_db()
        self.assertEqual(self.company_b.name, "B社")

    def test_資格の更新_削除(self):
        payload = {"name": "乗っ取り", "org": "X", "acquired_on": "2024-01"}
        kwargs = {"certification_id": self.cert_b.certification_id}
        self.assertEqual(
            self.call("put", "manage-api-certification", payload, **kwargs).status_code,
            404,
        )
        self.assertEqual(
            self.call("delete", "manage-api-certification", **kwargs).status_code, 404
        )
        self.assertTrue(Certification.objects.filter(pk=self.cert_b.pk).exists())

    def test_実績の更新_削除(self):
        payload = {"title": "乗っ取り", "desc_ja": "d", "achieved_on": "2024-01"}
        kwargs = {"work_id": self.work_b.work_id}
        self.assertEqual(
            self.call("put", "manage-api-work", payload, **kwargs).status_code, 404
        )
        self.assertEqual(
            self.call("delete", "manage-api-work", **kwargs).status_code, 404
        )
        self.assertTrue(Work.objects.filter(pk=self.work_b.pk).exists())

    def test_独自スキル項目の更新_削除(self):
        payload = {"category": "言語", "name": "乗っ取り"}
        kwargs = {"skill_id": self.skill_b.skill_id}
        self.assertEqual(
            self.call("put", "manage-api-skill", payload, **kwargs).status_code, 404
        )
        self.assertEqual(
            self.call("delete", "manage-api-skill", **kwargs).status_code, 404
        )
        self.skill_b.refresh_from_db()
        self.assertEqual(self.skill_b.name, "独自B")


class ListsContainOnlyOwnRowsTests(TwoUsersTestCase):
    def test_一覧には自分の行だけが含まれる(self):
        names = {
            "manage-api-companies": ("name", {"A社"}),
            "manage-api-certifications": ("name", set()),
            "manage-api-works": ("title", set()),
        }
        for name, (key, expected) in names.items():
            with self.subTest(name):
                rows = self.call("get", name).json()
                self.assertEqual({row[key] for row in rows}, expected)

    def test_初期表示データには他のユーザーの行が含まれない(self):
        body = self.call("get", "manage-api-bootstrap").json()
        skill_ids = {s["skill_id"] for s in body["skills"]}
        self.assertEqual(skill_ids, {"python", "own-a"})
        self.assertEqual([c["name"] for c in body["companies"]], ["A社"])
        self.assertEqual(body["finished_projects"], [])
        self.assertEqual(
            [p["project_id"] for p in body["ongoing_projects"]],
            [self.project_a.project_id],
        )

    def test_サイト情報は自分の行のみ(self):
        SiteInfo.objects.create(
            owner=self.user_b,
            name="B",
            typing_titles=["x"],
            catchphrase="c",
            intro="i",
            birth_date=date(1990, 1, 1),
            job="j",
            education="e",
            location="l",
            hobby="h",
            github_url="https://github.com/b",
            contact_message="m",
            contact_form_url="https://example.com",
            copyright_start_year=2024,
        )
        self.assertEqual(self.call("get", "manage-api-site").json()["name"], "")


class OwnerIsAlwaysTheLoggedInUserTests(TwoUsersTestCase):
    def test_リクエストの所有者の値は無視される(self):
        response = self.call(
            "post",
            "manage-api-projects",
            {
                "name": "新規",
                "start_year_month": "2025-01",
                "owner": self.user_b.pk,
                "owner_id": self.user_b.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.get(name="新規").owner, self.user_a)

    def test_登録した行の所有者はログインしたユーザー(self):
        self.call(
            "post",
            "manage-api-works",
            {
                "title": "T",
                "desc_ja": "d",
                "achieved_on": "2025-01",
                "owner": self.user_b.pk,
            },
        )
        self.assertEqual(Work.objects.get(title="T").owner, self.user_a)

    def test_サイト情報と文章項目はユーザーごとに別の行になる(self):
        self.call(
            "put",
            "manage-api-skillsheet-text",
            {"body": "A の職務概要", "expected_updated_at": None},
            text_key="summary",
        )
        self.assertEqual(
            SkillsheetText.objects.get(owner=self.user_a, text_key="summary").body,
            "A の職務概要",
        )
        self.assertEqual(
            SkillsheetText.objects.get(owner=self.user_b, text_key="summary").body,
            "B の職務概要",
        )


class ReferencesAreLimitedToOwnRowsTests(TwoUsersTestCase):
    def test_他のユーザーの会社は案件に設定できない(self):
        response = self.call(
            "post",
            "manage-api-projects",
            {
                "name": "新規",
                "start_year_month": "2025-01",
                "company_id": self.company_b.company_id,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Project.objects.filter(name="新規").exists())

    def test_他のユーザーの独自スキル項目は使用実績にできない(self):
        response = self.call(
            "post",
            "manage-api-projects",
            {
                "name": "新規",
                "start_year_month": "2025-01",
                "skills": [{"skill_id": self.skill_b.skill_id, "version": ""}],
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_共通マスタと自分の独自スキル項目は使用実績にできる(self):
        response = self.call(
            "post",
            "manage-api-projects",
            {
                "name": "新規",
                "start_year_month": "2025-01",
                "skills": [
                    {"skill_id": "python", "version": ""},
                    {"skill_id": "own-a", "version": ""},
                ],
            },
        )
        self.assertEqual(response.status_code, 200)


class AggregationAndGenerationTests(TwoUsersTestCase):
    def test_経験年数の集計は対象ユーザーの案件のみ(self):
        rows_a = services.build_skill_rows(self.user_a, TODAY)
        rows_b = services.build_skill_rows(self.user_b, TODAY)
        self.assertEqual([r.skill.skill_id for r in rows_a], ["python"])
        self.assertEqual({r.skill.skill_id for r in rows_b}, {"python", "own-b"})
        # A の案件は継続中（2024-01 から 2026-09 まで）、B の案件は 2024 年の 12 か月。
        self.assertGreater(rows_a[0].months, rows_b[0].months)

    def test_職務経歴書には対象ユーザーのデータのみ出力される(self):
        markdown_a, _ = export.build_markdown(self.user_a, TODAY)
        markdown_b, _ = export.build_markdown(self.user_b, TODAY)
        for forbidden in ("B社", "案件B", "資格B", "B の職務概要", "独自B"):
            self.assertNotIn(forbidden, markdown_a)
        for forbidden in ("A社", "独自A"):
            self.assertNotIn(forbidden, markdown_b)
        self.assertIn("B の職務概要", markdown_b)

    def test_職務経歴書のAPIは自分のデータのみ(self):
        for name in ("manage-skillsheet-markdown", "manage-api-skillsheet"):
            with self.subTest(name):
                content = self.client.get(reverse(name)).content.decode()
                self.assertNotIn("B社", content)
                self.assertNotIn("B の職務概要", content)

    def test_公開データは対象ユーザーのデータのみ(self):
        self.assertEqual(services.build_certifications_payload(self.user_a), [])
        self.assertEqual(
            [c["name"] for c in services.build_certifications_payload(self.user_b)],
            ["資格B"],
        )
        self.assertEqual(services.build_works_payload(self.user_a), [])
        self.assertIsNone(services.build_site_payload(self.user_a, TODAY))


class UnauthenticatedAndPublicTests(TwoUsersTestCase):
    def test_公開APIは運営者のデータのみを返す(self):
        operator = create_operator()
        Certification.objects.create(
            owner=operator, name="運営者の資格", acquired_on=date(2024, 1, 1), org="X"
        )
        self.client.logout()
        body = self.client.get(reverse("api-certifications", args=["operator"])).json()
        self.assertEqual([c["name"] for c in body], ["運営者の資格"])


class OwnerCascadeTests(TwoUsersTestCase):
    def test_ユーザーを削除すると所有する行が連鎖して削除される(self):
        self.user_b.delete()
        self.assertFalse(Project.objects.filter(name="案件B").exists())
        self.assertFalse(Company.objects.filter(name="B社").exists())
        self.assertFalse(Certification.objects.filter(name="資格B").exists())
        self.assertFalse(Work.objects.filter(title="実績B").exists())
        self.assertFalse(
            SkillsheetText.objects.filter(owner_id=self.user_b.pk).exists()
        )
        self.assertFalse(Skill.objects.filter(skill_id="own-b").exists())
        self.assertFalse(ProjectSkill.objects.filter(project__name="案件B").exists())
        # 共通マスタと他のユーザーの行は残る。
        self.assertTrue(Skill.objects.filter(skill_id="python").exists())
        self.assertTrue(Project.objects.filter(name="案件A").exists())
