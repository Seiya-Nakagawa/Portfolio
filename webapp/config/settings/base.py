from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# 機密値は環境変数から取得する。本番では OCI Vault から External Secrets 経由で
# Kubernetes Secret に同期され、環境変数として渡される。
SECRET_KEY = env("SECRET_KEY")

INSTALLED_APPS = [
    # 登録するテーブルを限定した運営管理の管理サイト（portfolio.admin）を用いる。
    "portfolio.admin_apps.OperatorAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "portfolio",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # 旧 URL のホストへのリクエストは、リダイレクト以外を応答しない。
    "portfolio.middleware.LegacyUrlRedirectMiddleware",
    # 静的ファイルを gunicorn から直接配信する（本番）。
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    # 公開ページ・ログイン・サインアップの呼び出し回数を接続元ごとに制限する。
    "portfolio.middleware.RateLimitMiddleware",
    # 規約の版が改定された場合に、同意していないユーザーを再同意画面へ誘導する。
    "portfolio.middleware.ReconsentMiddleware",
]

# 認証は外部アカウント（Google・GitHub）のみとし、パスワードによるログインは提供しない。
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "manage"
LOGOUT_REDIRECT_URL = "index"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_ADAPTER = "portfolio.accounts.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"username"}
# メールアドレスは外部アカウントから取得した値を表示するのみとし、入力は求めない（任意・変更不可）。
ACCOUNT_SIGNUP_FIELDS = ["email", "username*"]
# 検証済みでないメールアドレスは既存ユーザーと紐づけず、新規のサインアップとして扱うため重複を許す。
ACCOUNT_UNIQUE_EMAIL = False
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_USERNAME_MAX_LENGTH = 30
ACCOUNT_LOGOUT_ON_GET = False
# 外部アカウントのみで認証する（ローカルのアカウント作成・パスワードは使わない）。
SOCIALACCOUNT_ONLY = True

SOCIALACCOUNT_ADAPTER = "portfolio.accounts.SocialAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "portfolio.accounts.SignupForm"}
# サインアップ時は必ずユーザー名の入力と規約への同意を求める。
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_STORE_TOKENS = False
# 取得する情報は外部アカウントの識別子・メールアドレス・表示名に限り、スコープも最小限にする。
# OAuth クライアントの ID・シークレットは環境変数で受け取る（本番は OCI Vault から同期）。
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [
            {
                "client_id": env("GOOGLE_CLIENT_ID", default=""),
                "secret": env("GOOGLE_CLIENT_SECRET", default=""),
            }
        ],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "github": {
        "APPS": [
            {
                "client_id": env("GITHUB_CLIENT_ID", default=""),
                "secret": env("GITHUB_CLIENT_SECRET", default=""),
            }
        ],
        "SCOPE": ["user:email"],
    },
}

# サービス名と、運営者への問い合わせ窓口（Google フォーム）の URL。
SERVICE_NAME = "SkillSheet"
CONTACT_FORM_URL = env("CONTACT_FORM_URL", default="")

# サービス紹介のタイトル・SNS 共有時の名称。検索結果で内容が伝わるよう検索語句を含める。
SERVICE_TITLE = (
    "SkillSheet | エンジニアの職務経歴書を案件登録だけで作成・経験年数を自動計算"
)

# サービス紹介・SNS 共有時に表示するサービスの説明。
SERVICE_DESCRIPTION = (
    "エンジニア向けの職務経歴書作成サービス。案件を登録するだけで、"
    "技術ごとの経験年数を自動で算出し、職務経歴書の PDF を出力できます。"
)

# Cloudflare Web Analytics の計測用トークン（ページに埋め込まれる公開値）。空の場合は計測しない。
CLOUDFLARE_ANALYTICS_TOKEN = env("CLOUDFLARE_ANALYTICS_TOKEN", default="")

# 旧 URL（technohonesty.com/portfolio）からのリダイレクト。LEGACY_HOSTS が空の場合は行わない。
# 転送先は SERVICE_HOST の運営者の公開ポートフォリオ（LEGACY_REDIRECT_USERNAME。未設定ならトップ）。
SERVICE_HOST = env("SERVICE_HOST", default="")
LEGACY_HOSTS = env.list("LEGACY_HOSTS", default=[])
LEGACY_REDIRECT_USERNAME = env("LEGACY_REDIRECT_USERNAME", default="")

# 現行の利用規約・プライバシーポリシーの版。改定したら更新する。
# 同意した版が現行と異なるユーザーは、ログイン後に再同意が必要になる。
TERMS_VERSION = "2026-10-28"
PRIVACY_VERSION = "2026-10-28"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.media",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "portfolio.context_processors.service",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ja"

TIME_ZONE = "Asia/Tokyo"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# 実績の画像など、管理画面からアップロードしたファイル（git 管理対象外）。
MEDIA_URL = "media/"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 流量制限（対象: (区間あたりの上限回数, 区間の秒数)）。上限を超えた呼び出しには 429 を返す。
RATE_LIMITS = {
    "public": (120, 60),  # 公開ポートフォリオのページ・API・画像（接続元ごと）
    "login": (20, 60),  # ログイン・サインアップ（接続元ごと）
    "pdf": (10, 60),  # 職務経歴書 PDF の生成（ユーザーごと）
    "upload": (30, 60),  # 画像のアップロード（ユーザーごと）
}
# 接続元の IP アドレスは、X-Forwarded-For の末尾から数えてこの番目（共有 Ingress が付与した値）を用いる。
# それより前の値は接続元が任意に付与できるため信用しない。プロキシを経由しない場合は 0。
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT", default=0)

# 1 ユーザーあたりの保存済み画像の合計の上限と、1 ファイルの上限（バイト）。
MAX_USER_IMAGE_BYTES = 50 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
# アップロード後に実績へ保存されなかった画像を、日次の整理で削除するまでの猶予（秒）。
UNREFERENCED_IMAGE_GRACE_SECONDS = 24 * 60 * 60

# 死活監視。日次の整理処理の最終成功から `HEALTH_MAINTENANCE_MAX_AGE_HOURS` 時間を超えた場合、
# ヘルスチェックは異常（503）を返す。
HEALTH_MAINTENANCE_MAX_AGE_HOURS = 26

# 変更・退会で解放したユーザー名を、他のユーザーが取得できないようにする日数。
USERNAME_RESERVATION_DAYS = 90
# 退会など取り消せない操作に求める、直近のログインからの許容時間（分）。
RECENT_LOGIN_MINUTES = 10
