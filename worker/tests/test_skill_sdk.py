import asyncio
from datetime import UTC, datetime
from enum import StrEnum
import io
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import Field, ValidationError

from app.contracts import (
    AccountPayload,
    ExecutionStatus,
    RuntimeEventType,
    SkillProcessInput,
    SkillProcessPaths,
)
from app.contracts import WorkerTask
from app.executors.python import PythonExecutor
from app.runtime_events import RuntimeEventBus
from app.skills import registry as production_registry
from app.skills.registry import (
    BUSINESS_SKILL_INPUT_SCHEMA_MAX_BYTES,
    SkillClassification,
    SkillDescriptor,
    SkillRegistry,
    SkillRuntime,
)
from app.skills.runner import execute_async
from app.skills.sdk import (
    BusinessSkillInput,
    BusinessSkillRunner,
    SkillContext,
    SkillExecutionError,
    SkillResult,
    register_business_skill,
)
from app.skills.sdk.contracts import MAX_SKILL_RESULT_BYTES
from app.skills.sdk.process_events import (
    ProcessRuntimeEventWriter,
    decode_process_event_line,
)


class ProgressInput(BusinessSkillInput):
    steps: int = Field(gt=0, le=10)


class RunMode(StrEnum):
    SAFE = "safe"
    FAST = "fast"


class CatalogInput(BusinessSkillInput):
    keyword: str = Field(title="关键词", description="需要处理的关键词")
    count: int = Field(default=10, title="数量")
    ratio: float = Field(default=0.5, title="比例")
    enabled: bool = Field(default=True, title="启用")
    mode: RunMode = Field(default=RunMode.SAFE, title="模式")


class ProgressSkill:
    descriptor = SkillDescriptor(
        skill_id="demo.progress",
        display_name="SDK进度测试",
        runtime=SkillRuntime.PYTHON,
        provider=None,
        version="1",
        classification=SkillClassification.BUSINESS,
    )
    input_model = ProgressInput
    timeout_seconds = 1.0

    def __init__(self) -> None:
        self.context: SkillContext | None = None
        self.received_input: ProgressInput | None = None

    async def run(
        self,
        ctx: SkillContext,
        input: ProgressInput,
    ) -> SkillResult:
        self.context = ctx
        self.received_input = input
        ctx.log("开始处理", metadata={"page": 1})
        ctx.progress(current=input.steps, total=input.steps, message="处理完成")
        return SkillResult(
            summary="SDK执行完成",
            data={"processed": input.steps},
        )


def make_registered(skill: object) -> tuple[SkillRegistry, object]:
    skill_registry = SkillRegistry()
    definition = register_business_skill(skill_registry, skill)  # type: ignore[arg-type]
    return skill_registry, definition


def process_input(
    task_id: UUID,
    params: dict[str, object],
    *,
    accounts: list[AccountPayload] | None = None,
    images: Path = Path("fixture-images"),
) -> SkillProcessInput:
    return SkillProcessInput(
        task_id=task_id,
        skill_id="demo.progress",
        params=params,
        accounts=accounts or [],
        paths=SkillProcessPaths(images=images),
    )


def account_payload(*, secret: str = "must-not-leak") -> AccountPayload:
    return AccountPayload(
        shop_id="7cb00c72-f6f9-4e89-9ac6-f1ce03c5544b",
        shop_name="中文店铺",
        platform_code="DOUYIN",
        login_identifier="fixture-account",
        secret=secret,
        preferred_verification_channel="SMS",
    )


def test_business_skill_registration_reuses_descriptor_and_registry() -> None:
    skill = ProgressSkill()
    skill_registry, definition = make_registered(skill)

    descriptor = definition.descriptor()  # type: ignore[attr-defined]
    assert descriptor.model_dump(
        exclude={"input_schema"},
    ) == skill.descriptor.model_dump(exclude={"input_schema"})  # type: ignore[attr-defined]
    assert descriptor.input_schema == ProgressInput.model_json_schema(
        mode="validation",
    )
    assert definition.business_skill is skill  # type: ignore[attr-defined]
    assert skill_registry.require("demo.progress") is definition
    assert definition.classification is SkillClassification.BUSINESS  # type: ignore[attr-defined]


def test_business_skill_descriptor_uses_pydantic_schema_as_single_source() -> None:
    class CatalogSkill(ProgressSkill):
        input_model = CatalogInput

    _, definition = make_registered(CatalogSkill())
    schema = definition.descriptor().input_schema  # type: ignore[attr-defined]

    assert schema is not None
    assert schema["type"] == "object"
    assert schema["required"] == ["keyword"]
    assert schema["properties"]["keyword"] == {
        "description": "需要处理的关键词",
        "title": "关键词",
        "type": "string",
    }
    assert schema["properties"]["count"]["type"] == "integer"
    assert schema["properties"]["ratio"]["type"] == "number"
    assert schema["properties"]["enabled"]["type"] == "boolean"
    assert schema["properties"]["mode"]["$ref"] == "#/$defs/RunMode"
    assert schema["$defs"]["RunMode"]["enum"] == ["safe", "fast"]


