"""従来の保存先（`works/`）の画像を、所有するユーザーの保存先（`users/{id}/works/`）へ移す。"""

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from portfolio.media_paths import work_image_dir
from portfolio.models import Work

LEGACY_DIR = "works/"


class Command(BaseCommand):
    help = (
        "従来の保存先（works/）の画像を所有するユーザーの保存先へ移し、works の thumbnail を更新する。"
        "移動済みのファイルは再実行時にスキップする。"
    )

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        moved = skipped = missing = 0
        for work in Work.objects.filter(thumbnail__startswith=LEGACY_DIR):
            source = media_root / work.thumbnail
            relative = f"{work_image_dir(work.owner_id)}/{Path(work.thumbnail).name}"
            destination = media_root / relative
            if source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(source, destination)
                moved += 1
            elif destination.is_file():
                skipped += 1
            else:
                # 実体がない参照は、移動先が定まらないため更新せず報告する。
                missing += 1
                continue
            work.thumbnail = relative
            work.save(update_fields=["thumbnail"])
        self.stdout.write(
            f"画像を移動しました: 移動 {moved} 件、移動済み {skipped} 件、実体なし {missing} 件"
        )
