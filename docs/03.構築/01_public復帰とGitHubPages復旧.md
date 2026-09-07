# 01 構築手順書 - public 復帰と GitHub Pages 復旧

## 目次

- [1. 概要](#1-概要)
- [2. 前提条件](#2-前提条件)
- [3. 手順](#3-手順)
  - [3.1. リポジトリの可視性を public に変更する](#31-リポジトリの可視性を-public-に変更する)
  - [3.2. GitHub Pages を有効化する](#32-github-pages-を有効化する)
  - [3.3. Pages のビルド完了を確認する](#33-pages-のビルド完了を確認する)
  - [3.4. 公開サイトの動作確認](#34-公開サイトの動作確認)
  - [3.5. ドキュメントの公開 URL を更新する](#35-ドキュメントの公開-url-を更新する)

## 1. 概要

- 対応 Issue: [#6](https://github.com/Seiya-Nakagawa/Portfolio/issues/6)
- Portfolio リポジトリ（`Seiya-Nakagawa/Portfolio`）を private から public へ変更し、
  停止していた GitHub Pages によるサイト公開を復旧する

## 2. 前提条件

- リポジトリ履歴に機密情報が含まれないことは [#5](https://github.com/Seiya-Nakagawa/Portfolio/issues/5) で確認済みであること
- GitHub CLI（`gh`）でリポジトリの管理者権限を持つアカウントとして認証済みであること

## 3. 手順

### 3.1. リポジトリの可視性を public に変更する

```bash
gh repo edit Seiya-Nakagawa/Portfolio --visibility public --accept-visibility-change-consequences
```

### 3.2. GitHub Pages を有効化する

```bash
gh api repos/Seiya-Nakagawa/Portfolio/pages -X POST -f 'source[branch]=main' -f 'source[path]=/'
```

- 公開元を `main` ブランチのルートディレクトリとして GitHub Pages を有効化する

### 3.3. Pages のビルド完了を確認する

```bash
gh api repos/Seiya-Nakagawa/Portfolio/pages -q .status
```

- ステータスが `built` になるまで一定間隔でポーリングする

### 3.4. 公開サイトの動作確認

```bash
curl -s -o /dev/null -w "%{http_code}" https://seiya-nakagawa.github.io/Portfolio/
```

- トップページが HTTP 200 で応答することを確認する
- `css/style.css`、`js/i18n.js`、`js/data.js`、`js/main.js` など主要な静的アセットが
  それぞれ HTTP 200 で読み込めることを確認する
- ブラウザで公開 URL にアクセスし、About / Skills / Certifications / Works / Contact の
  各セクションが正しく描画されることを確認する
- 日本語 / 英語の言語切替が正常に動作することを確認する

### 3.5. ドキュメントの公開 URL を更新する

- [`docs/REQUIREMENTS.md`](../REQUIREMENTS.md) に記載の対象サイト URL を、
  旧アカウント名の URL（`seiyanakagawa2219.github.io`）から現行の URL
  （`https://seiya-nakagawa.github.io/Portfolio/`）へ修正する
