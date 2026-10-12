"""共通マスタと独自スキル項目の分離、運営者の権限のテスト（基本設計書 4.3・5.3.2）。"""

import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from portfolio import services
from portfolio.models import Skill, SkillCategory
from portfolio.tests.helpers import create_user

PASSWORD = "pw-for-test"


def _master(skill_id, category, name, sort_order, subcategory=""):
    return Skill.objects.create(
        skill_id=skill_id,
        category=category,
        subcategory=subcategory,
        name=name,
        sort_order=sort_order,
        is_master=True,
    )


class SplitTestCase(TestCase):
    """運営者 1 人と一般ユーザー 2 人を用意し、一般ユーザー A としてログインする。"""

    def setUp(self):
        self.operator = create_user("operator", password=PASSWORD, is_staff=True)
        self.user_a = create_user("user-a", password=PASSWORD)
        self.user_b = create_user("user-b", password=PASSWORD)
        self.master = _master("aws-ec2", "AWS", "EC2", 10, "Compute")
        _master("py", "言語", "Python", 20)
        self.client.login(username="user-a", password=PASSWORD)

    def call(self, method, name, data=None, **kwargs):
        body = json.dumps(data) if data is not None else None
        return getattr(self.client, method)(
            reverse(name, kwargs=kwargs), data=body, content_type="application/json"
        )

    def login_as(self, username):
        self.client.logout()
        self.client.login(username=username, password=PASSWORD)


