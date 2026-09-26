"""公開 API・エクスポートが共有する、実績 DB からの表示データ生成ロジック。"""

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


# 資格の取得日（表示用の文言）から年月を読み取るための月名。
MONTH_NUMBERS = {
    name: number
    for number, name in enumerate(
        [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ],
        start=1,
    )
}
MONTH_NAME_PATTERN = re.compile(r"([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{4})")
YEAR_MONTH_PATTERN = re.compile(r"(\d{4})\s*(?:-|/|年)\s*(\d{1,2})")
YEAR_PATTERN = re.compile(r"\d{4}")


def acquired_on_sort_key(acquired_on: str) -> tuple[int, int]:
    """取得日の文言（例: Jul 2024、2024-07、2024年7月）を (年, 月) に変換する。読み取れない場合は最古扱い。"""
    match = MONTH_NAME_PATTERN.search(acquired_on)
    if match and match.group(1).lower() in MONTH_NUMBERS:
        return int(match.group(2)), MONTH_NUMBERS[match.group(1).lower()]
    match = YEAR_MONTH_PATTERN.search(acquired_on)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = YEAR_PATTERN.search(acquired_on)
    return (int(match.group()), 0) if match else (0, 0)


def ordered_certifications() -> list[Certification]:
    """取得日の新しい順（同じ取得日は登録の新しい順）で返す。"""
    return sorted(
        Certification.objects.all(),
        key=lambda c: (*acquired_on_sort_key(c.acquired_on), c.certification_id),
        reverse=True,
    )


def ordered_works() -> list[Work]:
    """登録の新しい順で返す。実績は日付を持たないため、採番の降順を新しい順とみなす。"""
    return list(Work.objects.order_by("-work_id"))


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
