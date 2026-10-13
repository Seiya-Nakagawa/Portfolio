from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.static import serve

from portfolio import services


def _json_response(data) -> JsonResponse:
    # 配列をそのまま返すため safe=False とし、日本語をエスケープしない。
    return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})


def _public_owner():
    """公開ポートフォリオの表示対象のユーザー。

    ユーザー別の公開ポートフォリオ（`/u/{ユーザー名}/`）を実装するまでの暫定として、
    最初に登録された有効な運営者（`is_staff`）のポートフォリオを表示する。
    """
    owner = (
        get_user_model()
        .objects.filter(is_active=True, is_staff=True)
        .order_by("pk")
        .first()
    )
    if owner is None:
        raise Http404("公開できるポートフォリオがありません。")
    return owner


@require_GET
def index(request):
    """ポートフォリオサイトのページ本体。"""
    return render(request, "index.html")


@require_GET
def api_skills(request):
    return _json_response(
        services.build_skills_payload(_public_owner(), timezone.localdate())
    )


@require_GET
def api_certifications(request):
    return _json_response(services.build_certifications_payload(_public_owner()))


@require_GET
def api_works(request):
    return _json_response(services.build_works_payload(_public_owner()))


@require_GET
def api_site(request):
    payload = services.build_site_payload(_public_owner(), timezone.localdate())
    if payload is None:
        raise Http404("サイト情報が登録されていません。")
    return _json_response(payload)


@require_GET
def media(request, path):
    """管理画面からアップロードした画像を配信する。"""
    return serve(request, path, document_root=settings.MEDIA_ROOT)
