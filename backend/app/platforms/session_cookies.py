from collections.abc import Iterable

import httpx
from pydantic import SecretStr

from app.modules.sessions.auth_context import StoredSessionCookie


def to_httpx_cookies(
    stored_cookies: Iterable[StoredSessionCookie],
) -> httpx.Cookies:
    cookies = httpx.Cookies()
    for cookie in stored_cookies:
        if cookie.domain:
            cookies.set(
                cookie.name,
                cookie.value.get_secret_value(),
                domain=cookie.domain,
                path=cookie.path,
            )
        else:
            cookies.set(
                cookie.name,
                cookie.value.get_secret_value(),
                path=cookie.path,
            )
    return cookies


def response_cookie_updates(
    response: httpx.Response,
) -> tuple[StoredSessionCookie, ...]:
    updates: list[StoredSessionCookie] = []
    for cookie in response.cookies.jar:
        rest = {str(key).lower(): value for key, value in cookie._rest.items()}
        same_site = rest.get("samesite")
        updates.append(
            StoredSessionCookie(
                name=cookie.name,
                value=SecretStr(cookie.value),
                domain=cookie.domain or None,
                path=cookie.path or "/",
                secure=cookie.secure,
                httpOnly="httponly" in rest,
                sameSite=str(same_site) if same_site is not None else None,
                expirationDate=float(cookie.expires) if cookie.expires is not None else None,
            ),
        )
    return tuple(updates)
