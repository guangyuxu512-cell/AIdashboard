"""Read-only diagnostics for the existing same-user RPA inventory bridge.

The result contains only fixed status codes and counts. It never opens a
browser, reads a stored Session, or returns local paths or shop identities.
"""
from __future__ import annotations

from pathlib import Path

from app.contracts import ExecutionResult, ExecutionStatus
from app.rpa_session_bridge import BridgeDiscovery, RpaBridgeError, helper_tree_digest
from app.skills.sdk import BusinessSkillInput, SkillResult


SKILL_ID = "system.rpa_inventory_diagnostic"


class DiagnosticInput(BusinessSkillInput):
    pass


INPUT_SCHEMA = DiagnosticInput.model_json_schema(mode="validation")


def _result(code: str, facts: dict) -> ExecutionResult:
    result = SkillResult(summary="RPA 店铺连接诊断完成", data={"code": code, **facts})
    return ExecutionResult(status=ExecutionStatus.SUCCESS, result=result.model_dump(mode="json"))


async def execute(host, task):
    try:
        DiagnosticInput.model_validate(task.input)
        bridge = getattr(host, "_rpa", None)
        if bridge is None:
            return _result("RPA_BRIDGE_UNAVAILABLE", {})
        directory = Path(bridge.data_directory)
        marker = directory / "worker-session-bridge.json"
        database = directory / "shop-manager.db"
        facts = {
            "data_directory_exists": directory.is_dir(),
            "discovery_exists": marker.is_file(),
            "database_exists": database.is_file(),
        }
        if not facts["discovery_exists"]:
            return _result("RPA_DISCOVERY_UNAVAILABLE", facts)
        try:
            content = marker.read_bytes()
            if len(content) > 16 * 1024:
                raise ValueError("discovery too large")
            discovery = BridgeDiscovery.model_validate_json(content)
        except Exception:
            return _result("RPA_DISCOVERY_INVALID", facts)

        helper = Path(discovery.helper_path)
        parts = tuple(part.lower() for part in helper.parts[-3:])
        helper_path_valid = (
            helper.is_absolute()
            and not str(helper).startswith(("\\\\", "//"))
            and ".." not in helper.parts
            and parts == ("resources", "listing-worker", "listing-worker.exe")
        )
        facts["helper_path_valid"] = helper_path_valid
        facts["helper_exists"] = bool(helper_path_valid and helper.is_file())
        facts["database_matches_discovery"] = (
            Path(discovery.database_path).resolve() == database.resolve()
        )
        if not helper_path_valid or not facts["database_matches_discovery"]:
            return _result("RPA_DISCOVERY_MISMATCH", facts)
        if not facts["database_exists"] or not facts["helper_exists"]:
            return _result("RPA_FILES_UNAVAILABLE", facts)

        facts["rpa_executable_exists"] = (helper.parents[2] / "店群自动化软件.exe").is_file()
        if not facts["rpa_executable_exists"]:
            return _result("RPA_INSTALLATION_UNAVAILABLE", facts)
        try:
            allowed = bridge.trusted_digests()
            facts["signed_helper_list_available"] = bool(allowed)
            facts["helper_is_trusted"] = helper_tree_digest(helper.parent) in allowed
        except Exception:
            return _result("RPA_HELPER_CHECK_UNAVAILABLE", facts)
        if not facts["helper_is_trusted"]:
            return _result("RPA_HELPER_UNTRUSTED", facts)

        try:
            # Reuse the production bridge's own path, signature and identity
            # checks; the helper reads its stored shop inventory without opening
            # a browser or returning any Session to this capability.
            inventory = await bridge.list_shops()
        except RpaBridgeError as error:
            return _result(error.code, facts)
        except Exception:
            return _result("RPA_INVENTORY_READ_FAILED", facts)
        facts.update(
            shop_count=len(inventory.shops),
            douyin_shop_count=sum(shop.platform == "douyin" for shop in inventory.shops),
            identified_shop_count=sum(bool(shop.platform_shop_id) for shop in inventory.shops),
            saved_session_count=sum(shop.session_stored for shop in inventory.shops),
        )
        return _result("RPA_INVENTORY_READY", facts)
    except Exception:
        return _result("RPA_DIAGNOSTIC_FAILED", {})
