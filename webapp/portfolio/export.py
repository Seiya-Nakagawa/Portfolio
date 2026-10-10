"""職務経歴書の生成。実績 DB の内容から Markdown を組み立て、HTML・PDF に変換する。"""

from dataclasses import dataclass, field
from datetime import date

import markdown

from portfolio.models import (
    SKILLSHEET_TEXT_KEYS,
    Certification,
    Company,
    Project,
    SkillsheetText,
)
from portfolio.services import build_skill_rows, format_year_month

# 継続中の案件の終了年月の表記。
ONGOING_LABEL = "現在"

# 入れ子の箇条書きの字下げ。Markdown 変換ライブラリが入れ子と解釈する幅に合わせる。
LIST_INDENT = " " * 4

# 会社概要の項目。出力順に並べる。
COMPANY_PROFILE_FIELDS = [
    ("capital", "資本金"),
    ("employees", "従業員数"),
    ("offices", "拠点数"),
    ("annual_sales", "年商"),
    ("founded", "設立"),
]

# 会社の区分ごとの見出し。出力順に並べる。
COMPANY_SECTIONS = [
    (Company.KIND_MAIN, "■開発経歴"),
    (Company.KIND_SIDE, "■副業"),
]

END_MARK = "以上"

# PDF・プレビュー共通のスタイル（A4・余白 上下 18mm / 左右 16mm・10.5pt の日本語ゴシック体）。
STYLE = """
@page { size: A4; margin: 18mm 16mm; }
body {
  font-family: "IPAexGothic", "Noto Sans CJK JP", sans-serif;
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

    # 会社が未設定のため職務経歴書に出力されない案件名。
    unassigned_projects: list[str] = field(default_factory=list)
    # 未入力の文章項目名。
    missing_texts: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "unassigned_projects": self.unassigned_projects,
            "missing_texts": self.missing_texts,
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
    """`■テクニカルスキル` の表。使用実績のあるスキル項目がなければ空文字列を返す。"""
    rows = build_skill_rows(today)
    if not rows:
        return ""
    lines = [
        "| 種類 | 項目 | 開始年 | 使用期間 |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        skill = row.skill
        cells = [skill.category, skill.name, f"{row.start_year}年", row.years]
        lines.append("| " + " | ".join(_escape_cell(c) for c in cells) + " |")
    return "\n".join(lines)


def _company_label(company: Company) -> str:
    """会社名と部署名を半角空白で連結する。"""
    return " ".join(part for part in (company.name, company.department) if part)


def _build_company_summary(companies: list[Company]) -> str:
    """`■職務経歴 概略` の表。"""
    lines = ["| 期間 | 会社名 |", "| --- | --- |"]
    for company in companies:
        period = _format_period(company.start_year_month, company.end_year_month)
        lines.append(
            f"| {_escape_cell(period)} | {_escape_cell(_company_label(company))} |"
        )
    return "\n".join(lines)


def _bullet(label: str, value: str) -> list[str]:
    """複数行の値は、2 行目以降を箇条書きの項目内の改行として字下げする。"""
    first, *rest = value.splitlines()
    return [f"- {label}: {first}", *(f"{LIST_INDENT}{line}" for line in rest)]


def _build_project(project: Project) -> str:
    heading = (
        f"**{_format_period(project.start_year_month, project.end_year_month)}"
        f"｜{project.name}**"
    )
    if project.team_size:
        heading += f"（{project.team_size}）"

    lines = [heading, ""]
    if project.overview:
        lines += _bullet("案件概要", project.overview)
    tasks = [line.strip() for line in project.tasks.splitlines() if line.strip()]
    if len(tasks) == 1:
        lines.append(f"- 業務内容: {tasks[0]}")
    elif tasks:
        lines.append("- 業務内容:")
        lines += [f"{LIST_INDENT}- {task}" for task in tasks]
    if project.phases:
        lines.append(f"- 担当工程: {project.phases}")
    if project.environment:
        lines.append(f"- 環境・言語: {project.environment}")
    return "\n".join(lines).rstrip()


def _build_company(company: Company, projects: list[Project]) -> str:
    heading = f"### {_company_label(company)}"
    if company.employment_type:
        heading += f"（{company.employment_type}）"
    heading += f" {_format_period(company.start_year_month, company.end_year_month)}"

    blocks = [heading]
    profile = [
        f"【{label}】{getattr(company, key)}"
        for key, label in COMPANY_PROFILE_FIELDS
        if getattr(company, key)
    ]
    if profile:
        blocks.append("\u3000".join(profile))
    blocks += [_build_project(project) for project in projects]
    return "\n\n".join(blocks)


def _build_certifications() -> str:
    certifications = Certification.objects.order_by("acquired_on", "certification_id")
    return "\n".join(
        f"- {c.name}（{format_year_month(c.acquired_on)}）" for c in certifications
    )


def _section(title: str, body: str) -> str | None:
    """本文が空の項目は見出しごと出力しない。"""
    body = body.strip()
    return f"## {title}\n\n{body}" if body else None


def _load_texts() -> dict[str, str]:
    return {t.text_key: t.body.strip() for t in SkillsheetText.objects.all()}


def build_markdown(today: date) -> tuple[str, SkillsheetWarnings]:
    """実績 DB の内容から職務経歴書の Markdown と警告を組み立てる。"""
    texts = _load_texts()
    companies = list(Company.objects.all())
    projects = list(Project.objects.order_by("-start_year_month", "name"))

    projects_by_company: dict[int, list[Project]] = {}
    unassigned: list[str] = []
    for project in projects:
        if project.company_id is None:
            unassigned.append(project.name)
        else:
            projects_by_company.setdefault(project.company_id, []).append(project)
    warnings = SkillsheetWarnings(
        unassigned_projects=unassigned,
        missing_texts=[
            label for key, label in SKILLSHEET_TEXT_KEYS.items() if not texts.get(key)
        ],
    )

    title = [
        "# 職務経歴書",
        f"最終更新日: {today.year}年{today.month}月{today.day}日",
    ]
    if texts.get("full_name"):
        title.append(f"氏名: {texts['full_name']}")
    sections: list[str | None] = ["\n".join(title)]

    sections.append(_section("■職務概要", texts.get("summary", "")))
    main_companies = [c for c in companies if c.kind == Company.KIND_MAIN]
    if main_companies:
        sections.append(
            _section("■職務経歴 概略", _build_company_summary(main_companies))
        )
    for kind, heading in COMPANY_SECTIONS:
        body = "\n\n".join(
            _build_company(company, projects_by_company.get(company.company_id, []))
            for company in companies
            if company.kind == kind
        )
        sections.append(_section(heading, body))
    sections.append(_section("■テクニカルスキル", build_skill_table(today)))
    sections.append(_section("■活かせる経験・得意分野", texts.get("strengths", "")))
    sections.append(_section("■保有資格", _build_certifications()))
    sections.append(_section("■自己PR", texts.get("self_pr", "")))
    sections.append(END_MARK)

    body = "\n\n".join(section for section in sections if section)
    return body + "\n", warnings


def to_html_document(merged_markdown: str) -> str:
    """Markdown を、PDF と同じスタイルの HTML 文書に変換する。"""
    body = markdown.markdown(
        merged_markdown, extensions=["tables", "fenced_code", "nl2br"]
    )
    return (
        '<!DOCTYPE html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
        f"<style>{STYLE}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def render_skillsheet(today: date) -> RenderedSkillsheet:
    """実績 DB の内容から、Markdown・HTML・警告を返す。"""
    merged, warnings = build_markdown(today)
    return RenderedSkillsheet(
        markdown=merged, html=to_html_document(merged), warnings=warnings
    )


def build_url_fetcher():
    """`data:` 以外のリソース取得を拒否するフェッチャー。

    入力した文章に生の HTML（img・link 等）が含まれていても、PDF 生成時に
    ローカルファイルや内部ネットワークを読み込まないようにする。
    """
    from weasyprint import URLFetcher

    return URLFetcher(allowed_protocols={"data"})


def build_pdf(html: str) -> bytes:
    # WeasyPrint は依存ライブラリ（Pango 等）が重いため、PDF 生成時にのみ読み込む。
    from weasyprint import HTML

    return HTML(string=html, url_fetcher=build_url_fetcher()).write_pdf()
