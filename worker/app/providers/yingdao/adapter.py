from collections.abc import Mapping
from typing import Any, Protocol

from app.providers.yingdao.contracts import (
    YingdaoDiscoveryResult,
    YingdaoExecutionRequest,
)


class YingdaoTriggerError(RuntimeError):
    """Raised when the provider cannot trigger the selected application."""


class YingdaoAdapter(Protocol):
    async def discover(self) -> YingdaoDiscoveryResult: ...

    async def execute(
        self,
        request: YingdaoExecutionRequest,
    ) -> Mapping[str, Any]: ...

    async def cleanup(self, request: YingdaoExecutionRequest) -> None: ...


class UnavailableYingdaoAdapter:
    """Production-safe placeholder until a complete local trigger exists."""

    async def discover(self) -> YingdaoDiscoveryResult:
        return YingdaoDiscoveryResult(provider_available=False)

    async def execute(
        self,
        request: YingdaoExecutionRequest,
    ) -> Mapping[str, Any]:
        del request
        raise YingdaoTriggerError("Yingdao trigger contract is not configured")

    async def cleanup(self, request: YingdaoExecutionRequest) -> None:
        del request
