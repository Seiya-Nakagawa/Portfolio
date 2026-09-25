"""職務経歴書ビルダーが読み込む Markdown の生成。"""

from dataclasses import dataclass, field
from datetime import date

from portfolio.models import Level, Project, Skill
from portfolio.services import build_skill_rows

# 継続中の案件の終了年月の表記。
ONGOING_LABEL = "現在"


@dataclass
class ExportWarnings:
    """出力時の警告。"""

    unused_skill_count: int = 0
    invalid_level_skills: list[str] = field(default_factory=list)


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _format_period(start: str, end: str) -> str:
    def to_label(year_month: str) -> str:
        year, month = year_month.split("-")
        return f"{year}年{month}月"

    return f"{to_label(start)}〜{to_label(end) if end else ONGOING_LABEL}"


def build_skill_table(today: date) -> str:
    """`■テクニカルスキル` の表。"""
    resume_labels = dict(Level.objects.values_list("level", "resume_label"))
    lines = [
        "| 種類 | 項目 | 開始年 | 使用期間 | レベル |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in build_skill_rows(today):
        skill = row.skill
        level_text = resume_labels.get(skill.level_id, "")
        if skill.remarks:
            level_text += f"（{skill.remarks}）"
        cells = [
            skill.category,
            skill.name,
            f"{row.start_year}年",
            row.years,
            level_text,
        ]
        lines.append("| " + " | ".join(_escape_cell(c) for c in cells) + " |")
    return "\n".join(lines)


def build_project_periods() -> str:
    """`■開発経歴` の案件期間。開始年月の昇順。"""
    projects = Project.objects.order_by("start_year_month", "project_id")
    return "\n".join(
        f"**{_format_period(p.start_year_month, p.end_year_month)}｜{p.name}**"
        for p in projects
    )


def build_warnings(today: date) -> ExportWarnings:
    used = {row.skill.skill_id for row in build_skill_rows(today)}
    all_skills = list(Skill.objects.select_related("level"))
    levels = set(Level.objects.values_list("level", flat=True))
    return ExportWarnings(
        unused_skill_count=sum(1 for s in all_skills if s.skill_id not in used),
        invalid_level_skills=[s.name for s in all_skills if s.level_id not in levels],
    )


def build_export(today: date) -> dict:
    """職務経歴書用 Markdown と警告。表と案件期間は空行 1 行で区切る。"""
    warnings = build_warnings(today)
    return {
        "markdown": build_skill_table(today) + "\n\n" + build_project_periods() + "\n",
        "warnings": {
            "unused_skill_count": warnings.unused_skill_count,
            "invalid_level_skills": warnings.invalid_level_skills,
        },
    }
