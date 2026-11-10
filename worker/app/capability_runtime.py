"""Load only signed and locally verified capability entrypoints."""
from __future__ import annotations

import inspect
import json
from types import ModuleType

from app.capability_updates import CapabilityUpdateError, CapabilityUpdater
from app.contracts import ExecutionResult, ExecutionStatus, WorkerTask
from app.skills.registry import SkillClassification, SkillDescriptor, SkillRuntime


def _load_entry(skill_id: str, source: bytes) -> ModuleType:
    try:
        module = ModuleType(f"verified_capability_{skill_id.replace('.', '_')}")
        exec(compile(source, "<verified-capability>", "exec", dont_inherit=True), module.__dict__)
        schema = getattr(module, "INPUT_SCHEMA", None)
        if (getattr(module, "SKILL_ID", None) != skill_id
                or not inspect.iscoroutinefunction(getattr(module, "execute", None))
                or not isinstance(schema, dict) or schema.get("type") != "object"
                or len(json.dumps(schema, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > 32 * 1024):
            raise ValueError("invalid capability contract")
        return module
    except Exception:
        raise CapabilityUpdateError("CAPABILITY_ENTRY_INVALID") from None


class CapabilityRuntime:
    def __init__(self, updater: CapabilityUpdater, host, *, reserved_ids=()) -> None:
        self.updater = updater
        self.host = host
        self.reserved_ids = frozenset(reserved_ids)
        self._modules = {}
        self._descriptors: tuple[SkillDescriptor, ...] = ()

    def validate_entry(self, skill_id: str, version: str, source: bytes) -> None:
        del version
        if skill_id in self.reserved_ids:
            raise CapabilityUpdateError("CAPABILITY_SKILL_ID_RESERVED")
        _load_entry(skill_id, source)

    def refresh(self) -> None:
        try:
            modules, descriptors = {}, []
            for package in self.updater.active_packages():
                if package.skill_id in self.reserved_ids:
                    raise CapabilityUpdateError("CAPABILITY_SKILL_ID_RESERVED")
                module = _load_entry(package.skill_id, package.entrypoint.read_bytes())
                modules[package.skill_id] = module
                descriptors.append(SkillDescriptor(
                    skill_id=package.skill_id, display_name=package.skill_id, runtime=SkillRuntime.PYTHON,
                    provider=None, version=package.version, classification=SkillClassification.BUSINESS,
                    input_schema=module.INPUT_SCHEMA,
                ))
            self._modules = modules
            self._descriptors = tuple(descriptors)
        except Exception:
            # A tampered active file must no longer be advertised or executed.
            self._modules = {}
            self._descriptors = ()
            raise

    def descriptors(self) -> tuple[SkillDescriptor, ...]:
        return self._descriptors

    def has_skill(self, skill_id: str) -> bool:
        return skill_id in self._modules

    async def execute(self, task: WorkerTask) -> ExecutionResult:
        # Revalidate the active release immediately before starting a task.
        try:
            self.refresh()
            module = self._modules[task.skill_id]
            result = await module.execute(self.host, task)
            if not isinstance(result, ExecutionResult):
                raise ValueError("invalid result")
            return result
        except Exception:
            details = None
            if task.skill_id == "douyin.category_schema":
                details = {"kind": task.skill_id, "category_id": task.input.get("category_id"),
                           "device_id": str(self.host.device_id), "local_shop_id": task.input.get("local_shop_id"),
                           "platform_shop_id": task.input.get("platform_shop_id"), "http_status": None,
                           "platform_code": None, "error_stage": "result", "safe_error_code": "CAPABILITY_EXECUTION_FAILED"}
            return ExecutionResult(status=ExecutionStatus.FAILED, result=details,
                error_code="CAPABILITY_EXECUTION_FAILED", error_message="能力执行未完成")
