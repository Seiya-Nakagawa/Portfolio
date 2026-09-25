from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from portfolio import services


def _json_response(data) -> JsonResponse:
    # 配列をそのまま返すため safe=False とし、日本語をエスケープしない。
    return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})


@require_GET
def index(request):
    """ポートフォリオサイトのページ本体。"""
    return render(request, "index.html")


@require_GET
def api_skills(request):
    return _json_response(services.build_skills_payload(timezone.localdate()))


@require_GET
def api_certifications(request):
    return _json_response(services.build_certifications_payload())


@require_GET
def api_works(request):
    return _json_response(services.build_works_payload())
