from django.db import migrations, models

OLD_SEPARATOR = "、"


def split_environment(apps, schema_editor):
    """「、」区切りの環境・言語を、1 行 1 項目に変換する。"""
    Project = apps.get_model("portfolio", "Project")
    for project in Project.objects.exclude(environment=""):
        items = [i.strip() for i in project.environment.split(OLD_SEPARATOR)]
        project.environment = "\n".join(i for i in items if i)
        project.save(update_fields=["environment"])


def join_environment(apps, schema_editor):
    Project = apps.get_model("portfolio", "Project")
    for project in Project.objects.exclude(environment=""):
        project.environment = OLD_SEPARATOR.join(project.environment.splitlines())
        project.save(update_fields=["environment"])


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0016_skillsheet_structured_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="environment",
            field=models.TextField(blank=True, default="", verbose_name="環境・言語"),
        ),
        migrations.RunPython(split_environment, join_environment),
    ]
