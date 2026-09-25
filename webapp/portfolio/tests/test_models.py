from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from portfolio.models import Level, Project, ProjectSkill, Skill


class LevelInitialDataTests(TestCase):
    def test_初期値として1から5が登録されている(self):
        self.assertEqual(
            list(Level.objects.order_by("level").values_list("level", flat=True)),
            [1, 2, 3, 4, 5],
        )

    def test_レベル5のラベル(self):
        level = Level.objects.get(level=5)
        self.assertEqual(
            level.portfolio_label, "スペシャリスト (広範な知識と高い専門性)"
        )
        self.assertEqual(
            level.resume_label, "広範な知識と高い専門性をもって技術選定・標準化ができる"
        )


class ProjectTests(TestCase):
    def test_案件IDは自動採番される(self):
        project = Project.objects.create(name="案件A", start_year_month="2024-01")
        self.assertRegex(project.project_id, r"^p-[0-9a-f]{12}$")

    def test_年月の形式を検証する(self):
        project = Project(name="案件A", start_year_month="2024/01")
        with self.assertRaises(ValidationError):
            project.full_clean()

    def test_終了年月は空でもよい(self):
        project = Project(name="案件A", start_year_month="2024-01", end_year_month="")
        project.full_clean()


class ProjectSkillTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="案件A", start_year_month="2024-01")
        self.skill = Skill.objects.create(
            skill_id="python",
            category="言語",
            name="Python",
            level=Level.objects.get(level=3),
            sort_order=1,
        )

    def test_同じ案件とスキルの組み合わせは重複登録できない(self):
        ProjectSkill.objects.create(project=self.project, skill=self.skill)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectSkill.objects.create(project=self.project, skill=self.skill)

    def test_実績が紐づくスキルは削除できない(self):
        ProjectSkill.objects.create(project=self.project, skill=self.skill)
        with self.assertRaises(ProtectedError):
            self.skill.delete()

    def test_案件を削除すると使用実績も削除される(self):
        ProjectSkill.objects.create(project=self.project, skill=self.skill)
        self.project.delete()
        self.assertEqual(ProjectSkill.objects.count(), 0)

    def test_skill_idの形式を検証する(self):
        skill = Skill(
            skill_id="Bad_ID",
            category="言語",
            name="X",
            level=Level.objects.get(level=1),
            sort_order=1,
        )
        with self.assertRaises(ValidationError):
            skill.full_clean()
