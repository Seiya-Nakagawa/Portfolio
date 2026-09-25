from .base import *
from .base import env

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# TLS は Ingress で終端され Pod へはプレーン HTTP で転送されるため、
# 明示しないと request.is_secure() が False になる。
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# /portfolio 配下で動作させるため、URL 逆引き・リダイレクト先にプレフィックスを付与する。
# Ingress 側はプレフィックスを除去してバックエンドへ転送するため、Django 側は付与のみを担う。
FORCE_SCRIPT_NAME = env("FORCE_SCRIPT_NAME", default="/portfolio")

# 階層の深い URL でも静的ファイルを解決できるよう、プレフィックス起点の絶対パスにする。
STATIC_URL = f"{FORCE_SCRIPT_NAME}/static/"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_SOCKET_PATH", default="/var/run/mysqld/mysqld.sock"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

# 認証情報を含む Cookie は HTTPS でのみ送信する。
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Ingress で終端された HTTPS のオリジンからの POST を許可する（例: https://example.com）。
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
