"""登録画面の書き込み処理。入力値の検証はここで行い、画面側の入力制限に依存しない。

書き込みはトランザクション内で対象行をロックし、複数タブからの同時操作による不整合を防ぐ。
"""

import secrets
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from portfolio.media_files import delete_unreferenced_image
from portfolio.media_paths import USER_IMAGE_PATH, work_image_dir
from portfolio.models import (
    PROJECT_PHASE_SEPARATOR,
    PROJECT_PHASES,
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


class Forbidden(Exception):
    """権限のない操作。"""


class TooManyRequests(Exception):
    """流量制限を超えた呼び出し。超えた対象（`scope`）を保持する。"""

    def __init__(self, message: str, scope: str):
        super().__init__(message)
        self.scope = scope


def _validate_year_month(value: str, label: str, errors: list[str]) -> None:
    try:
        YEAR_MONTH_VALIDATOR(value)
    except ValidationError:
        errors.append(f"{label}は YYYY-MM 形式で入力してください。")


def _clean_project_payload(owner, payload: dict) -> tuple[dict, list[dict]]:
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

    # 参照できるのは共通マスタと自分の独自スキル項目のみ。他のユーザーの項目は存在しないものとして扱う。
    existing = set(
        Skill.objects.visible_to(owner)
        .filter(skill_id__in=seen)
        .values_list("skill_id", flat=True)
    )
    for skill_id in sorted(seen - existing):
        errors.append(f"存在しないスキル項目です: {skill_id}")

    project_id = str(payload.get("project_id") or "")
    current_phases = (
        Project.objects.for_owner(owner)
        .filter(pk=project_id)
        .values_list("phases", flat=True)
        .first()
        if project_id
        else None
    )
    details = _clean_project_details(owner, payload, errors, current_phases or "")

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
    owner, payload: dict, errors: list[str], current_phases: str
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
    elif not Company.objects.for_owner(owner).filter(pk=int(company_id)).exists():
        errors.append("存在しない会社です。")
    else:
        details["company_id"] = int(company_id)
    return details


def save_project(owner, payload: dict) -> Project:
    """案件と使用スキルを保存する。既存の使用スキルは削除して置き換える。

    所有者は常に `owner`（ログインしたユーザー）とし、リクエストの値は用いない。
    """
    fields, skills = _clean_project_payload(owner, payload)
    project_id = payload.get("project_id")

    with transaction.atomic():
        if project_id:
            try:
                project = (
                    Project.objects.for_owner(owner)
                    .select_for_update()
                    .get(pk=project_id)
                )
            except Project.DoesNotExist:
                raise NotFound("案件が見つかりません。") from None
            for key, value in fields.items():
                setattr(project, key, value)
            project.save()
            ProjectSkill.objects.filter(project=project).delete()
        else:
            project = Project.objects.create(owner=owner, **fields)

        ProjectSkill.objects.bulk_create(
            ProjectSkill(
                project=project, skill_id=item["skill_id"], version=item["version"]
            )
            for item in skills
        )
    return project


def delete_project(owner, project_id: str) -> None:
    """案件を削除する。紐づく使用スキルも同時に削除される。"""
    with transaction.atomic():
        try:
            project = (
                Project.objects.for_owner(owner).select_for_update().get(pk=project_id)
            )
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


# 採番し直した共通マスタの表示順の間隔。
SKILL_SORT_ORDER_STEP = 10
# 独自スキル項目の表示順は 0 とし、表示順は表示時に決める。
CUSTOM_SKILL_SORT_ORDER = 0
# 独自スキル項目の識別子は、接頭辞に推測されにくい文字列を続けて採番する。
CUSTOM_SKILL_ID_PREFIX = "u-"
CUSTOM_SKILL_ID_BYTES = 8

MAX_CATEGORY_NAME_LENGTH = 64


def _require_operator(user, action: str) -> None:
    if not user.is_staff:
        raise Forbidden(f"{action}は運営者のみ行えます。")


def category_names() -> list[str]:
    """種類の並び順を返す。種類マスタの順に、マスタ未登録の種類（共通マスタ側のみ）を続ける。"""
    names = list(SkillCategory.objects.values_list("name", flat=True))
    known = set(names)
    for skill in ordered_skills(None):
        if skill.category not in known:
            known.add(skill.category)
            names.append(skill.category)
    return names


def resequence_skills(category_order: list[str] | None = None) -> None:
    """種類マスタと共通マスタの表示順（sort_order）を、種類の並び順と種類内の昇順に従って採番し直す。

    種類間は category_order（未指定・未掲載の種類は現在の並び順）に従い、種類内は
    サブカテゴリ（未設定は末尾） ＞ 表示名の昇順とする。スキル項目を持たない種類も並び順に含める。
    独自スキル項目は全ユーザーに共通する表示順を持たないため、対象にしない。
    """
    skills = ordered_skills(None)
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
    list(
        Skill.objects.filter(owner__isnull=True)
        .select_for_update()
        .values_list("pk", flat=True)
    )
    list(SkillCategory.objects.select_for_update().values_list("pk", flat=True))


def _lock_categories() -> None:
    """種類の行を排他ロックする。種類の名称変更・削除と、独自スキル項目の保存を直列化する。

    ロックの順序は `_lock_skills`（共通マスタ → 種類）と合わせ、独自スキル項目の行をロックする前に取る。
    """
    list(SkillCategory.objects.select_for_update().values_list("pk", flat=True))


def _category_exists_locked(name: str) -> bool:
    """種類が存在するかを、最新の内容（ロック読み取り）で確認する。"""
    if SkillCategory.objects.select_for_update().filter(name=name).exists():
        return True
    # 種類マスタの行を持たない種類（共通マスタ側のみに存在するもの）。
    return (
        Skill.objects.select_for_update()
        .filter(owner__isnull=True, category=name)
        .exists()
    )


def merge_custom_skills_into_master(master: Skill) -> int:
    """共通マスタの項目と同じ種類・名前の独自スキル項目を、共通マスタの項目へ統合し、統合した件数を返す。

    独自スキル項目の使用実績は共通マスタの項目へ付け替える。同じ案件にすでに共通マスタの項目の
    使用実績がある場合は、独自スキル項目の使用実績を削除する。呼び出し元のトランザクション内で行う。
    """
    name = master.name.casefold()
    duplicates = [
        skill
        for skill in Skill.objects.filter(
            owner__isnull=False, category=master.category
        ).select_for_update()
        if skill.name.casefold() == name
    ]
    for duplicate in duplicates:
        already = ProjectSkill.objects.filter(skill=master).values("project_id")
        ProjectSkill.objects.filter(skill=duplicate, project_id__in=already).delete()
        ProjectSkill.objects.filter(skill=duplicate).update(skill=master)
        duplicate.delete()
    return len(duplicates)


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


def add_skill_category(user, payload: dict) -> None:
    """種類を末尾に追加する（運営者のみ）。"""
    _require_operator(user, "種類の追加")
    name = _clean_category_name(payload)
    with transaction.atomic():
        _lock_skills()
        if name in category_names():
            raise ValidationFailed([f"種類は既に登録されています: {name}"])
        resequence_skills()
        SkillCategory.objects.create(
            name=name,
            sort_order=(len(category_names()) + 1) * SKILL_SORT_ORDER_STEP,
        )
        resequence_skills()


def rename_skill_category(user, current: str, payload: dict) -> None:
    """種類名を変更する（運営者のみ）。全ユーザーの独自スキル項目を含め、対応する種類も同時に更新する。"""
    _require_operator(user, "種類名の変更")
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


def delete_skill_category(user, name: str) -> None:
    """スキル項目（全ユーザーの独自スキル項目を含む）が属さない種類のみ削除できる（運営者のみ）。"""
    _require_operator(user, "種類の削除")
    with transaction.atomic():
        _lock_skills()
        if name not in category_names():
            raise NotFound("種類が見つかりません。")
        if Skill.objects.filter(category=name).exists():
            raise ValidationFailed(["スキル項目が属する種類は削除できません。"])
        SkillCategory.objects.filter(name=name).delete()
        resequence_skills()


def reorder_skill_categories(user, payload: dict) -> None:
    """種類単位の並び順を保存する（運営者のみ）。"""
    _require_operator(user, "種類の並び替え")
    categories = payload.get("categories")
    if not isinstance(categories, list) or not all(
        isinstance(c, str) for c in categories
    ):
        raise ValidationFailed(["種類の並び順の形式が不正です。"])
    with transaction.atomic():
        _lock_skills()
        resequence_skills(categories)


def _generate_custom_skill_id() -> str:
    while True:
        skill_id = f"{CUSTOM_SKILL_ID_PREFIX}{secrets.token_hex(CUSTOM_SKILL_ID_BYTES)}"
        if not Skill.objects.filter(pk=skill_id).exists():
            return skill_id


def _check_custom_skill_name(user, skill: Skill) -> None:
    """独自スキル項目の名前が、共通マスタと自分の同じ種類の項目に重複しないことを確認する。"""
    name = skill.name.casefold()
    for other in Skill.objects.visible_to(user).filter(category=skill.category):
        if other.pk == skill.pk or other.name.casefold() != name:
            continue
        if other.owner_id is None:
            raise ValidationFailed(
                [
                    f"共通マスタに同じ項目があります。共通マスタの「{other.name}」を選んでください。"
                ]
            )
        raise ValidationFailed(["同じ種類に同じ名前の項目が既に登録されています。"])


def _new_skill(user, payload: dict) -> Skill:
    """追加するスキル項目を用意する。運営者は共通マスタ、それ以外のユーザーは独自スキル項目になる。"""
    if user.is_staff:
        new_id = str(payload.get("skill_id") or "").strip()
        if Skill.objects.filter(pk=new_id).exists():
            raise ValidationFailed([f"skill_id は既に登録されています: {new_id}"])
        return Skill(skill_id=new_id, is_master=True)
    return Skill(
        skill_id=_generate_custom_skill_id(),
        owner=user,
        is_master=False,
        sort_order=CUSTOM_SKILL_SORT_ORDER,
    )


def save_skill(user, payload: dict, skill_id: str | None = None) -> Skill:
    """スキル項目を追加（skill_id 未指定）または変更する。skill_id は変更できない。

    運営者は共通マスタを、それ以外のユーザーは自分の独自スキル項目のみ追加・変更できる。
    独自スキル項目の種類は既存の種類から選び、識別子は自動採番する。
    """
    with transaction.atomic():
        if not user.is_staff:
            # 種類の名称変更・削除と直列化する（独自スキル項目の行をロックする前に取る）。
            _lock_categories()
        if skill_id is None:
            skill = _new_skill(user, payload)
        else:
            try:
                skill = (
                    Skill.objects.visible_to(user).select_for_update().get(pk=skill_id)
                )
            except Skill.DoesNotExist:
                raise NotFound("スキル項目が見つかりません。") from None
            if skill.owner_id is None and not user.is_staff:
                raise Forbidden("共通マスタは変更できません。")

        previous_category = skill.category
        _apply(skill, payload, ["category", "subcategory", "name"])

        if skill.owner_id is not None:
            if (
                skill_id is None or skill.category != previous_category
            ) and not _category_exists_locked(skill.category):
                raise ValidationFailed(["種類は既存の種類から選択してください。"])
            _check_custom_skill_name(user, skill)
            _save_model(skill)
        else:
            _lock_skills()
            # 新規、または種類が変わった項目は末尾に置き、採番し直しで種類内の並びへ収める。
            if skill_id is None or skill.category != previous_category:
                last = (
                    Skill.objects.filter(owner__isnull=True)
                    .order_by("-sort_order")
                    .first()
                )
                skill.sort_order = (
                    last.sort_order if last else 0
                ) + SKILL_SORT_ORDER_STEP
            _save_model(skill)
            # 同じ種類・名前の独自スキル項目が二重に表示されないよう、共通マスタへ統合する。
            merge_custom_skills_into_master(skill)
            resequence_skills()
    return Skill.objects.get(pk=skill.pk)


def delete_skill(user, skill_id: str) -> None:
    """自分の独自スキル項目のうち、使用実績が紐づかないものだけ削除できる。共通マスタは削除できない。"""
    with transaction.atomic():
        try:
            skill = Skill.objects.visible_to(user).select_for_update().get(pk=skill_id)
        except Skill.DoesNotExist:
            raise NotFound("スキル項目が見つかりません。") from None
        if skill.owner_id is None:
            raise Forbidden("共通マスタは削除できません。")
        if skill.project_skills.exists():
            raise ValidationFailed(["使用実績が紐づくスキル項目は削除できません。"])
        skill.delete()


def save_certification(
    owner, payload: dict, certification_id: int | None = None
) -> Certification:
    with transaction.atomic():
        if certification_id is None:
            certification = Certification(owner=owner)
        else:
            try:
                certification = (
                    Certification.objects.for_owner(owner)
                    .select_for_update()
                    .get(pk=certification_id)
                )
            except Certification.DoesNotExist:
                raise NotFound("資格が見つかりません。") from None
        _apply(certification, payload, ["name", "org"])
        certification.acquired_on = _year_month_to_date(
            payload, "acquired_on", "取得年月"
        )
        _save_model(certification)
    return certification


def delete_certification(owner, certification_id: int) -> None:
    with transaction.atomic():
        deleted, _ = (
            Certification.objects.for_owner(owner).filter(pk=certification_id).delete()
        )
        if not deleted:
            raise NotFound("資格が見つかりません。")


def _clean_tags(value) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
        raise ValidationFailed(["使用技術タグは文字列の一覧で指定してください。"])
    return [t.strip() for t in value if t.strip()]


def _check_thumbnail(owner, thumbnail: str) -> None:
    """ユーザーごとの保存先の画像を指す場合は、自分の保存先のみ指定できる。"""
    if not thumbnail.startswith("users/"):
        return
    # 「..」で別のユーザーの画像を指せないよう、許可する形式に完全一致するものだけを受け付ける。
    if not USER_IMAGE_PATH.match(thumbnail) or not thumbnail.startswith(
        f"{work_image_dir(owner.pk)}/"
    ):
        raise ValidationFailed(["サムネイル: 自分の画像のみ指定できます。"])


def save_work(owner, payload: dict, work_id: int | None = None) -> Work:
    with transaction.atomic():
        if work_id is None:
            work = Work(owner=owner)
        else:
            try:
                work = Work.objects.for_owner(owner).select_for_update().get(pk=work_id)
            except Work.DoesNotExist:
                raise NotFound("実績が見つかりません。") from None
        previous_thumbnail = work.thumbnail
        _apply(
            work,
            payload,
            ["title", "desc_ja", "desc_en", "thumbnail", "github_url", "live_url"],
        )
        _check_thumbnail(owner, work.thumbnail)
        work.achieved_on = _year_month_to_date(payload, "achieved_on", "実績年月")
        work.tags = _clean_tags(payload.get("tags"))
        _save_model(work)
    # 画像を差し替えた場合は、参照されなくなった画像を削除する。
    if previous_thumbnail and previous_thumbnail != work.thumbnail:
        delete_unreferenced_image(owner, previous_thumbnail)
    return work


def delete_work(owner, work_id: int) -> None:
    with transaction.atomic():
        work = Work.objects.for_owner(owner).filter(pk=work_id).first()
        if work is None:
            raise NotFound("実績が見つかりません。")
        thumbnail = work.thumbnail
        work.delete()
    if thumbnail:
        delete_unreferenced_image(owner, thumbnail)


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


def save_site_info(owner, payload: dict) -> SiteInfo:
    """サイト情報（ユーザーごとに 1 行）を保存する。未登録の場合は作成する。"""
    with transaction.atomic():
        info = SiteInfo.objects.for_owner(owner).select_for_update().first()
        if info is None:
            info = SiteInfo(owner=owner)
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


def save_company(owner, payload: dict, company_id: int | None = None) -> Company:
    """会社を追加（company_id 未指定）または変更する。"""
    with transaction.atomic():
        if company_id is None:
            company = Company(owner=owner)
        else:
            try:
                company = (
                    Company.objects.for_owner(owner)
                    .select_for_update()
                    .get(pk=company_id)
                )
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


def delete_company(owner, company_id: int) -> None:
    """所属する案件がない会社のみ削除できる。"""
    with transaction.atomic():
        try:
            company = (
                Company.objects.for_owner(owner).select_for_update().get(pk=company_id)
            )
        except Company.DoesNotExist:
            raise NotFound("会社が見つかりません。") from None
        if company.projects.exists():
            raise ValidationFailed(["所属する案件がある会社は削除できません。"])
        company.delete()


def save_skillsheet_text(
    owner, key: str, body: str, expected_updated_at: str | None
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
        text = (
            SkillsheetText.objects.for_owner(owner)
            .select_for_update()
            .filter(text_key=key)
            .first()
        )
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
            text = SkillsheetText(owner=owner, text_key=key)
        text.body = body
        text.updated_at = timezone.now()
        text.save()
    return text
