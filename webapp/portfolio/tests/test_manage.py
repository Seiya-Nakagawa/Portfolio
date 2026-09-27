import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from portfolio.models import Certification, Project, ProjectSkill, Skill, Work

TODAY = date(2026, 9, 25)


def _skill(skill_id, category, name, sort_order):
    return Skill.objects.create(
        skill_id=skill_id,
        category=category,
        name=name,
        sort_order=sort_order,
    )


class LoggedInTestCase(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("owner", password="pw-for-test")
        self.client.login(username="owner", password="pw-for-test")

    def call(self, method, name, data=None, **kwargs):
        url = reverse(name, kwargs=kwargs)
        body = json.dumps(data) if data is not None else None
        return getattr(self.client, method)(
            url, data=body, content_type="application/json"
        )


class AuthenticationTests(TestCase):
    def test_未ログインでは登録画面がログイン画面へリダイレクトされる(self):
        response = self.client.get(reverse("manage"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('manage')}")

    def test_未ログインではAPIが401を返す(self):
        for name in (
            "manage-api-bootstrap",
            "manage-api-skills",
            "manage-api-categories",
            "manage-api-certifications",
            "manage-api-works",
            "manage-api-export",
            "manage-export-download",
        ):
            self.assertEqual(self.client.get(reverse(name)).status_code, 401, name)

    def test_未ログインでは書き込みできない(self):
        response = self.client.post(
            reverse("manage-api-projects"),
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Project.objects.count(), 0)

    def test_ログインすると登録画面を表示できる(self):
        get_user_model().objects.create_user("owner", password="pw-for-test")
        self.assertTrue(self.client.login(username="owner", password="pw-for-test"))
        response = self.client.get(reverse("manage"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'data-api-bootstrap="/manage/api/bootstrap"', response.content.decode()
        )

    def test_CSRFトークンなしの書き込みは拒否される(self):
        from django.test import Client

        get_user_model().objects.create_user("owner", password="pw-for-test")
        client = Client(enforce_csrf_checks=True)
        client.login(username="owner", password="pw-for-test")
        response = client.post(
            reverse("manage-api-projects"), data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)


class ProjectApiTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.java = _skill("java", "言語", "Java", 10)
        self.python = _skill("python", "言語", "Python", 20)

    def _payload(self, **overrides):
        payload = {
            "name": "案件A",
            "start_year_month": "2025-04",
            "end_year_month": "",
            "skills": [{"skill_id": "java", "version": "21"}],
        }
        payload.update(overrides)
        return payload

    def test_新規保存でIDが採番され使用スキルが登録される(self):
        response = self.call("post", "manage-api-projects", self._payload())
        self.assertEqual(response.status_code, 200)
        project = Project.objects.get()
        self.assertRegex(project.project_id, r"^p-[0-9a-f]{12}$")
        self.assertEqual(
            list(project.project_skills.values_list("skill_id", "version")),
            [("java", "21")],
        )

    def test_更新は使用スキルを置き換える(self):
        project_id = self.call("post", "manage-api-projects", self._payload()).json()[
            "project_id"
        ]
        self.call(
            "post",
            "manage-api-projects",
            self._payload(
                project_id=project_id,
                name="案件A改",
                end_year_month="2025-12",
                skills=[{"skill_id": "python", "version": ""}],
            ),
        )
        project = Project.objects.get()
        self.assertEqual(project.name, "案件A改")
        self.assertEqual(project.end_year_month, "2025-12")
        self.assertEqual(
            list(project.project_skills.values_list("skill_id", flat=True)), ["python"]
        )

    def test_入力値の検証エラー(self):
        cases = {
            "案件名なし": self._payload(name=" "),
            "開始年月なし": self._payload(start_year_month=""),
            "開始年月の形式": self._payload(start_year_month="2025/04"),
            "終了年月の形式": self._payload(end_year_month="2025-13"),
            "終了が開始より前": self._payload(end_year_month="2025-03"),
            "存在しないスキル": self._payload(skills=[{"skill_id": "nothing"}]),
            "スキル重複": self._payload(
                skills=[{"skill_id": "java"}, {"skill_id": "java"}]
            ),
            "バージョンが長すぎる": self._payload(
                skills=[{"skill_id": "java", "version": "x" * 65}]
            ),
        }
        for label, payload in cases.items():
            with self.subTest(label):
                response = self.call("post", "manage-api-projects", payload)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.json()["errors"])
        self.assertEqual(Project.objects.count(), 0)

    def test_存在しない案件の更新は404(self):
        response = self.call(
            "post", "manage-api-projects", self._payload(project_id="p-nothing")
        )
        self.assertEqual(response.status_code, 404)

    def test_検証エラー時は既存の使用スキルを変更しない(self):
        project_id = self.call("post", "manage-api-projects", self._payload()).json()[
            "project_id"
        ]
        self.call(
            "post",
            "manage-api-projects",
            self._payload(project_id=project_id, skills=[{"skill_id": "nothing"}]),
        )
        self.assertEqual(ProjectSkill.objects.filter(project_id=project_id).count(), 1)

    def test_削除すると使用スキルも消える(self):
        project_id = self.call("post", "manage-api-projects", self._payload()).json()[
            "project_id"
        ]
        response = self.call("delete", "manage-api-project", project_id=project_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(ProjectSkill.objects.count(), 0)

    def test_初期表示は開始年月が最新の継続中案件(self):
        Project.objects.create(
            name="終了済み", start_year_month="2026-01", end_year_month="2026-02"
        )
        Project.objects.create(name="継続中・古", start_year_month="2024-01")
        Project.objects.create(name="継続中・新", start_year_month="2025-06")
        body = self.call("get", "manage-api-bootstrap").json()
        self.assertEqual(
            [p["name"] for p in body["ongoing_projects"]], ["継続中・新", "継続中・古"]
        )
        self.assertEqual(body["initial_project"]["name"], "継続中・新")

    def test_終了済み案件は終了年月の降順で返す(self):
        Project.objects.create(
            name="古", start_year_month="2023-01", end_year_month="2023-06"
        )
        Project.objects.create(
            name="新", start_year_month="2024-01", end_year_month="2024-06"
        )
        Project.objects.create(name="継続中", start_year_month="2025-01")
        body = self.call("get", "manage-api-bootstrap").json()
        self.assertEqual([p["name"] for p in body["finished_projects"]], ["新", "古"])
        self.assertEqual(body["finished_projects"][0]["end_year_month"], "2024-06")

    def test_継続中の案件がなければ初期表示は空(self):
        body = self.call("get", "manage-api-bootstrap").json()
        self.assertIsNone(body["initial_project"])
        self.assertEqual(body["ongoing_projects"], [])


class CategoryApiTests(LoggedInTestCase):
    def test_一覧は種類マスタの順に項目数を含む(self):
        _skill("ec2", "AWS", "EC2", 10)
        _skill("py", "言語", "Python", 20)
        _skill("go", "言語", "Go", 30)
        rows = self.call("get", "manage-api-categories").json()
        self.assertEqual(
            rows,
            [
                {"name": "AWS", "skill_count": 1},
                {"name": "言語", "skill_count": 2},
            ],
        )

    def test_追加は末尾に置き重複と空は拒否する(self):
        _skill("ec2", "AWS", "EC2", 10)
        response = self.call("post", "manage-api-categories", {"name": "OS・MW"})
        self.assertEqual([r["name"] for r in response.json()], ["AWS", "OS・MW"])
        for name in ("AWS", "OS・MW", "", " ", "a/b", "x" * 65):
            with self.subTest(name):
                response = self.call("post", "manage-api-categories", {"name": name})
                self.assertEqual(response.status_code, 400)

    def test_スキル項目のない種類も並び替えできる(self):
        _skill("ec2", "AWS", "EC2", 10)
        self.call("post", "manage-api-categories", {"name": "OS・MW"})
        response = self.call(
            "post", "manage-api-category-order", {"categories": ["OS・MW", "AWS"]}
        )
        self.assertEqual([r["name"] for r in response.json()], ["OS・MW", "AWS"])
        rows = self.call("get", "manage-api-categories").json()
        self.assertEqual([r["name"] for r in rows], ["OS・MW", "AWS"])

    def test_種類単位で並び替えるとスキル項目の順も変わる(self):
        _skill("ec2", "AWS", "EC2", 10)
        _skill("py", "言語", "Python", 20)
        _skill("go", "言語", "Go", 30)
        self.call("post", "manage-api-category-order", {"categories": ["言語", "AWS"]})
        rows = self.call("get", "manage-api-skills").json()
        self.assertEqual([r["skill_id"] for r in rows], ["go", "py", "ec2"])

    def test_種類の並び順の形式が不正なら400(self):
        response = self.call("post", "manage-api-category-order", {"categories": "AWS"})
        self.assertEqual(response.status_code, 400)

    def test_名称変更はスキル項目の種類にも反映される(self):
        _skill("ec2", "AWS", "EC2", 10)
        response = self.call(
            "put", "manage-api-category", {"name": "Amazon"}, category_name="AWS"
        )
        self.assertEqual(response.json(), [{"name": "Amazon", "skill_count": 1}])
        self.assertEqual(Skill.objects.get().category, "Amazon")

    def test_名称変更で既存名や未登録の種類は拒否する(self):
        _skill("ec2", "AWS", "EC2", 10)
        _skill("py", "言語", "Python", 20)
        response = self.call(
            "put", "manage-api-category", {"name": "言語"}, category_name="AWS"
        )
        self.assertEqual(response.status_code, 400)
        response = self.call(
            "put", "manage-api-category", {"name": "X"}, category_name="無い"
        )
        self.assertEqual(response.status_code, 404)

    def test_スキル項目のない種類は削除できる(self):
        _skill("ec2", "AWS", "EC2", 10)
        self.call("post", "manage-api-categories", {"name": "空"})
        response = self.call("delete", "manage-api-category", category_name="空")
        self.assertEqual([r["name"] for r in response.json()], ["AWS"])

    def test_スキル項目のある種類は削除できない(self):
        _skill("ec2", "AWS", "EC2", 10)
        response = self.call("delete", "manage-api-category", category_name="AWS")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Skill.objects.count(), 1)

    def test_スキル項目の追加で新しい種類が種類マスタに登録される(self):
        self.call(
            "post",
            "manage-api-skills",
            {"skill_id": "ec2", "category": "AWS", "name": "EC2"},
        )
        rows = self.call("get", "manage-api-categories").json()
        self.assertEqual(rows, [{"name": "AWS", "skill_count": 1}])


class SkillApiTests(LoggedInTestCase):
    def _payload(self, **overrides):
        payload = {
            "skill_id": "ec2",
            "category": "AWS",
            "name": "EC2",
        }
        payload.update(overrides)
        return payload

    def test_追加と変更(self):
        self.assertEqual(
            self.call("post", "manage-api-skills", self._payload()).status_code, 200
        )
        response = self.call(
            "put",
            "manage-api-skill",
            self._payload(name="EC2 (変更)", skill_id="ignored"),
            skill_id="ec2",
        )
        self.assertEqual(response.status_code, 200)
        skill = Skill.objects.get()
        self.assertEqual((skill.skill_id, skill.name), ("ec2", "EC2 (変更)"))

    def test_サブカテゴリを保存して一覧に含む(self):
        self.call("post", "manage-api-skills", self._payload(subcategory="Compute"))
        self.assertEqual(Skill.objects.get().subcategory, "Compute")
        rows = self.call("get", "manage-api-skills").json()
        self.assertEqual(rows[0]["subcategory"], "Compute")

    def test_サブカテゴリは省略できる(self):
        self.call("post", "manage-api-skills", self._payload())
        self.assertEqual(Skill.objects.get().subcategory, "")

    def test_入力値の検証エラー(self):
        _skill("ec2", "AWS", "EC2", 10)
        cases = {
            "skill_id の形式": self._payload(skill_id="EC 2"),
            "skill_id の重複": self._payload(),
            "種類なし": self._payload(skill_id="vpc", category=""),
        }
        for label, payload in cases.items():
            with self.subTest(label):
                response = self.call("post", "manage-api-skills", payload)
                self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Skill.objects.count(), 1)

    def test_追加した項目は種類内でサブカテゴリ_表示名の昇順に採番される(self):
        for skill_id, sub, name in [
            ("s3", "Storage", "S3"),
            ("ec2", "Compute", "EC2"),
            ("lambda", "Compute", "Lambda"),
            ("other", "", "Other"),
        ]:
            self.call(
                "post",
                "manage-api-skills",
                self._payload(skill_id=skill_id, subcategory=sub, name=name),
            )
        rows = self.call("get", "manage-api-skills").json()
        self.assertEqual(
            [r["skill_id"] for r in rows], ["ec2", "lambda", "s3", "other"]
        )

    def test_使用実績のない項目は削除できる(self):
        _skill("ec2", "AWS", "EC2", 10)
        self.assertEqual(
            self.call("delete", "manage-api-skill", skill_id="ec2").status_code, 200
        )
        self.assertEqual(Skill.objects.count(), 0)

    def test_使用実績のある項目は削除できない(self):
        skill = _skill("ec2", "AWS", "EC2", 10)
        project = Project.objects.create(name="A", start_year_month="2025-01")
        ProjectSkill.objects.create(project=project, skill=skill)
        response = self.call("delete", "manage-api-skill", skill_id="ec2")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Skill.objects.count(), 1)

    def test_一覧に経験年数を含む(self):
        skill = _skill("ec2", "AWS", "EC2", 10)
        _skill("vpc", "AWS", "VPC", 20)
        project = Project.objects.create(
            name="A", start_year_month="2025-01", end_year_month="2025-12"
        )
        ProjectSkill.objects.create(project=project, skill=skill)
        with patch("portfolio.manage_views.timezone.localdate", return_value=TODAY):
            rows = self.call("get", "manage-api-skills").json()
        self.assertEqual(
            [(r["skill_id"], r["years"]) for r in rows], [("ec2", "1年"), ("vpc", "")]
        )


