"""Injectable durable consumers for the mobile product-collection pipeline."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session_factory
from app.modules.product_collection.cleaner import ExistingUuProductPackageCleaner
from app.modules.product_collection.dispatch_service import (
    ProductCollectionDispatchService,
)
from app.modules.product_collection.exceptions import (
    ProductCollectionConfigurationError,
)
from app.modules.product_collection.gateway import HttpProductCollectionGateway
from app.modules.product_collection.ports import (
    ProductCollectionGateway,
    ProductPackageCleaner,
)
from app.modules.product_collection.service import (
    ProductCollectionProcessingService,
    ProductCollectionSettlementService,
)


class ProductCollectionExecutor:
    """One-step methods keep DB transactions outside gateway/cleaner I/O."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], AbstractContextManager[Session]],
        settings: Settings,
        gateway: ProductCollectionGateway | None,
        cleaner: ProductPackageCleaner | None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.gateway = gateway
        self.cleaner = cleaner

    def dispatch_once(self) -> bool:
        gateway_id = self.settings.product_collection_gateway_id
        if not self.settings.product_collection_execution_enabled:
            return False
        if gateway_id is None or self.gateway is None:
            raise ProductCollectionConfigurationError()
        with self.session_factory() as session:
            if ProductCollectionDispatchService(session).cancel_requested_once(self.gateway):
                return True
        with self.session_factory() as session:
            ProductCollectionDispatchService(session).plan_pending(
                gateway_id=gateway_id,
                limit=100,
            )
        with self.session_factory() as session:
            return ProductCollectionDispatchService(session).deliver_once(
                self.gateway,
                lease_seconds=self.settings.product_collection_dispatch_lease_seconds,
                max_attempts=self.settings.product_collection_delivery_max_attempts,
                retry_delay_seconds=self.settings.product_collection_delivery_retry_seconds,
            )

    def process_once(self) -> bool:
        if not self.settings.product_collection_processing_enabled:
            return False
        if self.cleaner is None:
            raise ProductCollectionConfigurationError()
        with self.session_factory() as session:
            service = ProductCollectionProcessingService(session)
            claim = service.claim(
                lease_seconds=self.settings.product_collection_processing_lease_seconds,
            )
        if claim is None:
            return False
        try:
            with self.session_factory() as session:
                raw = ProductCollectionProcessingService(session).raw_payload(claim)
            package = self.cleaner.convert(raw)
        except Exception:
            with self.session_factory() as session:
                ProductCollectionProcessingService(session).fail(
                    claim,
                    error_code="PRODUCT_COLLECTION_CLEANER_INVALID",
                    error_stage="cleaner",
                    error_message="商品完整包清洗失败",
                )
            return True
        with self.session_factory() as session:
            ProductCollectionProcessingService(session).persist(claim, package)
        return True

    def settle_once(self) -> bool:
        if not self.settings.product_collection_settlement_enabled:
            return False
        if self.gateway is None:
            raise ProductCollectionConfigurationError()
        with self.session_factory() as session:
            claim = ProductCollectionSettlementService(session).claim(
                max_attempts=self.settings.product_collection_settlement_max_attempts,
                delivery_timeout_seconds=(
                    self.settings.product_collection_settlement_delivery_timeout_seconds
                ),
            )
        if claim is None:
            return False
        try:
            self.gateway.settle(claim.settlement)
        except Exception as error:
            terminal_attempt_budget = (
                claim.attempt_no
                if getattr(error, "retryable", True) is False
                else self.settings.product_collection_settlement_max_attempts
            )
            with self.session_factory() as session:
                ProductCollectionSettlementService(session).fail(
                    claim,
                    error_code=getattr(
                        error,
                        "failure_code",
                        "PRODUCT_COLLECTION_GATEWAY_SETTLEMENT_FAILED",
                    ),
                    error_message=getattr(
                        error,
                        "safe_message",
                        "手机采集网关结算失败",
                    ),
                    max_attempts=terminal_attempt_budget,
                    retry_delay_seconds=(
                        self.settings.product_collection_settlement_retry_seconds
                    ),
                )
            return True
        with self.session_factory() as session:
            ProductCollectionSettlementService(session).succeed(claim)
        return True


