from django.db import migrations

# 習熟度レベル（1〜5）の初期値。(level, portfolio_label, resume_label)
LEVELS = [
    (
        5,
        "スペシャリスト (広範な知識と高い専門性)",
        "広範な知識と高い専門性をもって技術選定・標準化ができる",
    ),
    (
        4,
        "上級 (中規模システム以上の設計・実装能力)",
        "中規模システム以上の設計・実装ができる",
    ),
    (3, "中級 (一人称で開発可能)", "一人称で設計・開発ができる"),
    (2, "初級 (実務経験あり)", "実務での使用経験があり、指示のもとで作業ができる"),
    (1, "入門 (基礎学習済み)", "基礎を学習済みで、手順書をもとに作業ができる"),
]


def insert_levels(apps, schema_editor):
    Level = apps.get_model("portfolio", "Level")
    for level, portfolio_label, resume_label in LEVELS:
        Level.objects.update_or_create(
            level=level,
            defaults={
                "portfolio_label": portfolio_label,
                "resume_label": resume_label,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0001_initial"),
    ]

    operations = [
        # 逆方向は何もしない（テーブル削除は 0001 の巻き戻しで行われる）。
        migrations.RunPython(insert_levels, migrations.RunPython.noop),
    ]
