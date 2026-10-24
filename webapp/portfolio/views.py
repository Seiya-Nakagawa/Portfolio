import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.static import serve

from portfolio import health, services
from portfolio.media_paths import USER_IMAGE_PATH
from portfolio.models import Work


def _json_response(data) -> JsonResponse:
    # 配列をそのまま返すため safe=False とし、日本語をエスケープしない。
    return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})


def _is_published(user_queryset):
    """公開中かつ有効なユーザーに絞り込む。"""
    return user_queryset.filter(is_active=True, profile__is_public=True)


def get_published_user(username: str):
    """公開ポートフォリオの表示対象のユーザーを返す。

    非公開・存在しない・利用停止中は区別せず、同じ 404 とする。
    """
    user = _is_published(
        get_user_model().objects.filter(username__iexact=username)
    ).first()
    if user is None:
        raise Http404("ポートフォリオが見つかりません。")
    return user


@require_GET
def index(request):
    """サービス紹介ページ。"""
    return render(request, "service/index.html")


@require_GET
def portfolio(request, username):
    """ユーザーの公開ポートフォリオのページ本体。"""
    user = get_published_user(username)
    return render(request, "index.html", {"portfolio_username": user.username})


@require_GET
def api_skills(request, username):
    user = get_published_user(username)
    return _json_response(services.build_skills_payload(user, timezone.localdate()))


@require_GET
def api_certifications(request, username):
    user = get_published_user(username)
    return _json_response(services.build_certifications_payload(user))


@require_GET
def api_works(request, username):
    user = get_published_user(username)
    return _json_response(services.build_works_payload(user))


@require_GET
def api_site(request, username):
    user = get_published_user(username)
    payload = services.build_site_payload(user, timezone.localdate())
    if payload is None:
        raise Http404("サイト情報が登録されていません。")
    return _json_response(payload)


# 従来の保存先（`works/`）の画像のパス。`migrate_media` が移し終えるまでの間のみ配信する。
LEGACY_IMAGE_PATH = re.compile(r"^works/[A-Za-z0-9_-]+\.[A-Za-z0-9]+$")


def _image_owner_id(path: str) -> int | None:
    """配信する画像の所有者の id を返す。配信の対象外のパスは None を返す。"""
    matched = USER_IMAGE_PATH.match(path)
    if matched is not None:
        return int(matched.group("user_id"))
    if LEGACY_IMAGE_PATH.match(path):
        # 移行前の旧パスは、実績の画像の参照から所有者を特定する。
        return (
            Work.objects.filter(thumbnail=path)
            .values_list("owner_id", flat=True)
            .first()
        )
    return None


@require_GET
def media(request, path):
    """アップロードした画像を配信する。

    ユーザーごとの保存先の画像（と、移行前の旧パスの画像）のみを対象とし、所有するユーザーの
    公開ポートフォリオが公開中であるか、閲覧者が所有するユーザー本人である場合のみ返す。
    それ以外は 404 とする。非公開化後に画像がキャッシュに残らないよう、毎回サーバーで確認させる。
    """
    owner_id = _image_owner_id(path)
    if owner_id is None:
        raise Http404("画像が見つかりません。")
    is_owner = request.user.is_authenticated and request.user.pk == owner_id
    if (
        not is_owner
        and not _is_published(get_user_model().objects.filter(pk=owner_id)).exists()
    ):
        raise Http404("画像が見つかりません。")
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response["Cache-Control"] = "private, no-cache"
    return response


@require_GET
def healthz(request):
    """死活監視用のヘルスチェック（認証不要）。件数・構成などの内部情報は応答に含めない。"""
    healthy = health.is_healthy()
    return HttpResponse(
        "ok" if healthy else "ng",
        status=200 if healthy else 503,
        content_type="text/plain; charset=utf-8",
    )
