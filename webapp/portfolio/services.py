"""公開 API・エクスポートが共有する、実績 DB からの表示データ生成ロジック。"""

from dataclasses import dataclass
from datetime import date

from django.db.models import F

from portfolio.experience import (
    ProjectPeriod,
    SkillUsage,
    aggregate_skill_experience,
    calculate_stars,
    format_experience,
)
from portfolio.models import (
    Certification,
    Project,
    ProjectSkill,
    SiteInfo,
    Skill,
    Work,
)


@dataclass(frozen=True)
class SkillRow:
    """実績のあるスキル項目 1 件分の集計結果。"""

    skill: Skill
    months: int
    start_year: int
    years: str


def ordered_skills() -> list[Skill]:
    """種類 → サブカテゴリ → 表示順の順で返す。

    種類間は各種類の sort_order 最小値の昇順、種類内のサブカテゴリ間は各サブカテゴリの
    sort_order 最小値の昇順とし、サブカテゴリ未設定の項目は種類内の末尾に置く。
    """
    skills = list(Skill.objects.order_by("sort_order"))
    category_order: dict[str, int] = {}
    subcategory_order: dict[tuple[str, str], int] = {}
    for skill in skills:
        category_order.setdefault(skill.category, skill.sort_order)
        subcategory_order.setdefault(
            (skill.category, skill.subcategory), skill.sort_order
        )
    return sorted(
        skills,
        key=lambda s: (
            category_order[s.category],
            s.category,
            s.subcategory == "",
            subcategory_order[(s.category, s.subcategory)],
            s.subcategory,
            s.sort_order,
            s.skill_id,
        ),
    )


def format_year_month(value: date) -> str:
    """年月の表示形式（YYYY年MM月）に整形する。"""
    return f"{value.year}年{value.month:02d}月"


def ordered_certifications() -> list[Certification]:
    """取得年月の新しい順（同じ取得年月は登録の新しい順）で返す。"""
    return list(Certification.objects.order_by("-acquired_on", "-certification_id"))


def ordered_works() -> list[Work]:
    """実績年月の新しい順（未設定は末尾。同じ年月は登録の新しい順）で返す。"""
    return list(
        Work.objects.order_by(F("achieved_on").desc(nulls_last=True), "-work_id")
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
        {"name": c.name, "date": format_year_month(c.acquired_on), "org": c.org}
        for c in ordered_certifications()
    ]


def build_works_payload() -> list[dict]:
    """実績 API のレスポンス。未設定の任意項目（サムネイル・リンク）はキーごと省略する。"""
    payload = []
    for work in ordered_works():
        item = {
            "title": work.title,
            "desc_ja": work.desc_ja,
            "desc_en": work.desc_en,
            "tags": work.tags,
        }
        if work.achieved_on:
            item["date"] = format_year_month(work.achieved_on)
        for key in ("thumbnail", "github_url", "live_url"):
            value = getattr(work, key)
            if value:
                item[key] = value
        payload.append(item)
    return payload


def calculate_age(birth_date: date, today: date) -> int:
    """満年齢を返す。"""
    before_birthday = (today.month, today.day) < (birth_date.month, birth_date.day)
    return today.year - birth_date.year - before_birthday


def format_copyright(start_year: int, today: date) -> str:
    """著作権の年表記を返す。開始年と現在の年が同じ場合は 1 つの年のみとする。"""
    if start_year >= today.year:
        return str(start_year)
    return f"{start_year}-{today.year}"


def build_site_payload(today: date) -> dict | None:
    """サイト情報 API のレスポンス。生年月日は含めず、年齢のみ返す。未登録の場合は None。"""
    info = SiteInfo.objects.first()
    if info is None:
        return None
    return {
        "name": info.name,
        "typing_titles": info.typing_titles,
        "catchphrase": info.catchphrase,
        "intro": info.intro,
        "age": calculate_age(info.birth_date, today),
        "job": info.job,
        "education": info.education,
        "location": info.location,
        "hobby": info.hobby,
        "github_url": info.github_url,
        "contact_message": info.contact_message,
        "contact_form_url": info.contact_form_url,
        "copyright": format_copyright(info.copyright_start_year, today),
    }
