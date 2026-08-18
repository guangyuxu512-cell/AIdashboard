import asyncio
import logging
import signal

from pydantic import ValidationError

from app.client import WorkerApiClient
from app.config import get_settings
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
from app.skills import registry
from app.skills.registry import SkillProvider, SkillRuntime
from app.worker import Worker


async def run_worker() -> None:
    settings = get_settings()
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        return 0
    except ValidationError as error:
        logging.getLogger(__name__).error(
            "Worker configuration is invalid: %s",
            error.errors(include_input=False),
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
