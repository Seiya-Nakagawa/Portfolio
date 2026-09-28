# CLAUDE.md

このファイルは、本リポジトリ固有の事情を記録したものです。

基本方針・機密情報の取り扱い・Git 運用・コーディング規約・Markdown 記法などの共通規約は
グローバル規約（`~/.claude/`、`~/.gemini/`）に従います。
**本ファイルに共通規約を重複定義しないこと。**

## デプロイ先（OCI ホスト）

- infra-oci リポジトリが管理する OCI Compute Instance（Kubernetes・containerd）
- パブリック IP: `217.142.230.83`（作業端末からの直接 SSH・障害調査用）
- プライベート IP: `10.0.1.60`（OCI Bastion 経由の接続用）
- OS ユーザー: `seiya`
- Kubernetes Namespace: `app-prod`

## CI/CD（GitHub Actions）

- `.github/workflows/ci.yml`: Pull Request 作成時に `webapp/` の `ruff`・Django テストを実行する
- `.github/workflows/deploy.yml`: `main` マージ後、`scripts/deploy_via_bastion.sh` 経由で
  `deploy-oci.sh` を実行し本番環境へ自動デプロイする
- OCI Bastion（Managed SSH Session）を使い、セキュリティ・リストを変更せずに GitHub Actions から
  OCI ホストへ到達する（詳細は [基本設計書 7.1](docs/02.design/DESIGN.md#71-cicd-パイプライン) を参照）
- Bastion セッション作成用の IAM ユーザーは infra-oci リポジトリの Ansible CI/CD と共用する。
  ユーザー OCID・フィンガープリントは秘密情報ではないため `scripts/deploy_via_bastion.sh` に
  直接定義する（セットアップ手順は [16 構築手順書](docs/04.build/16_GitHubActionsCICD構築.md) を参照）
- GitHub Secrets: `BASTION_OCI_PRIVATE_KEY`（秘密鍵のみ）
- 作業端末からの `deploy-oci.sh` 直接実行は、障害調査等の一時的な用途にのみ使う
  （本番デプロイは CI/CD 経由に統一する）
