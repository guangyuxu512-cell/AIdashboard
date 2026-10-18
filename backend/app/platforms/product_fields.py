"""Public product image validation shared by platform response adapters."""

from typing import Any
from urllib.parse import parse_qsl, urlsplit


def public_product_image_url(value: Any) -> str | None:
    """Preserve an allowed URL without fetching, rewriting or logging it."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            return None
        sensitive_keys = {
            "cookie", "token", "mstoken", "a_bogus", "authorization",
            "sessionid", "verifyfp", "fp", "_lid",
        }
        if any(key.lower() in sensitive_keys for key, _ in parse_qsl(parsed.query)):
            return None
    except ValueError:
        return None
    return value
