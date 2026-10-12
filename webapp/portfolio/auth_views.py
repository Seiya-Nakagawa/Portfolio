"""ログイン・再同意・規約の画面。"""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods

from portfolio.accounts import ReconsentForm, record_agreement


@require_GET
def login_page(request):
    """Google・GitHub のボタンのみを置くログイン画面。パスワードの入力欄は持たない。"""
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    return render(request, "account/login.html", {"next": request.GET.get("next", "")})


def _safe_next(request) -> str:
    target = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return settings.LOGIN_REDIRECT_URL


@login_required
@require_http_methods(["GET", "POST"])
def reconsent(request):
    """改定された規約への再同意。同意しない場合はログアウトのみ選べる。"""
    form = ReconsentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record_agreement(request.user)
        return redirect(_safe_next(request))
    return render(
        request,
        "account/reconsent.html",
        {
            "form": form,
            "next": request.GET.get("next", ""),
            "terms_version": settings.TERMS_VERSION,
            "privacy_version": settings.PRIVACY_VERSION,
        },
    )


@require_GET
def terms(request):
    return render(
        request,
        "legal/terms.html",
        {
            "version": settings.TERMS_VERSION,
            "body_template": f"legal/terms/{settings.TERMS_VERSION}.html",
        },
    )


@require_GET
def privacy(request):
    return render(
        request,
        "legal/privacy.html",
        {
            "version": settings.PRIVACY_VERSION,
            "body_template": f"legal/privacy/{settings.PRIVACY_VERSION}.html",
        },
    )
