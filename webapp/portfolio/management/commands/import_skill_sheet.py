"""旧実績シートを CSV に書き出したものを、実績 DB へ移行する。

実データ（案件名・期間）は個人の職歴を含むためリポジトリには置かず、CSV は実行時に渡す。
"""

import csv
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portfolio.models import Level, Project, ProjectSkill, Skill

SKILLS_FILE = "skills.csv"
PROJECTS_FILE = "projects.csv"
PROJECT_SKILLS_FILE = "project_skills.csv"


def read_rows(path: Path, required: list[str]) -> list[dict[str, str]]:
    """CSV を読み込む。必須列がなければエラーとする。余分な列は無視する。"""
    if not path.is_file():
        raise CommandError(f"CSV が見つかりません: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise CommandError(
                f"{path.name} に必須列がありません: {', '.join(missing)}"
            )
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def full_clean_or_raise(instance, label: str) -> None:
    try:
        instance.full_clean()
    except ValidationError as error:
        raise CommandError(f"{label}: {'; '.join(error.messages)}") from None


class Command(BaseCommand):
    help = (
        "実績シートの CSV（skills.csv・projects.csv・project_skills.csv）を実績 DB へ移行する。"
        "スキル項目・案件・使用実績のいずれかに既存データがある場合は何も変更しない。"
    )

    def add_arguments(self, parser):
        parser.add_argument("directory", type=Path, help="CSV を置いたディレクトリ")

    def handle(self, *args, **options):
        directory: Path = options["directory"]
        skill_rows = read_rows(
            directory / SKILLS_FILE,
            ["skill_id", "category", "name", "level", "sort_order"],
        )
        project_rows = read_rows(
            directory / PROJECTS_FILE,
            ["project_id", "name", "start_year_month", "end_year_month"],
        )
        usage_rows = read_rows(
            directory / PROJECT_SKILLS_FILE, ["project_id", "skill_id", "version"]
        )

        if any(m.objects.exists() for m in (Skill, Project, ProjectSkill)):
            self.stdout.write("既存データがあるため移行しませんでした。")
            return

        levels = set(Level.objects.values_list("level", flat=True))
        skills = []
        for row in skill_rows:
            label = f"skills.csv skill_id={row['skill_id']}"
            try:
                level = int(row["level"])
                sort_order = int(row["sort_order"])
            except ValueError:
                raise CommandError(
                    f"{label}: level・sort_order は整数で指定してください。"
                ) from None
            if level not in levels:
                raise CommandError(f"{label}: 存在しないレベルです: {level}")
            skill = Skill(
                skill_id=row["skill_id"],
                category=row["category"],
                name=row["name"],
                level_id=level,
                remarks=row.get("remarks", ""),
                sort_order=sort_order,
            )
            full_clean_or_raise(skill, label)
            skills.append(skill)

        projects = []
        for row in project_rows:
            project = Project(
                project_id=row["project_id"],
                name=row["name"],
                start_year_month=row["start_year_month"],
                end_year_month=row["end_year_month"],
            )
            full_clean_or_raise(project, f"projects.csv project_id={row['project_id']}")
            projects.append(project)

        skill_ids = {s.skill_id for s in skills}
        project_ids = {p.project_id for p in projects}
        usages = []
        seen: set[tuple[str, str]] = set()
        for row in usage_rows:
            key = (row["project_id"], row["skill_id"])
            label = f"project_skills.csv {key[0]} / {key[1]}"
            if key[0] not in project_ids:
                raise CommandError(f"{label}: 存在しない案件です。")
            if key[1] not in skill_ids:
                raise CommandError(f"{label}: 存在しないスキル項目です。")
            if key in seen:
                raise CommandError(f"{label}: 重複しています。")
            seen.add(key)
            usages.append(
                ProjectSkill(project_id=key[0], skill_id=key[1], version=row["version"])
            )

        with transaction.atomic():
            Skill.objects.bulk_create(skills)
            Project.objects.bulk_create(projects)
            ProjectSkill.objects.bulk_create(usages)

        self.stdout.write(
            f"移行しました: スキル項目 {len(skills)} 件、案件 {len(projects)} 件、"
            f"使用実績 {len(usages)} 件"
        )
