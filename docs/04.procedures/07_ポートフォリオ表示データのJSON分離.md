# 07 構築手順書 - ポートフォリオ表示データのJSON分離

## 目次

- [1. 概要](#1-概要)
- [2. 前提条件](#2-前提条件)
- [3. 手順](#3-手順)
  - [3.1. 表示データを JSON ファイルへ切り出す](#31-表示データを-json-ファイルへ切り出す)
  - [3.2. JavaScript を JSON 読み込み方式へ変更する](#32-javascript-を-json-読み込み方式へ変更する)
  - [3.3. 動作確認](#33-動作確認)

## 1. 概要

Issue #31。ポートフォリオサイトの表示データ（スキル・資格・実績）を `js/data.js` から
`data/*.json` へ切り出し、`fetch` で読み込んで描画する構成に変更する。

## 2. 前提条件

- [基本設計書 6.2](../02.design/DESIGN.md#62-ポートフォリオ用スキルデータjson)・
  [6.3](../02.design/DESIGN.md#63-ポートフォリオ用資格実績データjson)で JSON のスキーマ・
  出力先が確定していること

## 3. 手順

### 3.1. 表示データを JSON ファイルへ切り出す

1. `data/` ディレクトリを作成する。
2. `js/data.js` の `skillsData` を、[基本設計書 6.2](../02.design/DESIGN.md#62-ポートフォリオ用スキルデータjson)
   のスキーマに従い `data/skills.json` へ変換する。
3. `js/data.js` の `certificationsData`・`worksData` を、
   [基本設計書 6.3](../02.design/DESIGN.md#63-ポートフォリオ用資格実績データjson)のスキーマに従い
   `data/certifications.json`・`data/works.json` へ変換する。
4. `js/data.js` を削除し、`index.html` の `<script src="js/data.js">` を除去する。

### 3.2. JavaScript を JSON 読み込み方式へ変更する

1. `js/main.js` に、指定した URL を `fetch` で取得し、成功時はコールバックへ渡し、失敗時は
   対象コンテナへ読み込み失敗を示す文言を表示する共通関数（`loadAndRender`）を実装する。
2. 初期化処理を、`skillsData` などのグローバル変数を直接参照する方式から、`loadAndRender` で
   `data/skills.json`・`data/certifications.json`・`data/works.json` をそれぞれ取得して
   描画する方式へ変更する。
3. `renderSkills` / `renderCertifications` / `renderWorks` の各描画関数を、グローバル変数では
   なく引数でデータを受け取る形式に変更する。
4. `css/style.css` に、読み込み失敗時の文言用のスタイル（`.data-load-error`）を追加する。

### 3.3. 動作確認

1. リポジトリルートで簡易 HTTP サーバーを起動する。

   ```bash
   python3 -m http.server 8000
   ```

2. ブラウザで `http://localhost:8000/index.html` を開き、Skills・Certifications・Works の
   各セクションが `data/*.json` の内容で描画されることを確認する。
3. ブラウザの開発者ツールでコンソールエラーが発生していないことを確認する。
4. いずれかの JSON ファイルを一時的に取得できない状態にし、該当セクションのみ読み込み失敗の
   文言が表示され、他のセクションの描画が継続することを確認する。
