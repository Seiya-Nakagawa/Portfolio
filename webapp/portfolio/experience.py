"""経験年数の算出ロジック。

スキル項目ごとに、そのスキルを使用した全案件の期間を年月に展開して和集合を取り、
異なり月数（ユニーク月数）を N年Mヶ月 の表記に換算する。DB には依存しない。
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

MONTHS_PER_YEAR = 12


@dataclass(frozen=True)
class ProjectPeriod:
    """案件の期間。end_year_month が空文字列の場合は継続中を表す。"""

    project_id: str
    start_year_month: str
    end_year_month: str = ""


@dataclass(frozen=True)
class SkillUsage:
    """案件でスキル項目を使用した実績 1 件。"""

    project_id: str
    skill_id: str


@dataclass(frozen=True)
class SkillExperience:
    """スキル項目ごとの集計結果。"""

    skill_id: str
    months: int
    start_year: int


def to_month_index(year_month: str) -> int:
    """YYYY-MM を、年月の大小比較・連番展開ができる通し月番号に変換する。"""
    year, month = year_month.split("-")
    return int(year) * MONTHS_PER_YEAR + int(month) - 1


def expand_months(start_year_month: str, end_year_month: str, today: date) -> set[int]:
    """開始年月から終了年月（空の場合は基準日）までの通し月番号の集合を返す。

    開始が終了より後の場合は空集合を返す。
    """
    start = to_month_index(start_year_month)
    end = (
        to_month_index(end_year_month)
        if end_year_month
        else today.year * MONTHS_PER_YEAR + today.month - 1
    )
    return set(range(start, end + 1))


# 星の段階の下限ユニーク月数。(下限月数, 星) を星の大きい順に並べる。
STAR_THRESHOLDS = ((60, 5), (36, 4), (12, 3), (6, 2), (0, 1))


def calculate_stars(months: int) -> int:
    """ユニーク月数から経験年数に基づく星の段階（1〜5）を返す。"""
    for lower_bound, stars in STAR_THRESHOLDS:
        if months >= lower_bound:
            return stars
    return 1


def format_experience(months: int) -> str | None:
    """ユニーク月数を表記に変換する。0 ヶ月の場合は出力対象外として None を返す。"""
    if months <= 0:
        return None

    years, rest = divmod(months, MONTHS_PER_YEAR)
    if years == 0:
        return f"{rest}ヶ月"
    if rest == 0:
        return f"{years}年"
    return f"{years}年{rest}ヶ月"


def aggregate_skill_experience(
    projects: Iterable[ProjectPeriod],
    usages: Iterable[SkillUsage],
    today: date,
) -> dict[str, SkillExperience]:
    """スキル項目ごとのユニーク月数と開始年を集計する。

    使用実績が 1 件もないスキル項目、および展開した月数が 0 のスキル項目は
    結果に含めない。
    """
    period_by_project = {p.project_id: p for p in projects}

    months_by_skill: dict[str, set[int]] = {}
    start_year_by_skill: dict[str, int] = {}
    for usage in usages:
        project = period_by_project.get(usage.project_id)
        if project is None:
            continue

        months_by_skill.setdefault(usage.skill_id, set()).update(
            expand_months(project.start_year_month, project.end_year_month, today)
        )

        # 開始年は、そのスキル項目が紐づく案件の開始年月の最小値の年とする。
        start_year = int(project.start_year_month[:4])
        start_year_by_skill[usage.skill_id] = min(
            start_year, start_year_by_skill.get(usage.skill_id, start_year)
        )

    return {
        skill_id: SkillExperience(
            skill_id=skill_id,
            months=len(months),
            start_year=start_year_by_skill[skill_id],
        )
        for skill_id, months in months_by_skill.items()
        if months
    }
