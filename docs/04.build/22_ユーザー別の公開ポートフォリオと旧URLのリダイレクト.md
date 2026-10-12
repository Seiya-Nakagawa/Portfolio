# 22 構築手順書 - ユーザー別の公開ポートフォリオと旧 URL のリダイレクト

## 目次

- [1. 概要](#1-概要)
- [2. 前提条件](#2-前提条件)
- [3. 手順](#3-手順)
  - [3.1. ローカルでの動作確認](#31-ローカルでの動作確認)
  - [3.2. 本番への適用](#32-本番への適用)
  - [3.3. 運営者のユーザー名の設定後の作業](#33-運営者のユーザー名の設定後の作業)

## 1. 概要

Issue #168 の対応。公開ポートフォリオと読み取り専用 API を `/u/{ユーザー名}/` 配下に移し、非公開・存在しない・
利用停止中のユーザーを同一の 404 とする。画像をユーザーごとの保存先から配信し、公開設定と閲覧者で配信を制御する。
旧 URL からのリダイレクトを実装し、パス設定をサービスホストのルートに合わせる。設計は
[基本設計書 5.1](../02.design/DESIGN.md#51-画面一覧)・
[6.2](../02.design/DESIGN.md#62-公開ポートフォリオ用読み取り専用api)・
[6.5](../02.design/DESIGN.md#65-旧-url-からのリダイレクト) を参照する。

| 区分 | 内容 |
| ---- | ---- |
| アプリ | `/u/{ユーザー名}/` 配下の公開ページ・API、ユーザー別の保存先（`users/{ユーザーの id}/works/`）への画像保存、`/media/` の配信制御、旧 URL のホストへのリダイレクトを追加する。URL 設定からプレフィックス（`FORCE_SCRIPT_NAME`）を除く |
| 管理コマンド | `migrate_media`: 従来の保存先（`works/`）の画像を所有するユーザーの保存先へ移し、`works.thumbnail` を更新する |
| マニフェスト | `k8s/configmap.yaml` の `ALLOWED_HOSTS`・`CSRF_TRUSTED_ORIGINS` をサービスホストに合わせ、`SERVICE_HOST`・`LEGACY_HOSTS` を追加する。`FORCE_SCRIPT_NAME` を削除する。`k8s/web.yaml` の準備確認の `Host` をサービスホストにする |

## 2. 前提条件

- サービスホスト `skillsheet.technohonesty.com` の DNS レコード・TLS 証明書・Ingress が、infra-oci で用意されていること
- 旧 URL のホスト `technohonesty.com` の `/portfolio` が、引き続きこのサービスへ転送されること（Ingress が `/portfolio` を除去する場合も、しない場合も動作する）

## 3. 手順

### 3.1. ローカルでの動作確認

```bash
docker compose -f webapp/docker-compose.yml up -d db
```

- 確認用の MySQL を起動する

```bash
uv run python manage.py runserver
```

1. 公開設定を有効にしたユーザーの `/u/{ユーザー名}/` が表示され、`/u/{ユーザー名}/api/skills` 等がそのユーザーのデータを返すことを確認する
2. 非公開のユーザー・存在しないユーザー名・`is_active` が偽のユーザーで、同じ内容の 404 になることを確認する
3. 実績の画像をアップロードし、`MEDIA_ROOT/users/{ユーザーの id}/works/` に保存されることを確認する
4. 非公開のユーザーの画像が、ログインしていないブラウザーでは 404、本人では表示できることを確認する

### 3.2. 本番への適用

マージ後の CD（`deploy-oci.sh`）で、マイグレーションの後に `migrate_media` が実行され、従来の画像が移される。

1. 適用後、運営者の画像が表示されることを確認する

   ```bash
   ssh oci-server
   ```

   ```bash
   kubectl -n app-prod exec deploy/portfolio-web -c web -- python manage.py migrate_media
   ```

   - 再実行して `移動 0 件` かつ `実体なし 0 件` になることを確認する

### 3.3. 運営者のユーザー名の設定後の作業

運営者のユーザー名をアカウント画面から設定した後、旧 URL の転送先を設定する。設定するまでの間、旧 URL は
サービスホストのトップへ転送される。

1. `k8s/configmap.yaml` に `LEGACY_REDIRECT_USERNAME: "{運営者のユーザー名}"` を追加し、デプロイする
2. `https://technohonesty.com/portfolio/` が `https://skillsheet.technohonesty.com/u/{運営者のユーザー名}/` へ 301 で転送されることを確認する

   ```bash
   curl -sI https://technohonesty.com/portfolio/
   ```

   - `HTTP/2 301` と `location` ヘッダーを確認する
