#!/usr/bin/env python3
"""Markdown マスターデータを HTML 経由で A4 PDF に変換する（wkhtmltopdf 使用）。"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "sample" / "master.md"
DEFAULT_OUTPUT = SCRIPT_DIR / "output" / "職務経歴書.pdf"

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


def build_html(markdown_path: Path) -> str:
    text = markdown_path.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    return HTML_TEMPLATE.format(body=body)


def build_pdf(markdown_path: Path, pdf_path: Path) -> None:
    html = build_html(markdown_path)
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
    args = parser.parse_args()

    if not args.input.exists():
        print(f"入力ファイルが見つかりません: {args.input}", file=sys.stderr)
        return 1

    build_pdf(args.input, args.output)
    print(f"PDF を生成しました: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
