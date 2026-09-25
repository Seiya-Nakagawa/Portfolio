#!/usr/bin/env python3
"""Markdown マスターデータを HTML 経由で A4 PDF に変換する（wkhtmltopdf 使用）。"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import markdown

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "sample" / "master.md"
DEFAULT_OUTPUT = SCRIPT_DIR / "output" / "職務経歴書.pdf"

# ポートフォリオアプリのエクスポートが出力する案件期間の行（例: **2025年04月〜現在｜案件名**）
PROJECT_PERIOD_LINE = re.compile(r'^\*\*(?P<period>[^\n｜]+)｜(?P<name>[^\n*]+)\*\*', re.MULTILINE)


def parse_export(export_text: str) -> tuple[str, dict[str, str]]:
    """ポートフォリオアプリのエクスポート（Markdown）を、スキル表と案件ごとの期間に分解する。"""
    parts = export_text.strip().split("\n\n", 1)
    if len(parts) != 2:
        raise ValueError("エクスポートの Markdown 形式が想定と異なります（スキル表・案件期間の区切りが見つかりません）")

    skill_table_md, project_block = parts
    project_periods = {}
    for line in project_block.strip().splitlines():
        matched = PROJECT_PERIOD_LINE.match(line.strip())
        if matched:
            project_periods[matched.group("name")] = matched.group("period")
    return skill_table_md, project_periods


def replace_skill_table(master_text: str, skill_table_md: str) -> str:
    """`■テクニカルスキル` 見出し直下の内容を、エクスポートの表に差し替える。"""
    pattern = re.compile(r"(?P<head>^## ■テクニカルスキル\n\n).*?(?=\n## |\Z)", re.DOTALL | re.MULTILINE)
    new_text, count = pattern.subn(lambda m: m.group("head") + skill_table_md + "\n", master_text)
    if count != 1:
        raise ValueError(f"■テクニカルスキル セクションの置換に失敗しました（マッチ数: {count}）")
    return new_text


def replace_project_periods(master_text: str, project_periods: dict) -> tuple[str, list]:
    """案件見出し行の期間部分のみを、名称の一致で差し替える。本文は変更しない。"""
    matched_names = set()

    def _substitute(matched: re.Match) -> str:
        name = matched.group("name")
        if name in project_periods:
            matched_names.add(name)
            return f"**{project_periods[name]}｜{name}**"
        return matched.group(0)

    new_text = PROJECT_PERIOD_LINE.sub(_substitute, master_text)
    unmatched = sorted(set(project_periods) - matched_names)
    return new_text, unmatched


def apply_export(master_text: str, export_text: str) -> tuple[str, list]:
    """職務経歴書マスタへ、エクスポート（スキル表・案件期間）を差し替えて反映する。"""
    skill_table_md, project_periods = parse_export(export_text)
    merged_text = replace_skill_table(master_text, skill_table_md)
    merged_text, unmatched = replace_project_periods(merged_text, project_periods)
    return merged_text, unmatched

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 18mm 16mm; }}
  body {{
    font-family: "Noto Sans CJK JP", "Noto Sans JP", sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #222;
  }}
  h1 {{ font-size: 16pt; border-bottom: 2px solid #333; padding-bottom: 4px; }}
  h2 {{ font-size: 13pt; margin-top: 20px; border-left: 4px solid #555; padding-left: 8px; }}
  h3 {{ font-size: 11.5pt; margin-top: 16px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
  th, td {{ border: 1px solid #999; padding: 4px 8px; font-size: 9.5pt; text-align: left; }}
  th {{ background-color: #eee; }}
  ul {{ margin: 4px 0; padding-left: 20px; }}
  blockquote {{ color: #666; border-left: 3px solid #ccc; padding-left: 8px; margin: 8px 0; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def build_html(markdown_path: Path, export_path: Optional[Path] = None) -> str:
    text = markdown_path.read_text(encoding="utf-8")

    if export_path is not None:
        export_text = export_path.read_text(encoding="utf-8")
        text, unmatched = apply_export(text, export_text)
        if unmatched:
            print(
                "警告: エクスポートに対応する見出しが見つからない案件があります: " + "、".join(unmatched),
                file=sys.stderr,
            )

    body = markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    return HTML_TEMPLATE.format(body=body)


def build_pdf(markdown_path: Path, pdf_path: Path, export_path: Optional[Path] = None) -> None:
    html = build_html(markdown_path, export_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", encoding="utf-8", delete=False
    ) as tmp_html:
        tmp_html.write(html)
        tmp_html_path = Path(tmp_html.name)

    try:
        subprocess.run(
            [
                "wkhtmltopdf",
                "--encoding",
                "utf-8",
                "--enable-local-file-access",
                "--page-size",
                "A4",
                str(tmp_html_path),
                str(pdf_path),
            ],
            check=True,
        )
    finally:
        tmp_html_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="ポートフォリオアプリの職務経歴書エクスポートで出力した Markdown を保存したファイル。"
        "指定すると ■テクニカルスキル 表と ■開発経歴 の案件期間を差し替える",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"入力ファイルが見つかりません: {args.input}", file=sys.stderr)
        return 1

    if args.export is not None and not args.export.exists():
        print(f"エクスポートファイルが見つかりません: {args.export}", file=sys.stderr)
        return 1

    build_pdf(args.input, args.output, args.export)
    print(f"PDF を生成しました: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
