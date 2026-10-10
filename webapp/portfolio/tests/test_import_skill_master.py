import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from portfolio.management.commands.import_skill_master import (
    SEED_FILE,
    comparison_keys,
    make_skill_id,
)
from portfolio.models import Skill, SkillCategory


class ComparisonKeysTests(SimpleTestCase):
    def test_提供元の接頭辞と記号を除いて比較する(self):
        self.assertEqual(comparison_keys("Amazon EC2"), comparison_keys("EC2"))
        self.assertEqual(comparison_keys("AWS Lambda"), comparison_keys("lambda"))
        self.assertEqual(comparison_keys("Route 53"), comparison_keys("Route53"))

    def test_括弧書きの別名でも同じ項目とみなす(self):
        self.assertIn("vcn", comparison_keys("Virtual Cloud Network (VCN)"))
        self.assertTrue(
            comparison_keys("VCN") & comparison_keys("Virtual Cloud Network (VCN)")
        )


class MakeSkillIdTests(SimpleTestCase):
    def test_記号を読み替えて重複には連番を付ける(self):
        used: set[str] = set()
        self.assertEqual(make_skill_id("", "C++", used), "cplusplus")
        self.assertEqual(make_skill_id("", "C#", used), "csharp")
        self.assertEqual(make_skill_id("aws-", "Route 53", used), "aws-route-53")
        self.assertEqual(make_skill_id("aws-", "Route53 ", used), "aws-route53")
        self.assertEqual(make_skill_id("aws-", "Route 53", used), "aws-route-53-2")

    def test_括弧書きは含めない(self):
        self.assertEqual(
            make_skill_id("oci-", "Virtual Cloud Network (VCN)", set()),
            "oci-virtual-cloud-network",
        )


class SeedFileTests(SimpleTestCase):
    def test_種データは重複なく網羅したクラウドを含む(self):
        categories = json.loads(SEED_FILE.read_text(encoding="utf-8"))["categories"]
        by_name = {c["name"]: c["skills"] for c in categories}
        for cloud in ("AWS", "Azure", "Google Cloud", "OCI"):
            names = [s["name"].casefold() for s in by_name[cloud]]
            self.assertEqual(len(names), len(set(names)), cloud)
            self.assertGreaterEqual(len(names), 100, cloud)
            self.assertTrue(all(s["subcategory"] for s in by_name[cloud]), cloud)


class ImportSkillMasterTests(TestCase):
    def setUp(self):
        Skill.objects.all().delete()
        SkillCategory.objects.all().delete()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "skills_master.json"
        self.path.write_text(
            json.dumps(
                {
                    "categories": [
                        {
                            "name": "AWS",
                            "skill_id_prefix": "aws-",
                            "skills": [
                                {"name": "EC2", "subcategory": "Compute"},
                                {"name": "S3", "subcategory": "Storage"},
                            ],
                        },
                        {
                            "name": "言語",
                            "skill_id_prefix": "",
                            "skills": [{"name": "Go"}],
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

    def _run(self) -> str:
        out = StringIO()
        call_command("import_skill_master", seed_file=self.path, stdout=out)
        return out.getvalue()

    def test_未登録の種類とスキル項目を追加する(self):
        self.assertIn("3 件", self._run())
        self.assertEqual(
            sorted(Skill.objects.values_list("skill_id", "category", "subcategory")),
            [
                ("aws-ec2", "AWS", "Compute"),
                ("aws-s3", "AWS", "Storage"),
                ("go", "言語", ""),
            ],
        )
        self.assertEqual(
            list(SkillCategory.objects.values_list("name", flat=True)), ["AWS", "言語"]
        )
        self.assertTrue(all(s.is_master for s in Skill.objects.all()))

    def test_登録済みの項目は変更せず再実行しても増えない(self):
        SkillCategory.objects.create(name="AWS", sort_order=10)
        Skill.objects.create(
            skill_id="ec2",
            category="AWS",
            subcategory="",
            name="Amazon EC2",
            sort_order=10,
        )
        self.assertIn("2 件", self._run())
        ec2 = Skill.objects.get(skill_id="ec2")
        self.assertEqual((ec2.name, ec2.subcategory), ("Amazon EC2", ""))
        self.assertFalse(ec2.is_master)
        self.assertFalse(Skill.objects.filter(skill_id="aws-ec2").exists())
        self.assertIn("0 件", self._run())
        self.assertEqual(Skill.objects.count(), 3)

    def test_既存の種類の並びは保ち新しい種類は末尾に置く(self):
        SkillCategory.objects.create(name="言語", sort_order=10)
        SkillCategory.objects.create(name="DB", sort_order=20)
        self._run()
        self.assertEqual(
            list(SkillCategory.objects.values_list("name", flat=True)),
            ["言語", "DB", "AWS"],
        )


class ImportRealSeedTests(TestCase):
    def test_種データを登録でき既存の項目と重複しない(self):
        SkillCategory.objects.create(name="AWS", sort_order=10)
        Skill.objects.create(
            skill_id="aws-ecs", category="AWS", name="ECS", sort_order=10
        )
        Skill.objects.create(
            skill_id="oci-vcn", category="OCI", name="VCN", sort_order=20
        )
        call_command("import_skill_master", stdout=StringIO())

        total = Skill.objects.count()
        self.assertGreater(total, 1000)
        self.assertEqual(
            Skill.objects.filter(category="AWS", name__iexact="ECS").count(), 1
        )
        self.assertFalse(
            Skill.objects.filter(category="OCI", name__icontains="(VCN)").exists()
        )
        self.assertEqual(Skill.objects.get(skill_id="aws-ecs").subcategory, "")

        call_command("import_skill_master", stdout=StringIO())
        self.assertEqual(Skill.objects.count(), total)