def product_collection_consumers_enabled(settings: Settings) -> bool:
    return any(
        (
            settings.product_collection_execution_enabled,
            settings.product_collection_processing_enabled,
            settings.product_collection_settlement_enabled,
        ),
    )


def build_product_collection_executor(
    settings: Settings | None = None,
    *,
    session_factory: Callable[[], AbstractContextManager[Session]] | None = None,
    gateway: ProductCollectionGateway | None = None,
    cleaner: ProductPackageCleaner | None = None,
) -> ProductCollectionExecutor:
    """Build only the adapters needed by explicitly enabled stages.

    Enabling a stage without its protected deployment configuration fails the
    Backend startup.  Disabled Feature and Integration environments therefore
    open neither the database nor an external gateway connection.
    """

    resolved = settings or get_settings()
    if not product_collection_consumers_enabled(resolved):
        raise ProductCollectionConfigurationError()

    resolved_gateway = gateway
    if (
        resolved_gateway is None
        and (
            resolved.product_collection_execution_enabled
            or resolved.product_collection_settlement_enabled
        )
    ):
        if (
            resolved.product_collection_gateway_id is None
            or resolved.product_collection_gateway_base_url is None
            or (
                resolved.product_collection_execution_enabled
                and resolved.product_collection_gateway_control_token is None
            )
            or (
                resolved.product_collection_settlement_enabled
                and resolved.product_collection_gateway_callback_token is None
            )
        ):
            raise ProductCollectionConfigurationError()
        if (
            resolved.product_collection_execution_enabled
            and resolved.product_collection_dispatch_lease_seconds
            <= resolved.product_collection_gateway_timeout_seconds
        ):
            raise ProductCollectionConfigurationError()
        if (
            resolved.product_collection_settlement_enabled
            and resolved.product_collection_settlement_delivery_timeout_seconds
            <= resolved.product_collection_gateway_timeout_seconds
        ):
            raise ProductCollectionConfigurationError()
        resolved_gateway = HttpProductCollectionGateway(
            base_url=resolved.product_collection_gateway_base_url,
            gateway_id=resolved.product_collection_gateway_id,
            control_token=resolved.product_collection_gateway_control_token,
            callback_token=resolved.product_collection_gateway_callback_token,
            timeout_seconds=resolved.product_collection_gateway_timeout_seconds,
        )

    resolved_cleaner = cleaner
    if resolved.product_collection_processing_enabled and resolved_cleaner is None:
        if resolved.product_collection_cleaner_module_path is None:
            raise ProductCollectionConfigurationError()
        if (
            resolved.product_collection_processing_lease_seconds
            <= resolved.product_collection_cleaner_timeout_seconds
        ):
            raise ProductCollectionConfigurationError()
        resolved_cleaner = ExistingUuProductPackageCleaner(resolved)

    return ProductCollectionExecutor(
        session_factory=session_factory or get_session_factory(),
        settings=resolved,
        gateway=resolved_gateway,
        cleaner=resolved_cleaner,
    )


async def execute_product_collections_forever(
    *,
    settings: Settings | None = None,
    executor: ProductCollectionExecutor | None = None,
) -> None:
    """Run independent durable stages without creating another queue system."""

    resolved = settings or get_settings()
    if not product_collection_consumers_enabled(resolved):
        return
    active_executor = executor or build_product_collection_executor(resolved)
    operations: list[Callable[[], bool]] = []
    if resolved.product_collection_execution_enabled:
        operations.append(active_executor.dispatch_once)
    if resolved.product_collection_processing_enabled:
        operations.append(active_executor.process_once)
    if resolved.product_collection_settlement_enabled:
        operations.append(active_executor.settle_once)

    async def worker(operation: Callable[[], bool]) -> None:
        while True:
            try:
                processed = await asyncio.to_thread(operation)
            except asyncio.CancelledError:
                # In-flight finite external I/O cannot be physically retracted;
                # all late writes remain protected by database fences.
                raise
            except Exception:
                # Never log a raw gateway response, uploaded package or secret.
                processed = False
            if not processed:
                await asyncio.sleep(resolved.product_collection_scan_interval_seconds)

    await asyncio.gather(*(worker(operation) for operation in operations))
