"""登録画面（本人のログインが必要）のページと JSON API。"""

import json
from collections import Counter
from functools import wraps
from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from portfolio import export, ratelimit, registry, uploads, usage
from portfolio.models import (
    PROJECT_PHASES,
    SKILLSHEET_TEXT_KEYS,
    Certification,
    Company,
    Project,
    SiteInfo,
    Skill,
    SkillsheetText,
    UsageDaily,
    Work,
)
from portfolio.services import (
    build_skill_rows,
    ordered_certifications,
    ordered_skills,
    ordered_works,
)


def _json(data, status: int = 200) -> JsonResponse:
    return JsonResponse(
        data, status=status, safe=False, json_dumps_params={"ensure_ascii": False}
    )


def api_view(*methods: str):
    """ログイン必須・メソッド制限・エラー応答の共通処理を行う API ビューのデコレータ。"""

    def decorator(view):
        @wraps(view)
        @require_http_methods(list(methods))
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return _json({"errors": ["ログインが必要です。"]}, status=401)
            try:
                return view(request, *args, **kwargs)
            except registry.ValidationFailed as error:
                return _json({"errors": error.errors}, status=400)
            except registry.NotFound as error:
                return _json({"errors": [str(error)]}, status=404)
            except registry.Forbidden as error:
                return _json({"errors": [str(error)]}, status=403)
            except registry.TooManyRequests as error:
                response = _json({"errors": [str(error)]}, status=429)
                response["Retry-After"] = str(ratelimit.retry_after(error.scope))
                return response

        return wrapper

    return decorator


def _require_operator(user) -> None:
    """運営者のみが使える API（実績・サイト情報）で、一般ユーザーを拒否する。"""
    if not user.is_staff:
        raise registry.Forbidden("この機能は運営者のみ利用できます。")


def _limit_per_user(user, scope: str) -> None:
    """ユーザーごとの流量制限を数え、上限を超えた場合は例外とする。"""
    if not ratelimit.hit(scope, str(user.pk)):
        raise registry.TooManyRequests(
            "操作が集中しています。しばらく待ってから再度お試しください。", scope
        )


def _body(request) -> dict:
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise registry.ValidationFailed(["リクエストの形式が不正です。"]) from None
    if not isinstance(body, dict):
        raise registry.ValidationFailed(["リクエストの形式が不正です。"])
    return body


def _skill_dict(skill: Skill, years: str = "", user=None) -> dict:
    """スキル項目の表示用データ。`editable` は、ログインしたユーザーが変更できるか。"""
    is_custom = skill.owner_id is not None
    return {
        "skill_id": skill.skill_id,
        "category": skill.category,
        "subcategory": skill.subcategory,
        "name": skill.name,
        "is_master": skill.is_master,
        "is_custom": is_custom,
        "editable": is_custom or bool(user and user.is_staff),
        "years": years,
    }


def _project_dict(project: Project) -> dict:
    return {
        "project_id": project.project_id,
        "name": project.name,
        "start_year_month": project.start_year_month,
        "end_year_month": project.end_year_month,
        "company_id": project.company_id,
        "team_size": project.team_size,
        "overview": project.overview,
        "tasks": project.tasks,
        "phases": registry.split_phases(project.phases),
        "environment": project.environment,
        "skills": [
            {"skill_id": ps.skill_id, "version": ps.version}
            for ps in project.project_skills.order_by("skill_id")
        ],
    }


COMPANY_FIELDS = [
    "company_id",
    "name",
    "department",
    "employment_type",
    "kind",
    "start_year_month",
    "end_year_month",
    "capital",
    "employees",
    "offices",
    "annual_sales",
    "founded",
]


def _company_dict(company: Company, project_count: int) -> dict:
    return {
        **{name: getattr(company, name) for name in COMPANY_FIELDS},
        "project_count": project_count,
    }


def _companies(owner) -> list[dict]:
    counts = Counter(
        Project.objects.for_owner(owner)
        .exclude(company=None)
        .values_list("company_id", flat=True)
    )
    return [
        _company_dict(c, counts.get(c.company_id, 0))
        for c in Company.objects.for_owner(owner)
    ]


def _certification_dict(c: Certification) -> dict:
    return {
        "certification_id": c.certification_id,
        "name": c.name,
        "acquired_on": c.acquired_on.strftime("%Y-%m"),
        "org": c.org,
    }


