import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from app.contracts import AccountPayload, ExecutionResult, ExecutionStatus, WorkerTask
from app.executors.router import ExecutorRouter
from app.executors.rpa import RPAExecutor
from app.local_config import LocalInputPaths
from app.local_input import (
    LocalInputBridge,
    LocalInputPreparationError,
)
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
        self.requests: list[YingdaoExecutionRequest] = []
        self.active = 0
        self.max_active = 0

    async def discover(self) -> YingdaoDiscoveryResult:
        return self.discovery

    async def execute(
        self,
        request: YingdaoExecutionRequest,
    ) -> Mapping[str, Any]:
        self.execute_calls.append(str(request.task_id))
        self.requests.append(request)
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
        LocalInputBridge(
            LocalInputPaths(
                params_json_path=runtime_root / "local-input" / "params.json",
                account_json_path=runtime_root / "local-input" / "account.json",
                images_dir=runtime_root / "local-input" / "images",
            ),
        ),
    )


def make_task(
    *,
    params: dict[str, Any] | None = None,
    accounts: list[AccountPayload] | None = None,
) -> WorkerTask:
    return WorkerTask(
        task_id=uuid4(),
        skill_id="yingdao.test",
        input={"params": params or {}},
        accounts=accounts or [],
        lease_until="2026-08-20T12:00:00+00:00",
    )


def make_account(*, secret: str = "task-secret") -> AccountPayload:
    return AccountPayload(
        shop_id="7cb00c72-f6f9-4e89-9ac6-f1ce03c5544b",
        shop_name="测试店铺",
        platform_code="DOUYIN",
        login_identifier="测试账号",
        secret=secret,
        preferred_verification_channel="SMS",
    )


def run(executor: RPAExecutor, task: WorkerTask):
    return asyncio.run(executor.execute(task))


def test_rpa_executor_parses_success_and_uses_shared_runtime(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(
        discovery=discovery(),
        result={"status": "success", "result": {"message": "ok"}},
    )
    executor = make_executor(tmp_path, adapter)
    task = make_task(
        params={"关键词": "测试", "count": 2},
        accounts=[make_account()],
    )

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
    local_input = tmp_path / "local-input"
    assert json.loads((local_input / "params.json").read_text("utf-8")) == {
        "关键词": "测试",
        "count": 2,
    }
    assert json.loads((local_input / "account.json").read_text("utf-8")) == {
        "店铺列表": [
            {
                "店铺ID": "7cb00c72-f6f9-4e89-9ac6-f1ce03c5544b",
                "店铺名称": "测试店铺",
                "平台编码": "DOUYIN",
                "登录账号": "测试账号",
                "登录密码": "task-secret",
                "首选验证方式": "SMS",
            },
        ],
    }
    assert (local_input / "images").is_dir()
    assert adapter.requests[0].params == {"关键词": "测试", "count": 2}


def test_yingdao_claim_params_preserve_unicode_key_and_json_looking_text(
    tmp_path: Path,
) -> None:
    adapter = FakeYingdaoAdapter(discovery=discovery())
    executor = make_executor(tmp_path, adapter)
    task = make_task(params={"商品列表": '{"page":1}'})

    result = run(executor, task)

    assert result.status is ExecutionStatus.SUCCESS
    params_path = tmp_path / "local-input" / "params.json"
    params = json.loads(params_path.read_text("utf-8"))
    assert params == {"商品列表": '{"page":1}'}
    assert isinstance(params["商品列表"], str)
    assert not list(params_path.parent.glob(".*.tmp"))
    assert adapter.requests[0].params == {"商品列表": '{"page":1}'}


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
            LocalInputBridge(
                LocalInputPaths(
                    params_json_path=tmp_path / "local-input" / "params.json",
                    account_json_path=tmp_path / "local-input" / "account.json",
                    images_dir=tmp_path / "local-input" / "images",
                ),
            ),
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


def test_yingdao_bridge_overwrites_stale_params_and_account(tmp_path: Path) -> None:
    adapter = FakeYingdaoAdapter(discovery=discovery())
    executor = make_executor(tmp_path, adapter)

    first = run(
        executor,
        make_task(
            params={"a": 1},
            accounts=[make_account(secret="task-a")],
        ),
    )
    second = run(executor, make_task(params={"b": 2}))

    assert first.status is ExecutionStatus.SUCCESS
    assert second.status is ExecutionStatus.SUCCESS
    local_input = tmp_path / "local-input"
    assert json.loads((local_input / "params.json").read_text("utf-8")) == {
        "b": 2,
    }
    assert json.loads((local_input / "account.json").read_text("utf-8")) == {
        "店铺列表": [],
    }


def test_yingdao_preparation_failure_does_not_launch_application(
    tmp_path: Path,
) -> None:
    class FailingPreparer:
        def prepare(self, **_: object) -> None:
            raise LocalInputPreparationError(
                "LOCAL_PARAMS_FILE_PREPARATION_FAILED",
                "本地参数文件准备失败",
            )

    adapter = FakeYingdaoAdapter(discovery=discovery())
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
    executor = RPAExecutor(
        tmp_path,
        skill_registry,
        {SkillProvider.YINGDAO: adapter},
        FailingPreparer(),
    )

    result = run(executor, make_task(params={"private_marker": "hidden"}))

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "LOCAL_PARAMS_FILE_PREPARATION_FAILED"
    assert result.error_message == "本地参数文件准备失败"
    assert adapter.execute_calls == []
    assert adapter.cleanup_calls == 0


def test_unavailable_images_directory_does_not_launch_application(
    tmp_path: Path,
) -> None:
    images_path = tmp_path / "local-input" / "images"
    images_path.parent.mkdir(parents=True)
    images_path.write_text("not a directory", encoding="utf-8")
    adapter = FakeYingdaoAdapter(discovery=discovery())
    executor = make_executor(tmp_path, adapter)

    result = run(executor, make_task())

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "LOCAL_IMAGES_DIRECTORY_UNAVAILABLE"
    assert result.error_message == "图片目录不可用"
    assert adapter.execute_calls == []
