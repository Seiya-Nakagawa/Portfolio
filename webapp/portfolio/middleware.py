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
