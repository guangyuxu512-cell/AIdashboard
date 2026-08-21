import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from app.contracts import ExecutionStatus, WorkerTask
from app.executors.rpa import RPAExecutor
from app.providers.yingdao import (
    YingdaoApplication,
    YingdaoDiscoveryResult,
    YingdaoExecutionRequest,
    YingdaoTriggerError,
)
from app.skills.registry import (
    SkillDefinition,
    SkillProvider,
    SkillRegistry,
    SkillRuntime,
)


FAKE_APP_ID = "fake-yingdao-test-app"


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FakeYingdaoAdapter:
    def __init__(
        self,
        *,
        discovery: YingdaoDiscoveryResult,
        result: Mapping[str, Any] | None = None,
        trigger_error: bool = False,
        delay: float = 0,
    ) -> None:
        self.discovery = discovery
        self.result = result or {"status": "success", "result": {}}
        self.trigger_error = trigger_error
        self.delay = delay
        self.cleanup_calls = 0

    async def discover(self) -> YingdaoDiscoveryResult:
        return self.discovery

    async def execute(
        self,
        request: YingdaoExecutionRequest,
    ) -> Mapping[str, Any]:
        del request
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.trigger_error:
            raise YingdaoTriggerError("fake trigger failed")
        return self.result

    async def cleanup(self, request: YingdaoExecutionRequest) -> None:
        del request
        self.cleanup_calls += 1


def discovery(*, available: bool = True, app_id: str | None = FAKE_APP_ID):
    applications = (
        [YingdaoApplication(app_id=app_id, app_name="Fake test app")]
        if app_id
        else []
    )
    return YingdaoDiscoveryResult(
        provider_available=available,
        account_display="Fake account" if available else None,
        applications=applications,
    )


def make_executor(
    runtime_root: Path,
    adapter: FakeYingdaoAdapter,
    *,
    app_id: str | None = FAKE_APP_ID,
    timeout: float = 1,
) -> RPAExecutor:
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="yingdao.test",
            display_name="影刀测试",
            version="1",
            input_model=EmptyInput,
            runtime=SkillRuntime.RPA,
            provider=SkillProvider.YINGDAO,
            provider_app_id=app_id,
            timeout_seconds=timeout,
        ),
    )
    return RPAExecutor(
        runtime_root,
        registry,
        {SkillProvider.YINGDAO: adapter},
    )


def make_task() -> WorkerTask:
    return WorkerTask(
        task_id=uuid4(),
        skill_id="yingdao.test",
        input={},
        lease_until="2026-08-20T12:00:00+00:00",
    )


def run(executor: RPAExecutor, task: WorkerTask):
    return asyncio.run(executor.execute(task))


def test_rpa_executor_parses_success_and_uses_shared_runtime(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(
        discovery=discovery(),
        result={"status": "success", "result": {"message": "ok"}},
    )
    executor = make_executor(tmp_path, adapter)
    task = make_task()

    result = run(executor, task)
    runtime = tmp_path / str(task.task_id)

    assert result.status is ExecutionStatus.SUCCESS
    assert result.result == {"message": "ok"}
    assert adapter.cleanup_calls == 1
    assert (runtime / "input.json").exists()
    assert (runtime / "status.json").exists()
    assert (runtime / "output.json").exists()
    assert (runtime / "stdout.log").exists()
    assert (runtime / "stderr.log").exists()
    assert (runtime / "artifacts").is_dir()
    assert json.loads((runtime / "status.json").read_text("utf-8"))["status"] == (
        "success"
    )


def test_rpa_provider_unavailable_finishes_failed(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(discovery=discovery(available=False))
    task = make_task()
    result = run(make_executor(tmp_path, adapter), task)

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "RPA_PROVIDER_UNAVAILABLE"
    status = json.loads(
        (tmp_path / str(task.task_id) / "status.json").read_text("utf-8"),
    )
    assert status["status"] == "failed"


def test_rpa_application_not_found_finishes_failed(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(discovery=discovery(app_id=None))
    result = run(make_executor(tmp_path, adapter), make_task())

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "RPA_APPLICATION_NOT_FOUND"


def test_rpa_application_mapping_missing_finishes_failed(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(discovery=discovery())
    result = run(make_executor(tmp_path, adapter, app_id=None), make_task())

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "RPA_APPLICATION_NOT_CONFIGURED"


def test_rpa_trigger_failure_finishes_failed_and_cleans_up(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(discovery=discovery(), trigger_error=True)
    result = run(make_executor(tmp_path, adapter), make_task())

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "RPA_TRIGGER_FAILED"
    assert adapter.cleanup_calls == 1


def test_rpa_timeout_finishes_failed_and_cleans_up(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(discovery=discovery(), delay=0.05)
    result = run(make_executor(tmp_path, adapter, timeout=0.01), make_task())

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "RPA_TIMEOUT"
    assert adapter.cleanup_calls == 1


def test_rpa_invalid_result_finishes_failed(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(
        discovery=discovery(),
        result={"status": "success", "unexpected": True},
    )
    result = run(make_executor(tmp_path, adapter), make_task())

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "RPA_RESULT_INVALID"


def test_rpa_explicit_failed_result_uses_worker_error_code(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(
        discovery=discovery(),
        result={
            "status": "failed",
            "error_code": "YINGDAO_TEST_FAILED",
            "error_message": "Fake application reported failure",
        },
    )
    result = run(make_executor(tmp_path, adapter), make_task())

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "RPA_EXECUTION_FAILED"
    assert result.error_message == "Fake application reported failure"
