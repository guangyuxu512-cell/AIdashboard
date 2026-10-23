"""Fail-closed normalization for human-supplied collection targets."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlsplit

from app.modules.product_collection.contracts import ManualCollectionTarget, SourcePlatform
from app.modules.product_collection.exceptions import ProductCollectionTargetUnsupportedError


_STABLE_NUMERIC_ID = re.compile(r"^[0-9]{1,128}$")
_PDD_PRODUCT_HOSTS = frozenset({"mobile.yangkeduo.com"})


@dataclass(frozen=True, slots=True)
class NormalizedCollectionTarget:
    platform: SourcePlatform
    source_product_id: str


def normalize_manual_target(target: ManualCollectionTarget) -> NormalizedCollectionTarget:
    raw = target.product_id_or_supported_url.strip()
    if _STABLE_NUMERIC_ID.fullmatch(raw):
        return NormalizedCollectionTarget(
            platform=target.platform,
            source_product_id=raw,
        )

    try:
        parsed = urlsplit(raw)
        parsed.port
    except ValueError as error:
        raise ProductCollectionTargetUnsupportedError() from error
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ProductCollectionTargetUnsupportedError()

    if (
        target.platform is SourcePlatform.PINDUODUO
        and parsed.hostname.lower() in _PDD_PRODUCT_HOSTS
        and parsed.path == "/goods.html"
    ):
        values = parse_qs(parsed.query, keep_blank_values=True).get("goods_id", [])
        if len(values) == 1 and _STABLE_NUMERIC_ID.fullmatch(values[0]):
            return NormalizedCollectionTarget(
                platform=target.platform,
                source_product_id=values[0],
            )

    # No Douyin product URL contract has been frozen for V1. Reject instead of
    # extracting an arbitrary numeric substring from a share link.
    raise ProductCollectionTargetUnsupportedError()


def distinct_targets(
    targets: tuple[ManualCollectionTarget, ...],
) -> tuple[NormalizedCollectionTarget, ...]:
    result: list[NormalizedCollectionTarget] = []
    seen: set[tuple[SourcePlatform, str]] = set()
    for target in targets:
        normalized = normalize_manual_target(target)
        key = (normalized.platform, normalized.source_product_id)
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return tuple(result)
