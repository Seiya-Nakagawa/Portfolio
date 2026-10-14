# 21 構築手順書 - OAuth クライアントの作成と OCI Vault への登録

## 目次

- [1. 概要](#1-概要)
- [2. 前提条件](#2-前提条件)
- [3. 手順](#3-手順)
  - [3.1. Google の OAuth クライアントの作成](#31-google-の-oauth-クライアントの作成)
  - [3.2. GitHub の OAuth App の作成](#32-github-の-oauth-app-の作成)
  - [3.3. 開発用の資格情報の設定](#33-開発用の資格情報の設定)
  - [3.4. 本番の資格情報の OCI Vault への登録](#34-本番の資格情報の-oci-vault-への登録)
  - [3.5. 同期の確認](#35-同期の確認)

## 1. 概要

Issue #167 の対応。Google・GitHub の OAuth クライアント（開発用・本番用）を作成し、本番の ID・シークレットを
OCI Vault に登録してアプリから参照できるようにする。設計は
[基本設計書 6.4](../02.design/DESIGN.md#64-ポートフォリオアプリ) を参照する。

| 項目 | 値 |
| ---- | -- |
| サービスホスト | `skillsheet.technohonesty.com` |
| Google の本番の戻り先 URL | `https://skillsheet.technohonesty.com/accounts/google/login/callback/` |
| GitHub の本番の戻り先 URL | `https://skillsheet.technohonesty.com/accounts/github/login/callback/` |
| 開発用の戻り先 URL | `http://localhost:8000/accounts/{google,github}/login/callback/` |

OCI Vault のシークレット名と、アプリが受け取る環境変数の対応は次のとおり（`k8s/vault-sync.yaml` が同期する）。

| OCI Vault のシークレット名 | 環境変数 |
| -------------------------- | -------- |
| `portfolio-google-client-id` | `GOOGLE_CLIENT_ID` |
| `portfolio-google-client-secret` | `GOOGLE_CLIENT_SECRET` |
| `portfolio-github-client-id` | `GITHUB_CLIENT_ID` |
| `portfolio-github-client-secret` | `GITHUB_CLIENT_SECRET` |

## 2. 前提条件

- Google アカウントで Google Cloud プロジェクトを利用できること
- GitHub アカウントで OAuth App を作成できること
- OCI Vault にシークレットを登録できる権限があること
- サービスホスト名が確定していること

## 3. 手順

### 3.1. Google の OAuth クライアントの作成

本番用と開発用の 2 つを作成する。

1. Google Cloud コンソールで、プロジェクトを作成（または選択）する
2. 「Google Auth Platform」の「ブランディング」で、同意画面を設定する
   - アプリ名はサービス名、ユーザーサポートメールと連絡先は運営者のものにする
   - アプリのドメインに、サービスホストのトップページ・プライバシーポリシー・利用規約の URL を設定する
3. 「データアクセス」で、スコープを `openid`・`email`・`profile` のみにする
4. 「クライアント」で、種類を「ウェブ アプリケーション」として作成する
   - 本番用: 承認済みの JavaScript 生成元に `https://skillsheet.technohonesty.com`、承認済みのリダイレクト URI に本番の戻り先 URL を設定する
   - 開発用: 承認済みの JavaScript 生成元に `http://localhost:8000`、承認済みのリダイレクト URI に開発用の戻り先 URL を設定する
5. 作成したクライアントの ID とシークレットを控える（シークレットはリポジトリ・チャットに貼らない）
6. 公開ステータスを「本番」にする（テスト中のままではテストユーザー以外はログインできない）

### 3.2. GitHub の OAuth App の作成

本番用と開発用の 2 つを作成する。

1. GitHub の「Settings」→「Developer settings」→「OAuth Apps」で「New OAuth App」を選ぶ
2. 本番用: Homepage URL に `https://skillsheet.technohonesty.com`、Authorization callback URL に本番の戻り先 URL を設定する
3. 開発用: Homepage URL に `http://localhost:8000`、Authorization callback URL に開発用の戻り先 URL を設定する
4. 作成後、Client ID を控え、「Generate a new client secret」でシークレットを発行して控える

### 3.3. 開発用の資格情報の設定

1. `webapp/.env` に、開発用の Client ID とシークレットを設定する（`.env` はコミットしない）

   ```bash
   GOOGLE_CLIENT_ID={開発用の Google の ID}
   GOOGLE_CLIENT_SECRET={開発用の Google のシークレット}
   GITHUB_CLIENT_ID={開発用の GitHub の ID}
   GITHUB_CLIENT_SECRET={開発用の GitHub のシークレット}
   ```

   - 上記の `{…}` を実際の値に置き換える

### 3.4. 本番の資格情報の OCI Vault への登録

マージ（CD による `k8s/vault-sync.yaml` の適用）より前に実施する。値が登録されていない状態で適用すると、
ログインできない。

次の 4 つのシークレットは infra-oci の Terraform が作成する（作成時の値はプレースホルダー）。
値は Terraform へ渡さず、OCI コンソールで新しいバージョンとして登録する
（[infra-oci 構築手順書 08](https://github.com/Seiya-Nakagawa/infra-oci/blob/main/docs/04.build/08_OAuthクライアント資格情報のVaultシークレット追加.md)）。

| シークレット名 | 登録する値（3.1・3.2 で控えた本番用） |
| -------------- | ------------------------------------- |
| `portfolio-google-client-id` | Google の本番用クライアントの ID |
| `portfolio-google-client-secret` | Google の本番用クライアントのシークレット |
| `portfolio-github-client-id` | GitHub の本番用 OAuth App の Client ID |
| `portfolio-github-client-secret` | GitHub の本番用 OAuth App のシークレット |

1. OCI コンソールで、`portfolio-secret-key` 等を登録している Vault を開く
2. 左メニューの「シークレット」から、上記のシークレットの名前をクリックする
3. 左メニューの「バージョン」を開き、「新規バージョンの作成」を押す
4. 「シークレット・タイプのテンプレート」で「プレーン・テキスト」を選び、「シークレットの内容」に値を貼る
   - 値の前後に空白・改行を入れない
5. 「新規バージョンの作成」を押し、最新のバージョンが「現行」になっていること
6. 4 つのシークレットすべてについて、2〜5 を繰り返す

### 3.5. 同期の確認

CD による適用の完了後に実施する。

```bash
ssh oci-server
```

```bash
kubectl -n app-prod get externalsecret portfolio-secrets
```

- `STATUS` が `SecretSynced`、`READY` が `True` であること

```bash
kubectl -n app-prod get secret portfolio-secrets -o jsonpath='{.data}' | grep -o '"[A-Z_]*"' | tr '\n' ' '
```

- 出力に `GOOGLE_CLIENT_ID`・`GOOGLE_CLIENT_SECRET`・`GITHUB_CLIENT_ID`・`GITHUB_CLIENT_SECRET` が含まれること（値は出力しない）
