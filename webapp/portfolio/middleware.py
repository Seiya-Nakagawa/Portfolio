from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.urls.exceptions import Resolver404

from portfolio.accounts import has_agreed_to_current_terms

# 再同意が済んでいなくても表示できる画面（URL 名）。
EXEMPT_URL_NAMES = frozenset({"reconsent", "logout", "terms", "privacy"})


class ReconsentMiddleware:
    """同意した規約の版が現行と異なるログイン中のユーザーを、再同意画面へ誘導する。

    再同意画面・ログアウト・規約の閲覧・静的ファイルは対象外とする。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not self._is_exempt(request)
            and not has_agreed_to_current_terms(user)
        ):
            return redirect(f"{reverse('reconsent')}?next={request.get_full_path()}")
        return self.get_response(request)

    @staticmethod
    def _is_exempt(request) -> bool:
        if request.path.startswith(("/static/", "/media/")):
            return True
        try:
            return resolve(request.path_info).url_name in EXEMPT_URL_NAMES
        except Resolver404:
            return False


class LegacyUrlRedirectMiddleware:
    """旧 URL（技術ブログのホスト配下の `/portfolio`）へのリクエストを、サービスホストへ 301 で転送する。

    管理画面（`/manage/` 以下）はサービスホストの同じ画面へ、それ以外（API を含む）は運営者の
    公開ポートフォリオへ転送する。旧 URL のホストでは、リダイレクト以外を応答しない。
    """

    LEGACY_PREFIX = "/portfolio"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.LEGACY_HOSTS and request.get_host().split(":")[0] in (
            settings.LEGACY_HOSTS
        ):
            return HttpResponsePermanentRedirect(self._target(request))
        return self.get_response(request)

    def _target(self, request) -> str:
        base = f"https://{settings.SERVICE_HOST}"
        path = request.path
        # Ingress がプレフィックスを除去して転送する場合と、除去しない場合の双方に対応する。
        if path == self.LEGACY_PREFIX or path.startswith(f"{self.LEGACY_PREFIX}/"):
            path = path[len(self.LEGACY_PREFIX) :] or "/"
        if path.startswith("/manage"):
            query = request.META.get("QUERY_STRING")
            return f"{base}{path}{'?' + query if query else ''}"
        username = settings.LEGACY_REDIRECT_USERNAME
        return f"{base}/u/{username}/" if username else f"{base}/"
