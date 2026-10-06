import re

from django.db import migrations

ECS_NAME = "ECS"
# 「ECS (Fargate)」「Amazon ECS(Fargate)」のように Fargate の補足が付いた表記と、単体の「Fargate」。
ECS_FARGATE_PATTERN = re.compile(
    r"^(?:(?:amazon\s+|aws\s+)?ecs\s*\(\s*fargate\s*\)|(?:amazon\s+|aws\s+)?fargate)$",
    re.I,
)
ECS_PATTERN = re.compile(r"^(?:amazon\s+|aws\s+)?ecs$", re.I)


def merge_ecs_fargate(apps, schema_editor):
    """「ECS (Fargate)」と単体の「Fargate」を「ECS」へ一本化する。"""
    Skill = apps.get_model("portfolio", "Skill")
    ProjectSkill = apps.get_model("portfolio", "ProjectSkill")

    skills = list(Skill.objects.order_by("sort_order", "skill_id"))
    sources = [s for s in skills if ECS_FARGATE_PATTERN.match(s.name.strip())]
    targets = [s for s in skills if ECS_PATTERN.match(s.name.strip())]

    for source in sources:
        # 「ECS」が存在しない場合は、表示名のみを「ECS」へ変更して残す。
        if not targets:
            source.name = ECS_NAME
            source.save(update_fields=["name"])
            targets = [source]
            continue

        target = targets[0]
        for project_skill in ProjectSkill.objects.filter(skill_id=source.skill_id):
            # 案件が既に「ECS」を使っている場合は、重複させず付け替え元のみ削除する。
            already_used = ProjectSkill.objects.filter(
                project_id=project_skill.project_id, skill_id=target.skill_id
            ).exists()
            if not already_used:
                ProjectSkill.objects.create(
                    project_id=project_skill.project_id,
                    skill_id=target.skill_id,
                    version=project_skill.version,
                )
            ProjectSkill.objects.filter(
                project_id=project_skill.project_id, skill_id=source.skill_id
            ).delete()
        source.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0013_split_os_middleware_categories"),
    ]

    operations = [
        migrations.RunPython(merge_ecs_fargate, migrations.RunPython.noop),
    ]
