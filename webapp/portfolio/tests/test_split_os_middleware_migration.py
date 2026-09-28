from importlib import import_module

from django.apps import apps
from django.test import TestCase

from portfolio.models import Skill, SkillCategory

migration = import_module("portfolio.migrations.0013_split_os_middleware_categories")


class SplitOsMiddlewareMigrationTests(TestCase):
    def test_OSとミドルウェアを2種類に分離する(self):
        Skill.objects.all().delete()
        SkillCategory.objects.all().delete()
        SkillCategory.objects.create(name="OS・MW", sort_order=10)
        SkillCategory.objects.create(name="言語", sort_order=20)
        for skill_id, name, order in [
            ("linux", "Linux", 10),
            ("nginx", "Nginx", 20),
            ("windows", "Windows", 30),
            ("py", "Python", 40),
        ]:
            category = "言語" if skill_id == "py" else "OS・MW"
            Skill.objects.create(
                skill_id=skill_id, category=category, name=name, sort_order=order
            )

        migration.split_categories(apps, None)

        self.assertEqual(
            dict(Skill.objects.values_list("skill_id", "category")),
            {
                "linux": "OS",
                "windows": "OS",
                "nginx": "ミドルウェア",
                "py": "言語",
            },
        )
        self.assertEqual(
            list(
                SkillCategory.objects.order_by("sort_order").values_list(
                    "name", flat=True
                )
            ),
            ["OS", "ミドルウェア", "言語"],
        )

    def test_統合前の種類がなければ何もしない(self):
        Skill.objects.all().delete()
        SkillCategory.objects.all().delete()
        SkillCategory.objects.create(name="言語", sort_order=10)
        Skill.objects.create(
            skill_id="py", category="言語", name="Python", sort_order=10
        )

        migration.split_categories(apps, None)

        self.assertEqual(
            list(SkillCategory.objects.values_list("name", flat=True)), ["言語"]
        )
