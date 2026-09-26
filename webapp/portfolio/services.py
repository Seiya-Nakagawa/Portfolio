"""公開 API・エクスポートが共有する、実績 DB からの表示データ生成ロジック。"""

from dataclasses import dataclass
from datetime import date

from portfolio.experience import (
    ProjectPeriod,
    SkillUsage,
    aggregate_skill_experience,
    calculate_stars,
    format_experience,
)
from portfolio.models import Certification, Project, ProjectSkill, Skill, Work


@dataclass(frozen=True)
class SkillRow:
    """実績のあるスキル項目 1 件分の集計結果。"""

    skill: Skill
    months: int
    start_year: int
    years: str


def ordered_skills() -> list[Skill]:
    """カテゴリ内は sort_order 順、カテゴリ間は各カテゴリの sort_order 最小値の昇順で返す。"""
    skills = list(Skill.objects.select_related("level").order_by("sort_order"))
    category_order: dict[str, int] = {}
    for skill in skills:
        category_order.setdefault(skill.category, skill.sort_order)
    return sorted(
        skills,
        key=lambda s: (
            category_order[s.category],
            s.category,
            s.sort_order,
            s.skill_id,
        ),
    )


def build_skill_rows(today: date) -> list[SkillRow]:
    """使用実績のあるスキル項目を表示順に集計して返す。"""
    projects = [
        ProjectPeriod(p.project_id, p.start_year_month, p.end_year_month)
        for p in Project.objects.all()
    ]
    usages = [
        SkillUsage(project_id, skill_id)
        for project_id, skill_id in ProjectSkill.objects.values_list(
            "project_id", "skill_id"
        )
    ]
    experiences = aggregate_skill_experience(projects, usages, today)

    rows = []
    for skill in ordered_skills():
        experience = experiences.get(skill.skill_id)
        if experience is None:
            continue
        rows.append(
            SkillRow(
                skill=skill,
                months=experience.months,
                start_year=experience.start_year,
                years=format_experience(experience.months),
            )
        )
    return rows


def build_skills_payload(today: date) -> dict:
    """スキル API のレスポンス。案件情報は含めない。"""
    return {
        "generated_at": today.isoformat(),
        "skills": [
            {
                "category": row.skill.category,
                "name": row.skill.name,
                "months": row.months,
                "years": row.years,
                "stars": calculate_stars(row.months),
            }
            for row in build_skill_rows(today)
        ],
    }


def build_certifications_payload() -> list[dict]:
    return [
        {"name": c.name, "date": c.acquired_on, "org": c.org}
        for c in Certification.objects.order_by("sort_order", "certification_id")
    ]


def build_works_payload() -> list[dict]:
    """実績 API のレスポンス。未設定の任意項目（サムネイル・リンク）はキーごと省略する。"""
    payload = []
    for work in Work.objects.order_by("sort_order", "work_id"):
        item = {
            "title": work.title,
            "desc_ja": work.desc_ja,
            "desc_en": work.desc_en,
            "tags": work.tags,
        }
        for key in ("thumbnail", "github_url", "live_url"):
            value = getattr(work, key)
            if value:
                item[key] = value
        payload.append(item)
    return payload
