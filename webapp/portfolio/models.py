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


class SkillCategory(models.Model):
    """スキル項目の種類マスタ。種類の一覧と並び順を保持する。"""

    name = models.CharField("種類名", max_length=64, unique=True)
    sort_order = models.PositiveIntegerField("表示順")

    class Meta:
        db_table = "skill_categories"
        verbose_name = "スキル項目の種類"
        verbose_name_plural = "スキル項目の種類"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.name


class Skill(models.Model):
    """スキル項目マスタ。"""

    skill_id = models.CharField(
        "スキル項目ID",
        max_length=64,
        primary_key=True,
        validators=[SKILL_ID_VALIDATOR],
    )
    category = models.CharField("種類", max_length=64)
    subcategory = models.CharField(
        "サブカテゴリ", max_length=64, blank=True, default=""
    )
    name = models.CharField("表示名", max_length=128)
    sort_order = models.PositiveIntegerField("表示順")

    class Meta:
        db_table = "skills"
        verbose_name = "スキル項目"
        verbose_name_plural = "スキル項目"
        ordering = ["category", "sort_order"]

    def __str__(self) -> str:
        return f"{self.category} / {self.name}"


# 担当工程の選択肢。出力順に並べる。
PROJECT_PHASES = [
    "要件定義",
    "基本設計",
    "詳細設計",
    "実装",
    "単体テスト",
    "結合テスト",
    "総合テスト",
    "運用・保守",
]
# 担当工程を 1 つの文字列に保持するときの区切り。
PROJECT_PHASE_SEPARATOR = "、"


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
    # 以下は職務経歴書にのみ用いる任意項目。
    company = models.ForeignKey(
        "Company",
        verbose_name="会社",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="company_id",
        related_name="projects",
    )
    team_size = models.CharField("体制", max_length=64, blank=True, default="")
    overview = models.TextField("案件概要", blank=True, default="")
    # 1 行を 1 項目とする。
    tasks = models.TextField("業務内容", blank=True, default="")
    # 選択した工程を PROJECT_PHASES の順に PROJECT_PHASE_SEPARATOR で連結して保持する。
    phases = models.CharField("担当工程", max_length=255, blank=True, default="")
    environment = models.CharField("環境・言語", max_length=512, blank=True, default="")

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
    # 年月の粒度で管理し、その月の 1 日を保持する。表示（YYYY年MM月）は出力時に整形する。
    acquired_on = models.DateField("取得年月")
    org = models.CharField("発行団体", max_length=255)

    class Meta:
        db_table = "certifications"
        verbose_name = "資格"
        verbose_name_plural = "資格"
        ordering = ["acquired_on", "certification_id"]

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
    # 年月の粒度で管理し、その月の 1 日を保持する。日付導入前の登録分は未設定（null）を許容する。
    achieved_on = models.DateField("実績年月", null=True)

    class Meta:
        db_table = "works"
        verbose_name = "実績"
        verbose_name_plural = "実績"
        ordering = [models.F("achieved_on").desc(nulls_last=True), "-work_id"]

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


class Company(models.Model):
    """会社（職務経歴書の開発経歴・副業の見出し単位）。"""

    KIND_MAIN = "main"
    KIND_SIDE = "side"
    KIND_CHOICES = [(KIND_MAIN, "本業"), (KIND_SIDE, "副業")]

    company_id = models.AutoField("会社ID", primary_key=True)
    name = models.CharField("会社名", max_length=255)
    department = models.CharField("部署名", max_length=255, blank=True, default="")
    employment_type = models.CharField(
        "雇用・契約形態", max_length=64, blank=True, default=""
    )
    kind = models.CharField("区分", max_length=8, choices=KIND_CHOICES)
    start_year_month = models.CharField(
        "在籍開始年月", max_length=7, validators=[YEAR_MONTH_VALIDATOR]
    )
    # 在籍中は空文字列とする。
    end_year_month = models.CharField(
        "在籍終了年月",
        max_length=7,
        blank=True,
        default="",
        validators=[YEAR_MONTH_VALIDATOR],
    )
    # 会社概要は職務経歴書に記載する文言をそのまま保持する（集計に用いない）。
    capital = models.CharField("資本金", max_length=64, blank=True, default="")
    employees = models.CharField("従業員数", max_length=64, blank=True, default="")
    offices = models.CharField("拠点数", max_length=64, blank=True, default="")
    annual_sales = models.CharField("年商", max_length=64, blank=True, default="")
    founded = models.CharField("設立", max_length=64, blank=True, default="")

    class Meta:
        db_table = "companies"
        verbose_name = "会社"
        verbose_name_plural = "会社"
        ordering = ["kind", "-start_year_month", "company_id"]

    def __str__(self) -> str:
        return self.name


# 職務経歴書の文章項目のキー。画面から追加・削除しない。
SKILLSHEET_TEXT_KEYS = {
    "full_name": "氏名",
    "summary": "職務概要",
    "strengths": "活かせる経験・得意分野",
    "self_pr": "自己PR",
}


class SkillsheetText(models.Model):
    """職務経歴書の文章項目。項目ごとに最新版のみを保持する。"""

    text_key = models.CharField("項目キー", max_length=32, primary_key=True)
    body = models.TextField("内容")
    updated_at = models.DateTimeField("最終更新日時")

    class Meta:
        db_table = "skillsheet_texts"
        verbose_name = "職務経歴書の文章項目"
        verbose_name_plural = "職務経歴書の文章項目"

    def __str__(self) -> str:
        return self.text_key
