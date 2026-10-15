from importlib import import_module

from django.contrib.admin.apps import SimpleAdminConfig


class OperatorAdminConfig(SimpleAdminConfig):
    """運営管理用に、登録するテーブルを限定した管理サイトを用いる。

    `AdminConfig` は全アプリの admin モジュールを自動登録するため、認証・外部アカウント等の
    テーブルまで管理対象になる。自動登録を行わず、`portfolio.admin` のみを読み込む。
    """

    default_site = "portfolio.admin.OperatorAdminSite"

    def ready(self):
        super().ready()
        import_module("portfolio.admin")
