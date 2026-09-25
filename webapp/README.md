# webapp

ポートフォリオサイトと、スキル実績管理（案件実績の蓄積・集計）を提供する Web アプリ。
infra-oci 基盤の Kubernetes 上にコンテナとして配置し、実績 DB（MySQL）に接続する。
設計は [基本設計書](../docs/02.design/DESIGN.md) を参照する。

## 言語・フレームワーク・バージョン

| 項目 | バージョン |
| ---- | ---------- |
| Python | 3.14 |
| Django | 5.2（5.2.8 以上 5.3 未満） |
| MySQL（実績 DB） | 8.0 |
| gunicorn | 26 以上 |
| パッケージ管理 | uv |

依存パッケージの確定バージョンは `uv.lock` を正とする。

## ディレクトリ構成

| パス | 内容 |
| ---- | ---- |
| `config/` | Django プロジェクト設定（`settings/` は base・development・production・test） |
| `portfolio/` | アプリ本体。モデル（実績 DB のテーブル定義）、マイグレーション、経験年数の算出ロジック |
| `templates/` | ページ本体のテンプレート |
| `static/` | 静的ファイル（css / js / img） |

## 実績 DB

テーブル定義は `portfolio/models.py`、スキーマ変更は `portfolio/migrations/` で管理する。
`levels`（習熟度 1〜5）の初期値はマイグレーション（`0002_insert_levels`）で投入する。

## 環境変数

`.env.example` をコピーして `.env` を作成する（`.env` はコミットしない）。

| 変数 | 用途 | 備考 |
| ---- | ---- | ---- |
| `SECRET_KEY` | Django の秘密鍵 | 本番は OCI Vault から同期 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | MySQL 接続情報 | 本番は OCI Vault から同期 |
| `DB_HOST` / `DB_PORT` | 接続先（開発のみ） | 既定値 `127.0.0.1` / `3306` |
| `DB_SOCKET_PATH` | 接続先の UNIX ソケット（本番のみ） | 既定値 `/var/run/mysqld/mysqld.sock` |
| `ALLOWED_HOSTS` | 許可ホスト（本番のみ、カンマ区切り） | |
| `FORCE_SCRIPT_NAME` | URL プレフィックス（本番のみ） | 既定値 `/portfolio` |

本番の機密値は `k8s/vault-sync.yaml`（ExternalSecret）により OCI Vault から
Kubernetes Secret（`portfolio-secrets`）へ同期し、環境変数として Pod に渡す。
コード・マニフェストへ値を直接記述しない。

## ローカル開発

`mysqlclient` のビルドに `libmysqlclient-dev` と `pkg-config` が必要。

```bash
cp .env.example .env
docker compose up -d db
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

## テスト・静的解析

ユニットテストは SQLite（メモリ）で実行するため、MySQL への接続は不要。

```bash
SECRET_KEY=test uv run python manage.py test --settings=config.settings.test
uv run ruff check .
uv run ruff format --check .
```
