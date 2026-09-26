import re

from django.db import migrations

AWS_CATEGORY = "AWS"
CONTAINERS_SUBCATEGORY = "Containers"
SORT_ORDER_STEP = 10

# 「ECS (Fargate)」「EKS(Kubernetes)」のように、サービス名に補足が付いた表記も対象とする。
CONTAINER_SERVICE_PATTERN = re.compile(r"^(?:amazon\s+|aws\s+)?(?:ecs|eks)(?![a-z0-9])", re.I)


def resequence(Skill):
    """スキル項目の表示順を、現在の種類の並び順・種類内の昇順（サブカテゴリ ＞ 表示名）で採番し直す。"""
    skills = list(Skill.objects.order_by("sort_order", "skill_id"))
    category_rank: dict[str, int] = {}
    for skill in skills:
        category_rank.setdefault(skill.category, len(category_rank))
    skills.sort(
        key=lambda s: (
            category_rank[s.category],
            s.subcategory == "",
            s.subcategory.casefold(),
            s.name.casefold(),
            s.skill_id,
        )
    )
    for index, skill in enumerate(skills, start=1):
        skill.sort_order = index * SORT_ORDER_STEP
    Skill.objects.bulk_update(skills, ["sort_order"])


def move_container_skills(apps, schema_editor):
    Skill = apps.get_model("portfolio", "Skill")
    last = Skill.objects.order_by("-sort_order").first()
    next_order = last.sort_order if last else 0
    for skill in Skill.objects.exclude(category=AWS_CATEGORY).order_by("sort_order"):
        if not CONTAINER_SERVICE_PATTERN.match(skill.name.strip()):
            continue
        next_order += SORT_ORDER_STEP
        skill.category = AWS_CATEGORY
        skill.subcategory = CONTAINERS_SUBCATEGORY
        skill.sort_order = next_order
        skill.save(update_fields=["category", "subcategory", "sort_order"])
    resequence(Skill)


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0007_move_aws_services_to_aws"),
    ]

    operations = [
        migrations.RunPython(move_container_skills, migrations.RunPython.noop),
    ]
