"""スキル項目マスタ（種類・スキル項目）の JSON を実績 DB へ追加する。

既に登録済みのスキル項目は変更せず、未登録の項目だけを追加する。再実行しても二重登録にならない。
"""

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portfolio import registry
from portfolio.models import Skill, SkillCategory

SEED_FILE = (
    Path(__file__).resolve().parent.parent.parent / "seed" / "skills_master.json"
)

# 提供元の名称が先頭に付いた表記を、付かない表記と同じ項目として扱うための接頭辞。
VENDOR_PREFIXES = re.compile(
    r"^(amazon|aws|azure|microsoft|oci|oracle|google cloud|google)\s+", re.IGNORECASE
)
# 比較用の名前から除く記号（空白を含む）。
SYMBOLS = re.compile(r"[\s\-_./・]+")
# skill_id に使えない文字の置換。記号は読み替えてから区切り文字にする。
ID_REPLACEMENTS = {"+": "plus", "#": "sharp"}
ID_SEPARATORS = re.compile(r"[^a-z0-9]+")
MAX_SKILL_ID_LENGTH = 64
PARENTHESIS = re.compile(r"^(.*?)\s*[(（](.+?)[)）]\s*$")


def comparison_keys(name: str) -> set[str]:
    """同じ項目かを判定するための比較用の名前を返す。

    「Virtual Private Cloud (VPC)」のように括弧書きの別名がある場合は、本体と別名の両方を返す。
    """
    names = [name]
    match = PARENTHESIS.match(name)
    if match:
        names += [match.group(1), match.group(2)]
    keys = set()
    for item in names:
        stripped = VENDOR_PREFIXES.sub("", item.strip())
        key = SYMBOLS.sub("", stripped).casefold()
        if key:
            keys.add(key)
    return keys


def make_skill_id(prefix: str, name: str, used: set[str]) -> str:
    """名前から skill_id を作る。既に使われている場合は連番を付けて重複を避ける。"""
    text = PARENTHESIS.sub(r"\1", name).strip().lower()
    for symbol, word in ID_REPLACEMENTS.items():
        text = text.replace(symbol, word)
    slug = ID_SEPARATORS.sub("-", text).strip("-") or "skill"
    base = f"{prefix}{slug}"[:MAX_SKILL_ID_LENGTH].rstrip("-")
    candidate, number = base, 1
    while candidate in used:
        number += 1
        suffix = f"-{number}"
        candidate = f"{base[: MAX_SKILL_ID_LENGTH - len(suffix)]}{suffix}"
    used.add(candidate)
    return candidate


def load_master(path: Path) -> list[dict]:
    if not path.is_file():
        raise CommandError(f"投入元のファイルが見つかりません: {path}")
    return json.loads(path.read_text(encoding="utf-8"))["categories"]


class Command(BaseCommand):
    help = "スキル項目マスタの JSON から、未登録の種類・スキル項目を追加する（登録済みの項目は変更しない）。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed-file",
            type=Path,
            default=SEED_FILE,
            help="skills_master.json のパス",
        )

    def handle(self, *args, **options):
        categories = load_master(options["seed_file"])

        with transaction.atomic():
            used_ids = set(Skill.objects.values_list("skill_id", flat=True))
            known_categories = set(registry.category_names())
            existing_keys: dict[str, set[str]] = {}
            for category, name in Skill.objects.values_list("category", "name"):
                existing_keys.setdefault(category, set()).update(comparison_keys(name))

            last = SkillCategory.objects.order_by("-sort_order").first()
            next_category_order = (last.sort_order if last else 0) + 1
            new_skills = []
            for entry in categories:
                category = entry["name"]
                if category not in known_categories:
                    # 新しい種類は末尾に置く。正式な並び順は採番し直しで決まる。
                    SkillCategory.objects.create(
                        name=category, sort_order=next_category_order
                    )
                    next_category_order += 1
                    known_categories.add(category)
                keys = existing_keys.setdefault(category, set())
                for item in entry["skills"]:
                    item_keys = comparison_keys(item["name"])
                    if item_keys & keys:
                        continue
                    keys.update(item_keys)
                    new_skills.append(
                        Skill(
                            skill_id=make_skill_id(
                                entry.get("skill_id_prefix", ""), item["name"], used_ids
                            ),
                            category=category,
                            subcategory=item.get("subcategory", ""),
                            name=item["name"],
                            sort_order=0,
                        )
                    )
            for skill in new_skills:
                skill.full_clean(validate_unique=False)
            Skill.objects.bulk_create(new_skills)
            registry.resequence_skills()

        self.stdout.write(f"スキル項目を {len(new_skills)} 件追加しました。")
