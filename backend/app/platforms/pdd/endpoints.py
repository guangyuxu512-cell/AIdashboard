from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PddEndpoint:
    """A verified PDD HTTP contract owned by the PDD platform layer."""

    host: str
    path: str
    method: Literal["GET", "POST"]
    headers: tuple[tuple[str, str], ...]

    @property
    def url(self) -> str:
        return f"https://{self.host}{self.path}"


MERCHANT_IDENTITY_ENDPOINT = PddEndpoint(
    host="mms.pinduoduo.com",
    path="/earth/api/merchant/queryMerchantInfoByMallId",
    method="POST",
    headers=(
        ("accept", "*/*"),
        ("accept-language", "zh-CN,zh;q=0.9"),
        ("cache-control", "no-cache"),
        ("content-type", "application/json"),
        ("origin", "https://mms.pinduoduo.com"),
        ("pragma", "no-cache"),
        ("referer", "https://mms.pinduoduo.com/goods/goods_list?msfrom=mms_sidenav"),
        (
            "user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36",
        ),
    ),
)