def test_business_skill_registration_rejects_oversized_input_schema() -> None:
    class OversizedInput(BusinessSkillInput):
        payload: str = Field(
            description="x" * BUSINESS_SKILL_INPUT_SCHEMA_MAX_BYTES,
        )

    class OversizedSkill(ProgressSkill):
        input_model = OversizedInput

    with pytest.raises(ValueError, match="32 KiB"):
        make_registered(OversizedSkill())


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"steps": {"invalid": True}},
        {"steps": 2, "unexpected": True},
    ],
)
def test_runner_rejects_missing_wrong_and_extra_input(
    params: dict[str, object],
) -> None:
    skill_registry, definition = make_registered(ProgressSkill())
    del skill_registry
    result = asyncio.run(
        BusinessSkillRunner(
            device_id=uuid4(),
            event_bus=RuntimeEventBus(),
        ).execute(definition, process_input(uuid4(), params)),  # type: ignore[arg-type]
    )

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "SKILL_INPUT_INVALID"


def test_context_log_progress_and_result_use_existing_runtime_contract(
    tmp_path: Path,
) -> None:
    task_id = uuid4()
    device_id = uuid4()
    bus = RuntimeEventBus()
    events = []
    bus.subscribe(events.append)
    skill = ProgressSkill()
    _, definition = make_registered(skill)

    result = asyncio.run(
        BusinessSkillRunner(device_id=device_id, event_bus=bus).execute(
            definition,  # type: ignore[arg-type]
            process_input(
                task_id,
                {"steps": 3},
                accounts=[account_payload()],
                images=tmp_path / "images",
            ),
        ),
    )

    assert result.status is ExecutionStatus.SUCCESS
    assert result.result == {
        "summary": "SDK执行完成",
        "data": {"processed": 3},
    }
    assert skill.context is not None
    assert isinstance(skill.received_input, ProgressInput)
    assert skill.context.task_id == task_id
    assert skill.context.device_id == device_id
    assert skill.context.skill_id == "demo.progress"
    assert skill.context.deadline > datetime.now(UTC)
    assert skill.context.is_cancelled is False
    assert skill.context.accounts == [
        {
            "shop_id": "7cb00c72-f6f9-4e89-9ac6-f1ce03c5544b",
            "shop_name": "中文店铺",
            "platform_code": "DOUYIN",
            "login_identifier": "fixture-account",
            "secret": "must-not-leak",
            "preferred_verification_channel": "SMS",
        },
    ]
    assert skill.context.paths.images == tmp_path / "images"
    assert [event.event_type for event in events] == [
        RuntimeEventType.LOG,
        RuntimeEventType.PROGRESS,
    ]
    assert all(event.task_id == task_id for event in events)
    assert events[0].metadata == {"page": 1, "skill_id": "demo.progress"}
    assert events[1].metadata == {
        "skill_id": "demo.progress",
        "current": 3,
        "total": 3,
    }
    assert "must-not-leak" not in "".join(
        event.model_dump_json() for event in events
    )
    assert "must-not-leak" not in result.model_dump_json()


def test_nonsecret_precheck_shop_ids_reach_skill_context() -> None:
    shops = [uuid4(), uuid4()]
    skill = ProgressSkill()
    _, definition = make_registered(skill)
    payload = process_input(uuid4(), {"steps": 1}).model_copy(update={"shop_ids": shops})
    result = asyncio.run(BusinessSkillRunner(
        device_id=uuid4(), event_bus=RuntimeEventBus(),
    ).execute(definition, payload))  # type: ignore[arg-type]
    assert result.status is ExecutionStatus.SUCCESS
    assert skill.context is not None
    assert skill.context.shop_ids == tuple(shops)
    assert skill.context.accounts == []


def test_skill_execution_error_keeps_code_retryable_and_safe_event() -> None:
    class ExpectedFailureSkill(ProgressSkill):
        async def run(
            self,
            ctx: SkillContext,
            input: ProgressInput,
        ) -> SkillResult:
            del ctx, input
            raise SkillExecutionError(
                "PLATFORM_TEMPORARILY_UNAVAILABLE",
                "平台暂时不可用",
                retryable=True,
                details={"attempt": 1},
            )

    bus = RuntimeEventBus()
    events = []
    bus.subscribe(events.append)
    _, definition = make_registered(ExpectedFailureSkill())
    result = asyncio.run(
        BusinessSkillRunner(device_id=uuid4(), event_bus=bus).execute(
            definition,  # type: ignore[arg-type]
            process_input(uuid4(), {"steps": 1}),
        ),
    )

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "PLATFORM_TEMPORARILY_UNAVAILABLE"
    assert result.error_message == "平台暂时不可用"
    assert events[-1].metadata["retryable"] is True
    assert "details" not in events[-1].metadata


