import asyncio
import logging
import signal

from pydantic import ValidationError

from app.client import WorkerApiClient
from app.config import WorkerSettings, get_settings
from app.executors import (
    ExecutorRouter,
    ProviderDiscoveryExecutor,
    PythonExecutor,
    RPAExecutor,
)
from app.providers.yingdao import (
    RuntimeYingdaoAdapter,
    WindowsYingdaoRuntimeLocator,
    YingdaoApplicationAdapter,
    YingdaoDiscoveryService,
    YingdaoSessionAdapter,
)
from app.runtime_events import (
    BackendEventReporter,
    LocalRuntimeState,
    RuntimeEventBuffer,
    RuntimeEventBus,
)
from app.logging_config import configure_logging
from app.single_instance import WorkerAlreadyRunningError, WorkerSingleInstance
from app.local_config import WorkerConfigurationError
from app.process_control import WorkerProcessState
from app.skills import registry
from app.skills.registry import SkillProvider, SkillRuntime
from app.worker import Worker


async def run_worker(settings: WorkerSettings) -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop_event.set)
        except NotImplementedError:
            pass
    client = WorkerApiClient(settings)
    event_bus = RuntimeEventBus()
    event_buffer = RuntimeEventBuffer(settings.event_buffer_capacity)
    local_runtime_state = LocalRuntimeState(
        path=settings.runtime_status_path,
        device_id=settings.device_id,
        device_display_name=settings.device_display_name,
        server_url=str(settings.server_url).rstrip("/"),
    )
    event_bus.subscribe(event_buffer.append)
    event_bus.subscribe(local_runtime_state.consume)
    event_reporter = BackendEventReporter(
        client,
        event_buffer,
        flush_interval_seconds=settings.event_flush_interval_seconds,
        batch_size=settings.event_batch_size,
        retry_count=settings.event_flush_retry_count,
    )
    runtime_locator = WindowsYingdaoRuntimeLocator(
        settings.yingdao_install_root,
        startup_timeout_seconds=settings.yingdao_startup_timeout_seconds,
    )
    session_adapter = YingdaoSessionAdapter(runtime_locator)
    application_adapter = YingdaoApplicationAdapter()
    discovery_service = YingdaoDiscoveryService(
        session_adapter=session_adapter,
        application_adapter=application_adapter,
    )
    yingdao_adapter = RuntimeYingdaoAdapter(
        discovery_service=discovery_service,
        session_adapter=session_adapter,
        application_adapter=application_adapter,
        data_root=settings.yingdao_data_root or discovery_service.data_root,
        event_bus=event_bus,
    )
    executor = ExecutorRouter(
        registry,
        {
            SkillRuntime.PYTHON: PythonExecutor(settings.runtime_root, event_bus),
            SkillRuntime.RPA: RPAExecutor(
                settings.runtime_root,
                registry,
                {SkillProvider.YINGDAO: yingdao_adapter},
                event_bus,
                (
                    {"yingdao.test": settings.yingdao_test_app_id}
                    if settings.yingdao_test_app_id is not None
                    else {}
                ),
            ),
            SkillRuntime.DISCOVERY: ProviderDiscoveryExecutor(
                settings.runtime_root,
                registry,
                {
                    SkillProvider.YINGDAO: discovery_service,
                },
                event_bus,
            ),
        },
    )
    worker = Worker(
        settings,
        client,
        executor,
        event_bus,
        event_reporter,
        local_runtime_state,
        provider_discovery=discovery_service,
        skill_registry=registry,
    )
    await worker.run(stop_event)


def main() -> int:
    try:
        settings = get_settings()
        configure_logging(settings)
        with WorkerSingleInstance(settings.device_id), WorkerProcessState(
            settings.device_id,
        ):
            asyncio.run(run_worker(settings))
    except KeyboardInterrupt:
        return 0
    except WorkerAlreadyRunningError:
        logging.getLogger(__name__).error(
            "Worker is already running for this Device identity",
        )
        return 3
    except ValidationError as error:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger(__name__).error(
            "Worker configuration is invalid: %s",
            error.errors(include_input=False),
        )
        return 2
    except WorkerConfigurationError as error:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger(__name__).error("Worker configuration error: %s", error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