class CertificationAndWorkApiTests(LoggedInTestCase):
    def test_資格の追加_変更_削除(self):
        payload = {
            "name": "資格A",
            "acquired_on": "2024-07",
            "org": "団体",
        }
        rows = self.call("post", "manage-api-certifications", payload).json()
        certification_id = rows[0]["certification_id"]
        rows = self.call(
            "put",
            "manage-api-certification",
            {**payload, "name": "資格A改"},
            certification_id=certification_id,
        ).json()
        self.assertEqual(rows[0]["name"], "資格A改")
        rows = self.call(
            "delete", "manage-api-certification", certification_id=certification_id
        ).json()
        self.assertEqual(rows, [])

    def test_資格は取得日の古い順に並ぶ(self):
        for name, acquired_on in [
            ("古い", "2020-09"),
            ("新しい", "2024-07"),
            ("中間", "2022-12"),
        ]:
            self.call(
                "post",
                "manage-api-certifications",
                {"name": name, "acquired_on": acquired_on, "org": "団体"},
            )
        rows = self.call("get", "manage-api-certifications").json()
        self.assertEqual([r["name"] for r in rows], ["古い", "中間", "新しい"])

    def test_実績は登録の新しい順に並ぶ(self):
        for title, achieved_on in [
            ("古", "2023-01"),
            ("新", "2024-06"),
            ("中", "2023-12"),
        ]:
            self.call(
                "post",
                "manage-api-works",
                {"title": title, "desc_ja": "d", "achieved_on": achieved_on},
            )
        rows = self.call("get", "manage-api-works").json()
        self.assertEqual([r["title"] for r in rows], ["新", "中", "古"])
        self.assertEqual(rows[0]["achieved_on"], "2024-06")

    def test_資格の必須項目が空ならエラー(self):
        response = self.call(
            "post",
            "manage-api-certifications",
            {"name": "", "acquired_on": "", "org": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Certification.objects.count(), 0)

    def test_実績の追加_変更_削除(self):
        payload = {
            "title": "実績A",
            "desc_ja": "説明",
            "desc_en": "",
            "achieved_on": "2024-05",
            "tags": ["Python", " ", "AWS"],
            "thumbnail": "",
            "github_url": "https://github.com/x/y",
            "live_url": "",
        }
        rows = self.call("post", "manage-api-works", payload).json()
        self.assertEqual(rows[0]["tags"], ["Python", "AWS"])
        work_id = rows[0]["work_id"]
        rows = self.call(
            "put", "manage-api-work", {**payload, "title": "実績A改"}, work_id=work_id
        ).json()
        self.assertEqual(rows[0]["title"], "実績A改")
        self.assertEqual(
            self.call("delete", "manage-api-work", work_id=work_id).json(), []
        )

    def test_実績の入力値検証(self):
        base = {"title": "T", "desc_ja": "d", "achieved_on": "2024-05"}
        cases = {
            "URL の形式": {**base, "github_url": "not-a-url"},
            "タグの形式": {**base, "tags": "Python"},
            "タイトルなし": {**base, "title": ""},
            "実績年月なし": {**base, "achieved_on": ""},
            "実績年月の形式": {**base, "achieved_on": "2024/05"},
        }
        for label, payload in cases.items():
            with self.subTest(label):
                self.assertEqual(
                    self.call("post", "manage-api-works", payload).status_code, 400
                )
        self.assertEqual(Work.objects.count(), 0)

    def test_存在しない対象の削除は404(self):
        self.assertEqual(
            self.call("delete", "manage-api-work", work_id=999).status_code, 404
        )
        self.assertEqual(
            self.call(
                "delete", "manage-api-certification", certification_id=999
            ).status_code,
            404,
        )


class ImageUploadTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)

    def _upload(self, name="a.png", content=b"\x89PNG-data"):
        return self.client.post(
            reverse("manage-api-upload-image"),
            {"image": SimpleUploadedFile(name, content)},
        )

    def test_画像を保存し相対パスを返す(self):
        response = self._upload()
        self.assertEqual(response.status_code, 200)
        path = response.json()["path"]
        self.assertRegex(path, r"^works/[0-9a-f]{32}\.png$")
        self.assertTrue((Path(self._media.name) / path).exists())

    def test_保存した画像を配信する(self):
        path = self._upload().json()["path"]
        response = self.client.get(f"/media/{path}")
        self.assertEqual(response.status_code, 200)

    def test_画像以外の拡張子は拒否する(self):
        response = self._upload("a.html", b"<script></script>")
        self.assertEqual(response.status_code, 400)

    def test_ファイル未指定は拒否する(self):
        response = self.client.post(reverse("manage-api-upload-image"))
        self.assertEqual(response.status_code, 400)

    def test_サイズ超過は拒否する(self):
        response = self._upload(content=b"0" * (5 * 1024 * 1024 + 1))
        self.assertEqual(response.status_code, 400)

    def test_未ログインでは401を返す(self):
        self.client.logout()
        self.assertEqual(self._upload().status_code, 401)


class ExportTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        java = _skill("java", "言語", "Java", 10)
        python = _skill("python", "言語", "Python", 20)
        _skill("cobol", "言語", "COBOL", 30)
        old = Project.objects.create(
            name="旧案件", start_year_month="2023-07", end_year_month="2025-03"
        )
        new = Project.objects.create(name="新案件 | 移行", start_year_month="2025-04")
        ProjectSkill.objects.create(project=old, skill=java)
        ProjectSkill.objects.create(project=new, skill=python)

    def _get(self, name):
        with patch("portfolio.manage_views.timezone.localdate", return_value=TODAY):
            return self.call("get", name)

    def test_マークダウンの形式(self):
        markdown = self._get("manage-api-export").json()["markdown"]
        table, periods = markdown.split("\n\n")
        self.assertEqual(
            table.splitlines()[:3],
            [
                "| 種類 | 項目 | 開始年 | 使用期間 |",
                "| --- | --- | --- | --- |",
                "| 言語 | Java | 2023年 | 1年9ヶ月 |",
            ],
        )
        self.assertEqual(
            periods.splitlines(),
            [
                "**2023年07月〜2025年03月｜旧案件**",
                "**2025年04月〜現在｜新案件 | 移行**",
            ],
        )

    def test_使用実績のない項目は表に含まない(self):
        self.assertNotIn("COBOL", self._get("manage-api-export").json()["markdown"])

    def test_警告に出力対象外の件数を含む(self):
        warnings = self._get("manage-api-export").json()["warnings"]
        self.assertEqual(warnings["unused_skill_count"], 1)

    def test_ダウンロード(self):
        response = self._get("manage-export-download")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(response.content.decode().startswith("| 種類 |"))
