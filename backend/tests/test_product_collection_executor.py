import asyncio
from contextlib import contextmanager
from threading import Barrier

from pydantic import SecretStr
import pytest

from app.core.config import Settings
from app.modules.product_collection.exceptions import (
    ProductCollectionConfigurationError,
)


def test_disabled_consumer_opens_neither_database_nor_gateway(monkeypatch) -> None:
    from app.modules.product_collection import executor

    monkeypatch.setattr(
        executor,
        "build_product_collection_executor",
        lambda *_args, **_kwargs: pytest.fail("disabled consumer must not be built"),
    )
    asyncio.run(
        executor.execute_product_collections_forever(
            settings=Settings(
                product_collection_execution_enabled=False,
                product_collection_processing_enabled=False,
                product_collection_settlement_enabled=False,
            ),
        ),
    )


def test_enabled_stages_have_independent_workers(monkeypatch) -> None:
    from app.modules.product_collection import executor

    calls: list[str] = []
    first_pass = Barrier(3)

    class FakeExecutor:
        def _run(self, stage: str) -> bool:
            calls.append(stage)
            first_pass.wait(timeout=5)
            return False

        def dispatch_once(self) -> bool:
            return self._run("dispatch")

        def process_once(self) -> bool:
            return self._run("process")

        def settle_once(self) -> bool:
            return self._run("settle")

    async def stop(_seconds: float) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr(executor.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            executor.execute_product_collections_forever(
                settings=Settings(
                    product_collection_execution_enabled=True,
                    product_collection_processing_enabled=True,
                    product_collection_settlement_enabled=True,
                ),
                executor=FakeExecutor(),
            ),
        )
    assert sorted(calls) == ["dispatch", "process", "settle"]


def test_enabled_stage_missing_protected_configuration_fails_closed() -> None:
    from app.modules.product_collection.executor import build_product_collection_executor

    with pytest.raises(ProductCollectionConfigurationError):
        build_product_collection_executor(
            Settings(product_collection_execution_enabled=True),
            session_factory=lambda: pytest.fail("database must not be opened"),
        )
    with pytest.raises(ProductCollectionConfigurationError):
        build_product_collection_executor(
            Settings(product_collection_processing_enabled=True),
            session_factory=lambda: pytest.fail("database must not be opened"),
        )


def test_lifespan_validates_product_collection_before_starting_any_task(
    monkeypatch,
) -> None:
    from app import main

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(product_collection_execution_enabled=True),
    )
    monkeypatch.setattr(
        main.asyncio,
        "create_task",
        lambda *_args, **_kwargs: pytest.fail(
            "invalid protected configuration must fail before background tasks start",
        ),
    )

    async def enter_lifespan() -> None:
        async with main.lifespan(object()):
            pytest.fail("invalid protected configuration cannot enter application lifespan")

    with pytest.raises(ProductCollectionConfigurationError):
        asyncio.run(enter_lifespan())


def test_execution_only_does_not_require_disabled_stage_secrets() -> None:
    from app.modules.product_collection.executor import build_product_collection_executor

    settings = Settings(
        product_collection_execution_enabled=True,
        product_collection_gateway_id="gateway-a",
        product_collection_gateway_base_url="https://gateway.example.test",
        product_collection_gateway_control_token=SecretStr("control-token"),
    )
    built = build_product_collection_executor(
        settings,
        session_factory=lambda: pytest.fail("builder must not open the database"),
    )
    assert built.gateway is not None
    assert built.cleaner is None


@pytest.mark.parametrize(
    "settings",
    [
        Settings(
            product_collection_execution_enabled=True,
            product_collection_gateway_id="gateway-a",
            product_collection_gateway_base_url="https://gateway.example.test",
            product_collection_gateway_control_token=SecretStr("control-token"),
            product_collection_gateway_timeout_seconds=60,
            product_collection_dispatch_lease_seconds=60,
        ),
        Settings(
            product_collection_settlement_enabled=True,
            product_collection_gateway_id="gateway-a",
            product_collection_gateway_base_url="https://gateway.example.test",
            product_collection_gateway_callback_token=SecretStr("callback-token"),
            product_collection_gateway_timeout_seconds=60,
            product_collection_settlement_delivery_timeout_seconds=60,
        ),
    ],
)
def test_gateway_timeout_must_fit_inside_database_fence(settings: Settings) -> None:
    from app.modules.product_collection.executor import build_product_collection_executor

    with pytest.raises(ProductCollectionConfigurationError):
        build_product_collection_executor(
            settings,
            session_factory=lambda: pytest.fail("database must not be opened"),
        )


def test_nonretryable_settlement_error_exhausts_only_current_claim(monkeypatch) -> None:
    from app.modules.product_collection import executor
    from app.modules.product_collection.gateway import ProductCollectionGatewayError

    claim = type("Claim", (), {"attempt_no": 2, "settlement": object()})()
    recorded: dict[str, object] = {}

    class SettlementService:
        def __init__(self, _session) -> None:
            pass

        def claim(self, **_kwargs):
            return claim

        def fail(self, received, **kwargs) -> None:
            recorded.update({"claim": received, **kwargs})

        def succeed(self, _claim) -> None:
            pytest.fail("terminal gateway rejection cannot be marked succeeded")

    class Gateway:
        def settle(self, _settlement) -> None:
            raise ProductCollectionGatewayError(
                "PRODUCT_COLLECTION_GATEWAY_SETTLEMENT_REJECTED",
                "手机采集网关拒绝了终态结算",
                retryable=False,
            )

    @contextmanager
    def sessions():
        yield object()

    monkeypatch.setattr(executor, "ProductCollectionSettlementService", SettlementService)
    worker = executor.ProductCollectionExecutor(
        session_factory=sessions,
        settings=Settings(
            product_collection_settlement_enabled=True,
            product_collection_settlement_max_attempts=5,
        ),
        gateway=Gateway(),
        cleaner=None,
    )
    assert worker.settle_once() is True
    assert recorded["claim"] is claim
    assert recorded["max_attempts"] == 2
    assert recorded["error_code"] == "PRODUCT_COLLECTION_GATEWAY_SETTLEMENT_REJECTED"
