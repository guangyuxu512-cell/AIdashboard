import asyncio
import logging
import signal

from pydantic import ValidationError

from app.client import WorkerApiClient
from app.config import get_settings
from app.executors import PythonExecutor
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
    worker = Worker(
        settings,
        WorkerApiClient(settings),
        PythonExecutor(settings.runtime_root),
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
