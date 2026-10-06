from importlib import import_module

from django.apps import apps
from django.test import TestCase

from portfolio.models import Project, ProjectSkill, Skill

migration = import_module("portfolio.migrations.0014_merge_ecs_fargate_skill")


class MergeEcsFargateMigrationTests(TestCase):
    def setUp(self):
        Skill.objects.all().delete()

    def test_ECSFargateの使用実績をECSへ付け替えて削除する(self):
        Skill.objects.create(
            skill_id="aws-ecs", category="AWS", name="ECS", sort_order=10
        )
        Skill.objects.create(
            skill_id="ecs-fargate", category="AWS", name="ECS (Fargate)", sort_order=20
        )
        only_fargate = Project.objects.create(name="A", start_year_month="2025-01")
        both = Project.objects.create(name="B", start_year_month="2025-02")
        ProjectSkill.objects.create(
            project=only_fargate, skill_id="ecs-fargate", version="1"
        )
        ProjectSkill.objects.create(project=both, skill_id="ecs-fargate")
        ProjectSkill.objects.create(project=both, skill_id="aws-ecs")

        migration.merge_ecs_fargate(apps, None)

        self.assertFalse(Skill.objects.filter(skill_id="ecs-fargate").exists())
        self.assertEqual(
            sorted(
                ProjectSkill.objects.values_list("project__name", "skill_id", "version")
            ),
            [("A", "aws-ecs", "1"), ("B", "aws-ecs", "")],
        )

    def test_ECSがなければECSFargateの表示名をECSへ変更する(self):
        Skill.objects.create(
            skill_id="ecs-fargate", category="AWS", name="ECS (Fargate)", sort_order=10
        )

        migration.merge_ecs_fargate(apps, None)

        self.assertEqual(Skill.objects.get(skill_id="ecs-fargate").name, "ECS")

    def test_単体のFargateもECSへ付け替えて削除する(self):
        Skill.objects.create(
            skill_id="aws-ecs", category="AWS", name="ECS", sort_order=10
        )
        Skill.objects.create(
            skill_id="aws-fargate", category="AWS", name="Fargate", sort_order=20
        )
        project = Project.objects.create(name="C", start_year_month="2025-03")
        ProjectSkill.objects.create(project=project, skill_id="aws-fargate")

        migration.merge_ecs_fargate(apps, None)

        self.assertFalse(Skill.objects.filter(skill_id="aws-fargate").exists())
        self.assertEqual(
            list(ProjectSkill.objects.values_list("skill_id", flat=True)),
            ["aws-ecs"],
        )
