import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from portfolio.models import Project, ProjectSkill, Skill

SKILLS = "skill_id,category,name,level,remarks,sort_order\nec2,AWS,EC2,5,,1\nlinux,OS,Linux,3,,1\n"
PROJECTS = (
    "project_id,name,sort_order,start_year_month,end_year_month\n"
    "proj-a,案件A,1,2025-01,2025-06\n"
    "proj-b,案件B,2,2025-07,\n"
)
USAGES = "project_id,skill_id,version\nproj-a,ec2,\nproj-a,linux,Ubuntu 26.04\nproj-b,linux,\n"


class ImportSkillSheetTests(TestCase):
    def _dir(self, skills=SKILLS, projects=PROJECTS, usages=USAGES):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name)
        (path / "skills.csv").write_text(skills, encoding="utf-8")
        (path / "projects.csv").write_text(projects, encoding="utf-8")
        (path / "project_skills.csv").write_text(usages, encoding="utf-8")
        return path

    def _run(self, path):
        out = StringIO()
        call_command("import_skill_sheet", path, stdout=out)
        return out.getvalue()

    def test_移行できる(self):
        self.assertIn(
            "スキル項目 2 件、案件 2 件、使用実績 3 件", self._run(self._dir())
        )
        self.assertEqual(Project.objects.get(project_id="proj-b").end_year_month, "")
        self.assertEqual(
            ProjectSkill.objects.get(project_id="proj-a", skill_id="linux").version,
            "Ubuntu 26.04",
        )

    def test_既存データがあれば何も変更しない(self):
        Skill.objects.create(
            skill_id="x", category="c", name="n", level_id=1, sort_order=1
        )
        self.assertIn("既存データがある", self._run(self._dir()))
        self.assertEqual(Skill.objects.count(), 1)
        self.assertEqual(Project.objects.count(), 0)

    def test_不正な入力はエラーで何も登録しない(self):
        cases = {
            "存在しないレベル": {
                "skills": SKILLS.replace("ec2,AWS,EC2,5", "ec2,AWS,EC2,9")
            },
            "skill_id の形式": {"skills": SKILLS.replace("ec2,", "EC 2,", 1)},
            "年月の形式": {"projects": PROJECTS.replace("2025-01", "2025/01")},
            "存在しない案件": {"usages": USAGES + "nothing,ec2,\n"},
            "存在しないスキル": {"usages": USAGES + "proj-a,nothing,\n"},
            "使用実績の重複": {"usages": USAGES + "proj-a,ec2,\n"},
        }
        for label, override in cases.items():
            with self.subTest(label), self.assertRaises(CommandError):
                self._run(self._dir(**override))
            self.assertEqual(Skill.objects.count(), 0, label)
            self.assertEqual(Project.objects.count(), 0, label)

    def test_必須列がなければエラー(self):
        with self.assertRaises(CommandError):
            self._run(self._dir(usages="project_id,skill_id\nproj-a,ec2\n"))

    def test_CSVがなければエラー(self):
        with self.assertRaises(CommandError):
            self._run(Path("/nonexistent"))
