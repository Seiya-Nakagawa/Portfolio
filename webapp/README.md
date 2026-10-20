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

共通マスタ（スキル項目の共通マスタ・種類マスタ）を除く全テーブルは、所有するユーザーを
`owner_id`（`auth_user` の `id`）で参照する。所有者で絞り込んだ取得は、モデルの共通の取得口
（`for_owner()`、スキル項目は共通マスタを含む `visible_to()`）を経由し、管理画面の API・
集計・職務経歴書の生成は、ログインしたユーザーのデータのみを対象とする。
ユーザーを削除すると、所有する行は連鎖して削除される。
テナント分離は `portfolio/tests/test_tenant_isolation.py` で検証する（API を追加した際は同じテストに追加する）。
設計は [基本設計書 4.13](../docs/02.design/DESIGN.md#413-テナント分離) を参照する。

| テーブル | 役割 |
| -------- | ---- |
| `user_profiles` | ユーザーのプロフィール（公開設定・規約の同意状況） |
| `usage_daily` | 利用状況の日次集計値（ユーザーを参照しない） |

## 公開ページ・読み取り専用 API

サービスホストのルートで、認証不要で公開する。対象は公開中（`user_profiles.is_public`）かつ有効なユーザーのみで、
非公開・存在しない・利用停止中のユーザー名は、区別せず同一の 404 を返す。

| パス | 内容 |
| ---- | ---- |
| `/` | サービス紹介 |
| `/u/{ユーザー名}/` | ユーザーのポートフォリオサイトのページ本体 |
| `/u/{ユーザー名}/api/skills` | スキルデータ（案件実績から集計した経験年数） |
| `/u/{ユーザー名}/api/certifications` | 資格データ |
| `/u/{ユーザー名}/api/works` | 実績データ |
| `/u/{ユーザー名}/api/site` | サイト情報データ（Hero・About・Contact・フッター） |
| `/media/users/{ユーザーの id}/…` | アップロードした画像。所有するユーザーが公開中か、閲覧者が本人の場合のみ返す |

アップロードした画像は `MEDIA_ROOT` 配下のユーザーごとのディレクトリ（`users/{ユーザーの id}/works/`）に保存する。
従来の保存先（`works/`）の画像は、次のコマンドで所有するユーザーの保存先へ移す（移動済みのファイルはスキップする。
デプロイ時にも実行される）。

```bash
uv run python manage.py migrate_media
```

### 旧 URL からのリダイレクト

旧 URL のホスト（`LEGACY_HOSTS`）へのリクエストは、リダイレクト（301）以外を応答しない。`/manage/` 以下は
サービスホストの同じ画面へ、それ以外は運営者の公開ポートフォリオ（`/u/{LEGACY_REDIRECT_USERNAME}/`。
未設定の場合はサービスホストのトップ）へ転送する。Ingress が `/portfolio` を除去して転送する場合も、除去しない場合も同じ結果になる。

資格・実績・サイト情報の初期データは、マイグレーション適用後に次のコマンドで投入する。
`--owner` に所有者とするユーザーのユーザー名を指定する（そのユーザーにデータがあるテーブルはスキップする）。

```bash
uv run python manage.py import_portfolio_data --owner {ユーザー名}
```

スキル項目マスタ（AWS・Azure・Google Cloud・OCI のサービスと、言語・DB などの汎用項目）は、
次のコマンドで未登録の項目のみを追加する（登録済みの項目は変更しない。デプロイ時にも実行される）。
追加した項目は共通マスタ（所有者なし）のマスタ項目となり、管理画面から削除できない。クラウドのサービス一覧は
`scripts/fetch_cloud_services.py` で各社の公式サイトから再取得して種データを更新する。

```bash
uv run python manage.py import_skill_master
```

## 登録画面

`/manage/` に、案件登録・会社・スキル項目管理・資格・実績・サイト情報・職務経歴書（プレビュー・PDF / Markdown ダウンロード・文章項目の編集）の画面を持つ
1 ページのアプリを配置する。ログインが必須で、未ログインの API 呼び出しは 401 を返す。
入力値の検証はサーバー側（`portfolio/registry.py`）で行い、書き込みはトランザクション内で
対象行をロックして排他制御する。

## サービス紹介・利用規約・プライバシーポリシー

| パス | 内容 |
| ---- | ---- |
| `/` | サービス紹介（特長・利用の流れ・職務経歴書の出力例・ログイン導線） |
| `/terms/`・`/privacy/` | 現行の版の利用規約・プライバシーポリシー |

- 規約の本文は版ごとのテンプレート（`templates/legal/terms/{版}.html`・`templates/legal/privacy/{版}.html`）で管理し、
  現行の版は設定 `TERMS_VERSION`・`PRIVACY_VERSION` で指定する。改定する場合は、新しい版のテンプレートを追加し、
  設定の版を更新する（過去の版のテンプレートは残す）。ユーザーは次回ログイン時に再同意を求められる
- 本文には運営者の氏名・連絡先等の個人情報を記載しない。問い合わせは Google フォームで受け付け、URL は環境変数 `CONTACT_FORM_URL` で設定する
  （未設定の場合はリンクを表示しない）。リンクはサービス紹介・規約・ログイン・公開ポートフォリオのフッターに置く
- 出力例の画像（`static/img/skillsheet-sample.png`）は、架空のデータで生成した職務経歴書を撮影したもので、実データを含まない
- 登録画面は、案件が 1 件もない初回の利用時に、案件の登録から職務経歴書の取得までの手順を案内する

## ログイン・サインアップ

ログインは外部アカウント（Google・GitHub）のみで、パスワードによるログインは提供しない
（認証ライブラリは django-allauth）。

| パス | 内容 |
| ---- | ---- |
| `/login/` | ログイン画面（Google・GitHub のボタンのみ） |
| `/accounts/{google,github}/login/` | 提供元の認可画面へ移動する（POST） |
| `/accounts/{google,github}/login/callback/` | 提供元からの戻り先 |
| `/accounts/signup/` | 初回の認可後に表示するサインアップ（ユーザー名の入力と規約への同意） |
| `/accounts/reconsent/` | 規約の版が改定された場合の再同意 |
| `/terms/`・`/privacy/` | 利用規約・プライバシーポリシー |
| `/admin/login/` | 管理サイトのログイン。`/login/` へ転送する |

- 取得する情報は外部アカウントの識別子・メールアドレス・表示名に限り、スコープも最小限（Google: `profile`・`email`、GitHub: `user:email`）にする
- 提供元が検証済みとしているメールアドレスが既存ユーザーと一致する場合のみ、そのユーザーに紐づける。未検証の場合は新規のサインアップとして扱う
- 利用停止中（`is_active` が偽）のユーザーは、認可が成功してもログインさせず、既存のセッションも無効になる
- 現行の規約の版は設定 `TERMS_VERSION`・`PRIVACY_VERSION` で定義する。改定した場合、同意した版が異なるユーザーはログイン後の全画面で再同意画面へ誘導される
- ユーザー名は半角英小文字で始まる、半角英小文字・数字・ハイフンの 3〜30 文字で、予約語は使えない（`portfolio/accounts.py`）

## アカウント画面

登録画面の「アカウント」で、ユーザー名の変更・公開設定の切替・外部アカウントの追加連携と解除・退会を行う。
API は `/manage/api/account`（取得・変更）、`/manage/api/account/providers/{提供元}`（連携の解除）、
`/manage/api/account/withdraw`（退会）で、いずれもログインしたユーザー自身のみを対象とする。

- ユーザー名の変更後は、旧ユーザー名の公開 URL が 404 になり、旧ユーザー名は他のユーザーが取得できる
- 連携が 1 つだけの場合は解除できない（ログインできなくなるため）。追加連携は、ログイン中に提供元の認可画面へ移動して行い、メールアドレスによる他のユーザーへの紐づけは行わない
- 退会は、ユーザー名の再入力が一致した場合のみ実行できる。1 トランザクションでユーザーと所有する全データを削除し、確定後にユーザーの画像の保存先（`users/{ユーザーの id}/`）を削除する。退会数のみ `usage_daily` に加算し、ユーザーを特定できる情報は残さない

## スキル項目（共通マスタと独自スキル項目）

スキル項目は、全ユーザーで共有する共通マスタ（`owner_id` が空）と、ユーザーごとの独自スキル項目に分かれる。

| 区分 | 追加・変更 | 削除 | 備考 |
| ---- | ---------- | ---- | ---- |
| 共通マスタ | 運営者（`is_staff`）のみ。`skill_id` を指定し、新しい種類も指定できる | 不可（API は 403） | 一般ユーザーが変更しようとすると 403 |
| 独自スキル項目 | 本人のみ。種類は既存の種類から選ぶ | 本人のみ（使用実績が紐づく間は不可） | `skill_id` は `u-` に推測されにくい文字列を続けてサーバー側で採番する |

- 独自スキル項目は、共通マスタと自分の同じ種類の項目と名前（大文字小文字を区別しない）を重複させられない
- 独自スキル項目の表示順は、同じ種類の共通マスタの後ろに、サブカテゴリ ＞ 名前の昇順で並べる（表示順は保存しない）
- 種類の追加・名称変更・並び替え・削除（`/manage/api/categories` 以下の変更）は運営者のみで、それ以外は 403。種類名の変更は全ユーザーの独自スキル項目にも反映する
- `import_skill_master` は共通マスタのみを対象にし、独自スキル項目を変更しない

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
案件は `--owner` で指定したユーザーの所有とし、スキル項目は共通マスタにする。

```bash
uv run python manage.py import_skill_sheet /path/to/csv --owner {ユーザー名}
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
| `SERVICE_HOST` | サービスホスト名（旧 URL からの転送先。本番のみ） | 既定値 空 |
| `LEGACY_HOSTS` | 旧 URL のホスト名（本番のみ、カンマ区切り。空の場合は転送しない） | 既定値 空 |
| `LEGACY_REDIRECT_USERNAME` | 旧 URL の転送先とする運営者のユーザー名（本番のみ） | 既定値 空 |
| `CSRF_TRUSTED_ORIGINS` | CSRF を許可するオリジン（本番のみ、カンマ区切り。例: `https://example.com`） | 既定値 空 |
| `CONTACT_FORM_URL` | 問い合わせ窓口（Google フォーム）の URL | 既定値 空（リンクを表示しない） |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google の OAuth クライアント | 本番は OCI Vault から同期 |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub の OAuth App | 本番は OCI Vault から同期 |

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
マイグレーションとスキル項目マスタの投入を行う。本番デプロイは GitHub Actions（`.github/workflows/deploy.yml`）
が `main` マージを契機に、OCI Bastion 経由で自動実行する。作業端末からの直接実行は障害調査等の
一時的な用途に限る。詳細は [基本設計書 7.1](../docs/02.design/DESIGN.md#71-cicd-パイプライン) を参照する。

## テスト・静的解析

ユニットテストは SQLite（メモリ）で実行するため、MySQL への接続は不要。

```bash
SECRET_KEY=test uv run python manage.py test --settings=config.settings.test
uv run ruff check .
uv run ruff format --check .
```