def _work_dict(w: Work) -> dict:
    return {
        "work_id": w.work_id,
        "title": w.title,
        "achieved_on": w.achieved_on.strftime("%Y-%m") if w.achieved_on else "",
        "desc_ja": w.desc_ja,
        "desc_en": w.desc_en,
        "tags": w.tags,
        "thumbnail": w.thumbnail,
        "github_url": w.github_url,
        "live_url": w.live_url,
    }


def _ongoing_projects(owner):
    """継続中（終了年月が未設定）の案件を、開始年月の降順で返す。"""
    return (
        Project.objects.for_owner(owner)
        .filter(end_year_month="")
        .order_by("-start_year_month", "project_id")
    )


def _finished_projects(owner):
    """終了済み（終了年月が設定済み）の案件を、終了年月・開始年月の降順で返す。"""
    return (
        Project.objects.for_owner(owner)
        .exclude(end_year_month="")
        .order_by("-end_year_month", "-start_year_month", "project_id")
    )


def _skills_with_years(owner) -> list[dict]:
    years_by_skill = {
        row.skill.skill_id: row.years
        for row in build_skill_rows(owner, timezone.localdate())
    }
    return [
        _skill_dict(s, years_by_skill.get(s.skill_id, ""), owner)
        for s in ordered_skills(owner)
    ]


@login_required
@ensure_csrf_cookie
@require_http_methods(["GET"])
def index(request):
    return render(request, "manage/index.html")


@api_view("GET")
def api_bootstrap(request):
    """案件登録の初期表示データ。"""
    owner = request.user
    ongoing = list(_ongoing_projects(owner))
    return _json(
        {
            "skills": _skills_with_years(owner),
            "categories": registry.category_names(),
            "is_operator": owner.is_staff,
            "companies": _companies(owner),
            "phases": PROJECT_PHASES,
            "ongoing_projects": [
                {"project_id": p.project_id, "name": p.name} for p in ongoing
            ],
            "finished_projects": [
                {
                    "project_id": p.project_id,
                    "name": p.name,
                    "start_year_month": p.start_year_month,
                    "end_year_month": p.end_year_month,
                }
                for p in _finished_projects(owner)
            ],
            "initial_project": _project_dict(ongoing[0]) if ongoing else None,
        }
    )


@api_view("GET", "DELETE")
def api_project(request, project_id):
    if request.method == "DELETE":
        registry.delete_project(request.user, project_id)
        return _json({"ok": True})
    try:
        return _json(
            _project_dict(Project.objects.for_owner(request.user).get(pk=project_id))
        )
    except Project.DoesNotExist:
        raise registry.NotFound("案件が見つかりません。") from None


@api_view("POST")
def api_projects(request):
    project = registry.save_project(request.user, _body(request))
    return _json(_project_dict(project))


@api_view("GET", "POST")
def api_skills(request):
    if request.method == "POST":
        registry.save_skill(request.user, _body(request))
    return _json(_skills_with_years(request.user))


def _categories(user) -> list[dict]:
    """種類の一覧。項目数は、運営者は全ユーザーの項目、それ以外は参照できる項目を数える。"""
    skills = Skill.objects.all() if user.is_staff else Skill.objects.visible_to(user)
    counts = Counter(skills.values_list("category", flat=True))
    return [
        {"name": name, "skill_count": counts.get(name, 0)}
        for name in registry.category_names()
    ]


@api_view("GET", "POST")
def api_categories(request):
    if request.method == "POST":
        registry.add_skill_category(request.user, _body(request))
    return _json(_categories(request.user))


@api_view("POST")
def api_category_order(request):
    """種類単位の並び順を保存する。"""
    registry.reorder_skill_categories(request.user, _body(request))
    return _json(_categories(request.user))


@api_view("PUT", "DELETE")
def api_category(request, category_name):
    if request.method == "DELETE":
        registry.delete_skill_category(request.user, category_name)
    else:
        registry.rename_skill_category(request.user, category_name, _body(request))
    return _json(_categories(request.user))


@api_view("PUT", "DELETE")
def api_skill(request, skill_id):
    if request.method == "DELETE":
        registry.delete_skill(request.user, skill_id)
    else:
        registry.save_skill(request.user, _body(request), skill_id)
    return _json(_skills_with_years(request.user))


def _certifications(owner) -> list[dict]:
    return [_certification_dict(c) for c in ordered_certifications(owner)]


@api_view("GET", "POST")
def api_certifications(request):
    if request.method == "POST":
        registry.save_certification(request.user, _body(request))
    return _json(_certifications(request.user))


