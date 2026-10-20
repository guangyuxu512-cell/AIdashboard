"""Collector V2's evidenced media fields, separate from request credentials."""

from urllib.parse import parse_qsl, urlsplit


MAX_URL_LENGTH = 4096
_VIDEO = "chunks.*.promotion_v3.header_v2.cells.*.multi_preview.cells.*.cell.media.video.play_opt_model"
_COMMENTS = "chunks.*.promotion_v3.components.*.slices.*.data.comments.*"
_GALLERY = "chunks.*.promotion_v3.gallery.pendants.lynx_pendant_container.top_left.*.mega_data.trust_data.bubble_list.*"


def _field_path(value: str) -> tuple[str | None, ...]:
    # None denotes a real JSON array item, never a dictionary key called '*'.
    return tuple(None if part == "*" else part for part in value.split("."))


_VIDEO_PATHS = frozenset(
    _field_path(f"{_VIDEO}.{address}.url_list.*")
    for address in ("play_addr", "play_addr_lowbr", "play_addr_h264", "bit_rate.*.play_addr")
)
_COMMENT_PATHS = frozenset(_field_path(value) for value in {
    f"{_COMMENTS}.comment_user_avatar.src",
    f"{_COMMENTS}.comment_medias_arr.*.media_image_src",
    f"{_COMMENTS}.comment_medias_arr.*.media_click_action.actions.*.fields.image_url_array.*",
})
_GALLERY_PATHS = frozenset(_field_path(value) for value in {
    f"{_GALLERY}.avatar.url_list.*",
    f"{_GALLERY}.content_list.*.icon.*.url_list.*",
})
_COVER_PATH = _field_path(f"{_VIDEO}.cover.url_list.*")
_SIGNED_MEDIA_PATHS = _VIDEO_PATHS | _COMMENT_PATHS | _GALLERY_PATHS | {_COVER_PATH}


def safe_url_parts(value: str, *, allowed_schemes: set[str]):
    """Shared intake/display URL boundary; never includes the URL in errors."""
    if len(value) > MAX_URL_LENGTH:
        raise ValueError("URL exceeds the configured length boundary")
    parts = urlsplit(value)
    if parts.scheme.lower() not in allowed_schemes or not parts.hostname:
        raise ValueError("URL scheme or host is not allowed")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URL userinfo is forbidden")
    return parts


def collector_v2_media_query_keys(path: tuple[str | None, ...], value: str) -> frozenset[str]:
    """Allow only resource signatures at observed V2 media locations.

    Exact field, HTTPS host, resource path and query-name sets are all required.
    This does not authorize API request signatures, arbitrary hosts or tokens.
    The original URL is retained only in the immutable package/UU snapshot;
    display projections still use their independent query-stripping boundary.
    """
    field = path
    if field not in _SIGNED_MEDIA_PATHS:
        return frozenset()
    # Unsigned legacy media keeps the original intake rules. This exception
    # applies only to the two observed resource-signature query names.
    if not any(key in {"sign", "x-signature"} for key, _ in parse_qsl(urlsplit(value).query)):
        return frozenset()
    parts = safe_url_parts(value, allowed_schemes={"https"})
    try:
        port = parts.port
    except ValueError:
        return frozenset()
    if port not in {None, 443} or parts.fragment or any(c.isspace() for c in value):
        return frozenset()
    host = parts.hostname.lower()
    signature = None
    allowed: set[str] = set()
    if (
        field in _VIDEO_PATHS
        and host in {"api-play.amemv.com", "api.amemv.com"}
        and parts.path == "/aweme/v1/play/"
    ):
        signature = "sign"
        allowed = {"video_id", "file_id", "line", "is_play_url", "sign"}
    elif (
        field in _COMMENT_PATHS
        and host in {"p3-product-comment-sign.byteimg.com", "p9-product-comment-sign.byteimg.com"}
        and parts.path.startswith(("/aweme-avatar/", "/tos-cn-i-8y5sebgt5i/"))
    ):
        signature = "x-signature"
        allowed = {"lk3s", "x-expires", "x-signature"}
    elif (
        field == _COVER_PATH
        and host == "p3-sign.douyinpic.com"
        and parts.path.startswith("/tos-cn-v-2e5523/")
    ):
        signature = "x-signature"
        allowed = {"dy_q", "l", "x-expires", "x-signature"}
    elif (
        field in _GALLERY_PATHS
        and host == "p3-sellpoint1-sign.byteimg.com"
        and parts.path.startswith("/") and len(parts.path) > 1
    ):
        signature = "x-signature"
        allowed = {"rk3s", "x-conf-key", "x-expires", "x-signature"}
    query = parse_qsl(parts.query, keep_blank_values=True)
    if (
        signature is None or any(key not in allowed for key, _ in query)
        or len({key for key, _ in query}) != len(query)
        or not any(key == signature and item for key, item in query)
    ):
        return frozenset()
    return frozenset({signature.replace("-", "_")})
