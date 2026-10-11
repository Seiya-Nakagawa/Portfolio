from importlib import import_module

from django.apps import apps
from django.test import TestCase

from portfolio.models import Skill

migration = import_module("portfolio.migrations.0020_all_skills_master")


class AllSkillsMasterMigrationTests(TestCase):
    def test_登録済みのスキル項目をすべてマスタ項目にする(self):
        for number, name in enumerate(["EC2", "S3"], start=1):
            Skill.objects.create(
                skill_id=name.lower(), category="AWS", name=name, sort_order=number
            )
        self.assertFalse(Skill.objects.filter(is_master=True).exists())

        migration.mark_all_master(apps, None)

        self.assertEqual(Skill.objects.filter(is_master=True).count(), 2)
