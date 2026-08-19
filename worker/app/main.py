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
    UnavailableYingdaoAdapter,
    YingdaoDiscoveryService,
)
from app.logging_config import configure_logging
from app.single_instance import WorkerAlreadyRunningError, WorkerSingleInstance
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
    executor = ExecutorRouter(
        registry,
        {
            SkillRuntime.PYTHON: PythonExecutor(settings.runtime_root),
            SkillRuntime.RPA: RPAExecutor(
                settings.runtime_root,
                registry,
                {SkillProvider.YINGDAO: UnavailableYingdaoAdapter()},
            ),
            SkillRuntime.DISCOVERY: ProviderDiscoveryExecutor(
                settings.runtime_root,
                registry,
                {
                    SkillProvider.YINGDAO: YingdaoDiscoveryService(
                        install_root=settings.yingdao_install_root,
                        data_root=settings.yingdao_data_root,
                        command_timeout_seconds=(
                            settings.yingdao_command_timeout_seconds
                        ),
                    ),
                },
            ),
        },
    )
    worker = Worker(
        settings,
        client,
        executor,
    )
    await worker.run(stop_event)


def main() -> int:
    try:
        settings = get_settings()
        configure_logging(settings)
        with WorkerSingleInstance(settings.device_id):
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