class CustomSkillCreationTests(SplitTestCase):
    def test_独自スキル項目はサーバー側で採番し_所有者はログインユーザー(self):
        response = self.call(
            "post",
            "manage-api-skills",
            {
                "skill_id": "ignored",
                "owner": self.user_b.pk,
                "is_master": True,
                "sort_order": 999,
                "category": "AWS",
                "subcategory": "Compute",
                "name": "独自サービス",
            },
        )
        self.assertEqual(response.status_code, 200)
        skill = Skill.objects.get(name="独自サービス")
        self.assertRegex(skill.skill_id, r"^u-[0-9a-f]{16}$")
        self.assertEqual(skill.owner, self.user_a)
        self.assertFalse(skill.is_master)
        self.assertEqual(skill.sort_order, 0)

    def test_種類は既存の種類から選ぶ(self):
        response = self.call(
            "post", "manage-api-skills", {"category": "新しい種類", "name": "X"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Skill.objects.filter(name="X").exists())
        self.assertFalse(SkillCategory.objects.filter(name="新しい種類").exists())

    def test_共通マスタと同じ種類_名前の項目は登録できない(self):
        for name in ("EC2", "ec2", " Ec2 "):
            with self.subTest(name):
                response = self.call(
                    "post", "manage-api-skills", {"category": "AWS", "name": name}
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("共通マスタ", response.json()["errors"][0])
        self.assertEqual(Skill.objects.filter(owner=self.user_a).count(), 0)

    def test_自分の同じ種類_名前の項目は重複登録できない(self):
        payload = {"category": "AWS", "name": "独自"}
        self.assertEqual(
            self.call("post", "manage-api-skills", payload).status_code, 200
        )
        self.assertEqual(
            self.call("post", "manage-api-skills", payload).status_code, 400
        )
        self.assertEqual(Skill.objects.filter(owner=self.user_a).count(), 1)

    def test_別の種類や他のユーザーの項目とは重複しない(self):
        Skill.objects.create(
            skill_id="u-bbbb",
            category="AWS",
            name="独自",
            sort_order=0,
            owner=self.user_b,
        )
        self.assertEqual(
            self.call(
                "post", "manage-api-skills", {"category": "AWS", "name": "独自"}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.call(
                "post", "manage-api-skills", {"category": "言語", "name": "独自"}
            ).status_code,
            200,
        )

    def test_独自スキル項目の追加で共通マスタの表示順は変わらない(self):
        before = dict(
            Skill.objects.filter(owner__isnull=True).values_list(
                "skill_id", "sort_order"
            )
        )
        self.call("post", "manage-api-skills", {"category": "AWS", "name": "独自"})
        after = dict(
            Skill.objects.filter(owner__isnull=True).values_list(
                "skill_id", "sort_order"
            )
        )
        self.assertEqual(before, after)
        self.assertFalse(SkillCategory.objects.exists())


class PermissionTests(SplitTestCase):
    def test_共通マスタは一般ユーザーが変更も削除もできない(self):
        payload = {"category": "AWS", "name": "EC2 (変更)"}
        self.assertEqual(
            self.call(
                "put", "manage-api-skill", payload, skill_id="aws-ec2"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.call("delete", "manage-api-skill", skill_id="aws-ec2").status_code, 403
        )
        self.master.refresh_from_db()
        self.assertEqual(self.master.name, "EC2")

    def test_自分の独自スキル項目は変更_削除できる(self):
        self.call("post", "manage-api-skills", {"category": "AWS", "name": "独自"})
        skill = Skill.objects.get(owner=self.user_a)
        response = self.call(
            "put",
            "manage-api-skill",
            {"category": "言語", "subcategory": "x", "name": "独自2"},
            skill_id=skill.skill_id,
        )
        self.assertEqual(response.status_code, 200)
        skill.refresh_from_db()
        self.assertEqual((skill.category, skill.name), ("言語", "独自2"))
        self.assertEqual(
            self.call(
                "delete", "manage-api-skill", skill_id=skill.skill_id
            ).status_code,
            200,
        )

    def test_独自スキル項目の種類の変更も既存の種類に限る(self):
        self.call("post", "manage-api-skills", {"category": "AWS", "name": "独自"})
        skill = Skill.objects.get(owner=self.user_a)
        response = self.call(
            "put",
            "manage-api-skill",
            {"category": "存在しない", "name": "独自"},
            skill_id=skill.skill_id,
        )
        self.assertEqual(response.status_code, 400)

    def test_種類の変更は一般ユーザーは403(self):
        for method, name, data, kwargs in [
            ("post", "manage-api-categories", {"name": "新種類"}, {}),
            (
                "put",
                "manage-api-category",
                {"name": "新名称"},
                {"category_name": "AWS"},
            ),
            ("delete", "manage-api-category", None, {"category_name": "AWS"}),
            ("post", "manage-api-category-order", {"categories": ["言語", "AWS"]}, {}),
        ]:
            with self.subTest(name, method=method):
                self.assertEqual(
                    self.call(method, name, data, **kwargs).status_code, 403
                )
        self.assertEqual(Skill.objects.get(skill_id="aws-ec2").category, "AWS")

    def test_種類の一覧は一般ユーザーも参照できる(self):
        response = self.call("get", "manage-api-categories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c["name"] for c in response.json()], ["AWS", "言語"])

    def test_運営者は共通マスタと種類を編集できる(self):
        self.login_as("operator")
        response = self.call(
            "post",
            "manage-api-skills",
            {"skill_id": "aws-vpc", "category": "AWS", "name": "VPC"},
        )
        self.assertEqual(response.status_code, 200)
        vpc = Skill.objects.get(skill_id="aws-vpc")
        self.assertTrue(vpc.is_master)
        self.assertIsNone(vpc.owner_id)

        response = self.call(
            "put",
            "manage-api-skill",
            {"category": "AWS", "name": "EC2改"},
            skill_id="aws-ec2",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.call("post", "manage-api-categories", {"name": "新種類"}).status_code,
            200,
        )

    def test_運営者が新しい種類のマスタ項目を追加すると種類マスタにも登録される(self):
        self.login_as("operator")
        self.call(
            "post",
            "manage-api-skills",
            {"skill_id": "tf", "category": "IaC", "name": "Terraform"},
        )
        self.assertTrue(SkillCategory.objects.filter(name="IaC").exists())

    def test_運営者による種類名の変更は全ユーザーの独自スキル項目にも反映される(self):
        Skill.objects.create(
            skill_id="u-bbbb",
            category="AWS",
            name="Bの独自",
            sort_order=0,
            owner=self.user_b,
        )
        self.login_as("operator")
        self.call("put", "manage-api-category", {"name": "Amazon"}, category_name="AWS")
        self.assertEqual(Skill.objects.get(skill_id="u-bbbb").category, "Amazon")

    def test_他のユーザーの独自スキル項目がある種類は運営者でも削除できない(self):
        self.call("post", "manage-api-categories", {"name": "空"})  # 一般ユーザーは403
        Skill.objects.create(
            skill_id="u-bbbb",
            category="専用",
            name="Bの独自",
            sort_order=0,
            owner=self.user_b,
        )
        SkillCategory.objects.create(name="専用", sort_order=999)
        self.login_as("operator")
        response = self.call("delete", "manage-api-category", category_name="専用")
        self.assertEqual(response.status_code, 400)

    def test_項目数の集計に他のユーザーの独自スキル項目を含めない(self):
        Skill.objects.create(
            skill_id="u-bbbb",
            category="AWS",
            name="Bの独自",
            sort_order=0,
            owner=self.user_b,
        )
        counts = {
            c["name"]: c["skill_count"]
            for c in self.call("get", "manage-api-categories").json()
        }
        self.assertEqual(counts["AWS"], 1)
        self.login_as("operator")
        counts = {
            c["name"]: c["skill_count"]
            for c in self.call("get", "manage-api-categories").json()
        }
        self.assertEqual(counts["AWS"], 2)

    def test_一覧には編集可否と独自の区別を含める(self):
        self.call("post", "manage-api-skills", {"category": "AWS", "name": "独自"})
        rows = {r["name"]: r for r in self.call("get", "manage-api-skills").json()}
        self.assertEqual(
            (rows["EC2"]["is_custom"], rows["EC2"]["editable"]), (False, False)
        )
        self.assertEqual(
            (rows["独自"]["is_custom"], rows["独自"]["editable"]), (True, True)
        )
        self.login_as("operator")
        rows = {r["name"]: r for r in self.call("get", "manage-api-skills").json()}
        self.assertEqual(rows["EC2"]["editable"], True)
        self.assertNotIn("独自", rows)

    def test_初期表示データで運営者かどうかを返す(self):
        self.assertFalse(self.call("get", "manage-api-bootstrap").json()["is_operator"])
        self.login_as("operator")
        self.assertTrue(self.call("get", "manage-api-bootstrap").json()["is_operator"])


class DisplayOrderTests(SplitTestCase):
    def test_独自スキル項目は同じ種類の共通マスタの後ろに_サブカテゴリ_名前の順で並ぶ(
        self,
    ):
        _master("aws-s3", "AWS", "S3", 30, "Storage")
        for sub, name in [
            ("Storage", "ZZ"),
            ("Compute", "CC"),
            ("", "AA"),
            ("Compute", "BB"),
        ]:
            self.call(
                "post",
                "manage-api-skills",
                {"category": "AWS", "subcategory": sub, "name": name},
            )
        names = [
            s.name for s in services.ordered_skills(self.user_a) if s.category == "AWS"
        ]
        self.assertEqual(names, ["EC2", "S3", "BB", "CC", "ZZ", "AA"])

    def test_種類の並びは共通マスタの順で_独自スキル項目で変わらない(self):
        self.call("post", "manage-api-skills", {"category": "言語", "name": "独自言語"})
        categories = []
        for skill in services.ordered_skills(self.user_a):
            if skill.category not in categories:
                categories.append(skill.category)
        self.assertEqual(categories, ["AWS", "言語"])

    def test_他のユーザーの独自スキル項目は含まれない(self):
        Skill.objects.create(
            skill_id="u-bbbb",
            category="AWS",
            name="Bの独自",
            sort_order=0,
            owner=self.user_b,
        )
        self.assertNotIn(
            "Bの独自", [s.name for s in services.ordered_skills(self.user_a)]
        )
        self.assertIn("Bの独自", [s.name for s in services.ordered_skills(self.user_b)])


class SeedImportDoesNotTouchCustomSkillsTests(SplitTestCase):
    def test_種データの取り込みで独自スキル項目は変更されない(self):
        Skill.objects.all().delete()
        custom = Skill.objects.create(
            skill_id="u-aaaa",
            category="AWS",
            subcategory="独自サブ",
            name="EC2",
            sort_order=0,
            owner=self.user_a,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "skills_master.json"
            path.write_text(
                json.dumps(
                    {
                        "categories": [
                            {
                                "name": "AWS",
                                "skill_id_prefix": "aws-",
                                "skills": [{"name": "EC2", "subcategory": "Compute"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            call_command("import_skill_master", seed_file=path, stdout=StringIO())

        custom.refresh_from_db()
        self.assertEqual(
            (custom.skill_id, custom.subcategory, custom.owner),
            ("u-aaaa", "独自サブ", self.user_a),
        )
        self.assertFalse(custom.is_master)
        master = Skill.objects.get(skill_id="aws-ec2")
        self.assertTrue(master.is_master)
        self.assertIsNone(master.owner_id)


class ManageScreenTests(SplitTestCase):
    def test_種類管理のタブは運営者にのみ表示する(self):
        html = self.client.get(reverse("manage")).content.decode()
        self.assertNotIn('data-tab="categories"', html)
        self.assertIn('data-is-operator="false"', html)
        self.login_as("operator")
        html = self.client.get(reverse("manage")).content.decode()
        self.assertIn('data-tab="categories"', html)
        self.assertIn('data-is-operator="true"', html)
