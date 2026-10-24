"""日次の整理処理。期限切れの流量制限の回数・解放後の予約が切れたユーザー名・実績から参照されなくなった画像を削除する。"""

from django.core.management.base import BaseCommand

from portfolio import accounts, health, media_files, ratelimit
from portfolio.models import JobRun


class Command(BaseCommand):
    help = (
        "期限切れの流量制限の回数と、予約が切れたユーザー名、実績に保存されないまま猶予を過ぎた画像を削除する。"
        "成功した時刻を記録し、死活監視の判定に用いる。ユーザーを特定できる情報は出力しない。"
    )

    def handle(self, *args, **options):
        counters = ratelimit.purge_expired()
        usernames = accounts.purge_expired_reservations()
        images = media_files.purge_unreferenced_images()
        # すべて成功した場合のみ記録する。失敗した場合は例外で終了し、記録は更新されない。
        health.record_job_success(JobRun.JOB_DAILY_MAINTENANCE)
        self.stdout.write(
            f"整理しました: 流量制限の回数 {counters} 件、予約が切れたユーザー名 {usernames} 件、"
            f"未使用の画像 {images} 件"
        )
