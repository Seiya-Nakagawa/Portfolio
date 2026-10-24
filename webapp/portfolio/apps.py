from django.apps import AppConfig


class PortfolioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portfolio"
    verbose_name = "ポートフォリオ"

    def ready(self):
        # ログイン時にセッションへ認証時刻を記録する受信関数を登録する。
        from portfolio import accounts  # noqa: F401
