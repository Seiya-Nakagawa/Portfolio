from .base import *
from .base import env

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# TLS は Ingress で終端され Pod へはプレーン HTTP で転送されるため、
# 明示しないと request.is_secure() が False になる。
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# サービスホストのルート（/）で動作させる。階層の深い URL（/u/{ユーザー名}/ 等）でも
# 静的ファイル・画像を解決できるよう、ルート起点の絶対パスにする。
STATIC_URL = "/static/"
MEDIA_URL = "/media/"

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
