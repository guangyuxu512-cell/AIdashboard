import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from app.contracts import ExecutionResult, ExecutionStatus, WorkerTask
from app.executors.router import ExecutorRouter
from app.executors.rpa import RPAExecutor
from app.providers.yingdao import (
    YingdaoApplication,
    YingdaoDiscoveryResult,
    YingdaoExecutionRequest,
    YingdaoTriggerError,
)
from app.skills.registry import (
    SkillClassification,
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
        self.execute_calls: list[str] = []
        self.active = 0
        self.max_active = 0

    async def discover(self) -> YingdaoDiscoveryResult:
        return self.discovery

    async def execute(
        self,
        request: YingdaoExecutionRequest,
    ) -> Mapping[str, Any]:
        self.execute_calls.append(str(request.task_id))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.trigger_error:
                raise YingdaoTriggerError("fake trigger failed")
            return self.result
        finally:
            self.active -= 1

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
            classification=SkillClassification.INTERNAL,
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


def test_yingdao_provider_capacity_serializes_three_tasks(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(discovery=discovery(), delay=0.01)
    executor = make_executor(tmp_path, adapter)
    tasks = [make_task(), make_task(), make_task()]

    async def scenario():
        return await asyncio.gather(*(executor.execute(task) for task in tasks))

    results = asyncio.run(scenario())

    assert [result.status for result in results] == [
        ExecutionStatus.SUCCESS,
        ExecutionStatus.SUCCESS,
        ExecutionStatus.SUCCESS,
    ]
    assert adapter.execute_calls == [str(task.task_id) for task in tasks]
    assert adapter.max_active == 1
    assert adapter.cleanup_calls == 3
    assert executor.can_claim() is True


def test_yingdao_failure_releases_slot_for_next_task(tmp_path: Path) -> None:
    class FailFirstAdapter(FakeYingdaoAdapter):
        async def execute(
            self,
            request: YingdaoExecutionRequest,
        ) -> Mapping[str, Any]:
            self.execute_calls.append(str(request.task_id))
            if len(self.execute_calls) == 1:
                raise YingdaoTriggerError("first failed")
            return self.result

    adapter = FailFirstAdapter(discovery=discovery())
    executor = make_executor(tmp_path, adapter)
    first, second = make_task(), make_task()

    async def scenario():
        return await asyncio.gather(
            executor.execute(first),
            executor.execute(second),
        )

    first_result, second_result = asyncio.run(scenario())

    assert first_result.status is ExecutionStatus.FAILED
    assert second_result.status is ExecutionStatus.SUCCESS
    assert adapter.execute_calls == [str(first.task_id), str(second.task_id)]
    assert executor.can_claim() is True


def test_timed_out_yingdao_keeps_slot_until_provider_really_returns(
    tmp_path: Path,
) -> None:
    class ControlledAdapter(FakeYingdaoAdapter):
        def __init__(self) -> None:
            super().__init__(discovery=discovery())
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(
            self,
            request: YingdaoExecutionRequest,
        ) -> Mapping[str, Any]:
            self.execute_calls.append(str(request.task_id))
            self.started.set()
            await self.release.wait()
            return self.result

    async def scenario() -> None:
        adapter = ControlledAdapter()
        executor = make_executor(tmp_path, adapter, timeout=0.05)
        first, second = make_task(), make_task()

        first_result = await executor.execute(first)
        assert first_result.error_code == "RPA_TIMEOUT"
        assert executor.can_claim() is False

        second_execution = asyncio.create_task(executor.execute(second))
        await asyncio.sleep(0.06)
        assert adapter.execute_calls == [str(first.task_id)]

        adapter.release.set()
        second_result = await asyncio.wait_for(second_execution, timeout=1)
        await asyncio.sleep(0)
        assert second_result.status is ExecutionStatus.SUCCESS
        assert adapter.execute_calls == [str(first.task_id), str(second.task_id)]
        assert executor.can_claim() is True

    asyncio.run(scenario())


def test_yingdao_provider_slot_is_not_a_global_executor_lock(tmp_path: Path) -> None:
    class ControlledAdapter(FakeYingdaoAdapter):
        def __init__(self) -> None:
            super().__init__(discovery=discovery())
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(
            self,
            request: YingdaoExecutionRequest,
        ) -> Mapping[str, Any]:
            self.execute_calls.append(str(request.task_id))
            self.started.set()
            await self.release.wait()
            return self.result

    class ImmediatePythonExecutor:
        def can_claim(self) -> bool:
            return True

        async def execute(self, task: WorkerTask) -> ExecutionResult:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={"task_id": str(task.task_id)},
            )

    async def scenario() -> None:
        adapter = ControlledAdapter()
        skill_registry = SkillRegistry()
        skill_registry.register(
            SkillDefinition(
                skill_id="yingdao.test",
                display_name="影刀测试",
                version="1",
                input_model=EmptyInput,
                runtime=SkillRuntime.RPA,
                provider=SkillProvider.YINGDAO,
                provider_app_id=FAKE_APP_ID,
                timeout_seconds=1,
                classification=SkillClassification.INTERNAL,
            ),
        )
        skill_registry.register(
            SkillDefinition(
                skill_id="system.fixture",
                display_name="Python Fixture",
                version="1",
                input_model=EmptyInput,
                runtime=SkillRuntime.PYTHON,
                timeout_seconds=1,
                handler=lambda _: {},
                classification=SkillClassification.INTERNAL,
            ),
        )
        rpa_executor = RPAExecutor(
            tmp_path,
            skill_registry,
            {SkillProvider.YINGDAO: adapter},
        )
        router = ExecutorRouter(
            skill_registry,
            {
                SkillRuntime.RPA: rpa_executor,
                SkillRuntime.PYTHON: ImmediatePythonExecutor(),
            },
        )
        rpa_task = make_task()
        python_task = WorkerTask(
            task_id=uuid4(),
            skill_id="system.fixture",
            input={},
            lease_until="2026-08-20T12:00:00+00:00",
        )

        running_rpa = asyncio.create_task(router.execute(rpa_task))
        await adapter.started.wait()
        python_result = await asyncio.wait_for(router.execute(python_task), timeout=0.1)

        assert python_result.status is ExecutionStatus.SUCCESS
        assert running_rpa.done() is False
        adapter.release.set()
        assert (await running_rpa).status is ExecutionStatus.SUCCESS

    asyncio.run(scenario())
