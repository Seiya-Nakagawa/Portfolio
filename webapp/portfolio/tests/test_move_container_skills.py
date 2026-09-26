import importlib

from django.apps import apps
from django.test import TestCase

from portfolio.models import Skill

migration = importlib.import_module(
    "portfolio.migrations.0008_move_container_skills_and_resequence"
)


class MoveContainerSkillsTests(TestCase):
    def test_ECSとEKSをAWSのContainersへ移し表示順を採番し直す(self):
        Skill.objects.create(
            skill_id="aws-ec2", category="AWS", name="EC2", sort_order=1
        )
        Skill.objects.create(
            skill_id="ecs-fargate",
            category="コンテナ",
            name="ECS (Fargate)",
            sort_order=2,
        )
        Skill.objects.create(
            skill_id="eks-kubernetes",
            category="コンテナ",
            name="EKS(Kubernetes)",
            sort_order=3,
        )
        Skill.objects.create(
            skill_id="docker", category="コンテナ", name="Docker", sort_order=4
        )
        migration.move_container_skills(apps, None)
        for skill_id in ["ecs-fargate", "eks-kubernetes"]:
            skill = Skill.objects.get(skill_id=skill_id)
            self.assertEqual((skill.category, skill.subcategory), ("AWS", "Containers"))
        self.assertEqual(Skill.objects.get(skill_id="docker").category, "コンテナ")
        ids = list(
            Skill.objects.order_by("sort_order").values_list("skill_id", flat=True)
        )
        self.assertEqual(ids, ["ecs-fargate", "eks-kubernetes", "aws-ec2", "docker"])
