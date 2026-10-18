"""Observed optional Compass fingerprint context from the selected CookieJar."""

import httpx

from app.modules.sessions.auth_context import ShopSessionAuthContext
from app.platforms.douyin.endpoints import DouyinEndpoint
from app.platforms.session_cookies import to_httpx_cookies


def session_query_context(endpoint: DouyinEndpoint, context: ShopSessionAuthContext) -> dict[str, str]:
    request = httpx.Request("GET", endpoint.url)
    to_httpx_cookies(context.cookies).set_cookie_header(request)
    values = {
        part.strip().partition("=")[2]
        for part in request.headers.get("cookie", "").split(";")
        if part.strip().partition("=")[0] == "s_v_web_id"
    }
    return {"fp": next(iter(values)), "verifyFp": next(iter(values))} if len(values) == 1 and "" not in values else {}
