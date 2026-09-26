import uuid

from django.core.validators import RegexValidator
from django.db import models

# 年月は YYYY-MM 形式の文字列で保持する。
YEAR_MONTH_VALIDATOR = RegexValidator(
    regex=r"^\d{4}-(0[1-9]|1[0-2])$",
    message="年月は YYYY-MM 形式で入力してください。",
)

# skill_id は半角英小文字・数字・ハイフンで構成する。
SKILL_ID_VALIDATOR = RegexValidator(
    regex=r"^[a-z0-9-]+$",
    message="skill_id は半角英小文字・数字・ハイフンで入力してください。",
)

# 案件識別子の自動採番に使う接頭辞と、UUID から切り出す桁数。
PROJECT_ID_PREFIX = "p-"
PROJECT_ID_HEX_LENGTH = 12


def generate_project_id() -> str:
    """案件の識別子をサーバー側で自動採番する。"""
    return f"{PROJECT_ID_PREFIX}{uuid.uuid4().hex[:PROJECT_ID_HEX_LENGTH]}"


class Skill(models.Model):
    """スキル項目マスタ。"""

    skill_id = models.CharField(
        "スキル項目ID",
        max_length=64,
        primary_key=True,
        validators=[SKILL_ID_VALIDATOR],
    )
    category = models.CharField("種類", max_length=64)
    name = models.CharField("表示名", max_length=128)
    remarks = models.CharField("補足", max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField("表示順")

    class Meta:
        db_table = "skills"
        verbose_name = "スキル項目"
        verbose_name_plural = "スキル項目"
        ordering = ["category", "sort_order"]

    def __str__(self) -> str:
        return f"{self.category} / {self.name}"


class Project(models.Model):
    """案件実績（期間）。"""

    project_id = models.CharField(
        "案件ID",
        max_length=64,
        primary_key=True,
        default=generate_project_id,
        editable=False,
    )
    name = models.CharField("案件名", max_length=255)
    start_year_month = models.CharField(
        "開始年月", max_length=7, validators=[YEAR_MONTH_VALIDATOR]
    )
    # 継続中の案件は空文字列とする。
    end_year_month = models.CharField(
        "終了年月",
        max_length=7,
        blank=True,
        default="",
        validators=[YEAR_MONTH_VALIDATOR],
    )
    skills = models.ManyToManyField(
        Skill, through="ProjectSkill", related_name="projects"
    )

    class Meta:
        db_table = "projects"
        verbose_name = "案件実績"
        verbose_name_plural = "案件実績"
        ordering = ["start_year_month"]

    def __str__(self) -> str:
        return self.name


class ProjectSkill(models.Model):
    """案件ごとの使用スキル実績（縦持ち）。"""

    # 複合主キー（project_id + skill_id）。同一の組み合わせの重複登録を防ぐ。
    pk = models.CompositePrimaryKey("project", "skill")
    project = models.ForeignKey(
        Project,
        verbose_name="案件",
        on_delete=models.CASCADE,
        db_column="project_id",
        related_name="project_skills",
    )
    skill = models.ForeignKey(
        Skill,
        verbose_name="スキル項目",
        on_delete=models.PROTECT,
        db_column="skill_id",
        related_name="project_skills",
    )
    # バージョンの概念がない項目や特定しない場合は空文字列とする。
    version = models.CharField("バージョン", max_length=64, blank=True, default="")

    class Meta:
        db_table = "project_skills"
        verbose_name = "案件使用スキル"
        verbose_name_plural = "案件使用スキル"

    def __str__(self) -> str:
        return f"{self.project_id} / {self.skill_id}"


class Certification(models.Model):
    """資格。"""

    certification_id = models.AutoField("資格ID", primary_key=True)
    name = models.CharField("資格名", max_length=255)
    # 表示用の文言（年月の粒度。例: Jul 2024）。
    acquired_on = models.CharField("取得日", max_length=32)
    org = models.CharField("発行団体", max_length=255)
    sort_order = models.PositiveIntegerField("表示順")

    class Meta:
        db_table = "certifications"
        verbose_name = "資格"
        verbose_name_plural = "資格"
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return self.name


class Work(models.Model):
    """実績（Works）。"""

    work_id = models.AutoField("実績ID", primary_key=True)
    title = models.CharField("タイトル", max_length=255)
    desc_ja = models.TextField("説明文（日本語）")
    desc_en = models.TextField("説明文（英語）", blank=True, default="")
    # 使用技術タグの一覧（JSON 配列）。
    tags = models.JSONField("使用技術タグ", blank=True, default=list)
    thumbnail = models.CharField("サムネイル", max_length=255, blank=True, default="")
    github_url = models.URLField("GitHub URL", max_length=255, blank=True, default="")
    live_url = models.URLField("公開 URL", max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField("表示順")

    class Meta:
        db_table = "works"
        verbose_name = "実績"
        verbose_name_plural = "実績"
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return self.title


# サイト情報は常に 1 行のみとし、この固定値の主キーで参照する。
SITE_INFO_ID = 1


class SiteInfo(models.Model):
    """サイト全体の表示情報（Hero・About・Contact・フッター）。1 行のみ。"""

    site_info_id = models.PositiveSmallIntegerField(
        "サイト情報ID", primary_key=True, default=SITE_INFO_ID, editable=False
    )
    name = models.CharField("氏名", max_length=255)
    # Hero のタイピングアニメーションに表示する肩書きの一覧（JSON 配列）。
    typing_titles = models.JSONField("肩書き", default=list)
    catchphrase = models.CharField("キャッチコピー", max_length=255)
    intro = models.TextField("自己紹介文")
    birth_date = models.DateField("生年月日")
    job = models.CharField("職業", max_length=255)
    education = models.CharField("学歴", max_length=255)
    location = models.CharField("居住地", max_length=255)
    hobby = models.CharField("趣味", max_length=255)
    github_url = models.URLField("GitHub URL", max_length=255)
    contact_message = models.TextField("Contact の案内文")
    contact_form_url = models.URLField("問い合わせフォーム URL", max_length=1024)
    copyright_start_year = models.PositiveSmallIntegerField("著作権の開始年")

    class Meta:
        db_table = "site_info"
        verbose_name = "サイト情報"
        verbose_name_plural = "サイト情報"

    def __str__(self) -> str:
        return self.name
