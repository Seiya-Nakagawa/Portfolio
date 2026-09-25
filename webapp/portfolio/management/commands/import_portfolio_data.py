"""表示データの JSON（資格・実績）を実績 DB へ投入する。"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portfolio.models import Certification, Work

SEED_DIR = Path(__file__).resolve().parent.parent.parent / "seed"


def load_certifications(path: Path) -> list[Certification]:
    items = json.loads(path.read_text(encoding="utf-8"))
    # JSON の並び順をそのまま表示順とする。
    return [
        Certification(
            name=item["name"],
            acquired_on=item["date"],
            org=item["org"],
            sort_order=index,
        )
        for index, item in enumerate(items, start=1)
    ]


def load_works(path: Path) -> list[Work]:
    items = json.loads(path.read_text(encoding="utf-8"))
    return [
        Work(
            title=item["title"],
            desc_ja=item["desc_ja"],
            desc_en=item.get("desc_en", ""),
            tags=item.get("tags", []),
            thumbnail=item.get("thumbnail", ""),
            github_url=item.get("github_url", ""),
            live_url=item.get("live_url", ""),
            sort_order=index,
        )
        for index, item in enumerate(items, start=1)
    ]


class Command(BaseCommand):
    help = (
        "資格・実績の JSON を実績 DB へ投入する。既にデータがあるテーブルは変更しない。"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed-dir",
            type=Path,
            default=SEED_DIR,
            help="certifications.json / works.json を置いたディレクトリ",
        )

    def handle(self, *args, **options):
        seed_dir: Path = options["seed_dir"]
        targets = [
            (Certification, seed_dir / "certifications.json", load_certifications),
            (Work, seed_dir / "works.json", load_works),
        ]
        for _, path, _ in targets:
            if not path.is_file():
                raise CommandError(f"投入元のファイルが見つかりません: {path}")

        # 再実行で二重登録にならないよう、片方ずつ空のテーブルにのみ投入する。
        with transaction.atomic():
            for model, path, loader in targets:
                label = model._meta.verbose_name
                if model.objects.exists():
                    self.stdout.write(f"{label}: 登録済みのためスキップしました。")
                    continue
                model.objects.bulk_create(loader(path))
                self.stdout.write(f"{label}: 投入しました。")
