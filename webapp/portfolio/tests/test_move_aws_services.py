import importlib

from django.apps import apps
from django.test import TestCase

from portfolio.models import Project, ProjectSkill, Skill

migration = importlib.import_module("portfolio.migrations.0007_move_aws_services_to_aws")


class MoveAwsServicesTests(TestCase):
    def _run(self):
        migration.move_aws_services(apps, None)

    def test_他カテゴリのAWSサービスをAWSへ移す(self):
        Skill.objects.create(skill_id="ec2", category="AWS", name="EC2", sort_order=10)
        Skill.objects.create(
            skill_id="eks", category="コンテナ", name="Amazon EKS", sort_order=10
        )
        self._run()
        moved = Skill.objects.get(skill_id="eks")
        self.assertEqual(moved.category, "AWS")
        self.assertEqual(moved.subcategory, "Containers")
        self.assertEqual(moved.sort_order, 20)

    def test_紛らわしい名称は接頭辞なしでは移さない(self):
        Skill.objects.create(skill_id="cdk", category="IaC", name="CDK", sort_order=10)
        self._run()
        self.assertEqual(Skill.objects.get(skill_id="cdk").category, "IaC")

    def test_AWS側に同名があれば案件実績を付け替えて統合する(self):
        Skill.objects.create(skill_id="rds", category="AWS", name="RDS", sort_order=10)
        Skill.objects.create(
            skill_id="rds-db", category="データベース", name="Amazon RDS", sort_order=10
        )
        project = Project.objects.create(
            project_id="p1", name="案件", start_year_month="2024-01"
        )
        ProjectSkill.objects.create(
            project=project, skill_id="rds-db", version="8.0"
        )
        self._run()
        self.assertFalse(Skill.objects.filter(skill_id="rds-db").exists())
        self.assertEqual(ProjectSkill.objects.get(project=project).skill_id, "rds")
