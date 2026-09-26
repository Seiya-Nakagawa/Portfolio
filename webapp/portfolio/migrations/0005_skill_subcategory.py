from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0004_remove_levels"),
    ]

    operations = [
        migrations.AddField(
            model_name="skill",
            name="subcategory",
            field=models.CharField(
                blank=True, default="", max_length=64, verbose_name="サブカテゴリ"
            ),
        ),
    ]