@api_view("PUT", "DELETE")
def api_certification(request, certification_id):
    if request.method == "DELETE":
        registry.delete_certification(request.user, certification_id)
    else:
        registry.save_certification(request.user, _body(request), certification_id)
    return _json(_certifications(request.user))


def _works(owner) -> list[dict]:
    return [_work_dict(w) for w in ordered_works(owner)]


@api_view("GET", "POST")
def api_works(request):
    _require_operator(request.user)
    if request.method == "POST":
        registry.save_work(request.user, _body(request))
    return _json(_works(request.user))


@api_view("PUT", "DELETE")
def api_work(request, work_id):
    _require_operator(request.user)
    if request.method == "DELETE":
        registry.delete_work(request.user, work_id)
    else:
        registry.save_work(request.user, _body(request), work_id)
    return _json(_works(request.user))


SITE_INFO_FIELDS = [
    *registry.SITE_INFO_TEXT_FIELDS,
    "typing_titles",
    "birth_date",
    "copyright_start_year",
]


def _site_info(owner) -> dict:
    """管理画面向けのサイト情報。未登録の場合は空のフォームを表示するため空の値を返す。"""
    info = SiteInfo.objects.for_owner(owner).first()
    if info is None:
        return {name: "" for name in SITE_INFO_FIELDS} | {"typing_titles": []}
    data = {name: getattr(info, name) for name in SITE_INFO_FIELDS}
    data["birth_date"] = info.birth_date.isoformat()
    return data


@api_view("GET", "PUT")
def api_site(request):
    _require_operator(request.user)
    if request.method == "PUT":
        registry.save_site_info(request.user, _body(request))
    return _json(_site_info(request.user))


@api_view("GET", "POST")
def api_companies(request):
    if request.method == "POST":
        registry.save_company(request.user, _body(request))
    return _json(_companies(request.user))


@api_view("PUT", "DELETE")
def api_company(request, company_id):
    if request.method == "DELETE":
        registry.delete_company(request.user, company_id)
    else:
        registry.save_company(request.user, _body(request), company_id)
    return _json(_companies(request.user))


def _skillsheet_payload(owner) -> dict:
    """職務経歴書画面向けのデータ。文章項目・プレビュー・警告を返す。"""
    saved = {t.text_key: t for t in SkillsheetText.objects.for_owner(owner)}
    texts = [
        {
            "key": key,
            "label": label,
            "body": saved[key].body if key in saved else "",
            "updated_at": saved[key].updated_at.isoformat() if key in saved else None,
        }
        for key, label in SKILLSHEET_TEXT_KEYS.items()
    ]
    rendered = export.render_skillsheet(owner, timezone.localdate())
    return {
        "texts": texts,
        "preview_html": rendered.html,
        "warnings": rendered.warnings.as_dict(),
    }


@api_view("GET")
def api_skillsheet(request):
    return _json(_skillsheet_payload(request.user))


@api_view("PUT")
def api_skillsheet_text(request, text_key):
    data = _body(request)
    registry.save_skillsheet_text(
        request.user, text_key, data.get("body"), data.get("expected_updated_at")
    )
    return _json(_skillsheet_payload(request.user))


def _attachment(content, content_type: str, fallback: str, filename: str):
    """日本語のファイル名を `filename*` で指定したダウンロード応答を返す。"""
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = (
        f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
    )
    return response


@api_view("GET")
def skillsheet_pdf(request):
    _limit_per_user(request.user, "pdf")
    today = timezone.localdate()
    rendered = export.render_skillsheet(request.user, today)
    pdf = export.build_pdf(rendered.html)
    usage.increment(UsageDaily.METRIC_SKILLSHEET_PDF)
    return _attachment(
        pdf,
        "application/pdf",
        "skillsheet.pdf",
        f"職務経歴書_{today:%Y%m%d}.pdf",
    )


@api_view("GET")
def skillsheet_markdown(request):
    today = timezone.localdate()
    rendered = export.render_skillsheet(request.user, today)
    usage.increment(UsageDaily.METRIC_SKILLSHEET_MD)
    return _attachment(
        rendered.markdown,
        "text/markdown; charset=utf-8",
        "skillsheet.md",
        f"職務経歴書_{today:%Y%m%d}.md",
    )


@api_view("POST")
def api_upload_image(request):
    """実績のサムネイル画像をアップロードする。保存先の相対パスを返す。"""
    _require_operator(request.user)
    _limit_per_user(request.user, "upload")
    path = uploads.save_work_image(request.user, request.FILES.get("image"))
    return _json({"path": path})
