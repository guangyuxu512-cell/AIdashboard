"""Durable finite manual-collection consumer; no automatic business retry."""

import asyncio
import logging

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.modules.product_data.collection import collect_complete_snapshot
from app.modules.product_data.exceptions import ProductDataCollectionLimitExceededError
from app.modules.product_data.service import ProductDataService
from app.modules.sessions.exceptions import ShopSessionAuthenticationInvalidError


logger = logging.getLogger(__name__)


SAFE_FAILURE_CODES = frozenset({
    ProductDataCollectionLimitExceededError.code,
    "PRODUCT_DATA_COLLECTION_UNAVAILABLE", "PRODUCT_DATA_PUBLICATION_REJECTED",
    "PRODUCT_DATA_SOURCE_CONTRACT_INVALID", "PRODUCT_DATA_SESSION_VALIDATION_REQUIRED",
    "SHOP_SESSION_NOT_CONFIGURED", "SHOP_SESSION_PAYLOAD_INVALID", "SESSION_VERSION_CONFLICT",
    "SESSION_ENCRYPTION_UNAVAILABLE", "AUTH_INVALID", "PLATFORM_TIMEOUT", "PLATFORM_REQUEST_FAILED",
    "PLATFORM_SIGNER_FAILED", "PLATFORM_RESPONSE_INVALID", "PLATFORM_IDENTITY_MISMATCH",
    "DOUYIN_PRODUCT_DATA_REJECTED", "DOUYIN_PRODUCT_DATA_EMPTY_UNCONFIRMED",
    "HUMAN_AUTHENTICATION_REQUIRED", "HUMAN_USER_DISABLED", "TEAM_ACCESS_DENIED",
    "TEAM_MEMBERSHIP_REQUIRED", "MODULE_ACCESS_DENIED", "SHOP_NOT_FOUND", "PRODUCT_DATA_SCOPE_UNSUPPORTED",
})


class ProductDataExecutor:
    def __init__(self, session_factory, settings, platform_io):
        self.session_factory, self.settings, self.platform_io = session_factory, settings, platform_io

    def execute_available(self):
        with self.session_factory() as session:
            claim = ProductDataService(session, settings=self.settings).claim_next()
        if claim is None:
            return 0
        self.execute(claim.generation_id, claim.lease_id)
        return 1

    def execute(self, generation_id, lease_id):
        stage = "session_preparation"
        try:
            if not self.settings.product_data_collection_execution_enabled:
                from app.modules.product_data.exceptions import ProductDataCollectionUnavailableError
                raise ProductDataCollectionUnavailableError()
            with self.session_factory() as session:
                context = ProductDataService(session, settings=self.settings).prepare_execution(
                    generation_id,
                    lease_id,
                    stage="session_preparation",
                    heartbeat=True,
                )

            def fetch(page_no):
                nonlocal stage
                stage = "platform_response"
                page = self.platform_io.page(generation_id, lease_id, page_no)
                stage = "collection_coverage"
                with self.session_factory() as session:
                    ProductDataService(session, settings=self.settings).note_progress(generation_id, lease_id, page)
                return page

            snapshot = collect_complete_snapshot(context.scope, fetch, max_pages=self.settings.product_data_collection_max_pages)
            stage = "publication"
            with self.session_factory() as session:
                ProductDataService(session, settings=self.settings).publish(generation_id, lease_id, snapshot)
        except Exception as error:
            # Never persist exception text/details, external URLs, headers or payloads.
            code = getattr(error, "code", None)
            code = code if isinstance(code, str) and code in SAFE_FAILURE_CODES else "PRODUCT_DATA_EXECUTION_FAILED"
            if isinstance(error, ShopSessionAuthenticationInvalidError) or code in {
                "PRODUCT_DATA_SESSION_VALIDATION_REQUIRED", "SHOP_SESSION_NOT_CONFIGURED",
                "SHOP_SESSION_PAYLOAD_INVALID", "SESSION_ENCRYPTION_UNAVAILABLE",
            }:
                stage = "session_preparation"
            elif code == "PLATFORM_SIGNER_FAILED":
                stage = "signing"
            elif isinstance(error, ProductDataCollectionLimitExceededError):
                stage = "collection_coverage"
            elif code in {"PLATFORM_RESPONSE_INVALID", "DOUYIN_PRODUCT_DATA_REJECTED", "DOUYIN_PRODUCT_DATA_EMPTY_UNCONFIRMED"}:
                stage = "response_parse" if stage != "collection_coverage" else stage
            try:
                with self.session_factory() as session:
                    metadata = (
                        {"expected_total": error.expected_total}
                        if isinstance(error, ProductDataCollectionLimitExceededError) else {}
                    )
                    ProductDataService(session, settings=self.settings).fail(generation_id, lease_id, code, stage, **metadata)
            except Exception:
                # If even the failure CAS cannot be committed, the durable lease
                # expires visibly. No fake success, automatic retry or raw logging.
                logger.warning("Product Data failure receipt could not be saved", extra={
                    "event": "product_data_failure_receipt_unavailable", "generation_id": str(generation_id),
                    "failure_code": code, "stage": stage,
                })


def execute_product_data_collection(generation_id, lease_id):
    from app.modules.product_data.platform_io import ProductDataStoredSessionIO
    settings, factory = get_settings(), get_session_factory()
    ProductDataExecutor(factory, settings, ProductDataStoredSessionIO(factory, settings)).execute(generation_id, lease_id)


def build_product_data_executor(settings=None):
    from app.modules.product_data.platform_io import ProductDataStoredSessionIO
    resolved = settings or get_settings()
    factory = get_session_factory()
    return ProductDataExecutor(
        factory,
        resolved,
        ProductDataStoredSessionIO(factory, resolved),
    )


async def execute_product_data_collections_forever():
    settings = get_settings()
    if not settings.product_data_collection_execution_enabled:
        return
    executor = build_product_data_executor(settings)

    async def worker():
        while True:
            try:
                processed = await asyncio.to_thread(executor.execute_available)
            except asyncio.CancelledError:
                # A finite in-flight HTTP call cannot be retracted. The durable
                # lease fence prevents its late result from being published.
                raise
            except Exception:
                # Never log a raw platform exception, URL or credential.
                processed = 0
            if not processed:
                await asyncio.sleep(
                    settings.product_data_collection_scan_interval_seconds,
                )

    await asyncio.gather(*(
        worker() for _ in range(settings.product_data_collection_max_running)
    ))
