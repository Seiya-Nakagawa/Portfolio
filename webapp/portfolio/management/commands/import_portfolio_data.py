"""表示データの JSON（資格・実績）を実績 DB へ投入する。"""

import json
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portfolio.models import Certification, SiteInfo, Work

SEED_DIR = Path(__file__).resolve().parent.parent.parent / "seed"


def _month_start(year_month: str) -> date:
    """JSON の年月（YYYY-MM）を、その月の 1 日の日付に変換する。"""
    return date.fromisoformat(f"{year_month}-01")


def load_certifications(path: Path, owner) -> list[Certification]:
    items = json.loads(path.read_text(encoding="utf-8"))
    # 表示順は取得日の降順で自動的に決まる。
    return [
        Certification(
            name=item["name"],
            acquired_on=_month_start(item["date"]),
            org=item["org"],
            owner=owner,
        )
        for item in items
    ]


def load_works(path: Path, owner) -> list[Work]:
    items = json.loads(path.read_text(encoding="utf-8"))
    # 表示順は登録の新しい順（採番の降順）のため、JSON の先頭が最後に採番されるよう逆順で投入する。
    return [
        Work(
            title=item["title"],
            desc_ja=item["desc_ja"],
            desc_en=item.get("desc_en", ""),
            tags=item.get("tags", []),
            thumbnail=item.get("thumbnail", ""),
            github_url=item.get("github_url", ""),
            live_url=item.get("live_url", ""),
            achieved_on=_month_start(item["date"]) if item.get("date") else None,
            owner=owner,
        )
        for item in reversed(items)
    ]


def load_site_info(path: Path, owner) -> list[SiteInfo]:
    item = json.loads(path.read_text(encoding="utf-8"))
    return [SiteInfo(owner=owner, **item)]


class Command(BaseCommand):
    help = (
        "資格・実績・サイト情報の JSON を、--owner で指定したユーザーの所有として実績 DB へ投入する。"
        "そのユーザーに既にデータがあるテーブルは変更しない。"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed-dir",
            type=Path,
            default=SEED_DIR,
            help="certifications.json / works.json / site_info.json を置いたディレクトリ",
        )
        parser.add_argument(
            "--owner", required=True, help="データを所有するユーザーのユーザー名"
        )

    def handle(self, *args, **options):
        seed_dir: Path = options["seed_dir"]
        try:
            owner = get_user_model().objects.get(username=options["owner"])
        except get_user_model().DoesNotExist:
            raise CommandError(
                f"ユーザーが見つかりません: {options['owner']}"
            ) from None
        targets = [
            (Certification, seed_dir / "certifications.json", load_certifications),
            (Work, seed_dir / "works.json", load_works),
            (SiteInfo, seed_dir / "site_info.json", load_site_info),
        ]
        for _, path, _ in targets:
            if not path.is_file():
                raise CommandError(f"投入元のファイルが見つかりません: {path}")

        # 再実行で二重登録にならないよう、片方ずつ空のテーブルにのみ投入する。
        with transaction.atomic():
            for model, path, loader in targets:
                label = model._meta.verbose_name
                if model.objects.for_owner(owner).exists():
                    self.stdout.write(f"{label}: 登録済みのためスキップしました。")
                    continue
                model.objects.bulk_create(loader(path, owner))
                self.stdout.write(f"{label}: 投入しました。")
