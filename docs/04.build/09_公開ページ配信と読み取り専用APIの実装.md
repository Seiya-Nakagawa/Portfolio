# 09 構築手順書 - 公開ページ配信と読み取り専用APIの実装

## 目次

- [1. 概要](#1-概要)
- [2. 前提条件](#2-前提条件)
- [3. 手順](#3-手順)
  - [3.1. ページ本体と静的ファイルの移設](#31-ページ本体と静的ファイルの移設)
  - [3.2. テンプレートの変更](#32-テンプレートの変更)
  - [3.3. 表示データ集計処理と API の作成](#33-表示データ集計処理と-api-の作成)
  - [3.4. main.js の API 呼び出しへの変更](#34-mainjs-の-api-呼び出しへの変更)
  - [3.5. 資格・実績の投入コマンドの作成](#35-資格実績の投入コマンドの作成)
  - [3.6. テストと静的解析](#36-テストと静的解析)
  - [3.7. 実績 DB への初期データ投入](#37-実績-db-への初期データ投入)

## 1. 概要

Issue #48。[基本設計書](../02.design/DESIGN.md)に基づき、ポートフォリオサイトのページ本体と
読み取り専用 API をポートフォリオアプリ（`webapp/`）から配信する。GitHub Pages 向けの
静的ファイル配置と `data/*.json` の読み込みを廃止する。

## 2. 前提条件

- [08 構築手順書](08_ポートフォリオアプリ基盤の構築.md)が完了していること
- `webapp/` で `uv sync` 済みであること

## 3. 手順

### 3.1. ページ本体と静的ファイルの移設

リポジトリ直下の `index.html`・`css/`・`js/`・`img/` を `webapp/` 配下へ移す。

```bash
git mv index.html webapp/templates/index.html
git mv css webapp/static/css
git mv js/i18n.js webapp/static/js/i18n.js
git mv js/main.js webapp/static/js/main.js
git mv img webapp/static/img
```

- ページ本体をテンプレートへ、css・js・画像を静的ファイルの配置先へ移す。

`data/certifications.json`・`data/works.json` は実績 DB への投入元として
`webapp/portfolio/seed/` へ移す。スキルは実績 DB から集計するため `data/skills.json` は削除する。

```bash
mkdir -p webapp/portfolio/seed
git mv data/certifications.json webapp/portfolio/seed/certifications.json
git mv data/works.json webapp/portfolio/seed/works.json
git rm data/skills.json
```

- 資格・実績の JSON を投入元として `seed/` へ移し、スキルの JSON を削除する。

### 3.2. テンプレートの変更

`webapp/templates/index.html` を次のとおり変更する。

1. 先頭に `{% load static %}` を追加し、先頭の BOM を除去する。
2. css・js の参照を `{% static '...' %}` に置き換える。
3. `<body>` に、静的ファイルの配信パス（`data-static-base`）と API の URL
   （`data-api-skills`・`data-api-certifications`・`data-api-works`、`{% url %}` で解決）を
   `data-*` 属性として持たせる。

配信パスのプレフィックス（`/portfolio`）が変わっても、テンプレートが解決した値を
`main.js` が使うため、相対パスの解決に依存しない。

### 3.3. 表示データ集計処理と API の作成

1. `webapp/portfolio/services.py` に、実績 DB からスキル・資格・実績の表示データを生成する処理を作成する。
   スキルは経験年数の算出ロジック（`experience.py`）で集計し、使用実績のない項目を除く。
   並び順は、カテゴリ間を各カテゴリの `sort_order` 最小値の昇順、カテゴリ内を `sort_order` 順とする。
2. `webapp/portfolio/views.py` に、ページ本体（`index`）と API 3 本
   （`api_skills`・`api_certifications`・`api_works`）を作成する。いずれも認証不要・GET のみとし、
   基準日は `timezone.localdate()`（`Asia/Tokyo`）とする。
3. `webapp/config/urls.py` に `""`・`api/skills`・`api/certifications`・`api/works` を定義する。
   Ingress がパスプレフィックスを除去して転送するため、URL にはプレフィックスを含めない。

### 3.4. main.js の API 呼び出しへの変更

`webapp/static/js/main.js` を次のとおり変更する。

1. `data/*.json` の読み込みを、`<body>` の `data-api-*` 属性の URL への `fetch` に変更する。
   取得に失敗した場合は該当セクションのみにエラー文言を表示する（既存の `loadAndRender` を継続使用）。
2. 実績カードのサムネイルは、相対パスの場合に `data-static-base` を前置して解決する。

### 3.5. 資格・実績の投入コマンドの作成

`webapp/portfolio/management/commands/import_portfolio_data.py` を作成する。

- `webapp/portfolio/seed/` の `certifications.json`・`works.json` を実績 DB へ投入する。
  JSON の並び順を `sort_order`（1 から連番）とする。
- テーブルにデータが既にある場合は、そのテーブルへの投入をスキップする（再実行で二重登録しない）。
- `--seed-dir` で投入元のディレクトリを変更できる。

### 3.6. テストと静的解析

`webapp/portfolio/tests/test_public_api.py` に、API のレスポンス形式・並び順・案件情報を含まないこと・
認証不要（GET のみ許可）・ページ本体の表示・投入コマンドのテストを作成し、実行する。

```bash
SECRET_KEY=test uv run python manage.py test --settings=config.settings.test
uv run ruff check .
uv run ruff format --check .
```

- ユニットテストを SQLite（メモリ）で実行する。
- lint とフォーマットの指摘がないことを確認する。

### 3.7. 実績 DB への初期データ投入

マイグレーション適用後、資格・実績を投入する。

```bash
uv run python manage.py migrate
uv run python manage.py import_portfolio_data
```

- 実績 DB のテーブルを作成する。
- 資格・実績の JSON を実績 DB へ投入する。

スキルは案件実績の登録（登録画面）から蓄積される。
