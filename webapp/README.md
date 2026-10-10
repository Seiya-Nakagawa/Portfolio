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
| `portfolio/` | アプリ本体。モデル（実績 DB のテーブル定義）、マイグレーション、経験年数の算出ロジック、公開ページ・読み取り専用 API のビュー、資格・実績・サイト情報の投入元（`seed/`） |
| `templates/` | ページ本体のテンプレート |
| `static/` | 静的ファイル（css / js / img） |

## 実績 DB

テーブル定義は `portfolio/models.py`、スキーマ変更は `portfolio/migrations/` で管理する。

## 公開ページ・読み取り専用 API

認証不要で公開する（パスプレフィックス `/portfolio` は Ingress が除去して転送する）。

| パス | 内容 |
| ---- | ---- |
| `/` | ポートフォリオサイトのページ本体 |
| `/api/skills` | スキルデータ（案件実績から集計した経験年数） |
| `/api/certifications` | 資格データ |
| `/api/works` | 実績データ |
| `/api/site` | サイト情報データ（Hero・About・Contact・フッター） |

資格・実績・サイト情報の初期データは、マイグレーション適用後に次のコマンドで投入する
（データがあるテーブルはスキップする）。

```bash
uv run python manage.py import_portfolio_data
```

スキル項目マスタ（AWS・Azure・Google Cloud・OCI のサービスと、言語・DB などの汎用項目）は、
次のコマンドで未登録の項目のみを追加する（登録済みの項目は変更しない。デプロイ時にも実行される）。
追加した項目はマスタ項目となり、管理画面から削除できない。クラウドのサービス一覧は
`scripts/fetch_cloud_services.py` で各社の公式サイトから再取得して種データを更新する。

```bash
uv run python manage.py import_skill_master
```

## 登録画面

`/manage/` に、案件登録・会社・スキル項目管理・資格・実績・サイト情報・職務経歴書（プレビュー・PDF / Markdown ダウンロード・文章項目の編集）の画面を持つ
1 ページのアプリを配置する。本人のログインが必須で、未ログインの API 呼び出しは 401 を返す。
入力値の検証はサーバー側（`portfolio/registry.py`）で行い、書き込みはトランザクション内で
対象行をロックして排他制御する。

ログインユーザーは初回のみ次のコマンドで作成する（パスワードはコマンドの対話入力で設定する）。

```bash
uv run python manage.py createsuperuser
```

## 職務経歴書

職務経歴書は、記載内容を項目ごとのデータとして実績 DB に保持し、ダウンロードのたびに Markdown を組み立てて生成する。

| 記載内容 | 保持先・編集画面 |
| -------- | ---------------- |
| 氏名・職務概要・活かせる経験・得意分野・自己PR | `skillsheet_texts`。「職務経歴書」で項目ごとに編集する |
| 会社（会社概要を含む。本業・副業の区分） | `companies`。「会社」で編集する |
| 案件の体制・案件概要・業務内容・担当工程・環境・言語、所属する会社 | `projects`。「案件登録」の「職務経歴書の記載内容」で編集する |
| テクニカルスキル・保有資格・職務経歴の概略 | 使用スキル実績・資格・会社から自動で生成する |

PDF は組み立てた Markdown を WeasyPrint で変換して生成する。実行環境に Pango と日本語フォント
（IPAex ゴシック）が必要で、コンテナイメージには `webapp/Dockerfile` で導入している。
ローカル（Docker を使わない場合）で PDF を生成するには、これらを OS にインストールする。
実データはリポジトリに含めない（テストは架空のダミーデータを使う）。

職務経歴書の生成時の警告は、会社が未設定の案件（職務経歴書に出力されない）と、未入力の文章項目の 2 種類である。

## 旧実績シートの移行

旧実績シートの CSV（`skills.csv`・`projects.csv`・`project_skills.csv`）を実績 DB へ移行する。
実データは個人の職歴を含むためリポジトリには置かない。既存データがある場合は何も変更しない。

```bash
uv run python manage.py import_skill_sheet /path/to/csv
```

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
| `CSRF_TRUSTED_ORIGINS` | CSRF を許可するオリジン（本番のみ、カンマ区切り。例: `https://example.com`） | 既定値 空 |

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

## デプロイ

リポジトリルートの `deploy-oci.sh` が、イメージのビルド・転送、`k8s/` のマニフェスト適用、
マイグレーション、初期データ投入を行う。本番デプロイは GitHub Actions（`.github/workflows/deploy.yml`）
が `main` マージを契機に、OCI Bastion 経由で自動実行する。作業端末からの直接実行は障害調査等の
一時的な用途に限る。詳細は [基本設計書 7.1](../docs/02.design/DESIGN.md#71-cicd-パイプライン) を参照する。

## テスト・静的解析

ユニットテストは SQLite（メモリ）で実行するため、MySQL への接続は不要。

```bash
SECRET_KEY=test uv run python manage.py test --settings=config.settings.test
uv run ruff check .
uv run ruff format --check .
```
