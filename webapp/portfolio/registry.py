"""登録画面の書き込み処理。入力値の検証はここで行い、画面側の入力制限に依存しない。

書き込みはトランザクション内で対象行をロックし、複数タブからの同時操作による不整合を防ぐ。
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from portfolio.models import (
    PROJECT_PHASE_SEPARATOR,
    PROJECT_PHASES,
    SITE_INFO_ID,
    SKILLSHEET_TEXT_KEYS,
    YEAR_MONTH_VALIDATOR,
    Certification,
    Company,
    Project,
    ProjectSkill,
    SiteInfo,
    Skill,
    SkillCategory,
    SkillsheetText,
    Work,
)
from portfolio.services import ordered_skills

MAX_PROJECT_NAME_LENGTH = 255
MAX_VERSION_LENGTH = 64

# 案件の詳細（職務経歴書の記載内容）のうち、1 行の文字列項目と最大文字数。
PROJECT_DETAIL_LINE_FIELDS = {
    "team_size": ("体制", 64),
}


def split_phases(value: str) -> list[str]:
    """保持している担当工程の文字列を、工程の一覧に分ける。"""
    return [p for p in value.split(PROJECT_PHASE_SEPARATOR) if p]


# 複数行の文字列項目。
PROJECT_DETAIL_TEXT_FIELDS = {"overview": "案件概要", "tasks": "業務内容"}
# 1 行を 1 項目とする項目と、整形後の最大文字数。
PROJECT_DETAIL_ITEM_FIELDS = {"environment": ("環境・言語", 512)}


class ValidationFailed(Exception):
    """入力値の検証エラー。画面へ返すメッセージの一覧を保持する。"""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class NotFound(Exception):
    """更新・削除の対象が存在しない。"""


def _validate_year_month(value: str, label: str, errors: list[str]) -> None:
    try:
        YEAR_MONTH_VALIDATOR(value)
    except ValidationError:
        errors.append(f"{label}は YYYY-MM 形式で入力してください。")


def _clean_project_payload(payload: dict) -> tuple[dict, list[dict]]:
    errors: list[str] = []

    name = str(payload.get("name") or "").strip()
    start = str(payload.get("start_year_month") or "").strip()
    end = str(payload.get("end_year_month") or "").strip()

    if not name:
        errors.append("案件名を入力してください。")
    elif len(name) > MAX_PROJECT_NAME_LENGTH:
        errors.append(f"案件名は{MAX_PROJECT_NAME_LENGTH}文字以内で入力してください。")

    if not start:
        errors.append("開始年月を入力してください。")
    else:
        _validate_year_month(start, "開始年月", errors)
    if end:
        _validate_year_month(end, "終了年月", errors)

    # YYYY-MM は文字列比較で年月の前後関係と一致する。形式エラーがない場合のみ比較する。
    if not errors and end and end < start:
        errors.append("終了年月は開始年月以降にしてください。")

    raw_skills = payload.get("skills") or []
    if not isinstance(raw_skills, list):
        errors.append("スキル項目の形式が不正です。")
        raw_skills = []

    skills: list[dict] = []
    seen: set[str] = set()
    for item in raw_skills:
        skill_id = str(item.get("skill_id") or "") if isinstance(item, dict) else ""
        version = (
            str(item.get("version") or "").strip() if isinstance(item, dict) else ""
        )
        if not skill_id:
            errors.append("スキル項目の形式が不正です。")
        elif skill_id in seen:
            errors.append(f"スキル項目が重複しています: {skill_id}")
        elif len(version) > MAX_VERSION_LENGTH:
            errors.append(
                f"バージョンは{MAX_VERSION_LENGTH}文字以内で入力してください: {skill_id}"
            )
        else:
            seen.add(skill_id)
            skills.append({"skill_id": skill_id, "version": version})

    existing = set(
        Skill.objects.filter(skill_id__in=seen).values_list("skill_id", flat=True)
    )
    for skill_id in sorted(seen - existing):
        errors.append(f"存在しないスキル項目です: {skill_id}")

    project_id = str(payload.get("project_id") or "")
    current_phases = (
        Project.objects.filter(pk=project_id).values_list("phases", flat=True).first()
        if project_id
        else None
    )
    details = _clean_project_details(payload, errors, current_phases or "")

    if errors:
        raise ValidationFailed(errors)
    return {
        "name": name,
        "start_year_month": start,
        "end_year_month": end,
        **details,
    }, skills


def _clean_phases(payload: dict, errors: list[str], current_phases: str) -> str:
    """担当工程（選択された工程の配列）を検証し、保持する文字列に整える。

    選択肢にない工程は、その案件に既に保持されている値に限り許可する
    （選択肢の導入前に自由入力された値を、編集時に失わないため）。
    """
    raw = payload.get("phases") or []
    if not isinstance(raw, list) or not all(isinstance(p, str) for p in raw):
        errors.append("担当工程の形式が不正です。")
        return ""
    legacy = [p for p in split_phases(current_phases) if p not in PROJECT_PHASES]
    unknown = sorted(set(raw) - set(PROJECT_PHASES) - set(legacy))
    if unknown:
        errors.append(f"存在しない担当工程です: {'、'.join(unknown)}")
        return ""
    ordered = [p for p in PROJECT_PHASES if p in raw] + [p for p in legacy if p in raw]
    return PROJECT_PHASE_SEPARATOR.join(ordered)


def _clean_project_details(
    payload: dict, errors: list[str], current_phases: str
) -> dict:
    """案件の詳細（会社・体制・案件概要・業務内容・担当工程・環境・言語）を検証する。"""
    details: dict = {}

    for key, (label, max_length) in PROJECT_DETAIL_LINE_FIELDS.items():
        value = str(payload.get(key) or "").strip()
        if len(value) > max_length:
            errors.append(f"{label}は{max_length}文字以内で入力してください。")
        details[key] = value
    for key in PROJECT_DETAIL_TEXT_FIELDS:
        details[key] = str(payload.get(key) or "").strip()
    for key, (label, max_length) in PROJECT_DETAIL_ITEM_FIELDS.items():
        lines = str(payload.get(key) or "").splitlines()
        value = "\n".join(line.strip() for line in lines if line.strip())
        if len(value) > max_length:
            errors.append(f"{label}は{max_length}文字以内で入力してください。")
        details[key] = value

    details["phases"] = _clean_phases(payload, errors, current_phases)

    company_id = payload.get("company_id")
    if company_id in (None, ""):
        details["company_id"] = None
    elif isinstance(company_id, bool) or not str(company_id).isdigit():
        errors.append("会社の形式が不正です。")
    elif not Company.objects.filter(pk=int(company_id)).exists():
        errors.append("存在しない会社です。")
    else:
        details["company_id"] = int(company_id)
    return details


def save_project(payload: dict) -> Project:
    """案件と使用スキルを保存する。既存の使用スキルは削除して置き換える。"""
    fields, skills = _clean_project_payload(payload)
    project_id = payload.get("project_id")

    with transaction.atomic():
        if project_id:
            try:
                project = Project.objects.select_for_update().get(pk=project_id)
            except Project.DoesNotExist:
                raise NotFound("案件が見つかりません。") from None
            for key, value in fields.items():
                setattr(project, key, value)
            project.save()
            ProjectSkill.objects.filter(project=project).delete()
        else:
            project = Project.objects.create(**fields)

        ProjectSkill.objects.bulk_create(
            ProjectSkill(
                project=project, skill_id=item["skill_id"], version=item["version"]
            )
            for item in skills
        )
    return project


def delete_project(project_id: str) -> None:
    """案件を削除する。紐づく使用スキルも同時に削除される。"""
    with transaction.atomic():
        try:
            project = Project.objects.select_for_update().get(pk=project_id)
        except Project.DoesNotExist:
            raise NotFound("案件が見つかりません。") from None
        project.delete()


def _to_int(value, label: str) -> int:
    try:
        return int(value)
    except TypeError, ValueError:
        raise ValidationFailed([f"{label}は整数で入力してください。"]) from None


def _save_model(instance) -> None:
    try:
        instance.full_clean()
    except ValidationError as error:
        labels = {f.name: f.verbose_name for f in instance._meta.fields}
        messages = []
        for field, field_errors in error.message_dict.items():
            label = labels.get(field, "")
            messages.extend(f"{label}: {m}" if label else m for m in field_errors)
        raise ValidationFailed(messages) from None
    instance.save()


def _year_month_to_date(payload: dict, key: str, label: str) -> date:
    """画面の年月（YYYY-MM）を、その月の 1 日の日付に変換する。"""
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValidationFailed([f"{label}を入力してください。"])
    try:
        YEAR_MONTH_VALIDATOR(value)
    except ValidationError:
        raise ValidationFailed(
            [f"{label}は YYYY-MM 形式で入力してください。"]
        ) from None
    return date(int(value[:4]), int(value[5:7]), 1)


def _apply(instance, payload: dict, text_fields: list[str]) -> None:
    for name in text_fields:
        setattr(instance, name, str(payload.get(name) or "").strip())


# 採番し直したスキル項目の表示順の間隔。
SKILL_SORT_ORDER_STEP = 10


MAX_CATEGORY_NAME_LENGTH = 64


def category_names() -> list[str]:
    """種類の並び順を返す。種類マスタの順に、マスタ未登録の種類（スキル項目側のみ）を続ける。"""
    names = list(SkillCategory.objects.values_list("name", flat=True))
    known = set(names)
    for skill in ordered_skills():
        if skill.category not in known:
            known.add(skill.category)
            names.append(skill.category)
    return names


def resequence_skills(category_order: list[str] | None = None) -> None:
    """種類マスタとスキル項目の表示順（sort_order）を、種類の並び順と種類内の昇順に従って採番し直す。

    種類間は category_order（未指定・未掲載の種類は現在の並び順）に従い、種類内は
    サブカテゴリ（未設定は末尾） ＞ 表示名の昇順とする。スキル項目を持たない種類も並び順に含める。
    """
    skills = ordered_skills()
    categories = category_names()
    requested = [c for c in (category_order or []) if c in categories]
    order = requested + [c for c in categories if c not in requested]
    rank = {category: index for index, category in enumerate(order)}
    skills.sort(
        key=lambda s: (
            rank[s.category],
            s.subcategory == "",
            s.subcategory.casefold(),
            s.name.casefold(),
            s.skill_id,
        )
    )
    for index, skill in enumerate(skills, start=1):
        skill.sort_order = index * SKILL_SORT_ORDER_STEP
    Skill.objects.bulk_update(skills, ["sort_order"])

    existing = {c.name: c for c in SkillCategory.objects.all()}
    for name in order:
        category = existing.get(name) or SkillCategory(name=name)
        category.sort_order = (rank[name] + 1) * SKILL_SORT_ORDER_STEP
        category.save()


def _lock_skills() -> None:
    list(Skill.objects.select_for_update().values_list("pk", flat=True))
    list(SkillCategory.objects.select_for_update().values_list("pk", flat=True))


def _clean_category_name(payload: dict) -> str:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValidationFailed(["種類名を入力してください。"])
    if len(name) > MAX_CATEGORY_NAME_LENGTH:
        raise ValidationFailed(
            [f"種類名は{MAX_CATEGORY_NAME_LENGTH}文字以内で入力してください。"]
        )
    if "/" in name:
        raise ValidationFailed(["種類名に「/」は使用できません。"])
    return name


def add_skill_category(payload: dict) -> None:
    """種類を末尾に追加する。"""
    name = _clean_category_name(payload)
    with transaction.atomic():
        _lock_skills()
        if name in category_names():
            raise ValidationFailed([f"種類は既に登録されています: {name}"])
        resequence_skills()
        SkillCategory.objects.create(
            name=name, sort_order=(len(category_names()) + 1) * SKILL_SORT_ORDER_STEP
        )
        resequence_skills()


def rename_skill_category(current: str, payload: dict) -> None:
    """種類名を変更する。対応するスキル項目の種類も同時に更新する。"""
    name = _clean_category_name(payload)
    with transaction.atomic():
        _lock_skills()
        names = category_names()
        if current not in names:
            raise NotFound("種類が見つかりません。")
        if name != current and name in names:
            raise ValidationFailed([f"種類は既に登録されています: {name}"])
        resequence_skills()
        SkillCategory.objects.filter(name=current).update(name=name)
        Skill.objects.filter(category=current).update(category=name)
        resequence_skills()


def delete_skill_category(name: str) -> None:
    """スキル項目が属さない種類のみ削除できる。"""
    with transaction.atomic():
        _lock_skills()
        if name not in category_names():
            raise NotFound("種類が見つかりません。")
        if Skill.objects.filter(category=name).exists():
            raise ValidationFailed(["スキル項目が属する種類は削除できません。"])
        SkillCategory.objects.filter(name=name).delete()
        resequence_skills()


def reorder_skill_categories(payload: dict) -> None:
    """種類単位の並び順を保存する。"""
    categories = payload.get("categories")
    if not isinstance(categories, list) or not all(
        isinstance(c, str) for c in categories
    ):
        raise ValidationFailed(["種類の並び順の形式が不正です。"])
    with transaction.atomic():
        _lock_skills()
        resequence_skills(categories)


def save_skill(payload: dict, skill_id: str | None = None) -> Skill:
    """スキル項目を追加（skill_id 未指定）または変更する。skill_id は変更できない。"""
    with transaction.atomic():
        if skill_id is None:
            new_id = str(payload.get("skill_id") or "").strip()
            if Skill.objects.filter(pk=new_id).exists():
                raise ValidationFailed([f"skill_id は既に登録されています: {new_id}"])
            skill = Skill(skill_id=new_id)
        else:
            try:
                skill = Skill.objects.select_for_update().get(pk=skill_id)
            except Skill.DoesNotExist:
                raise NotFound("スキル項目が見つかりません。") from None

        previous_category = skill.category
        _apply(skill, payload, ["category", "subcategory", "name"])
        # 新規、または種類が変わった項目は末尾に置き、採番し直しで種類内の並びへ収める。
        if skill_id is None or skill.category != previous_category:
            last = Skill.objects.order_by("-sort_order").first()
            skill.sort_order = (last.sort_order if last else 0) + SKILL_SORT_ORDER_STEP
        _save_model(skill)
        resequence_skills()
    return Skill.objects.get(pk=skill.pk)


def delete_skill(skill_id: str) -> None:
    """マスタ項目ではなく、使用実績が紐づかないスキル項目のみ削除できる。"""
    with transaction.atomic():
        try:
            skill = Skill.objects.select_for_update().get(pk=skill_id)
        except Skill.DoesNotExist:
            raise NotFound("スキル項目が見つかりません。") from None
        if skill.is_master:
            raise ValidationFailed(["マスタに登録されたスキル項目は削除できません。"])
        if skill.project_skills.exists():
            raise ValidationFailed(["使用実績が紐づくスキル項目は削除できません。"])
        skill.delete()
        resequence_skills()


def save_certification(
    payload: dict, certification_id: int | None = None
) -> Certification:
    with transaction.atomic():
        if certification_id is None:
            certification = Certification()
        else:
            try:
                certification = Certification.objects.select_for_update().get(
                    pk=certification_id
                )
            except Certification.DoesNotExist:
                raise NotFound("資格が見つかりません。") from None
        _apply(certification, payload, ["name", "org"])
        certification.acquired_on = _year_month_to_date(
            payload, "acquired_on", "取得年月"
        )
        _save_model(certification)
    return certification


def delete_certification(certification_id: int) -> None:
    with transaction.atomic():
        deleted, _ = Certification.objects.filter(pk=certification_id).delete()
        if not deleted:
            raise NotFound("資格が見つかりません。")


def _clean_tags(value) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
        raise ValidationFailed(["使用技術タグは文字列の一覧で指定してください。"])
    return [t.strip() for t in value if t.strip()]


def save_work(payload: dict, work_id: int | None = None) -> Work:
    with transaction.atomic():
        if work_id is None:
            work = Work()
        else:
            try:
                work = Work.objects.select_for_update().get(pk=work_id)
            except Work.DoesNotExist:
                raise NotFound("実績が見つかりません。") from None
        _apply(
            work,
            payload,
            ["title", "desc_ja", "desc_en", "thumbnail", "github_url", "live_url"],
        )
        work.achieved_on = _year_month_to_date(payload, "achieved_on", "実績年月")
        work.tags = _clean_tags(payload.get("tags"))
        _save_model(work)
    return work


def delete_work(work_id: int) -> None:
    with transaction.atomic():
        deleted, _ = Work.objects.filter(pk=work_id).delete()
        if not deleted:
            raise NotFound("実績が見つかりません。")


SITE_INFO_TEXT_FIELDS = [
    "name",
    "catchphrase",
    "intro",
    "job",
    "education",
    "location",
    "hobby",
    "github_url",
    "contact_message",
    "contact_form_url",
]


def save_site_info(payload: dict) -> SiteInfo:
    """サイト情報（1 行のみ）を保存する。未登録の場合は作成する。"""
    with transaction.atomic():
        info = SiteInfo.objects.select_for_update().filter(pk=SITE_INFO_ID).first()
        if info is None:
            info = SiteInfo(site_info_id=SITE_INFO_ID)
        for name in SITE_INFO_TEXT_FIELDS:
            setattr(info, name, str(payload.get(name) or "").strip())
        info.typing_titles = _clean_tags(payload.get("typing_titles"))
        if not info.typing_titles:
            raise ValidationFailed(["肩書き: 1 件以上入力してください。"])
        info.birth_date = str(payload.get("birth_date") or "").strip() or None
        info.copyright_start_year = _to_int(
            payload.get("copyright_start_year"), "著作権の開始年"
        )
        _save_model(info)
    return info


MAX_FULL_NAME_LENGTH = 255
COMPANY_TEXT_FIELDS = [
    "name",
    "department",
    "employment_type",
    "capital",
    "employees",
    "offices",
    "annual_sales",
    "founded",
]


def save_company(payload: dict, company_id: int | None = None) -> Company:
    """会社を追加（company_id 未指定）または変更する。"""
    with transaction.atomic():
        if company_id is None:
            company = Company()
        else:
            try:
                company = Company.objects.select_for_update().get(pk=company_id)
            except Company.DoesNotExist:
                raise NotFound("会社が見つかりません。") from None
        _apply(company, payload, COMPANY_TEXT_FIELDS)
        company.kind = str(payload.get("kind") or "").strip()
        company.start_year_month = str(payload.get("start_year_month") or "").strip()
        company.end_year_month = str(payload.get("end_year_month") or "").strip()

        errors: list[str] = []
        if company.kind not in dict(Company.KIND_CHOICES):
            errors.append("区分は本業または副業を選択してください。")
        if not company.start_year_month:
            errors.append("在籍開始年月を入力してください。")
        if (
            not errors
            and company.end_year_month
            and company.end_year_month < company.start_year_month
        ):
            errors.append("在籍終了年月は在籍開始年月以降にしてください。")
        if errors:
            raise ValidationFailed(errors)
        _save_model(company)
    return company


def delete_company(company_id: int) -> None:
    """所属する案件がない会社のみ削除できる。"""
    with transaction.atomic():
        try:
            company = Company.objects.select_for_update().get(pk=company_id)
        except Company.DoesNotExist:
            raise NotFound("会社が見つかりません。") from None
        if company.projects.exists():
            raise ValidationFailed(["所属する案件がある会社は削除できません。"])
        company.delete()


def save_skillsheet_text(
    key: str, body: str, expected_updated_at: str | None
) -> SkillsheetText:
    """職務経歴書の文章項目を保存する。

    編集開始時の `updated_at` と保存時点の値が一致しない場合は、他のタブ等での保存との
    競合として保存しない。行が存在しない項目は `expected_updated_at` を空として作成する。
    """
    label = SKILLSHEET_TEXT_KEYS.get(key)
    if label is None:
        raise NotFound("職務経歴書の項目が見つかりません。")
    if not isinstance(body, str) or not body.strip():
        raise ValidationFailed([f"{label}を入力してください。"])
    if key == "full_name":
        body = body.strip()
        if "\n" in body or len(body) > MAX_FULL_NAME_LENGTH:
            raise ValidationFailed(
                [f"{label}は{MAX_FULL_NAME_LENGTH}文字以内の 1 行で入力してください。"]
            )

    with transaction.atomic():
        text = SkillsheetText.objects.select_for_update().filter(pk=key).first()
        current = text.updated_at.isoformat() if text else None
        if (expected_updated_at or None) != current:
            raise ValidationFailed(
                [
                    (
                        f"編集を開始した後に{label}が更新されています。"
                        "内容を確認するため、画面を開き直してください。"
                    )
                ]
            )
        if text is None:
            text = SkillsheetText(text_key=key)
        text.body = body
        text.updated_at = timezone.now()
        text.save()
    return text
