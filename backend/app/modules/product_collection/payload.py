"""Bounded parsing and URL sanitization for untrusted phone packages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import math
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlunsplit

from app.modules.product_collection.contracts import (
    MobileCompletePackage,
    MobileCompletePackageV1,
    MobileCompletePackageV2,
)
from app.modules.product_collection.media_urls import MAX_URL_LENGTH, safe_url_parts


MAX_COMPLETE_PACKAGE_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_STRING_LENGTH = 1024 * 1024


def parse_complete_package(raw: bytes) -> MobileCompletePackage:
    if len(raw) > MAX_COMPLETE_PACKAGE_BYTES:
        raise ValueError("Complete package exceeds the configured size boundary")
    try:
        value = json.loads(raw, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Complete package must be valid UTF-8 JSON") from error
    _validate_shape(value, depth=0)
    if isinstance(value, Mapping) and value.get("schemaVersion") == 2:
        return MobileCompletePackageV2.model_validate(value)
    return MobileCompletePackageV1.model_validate(value)


def sanitize_source_url(value: str) -> str:
    parts = safe_url_parts(value, allowed_schemes={"http", "https"})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def sanitize_image_url(
    value: str,
    *,
    allowed_hosts: frozenset[str],
    safe_query_keys: frozenset[str] = frozenset(),
) -> str:
    parts = safe_url_parts(value, allowed_schemes={"https"})
    if parts.hostname is None or parts.hostname.lower() not in allowed_hosts:
        raise ValueError("Image host is not allowed")
    query = urlencode([
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key in safe_query_keys
    ])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _reject_json_constant(_value: str):
    raise ValueError("Complete package contains a non-finite number")


def _validate_shape(value: Any, *, depth: int) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError("Complete package exceeds the JSON depth boundary")
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise ValueError("Complete package contains an oversized string")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Complete package contains a non-finite number")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Complete package object keys must be strings")
            if len(key) > 256:
                raise ValueError("Complete package contains an oversized key")
            _validate_shape(item, depth=depth + 1)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            _validate_shape(item, depth=depth + 1)
