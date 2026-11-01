"""ログインなしのデモ。架空の案件を入力として、本番と同じ経験年数の算出ロジックで集計する。

データは保存せず、入力はすべてリクエストのクエリで受け取る。
"""

import re
from dataclasses import dataclass
from datetime import date

from portfolio.experience import (
    ProjectPeriod,
    SkillUsage,
    aggregate_skill_experience,
    calculate_stars,
    format_experience,
)

YEAR_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

DEMO_SKILLS = (
    ("python", "Python"),
    ("django", "Django"),
    ("aws", "AWS"),
    ("docker", "Docker"),
    ("mysql", "MySQL"),
    ("terraform", "Terraform"),
)
SKILL_NAMES = dict(DEMO_SKILLS)


@dataclass(frozen=True)
class DemoProject:
    project_id: str
    name: str
    start: str
    end: str
    skills: tuple[str, ...]


# 既定値。案件 A・B は期間が重なり、並行案件が重複せずに数えられる様子を示す。
DEFAULT_PROJECTS = (
    DemoProject(
        "p1",
        "A 社 基幹システムの改修",
        "2022-04",
        "2023-09",
        ("python", "django", "mysql"),
    ),
    DemoProject(
        "p2",
        "B 社 クラウド移行",
        "2023-04",
        "2024-12",
        ("python", "aws", "docker", "terraform"),
    ),
    DemoProject(
        "p3",
        "C 社 Web サービス開発",
        "2025-01",
        "",
        ("python", "django", "aws", "docker"),
    ),
)


@dataclass(frozen=True)
class DemoRow:
    name: str
    start_year: int
    duration: str
    stars: int


@dataclass(frozen=True)
class DemoResult:
    projects: tuple[DemoProject, ...]
    rows: tuple[DemoRow, ...]
    errors: tuple[str, ...]


def parse_projects(params) -> tuple[tuple[DemoProject, ...], list[str]]:
    """クエリから案件を読み取る。不正な案件は既定値に戻し、エラーを返す。"""
    if not any(key.startswith("p") for key in params):
        return DEFAULT_PROJECTS, []

    projects = []
    errors = []
    for default in DEFAULT_PROJECTS:
        pid = default.project_id
        start = params.get(f"{pid}_start", "").strip()
        end = params.get(f"{pid}_end", "").strip()
        skills = tuple(
            skill_id
            for skill_id, _ in DEMO_SKILLS
            if skill_id in params.getlist(f"{pid}_skills")
        )
        problem = None
        if not YEAR_MONTH_PATTERN.match(start):
            problem = "開始年月は YYYY-MM の形式で入力してください。"
        elif end and not YEAR_MONTH_PATTERN.match(end):
            problem = "終了年月は YYYY-MM の形式で入力してください。"
        elif end and end < start:
            problem = "終了年月は開始年月以降にしてください。"
        if problem:
            errors.append(f"{default.name}: {problem}")
            projects.append(default)
        else:
            projects.append(DemoProject(pid, default.name, start, end, skills))
    return tuple(projects), errors


def calculate(projects: tuple[DemoProject, ...], today: date) -> tuple[DemoRow, ...]:
    periods = [ProjectPeriod(p.project_id, p.start, p.end) for p in projects]
    usages = [SkillUsage(p.project_id, s) for p in projects for s in p.skills]
    aggregated = aggregate_skill_experience(periods, usages, today)
    rows = [
        DemoRow(
            name=SKILL_NAMES[skill_id],
            start_year=experience.start_year,
            duration=format_experience(experience.months) or "",
            stars=calculate_stars(experience.months),
        )
        for skill_id, experience in aggregated.items()
        if skill_id in SKILL_NAMES
    ]
    order = {skill_id: i for i, (skill_id, _) in enumerate(DEMO_SKILLS)}
    rows.sort(
        key=lambda r: order[next(k for k, v in SKILL_NAMES.items() if v == r.name)]
    )
    return tuple(rows)


def build_result(params, today: date) -> DemoResult:
    projects, errors = parse_projects(params)
    return DemoResult(projects, calculate(projects, today), tuple(errors))
