"""職務経歴書の生成。本文の該当箇所を集計結果で差し替え、HTML・PDF に変換する。"""

import re
from dataclasses import dataclass, field
from datetime import date

import markdown

from portfolio.models import Project, Skill, Skillsheet
from portfolio.registry import ValidationFailed
from portfolio.services import build_skill_rows

# 継続中の案件の終了年月の表記。
ONGOING_LABEL = "現在"

SKILL_SECTION_TITLE = "■テクニカルスキル"

# `■テクニカルスキル` 見出しと、その直下（次の `##` 見出しまで）。
SKILL_SECTION_HEADING = re.compile(r"^## ■テクニカルスキル[ \t]*$", re.MULTILINE)
SKILL_SECTION = re.compile(
    r"(?P<head>^## ■テクニカルスキル[ \t]*\n\n?).*?(?=\n## |\Z)",
    re.DOTALL | re.MULTILINE,
)

# 案件見出し行（例: **2025年04月〜現在｜案件名**）。
PROJECT_PERIOD_LINE = re.compile(
    r"^\*\*(?P<period>[^\n｜]+)｜(?P<name>[^\n*]+)\*\*", re.MULTILINE
)

# PDF・プレビュー共通のスタイル（A4・余白 上下 18mm / 左右 16mm・10.5pt の日本語ゴシック体）。
STYLE = """
@page { size: A4; margin: 18mm 16mm; }
body {
  font-family: "Noto Sans CJK JP", "Noto Sans JP", sans-serif;
  font-size: 10.5pt;
  line-height: 1.6;
  color: #222;
}
h1 { font-size: 16pt; border-bottom: 2px solid #333; padding-bottom: 4px; }
h2 { font-size: 13pt; margin-top: 20px; border-left: 4px solid #555; padding-left: 8px; }
h3 { font-size: 11.5pt; margin-top: 16px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th, td { border: 1px solid #999; padding: 4px 8px; font-size: 9.5pt; text-align: left; }
th { background-color: #eee; }
ul { margin: 4px 0; padding-left: 20px; }
blockquote { color: #666; border-left: 3px solid #ccc; padding-left: 8px; margin: 8px 0; }
"""


@dataclass
class SkillsheetWarnings:
    """生成時の警告。"""

    unmatched_projects: list[str] = field(default_factory=list)
    unused_skill_count: int = 0

    def as_dict(self) -> dict:
        return {
            "unmatched_projects": self.unmatched_projects,
            "unused_skill_count": self.unused_skill_count,
        }


@dataclass
class RenderedSkillsheet:
    markdown: str
    html: str
    warnings: SkillsheetWarnings


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _format_period(start: str, end: str) -> str:
    def to_label(year_month: str) -> str:
        year, month = year_month.split("-")
        return f"{year}年{month}月"

    return f"{to_label(start)}〜{to_label(end) if end else ONGOING_LABEL}"


def build_skill_table(today: date) -> str:
    """`■テクニカルスキル` の表。"""
    lines = [
        "| 種類 | 項目 | 開始年 | 使用期間 |",
        "| --- | --- | --- | --- |",
    ]
    for row in build_skill_rows(today):
        skill = row.skill
        cells = [skill.category, skill.name, f"{row.start_year}年", row.years]
        lines.append("| " + " | ".join(_escape_cell(c) for c in cells) + " |")
    return "\n".join(lines)


def build_project_periods() -> dict[str, str]:
    """案件名ごとの期間表記。"""
    return {
        p.name: _format_period(p.start_year_month, p.end_year_month)
        for p in Project.objects.all()
    }


def validate_body(body: str) -> None:
    """本文に `■テクニカルスキル` 見出しがちょうど 1 つあることを確認する。"""
    count = len(SKILL_SECTION_HEADING.findall(body))
    if count != 1:
        raise ValidationFailed(
            [
                (
                    f"本文の「## {SKILL_SECTION_TITLE}」見出しが"
                    f"ちょうど 1 つである必要があります（現在 {count} 件）。"
                )
            ]
        )


def replace_skill_table(body: str, skill_table_md: str) -> str:
    """`■テクニカルスキル` 見出し直下を表に差し替える。見出しがちょうど 1 つでなければエラー。"""
    validate_body(body)
    return SKILL_SECTION.sub(
        lambda m: "## " + SKILL_SECTION_TITLE + "\n\n" + skill_table_md + "\n",
        body,
        count=1,
    )


def replace_project_periods(
    body: str, periods: dict[str, str]
) -> tuple[str, list[str]]:
    """案件見出し行の期間部分のみを案件名の一致で差し替える。一致しなかった案件名も返す。"""
    matched: set[str] = set()

    def substitute(match: re.Match) -> str:
        name = match.group("name")
        if name in periods:
            matched.add(name)
            return f"**{periods[name]}｜{name}**"
        return match.group(0)

    new_body = PROJECT_PERIOD_LINE.sub(substitute, body)
    return new_body, sorted(set(periods) - matched)


def build_warnings(today: date, unmatched_projects: list[str]) -> SkillsheetWarnings:
    used = {row.skill.skill_id for row in build_skill_rows(today)}
    unused = Skill.objects.exclude(skill_id__in=used).count()
    return SkillsheetWarnings(
        unmatched_projects=unmatched_projects, unused_skill_count=unused
    )


def get_skillsheet() -> Skillsheet | None:
    return Skillsheet.objects.first()


def to_html_document(merged_markdown: str) -> str:
    """差し替え後の Markdown を、PDF と同じスタイルの HTML 文書に変換する。"""
    body = markdown.markdown(
        merged_markdown, extensions=["tables", "fenced_code", "nl2br"]
    )
    return (
        '<!DOCTYPE html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
        f"<style>{STYLE}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def render_skillsheet(today: date) -> RenderedSkillsheet:
    """本文を読み込み、集計結果で差し替えた Markdown・HTML・警告を返す。"""
    sheet = get_skillsheet()
    if sheet is None or not sheet.body.strip():
        raise ValidationFailed(["職務経歴書の本文が登録されていません。"])
    merged = replace_skill_table(sheet.body, build_skill_table(today))
    merged, unmatched = replace_project_periods(merged, build_project_periods())
    return RenderedSkillsheet(
        markdown=merged,
        html=to_html_document(merged),
        warnings=build_warnings(today, unmatched),
    )


def build_url_fetcher():
    """`data:` 以外のリソース取得を拒否するフェッチャー。

    本文の Markdown に生の HTML（img・link 等）が含まれていても、PDF 生成時に
    ローカルファイルや内部ネットワークを読み込まないようにする。
    """
    from weasyprint import URLFetcher

    return URLFetcher(allowed_protocols={"data"})


def build_pdf(html: str) -> bytes:
    # WeasyPrint は依存ライブラリ（Pango 等）が重いため、PDF 生成時にのみ読み込む。
    from weasyprint import HTML

    return HTML(string=html, url_fetcher=build_url_fetcher()).write_pdf()
