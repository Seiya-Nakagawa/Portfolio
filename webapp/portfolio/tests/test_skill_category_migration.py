from importlib import import_module

from django.apps import apps
from django.test import TestCase

from portfolio.models import Skill, SkillCategory

migration = import_module("portfolio.migrations.0011_skill_category")


class SkillCategoryMigrationTests(TestCase):
    def test_OSとミドルウェアを統合し種類マスタを作成する(self):
        Skill.objects.all().delete()
        SkillCategory.objects.all().delete()
        for skill_id, category, name, order in [
            ("linux", "OS", "Linux", 10),
            ("py", "言語", "Python", 20),
            ("nginx", "ミドルウェア", "Nginx", 30),
        ]:
            Skill.objects.create(
                skill_id=skill_id, category=category, name=name, sort_order=order
            )
        migration.create_categories(apps, None)
        self.assertEqual(
            list(
                Skill.objects.order_by("sort_order").values_list("skill_id", "category")
            ),
            [("linux", "OS・MW"), ("nginx", "OS・MW"), ("py", "言語")],
        )
        self.assertEqual(
            list(SkillCategory.objects.values_list("name", flat=True)),
            ["OS・MW", "言語"],
        )
