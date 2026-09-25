# 11 構築手順書 - Kubernetes マニフェストとデプロイスクリプトの OCI 適用

## 目次

- [1. 概要](#1-概要)
- [2. 前提条件](#2-前提条件)
- [3. 手順](#3-手順)
  - [3.1. マニフェストの作成](#31-マニフェストの作成)
  - [3.2. デプロイスクリプトの作成](#32-デプロイスクリプトの作成)
  - [3.3. イメージのローカル検証](#33-イメージのローカル検証)
  - [3.4. OCI 基盤へのデプロイ](#34-oci-基盤へのデプロイ)
  - [3.5. ログインユーザーの作成](#35-ログインユーザーの作成)
  - [3.6. 共有 Ingress 経由の動作確認](#36-共有-ingress-経由の動作確認)

## 1. 概要

Issue #50。[基本設計書](../02.design/DESIGN.md)に基づき、ポートフォリオアプリを infra-oci 基盤の
Kubernetes へ配置するための `k8s/` マニフェストと `deploy-oci.sh` を作成し、適用する。
infra-oci 上の既存アプリ（kakeibo）と同じ様式（hostPath 経由の UNIX ソケットで MySQL へ接続、
作業端末からのイメージ転送とマニフェスト適用）とする。

## 2. 前提条件

- [08](08_ポートフォリオアプリ基盤の構築.md)・[09](09_公開ページ配信と読み取り専用APIの実装.md)・
  [10](10_登録画面の実装.md)が完了していること
- infra-oci 側で、MySQL データベース `portfolio` と共有 Ingress の `/portfolio`
  パスプレフィックス（転送先 `portfolio-web`・ポート 80）が作成済みであること
  （[infra-oci Issue #127](https://github.com/Seiya-Nakagawa/infra-oci/issues/127)）
- OCI Vault に `portfolio-secret-key`・`portfolio-db-name`・`portfolio-db-user`・
  `portfolio-db-password` が登録済みであること
- 作業端末に Docker があり、OCI ホストへ SSH 接続できること

## 3. 手順

### 3.1. マニフェストの作成

`k8s/` に以下を作成する。`vault-sync.yaml`（ExternalSecret）は
[08](08_ポートフォリオアプリ基盤の構築.md)で作成済みである。

| ファイル | 内容 |
| -------- | ---- |
| `configmap.yaml` | 機密を含まない設定値（`ALLOWED_HOSTS`・`FORCE_SCRIPT_NAME`・`DB_SOCKET_PATH`・`CSRF_TRUSTED_ORIGINS`） |
| `web.yaml` | Deployment と Service（`portfolio-web`、ポート 80 → コンテナ 8000） |

- Deployment は `hostPath`（`/var/run/mysqld`）をマウントして MySQL のソケットへ接続する。
  init コンテナでソケットファイルの権限を調整し、非 root のアプリケーションコンテナから使えるようにする。
- 設定値は ConfigMap（`portfolio-config`）、機密値は Secret（`portfolio-secrets`）から環境変数として渡す。
- readiness は、`ALLOWED_HOSTS` のホスト名を Host ヘッダーに付けてコンテナ内から自身へ
  リクエストする exec プローブとする。

### 3.2. デプロイスクリプトの作成

リポジトリ直下に `deploy-oci.sh` を作成し、実行権限を付与する。処理は次の順とする。

1. `webapp/` のイメージを `linux/arm64` 向けにビルドする。
2. イメージを OCI ホストの containerd へ転送・ロードする。
3. `k8s/` のマニフェストを OCI ホストへ送り、`kubectl apply` する
   （Namespace・Ingress・TLS 証明書は基盤側の管理のため適用しない）。
4. Deployment を再起動し、ロールアウトの完了を待つ。
5. Pod 内で `migrate` と `import_portfolio_data` を実行する。

### 3.3. イメージのローカル検証

デプロイ前に、コンテナイメージがビルドでき、ページ・静的ファイルを返すことを確認する。

```bash
docker build -t portfolio:local ./webapp
docker run -d --rm --name portfolio-check -p 18000:8000 \
  -e SECRET_KEY=x -e DB_NAME=x -e DB_USER=x -e DB_PASSWORD=x \
  -e ALLOWED_HOSTS=technohonesty.com portfolio:local
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: technohonesty.com" localhost:18000/
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: technohonesty.com" localhost:18000/static/js/main.js
docker rm -f portfolio-check
```

- イメージをビルドする（`collectstatic` が実行される）。
- ダミーの環境変数でコンテナを起動する。
- ページ本体と静的ファイルが `200` を返すことを確認する（Ingress がプレフィックスを除去して転送するため、
  コンテナに対しては `/static/...` で確認する）。
- 確認用のコンテナを停止・削除する。

### 3.4. OCI 基盤へのデプロイ

リポジトリルートから実行する。

```bash
./deploy-oci.sh
```

- 3.2 の処理を順に実行する。完了時に Pod・Ingress・証明書の状態が表示される。

### 3.5. ログインユーザーの作成

デプロイ後、Pod 内で登録画面のログインユーザーを作成する。

```bash
kubectl exec -it -n app-prod deploy/portfolio-web -c web -- python manage.py createsuperuser
```

- ユーザー名・パスワードを対話入力して作成する。

### 3.6. 共有 Ingress 経由の動作確認

1. `https://technohonesty.com/portfolio/` を開き、ページ本体・静的ファイル・スキル/資格/実績の
   各セクションが表示されることを確認する。
2. `https://technohonesty.com/portfolio/api/skills`・`/api/certifications`・`/api/works` が
   JSON を返すことを確認する。
3. `https://technohonesty.com/portfolio/manage/` でログインし、登録画面が動作することを確認する。
