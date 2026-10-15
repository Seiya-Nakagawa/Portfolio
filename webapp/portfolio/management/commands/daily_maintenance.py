"""日次の整理処理。期限切れの流量制限の回数と、実績から参照されなくなった画像を削除する。"""

from django.core.management.base import BaseCommand

from portfolio import media_files, ratelimit


class Command(BaseCommand):
    help = (
        "期限切れの流量制限の回数と、実績に保存されないまま猶予を過ぎた画像を削除する。"
        "ユーザーを特定できる情報は出力しない。"
    )

    def handle(self, *args, **options):
        counters = ratelimit.purge_expired()
        images = media_files.purge_unreferenced_images()
        self.stdout.write(
            f"整理しました: 流量制限の回数 {counters} 件、未使用の画像 {images} 件"
        )
