import re
from datetime import date

from django.db import migrations, models

MONTH_NUMBERS = {
    name: number
    for number, name in enumerate(
        [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ],
        start=1,
    )
}
MONTH_NAME_PATTERN = re.compile(r"([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{4})")
YEAR_MONTH_PATTERN = re.compile(r"(\d{4})\s*(?:-|/|年)\s*(\d{1,2})")


def parse_year_month(label: str) -> date:
    """取得日の文言（例: Jul 2024、2024-07、2024年7月）を、その月の 1 日の日付に変換する。"""
    match = MONTH_NAME_PATTERN.search(label)
    if match and match.group(1).lower() in MONTH_NUMBERS:
        return date(int(match.group(2)), MONTH_NUMBERS[match.group(1).lower()], 1)
    match = YEAR_MONTH_PATTERN.search(label)
    if match:
        return date(int(match.group(1)), int(match.group(2)), 1)
    raise ValueError(f"資格の取得日を年月として読み取れません: {label!r}")


def convert_acquired_on(apps, schema_editor):
    Certification = apps.get_model("portfolio", "Certification")
    for certification in Certification.objects.all():
        certification.acquired_on_date = parse_year_month(certification.acquired_on)
        certification.save(update_fields=["acquired_on_date"])


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0009_remove_sort_order_from_certification_work"),
    ]

    operations = [
        migrations.AddField(
            model_name="certification",
            name="acquired_on_date",
            field=models.DateField(null=True, verbose_name="取得年月"),
        ),
        migrations.RunPython(convert_acquired_on, migrations.RunPython.noop),
        migrations.RemoveField(model_name="certification", name="acquired_on"),
        migrations.RenameField(
            model_name="certification",
            old_name="acquired_on_date",
            new_name="acquired_on",
        ),
        migrations.AlterField(
            model_name="certification",
            name="acquired_on",
            field=models.DateField(verbose_name="取得年月"),
        ),
        migrations.AddField(
            model_name="work",
            name="achieved_on",
            field=models.DateField(null=True, verbose_name="実績年月"),
        ),
        migrations.AlterModelOptions(
            name="certification",
            options={
                "ordering": ["-acquired_on", "-certification_id"],
                "verbose_name": "資格",
                "verbose_name_plural": "資格",
            },
        ),
        migrations.AlterModelOptions(
            name="work",
            options={
                "ordering": [models.F("achieved_on").desc(nulls_last=True), "-work_id"],
                "verbose_name": "実績",
                "verbose_name_plural": "実績",
            },
        ),
    ]
