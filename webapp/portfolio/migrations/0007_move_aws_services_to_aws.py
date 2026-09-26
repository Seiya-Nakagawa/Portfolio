import importlib

from django.db import migrations

aws_data = importlib.import_module("portfolio.migrations.0006_aws_subcategory_data")

AWS_CATEGORY = aws_data.AWS_CATEGORY
SORT_ORDER_STEP = 10

# 他の製品名・一般名詞と紛らわしいため、接頭辞（Amazon / AWS）なしの名前では
# AWS サービスとみなさない名称（正規化後）。
AMBIGUOUS_NAMES = {
    aws_data.normalize(name)
    for name in [
        "Config", "Connect", "Batch", "Artifact", "Detective", "Translate",
        "Lex", "Chime", "Backup", "VPN", "CDK", "MQ", "SSO", "Budgets",
        "Inspector", "Shield", "Forecast", "Polly", "Directory Service",
    ]
}


def is_aws_service(name: str, lookup: dict[str, str]) -> bool:
    """AWS サービス名として他カテゴリから AWS へ集約する対象かを判定する。"""
    normalized = aws_data.normalize(name)
    if normalized not in lookup:
        return False
    has_prefix = name.strip().lower().startswith(("amazon ", "aws "))
    return has_prefix or normalized not in AMBIGUOUS_NAMES


def merge_into(apps, source, target):
    """source の案件実績を target へ付け替え、source を削除する。"""
    ProjectSkill = apps.get_model("portfolio", "ProjectSkill")
    existing = set(
        ProjectSkill.objects.filter(skill=target).values_list("project_id", flat=True)
    )
    for project_skill in ProjectSkill.objects.filter(skill=source):
        if project_skill.project_id in existing:
            continue
        ProjectSkill.objects.create(
            project_id=project_skill.project_id,
            skill=target,
            version=project_skill.version,
        )
    ProjectSkill.objects.filter(skill=source).delete()
    source.delete()


def move_aws_services(apps, schema_editor):
    Skill = apps.get_model("portfolio", "Skill")
    lookup = aws_data.build_lookup()

    aws_skills = list(Skill.objects.filter(category=AWS_CATEGORY))
    aws_by_name = {aws_data.normalize(s.name): s for s in aws_skills}
    next_order = max((s.sort_order for s in aws_skills), default=0)

    for skill in Skill.objects.exclude(category=AWS_CATEGORY).order_by(
        "category", "sort_order"
    ):
        if not is_aws_service(skill.name, lookup):
            continue
        key = aws_data.normalize(skill.name)
        duplicate = aws_by_name.get(key)
        if duplicate:
            merge_into(apps, skill, duplicate)
            continue
        next_order += SORT_ORDER_STEP
        skill.category = AWS_CATEGORY
        skill.subcategory = lookup[key]
        skill.sort_order = next_order
        skill.save(update_fields=["category", "subcategory", "sort_order"])
        aws_by_name[key] = skill


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0006_aws_subcategory_data"),
    ]

    operations = [
        migrations.RunPython(move_aws_services, migrations.RunPython.noop),
    ]