def test_unexpected_exception_returns_safe_error_and_logs_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class UnexpectedFailureSkill(ProgressSkill):
        async def run(
            self,
            ctx: SkillContext,
            input: ProgressInput,
        ) -> SkillResult:
            del ctx, input
            raise RuntimeError("token=must-not-reach-task-error")

    _, definition = make_registered(UnexpectedFailureSkill())
    result = asyncio.run(
        BusinessSkillRunner(
            device_id=uuid4(),
            event_bus=RuntimeEventBus(),
        ).execute(definition, process_input(uuid4(), {"steps": 1})),  # type: ignore[arg-type]
    )

    assert result.error_code == "SKILL_EXECUTION_FAILED"
    assert result.error_message == "Skill execution failed"
    assert "must-not-reach-task-error" not in caplog.text
    assert "test_skill_sdk.py" in caplog.text
    assert "in run" in caplog.text


def test_runner_enforces_timeout() -> None:
    class TimeoutSkill(ProgressSkill):
        timeout_seconds = 0.01

        async def run(
            self,
            ctx: SkillContext,
            input: ProgressInput,
        ) -> SkillResult:
            del ctx, input
            await asyncio.sleep(1)
            raise AssertionError

    _, definition = make_registered(TimeoutSkill())
    result = asyncio.run(
        BusinessSkillRunner(
            device_id=uuid4(),
            event_bus=RuntimeEventBus(),
        ).execute(definition, process_input(uuid4(), {"steps": 1})),  # type: ignore[arg-type]
    )

    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "SKILL_TIMEOUT"


def test_skill_result_is_json_only_and_bounded() -> None:
    with pytest.raises(ValidationError):
        SkillResult(summary="too large", data={"payload": "x" * MAX_SKILL_RESULT_BYTES})

    result = SkillResult(summary="ok", data={"count": 2, "valid": True})
    assert result.model_dump() == {
        "summary": "ok",
        "data": {"count": 2, "valid": True},
    }


def test_process_event_transport_round_trips_runtime_event() -> None:
    stream = io.StringIO()
    bus = RuntimeEventBus()
    bus.subscribe(ProcessRuntimeEventWriter(stream))
    emitted = bus.emit(uuid4(), RuntimeEventType.LOG, "hello", level="info")

    decoded = decode_process_event_line(stream.getvalue().encode("utf-8"))

    assert decoded == emitted
    assert decode_process_event_line(b"ordinary stdout\n") is None


def test_python_executor_forwards_child_events_to_parent_bus(tmp_path) -> None:
    async def scenario() -> tuple[list[object], str]:
        task_id = uuid4()
        task = WorkerTask(
            task_id=task_id,
            skill_id="demo.progress",
            input={"steps": 1},
            lease_until=datetime.now(UTC),
        )
        child_stream = io.StringIO()
        child_bus = RuntimeEventBus()
        child_bus.subscribe(ProcessRuntimeEventWriter(child_stream))
        child_bus.emit(
            task_id,
            RuntimeEventType.PROGRESS,
            "half",
            metadata={"current": 1, "total": 2},
        )

        reader = asyncio.StreamReader()
        reader.feed_data(child_stream.getvalue().encode("utf-8"))
        reader.feed_data(b"ordinary stdout\n")
        reader.feed_eof()
        parent_bus = RuntimeEventBus()
        received = []
        parent_bus.subscribe(received.append)
        output = tmp_path / "stdout.log"
        output.touch()
        executor = PythonExecutor(
            tmp_path,
            parent_bus,
            device_id=uuid4(),
            images_dir=tmp_path / "images",
        )

        await executor._forward_stdout(reader, output, task)
        return received, output.read_text(encoding="utf-8")

    received, stdout = asyncio.run(scenario())

    assert len(received) == 1
    assert received[0].event_type is RuntimeEventType.PROGRESS  # type: ignore[attr-defined]
    assert received[0].message == "half"  # type: ignore[attr-defined]
    assert stdout == "ordinary stdout\n"


def test_process_runner_routes_business_skill_through_sdk() -> None:
    task_id = uuid4()
    skill = ProgressSkill()
    skill_registry, _ = make_registered(skill)
    result = asyncio.run(
        execute_async(
            "demo.progress",
            {
                "task_id": str(task_id),
                "skill_id": "demo.progress",
                "params": {"steps": 2},
                "accounts": [account_payload().model_dump(mode="json")],
                "paths": {"images": "fixture-images"},
            },
            device_id=uuid4(),
            event_bus=RuntimeEventBus(),
            skill_registry=skill_registry,
        ),
    )

    assert result.status is ExecutionStatus.SUCCESS
    assert result.result == {
        "summary": "SDK执行完成",
        "data": {"processed": 2},
    }
    assert isinstance(skill.received_input, ProgressInput)
    assert skill.context is not None
    assert skill.context.accounts == [account_payload().model_dump(mode="json")]
    assert skill.context.paths.images == Path("fixture-images")


def test_demo_skill_is_not_in_production_registry() -> None:
    descriptors = production_registry.descriptors()

    assert "demo.progress" not in {item.skill_id for item in descriptors}
    assert sum(
        item.classification is SkillClassification.BUSINESS
        for item in descriptors
    ) == 0
