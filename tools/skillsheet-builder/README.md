# Skillsheet Builder

Markdown で書いた職務経歴書（スキルシート）のマスターデータを、A4 の PDF に変換するローカル完結型のビルドツール。

- `master.md` に記載した内容を HTML 経由で PDF 化する
- CI（GitHub Actions 等）は使用せず、ローカル実行のみを想定する
- 本ディレクトリに含まれる `sample/master.md` は架空の氏名・企業名・案件内容によるサンプルデータであり、実データは一切含まない

## 構成

```text
tools/skillsheet-builder/
├── build_pdf.py       # Markdown -> HTML -> PDF 変換スクリプト
├── requirements.txt    # Python 依存パッケージ
├── sample/
│   ├── master.md        # サンプルデータ（架空の職務経歴書）
│   └── export.md        # ポートフォリオアプリのエクスポートのサンプル（--export の動作確認用）
└── README.md
```

## セットアップ

### 前提環境

- Python 3
- [wkhtmltopdf](https://wkhtmltopdf.org/)（PDF レンダリングに使用）
- 日本語フォント（Noto Sans CJK JP 等）

```bash
sudo apt-get install wkhtmltopdf fonts-noto-cjk
```

### Python 依存パッケージ

```bash
cd tools/skillsheet-builder
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 実行方法

引数を省略すると、`sample/master.md` を読み込み `output/職務経歴書.pdf` を生成する。

```bash
python build_pdf.py
```

自分のマスターデータで PDF を生成する場合は、`--input` / `--output` でファイルを指定する。

```bash
python build_pdf.py --input /path/to/your/master.md --output /path/to/output.pdf
```

## マスターデータの書式

`sample/master.md` の見出し構成（`■職務概要` / `■職務経歴 概略` / `■開発経歴` / `■テクニカルスキル` 等）をそのまま踏襲すれば、独自のマスターデータとして利用できる。Markdown の表・箇条書き・見出しがそのまま PDF のレイアウトに反映される。

## ポートフォリオアプリのエクスポートとの統合

`--export` に、ポートフォリオアプリの職務経歴書エクスポート画面で出力した Markdown（ダウンロードまたはコピーして保存したファイル）を指定すると、PDF 生成時にマスターデータの以下の箇所をエクスポートの内容へ差し替える。マスターデータ自体は書き換えない。

- `■テクニカルスキル` の表全体
- `■開発経歴`・`■副業` などの案件見出し行（`**期間｜案件名**`）の期間部分のみ。案件名の一致で対応付けるため、体制・案件概要・業務内容等の本文は変更しない

```bash
python build_pdf.py --export /path/to/export.md
```

エクスポートの案件名に対応する見出しがマスターデータに見つからない案件がある場合、標準エラー出力に警告を表示する（PDF 生成自体は継続する）。`sample/export.md` を使うと、この警告を含めた動作を確認できる。

```bash
python build_pdf.py --export sample/export.md
```

## 実データの取り扱いについて

本ツールは仕組み（スクリプト・テンプレート）のみを公開する目的で作成しており、実際の職務経歴書データはこのリポジトリには含めない。実データを扱う場合は、リモートを持たないローカル環境（例: 別ディレクトリのローカル git リポジトリ）で `master.md` を管理し、本ディレクトリの `build_pdf.py` を `--input` オプションで参照する運用を推奨する。
