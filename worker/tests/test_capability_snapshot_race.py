import asyncio
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.config import WorkerSettings
from app.contracts import ExecutionResult, ExecutionStatus
from app.skills import SkillDefinition, SkillRegistry
from app.skills.registry import SkillClassification, SkillDescriptor, SkillRuntime
from app.worker import Worker


class Executor:
    def can_claim(self):
        return True

    async def execute(self, task):
        return ExecutionResult(status=ExecutionStatus.SUCCESS)


def descriptor(skill_id):
    return SkillDescriptor(skill_id=skill_id, display_name=skill_id,
        runtime=SkillRuntime.PYTHON, provider=None, version="1",
        classification=SkillClassification.INTERNAL)


@pytest.mark.parametrize("initially_present", [False, True])
def test_inflight_old_snapshot_does_not_hide_install_or_removal(initially_present, tmp_path):
    async def scenario():
        first_report_started, release_first = asyncio.Event(), asyncio.Event()
        first = [descriptor("douyin.category_schema")] if initially_present else []
        second = [] if initially_present else [descriptor("douyin.category_schema")]

        class Updater:
            async def sync_when_idle(self, *args, **kwargs):
                return True

        class Runtime:
            updater = Updater()
            current = tuple(first)

            def descriptors(self):
                return self.current

            def validate_entry(self, *args):
                pass

            def refresh(self):
                self.current = tuple(second)

        class Client:
            snapshots = []
            requests = []

            async def heartbeat(self, **kwargs):
                pass

            async def report_skill_capabilities(self, snapshot):
                selected = [item.skill_id for item in snapshot.skills]
                self.requests.append(selected)
                if len(self.requests) == 1:
                    first_report_started.set()
                    await release_first.wait()
                self.snapshots.append(selected)

        class LocalState:
            updates = []

            def set_connection(self, *args, **kwargs):
                pass

            def set_skill_sync(self, synced, **kwargs):
                self.updates.append((synced, kwargs["count"]))

        registry = SkillRegistry()
        registry.register(SkillDefinition(skill_id="system.echo", display_name="echo", version="1",
            input_model=BaseModel, runtime=SkillRuntime.PYTHON, timeout_seconds=1,
            handler=lambda _: {}, classification=SkillClassification.INTERNAL))
        client, local_state = Client(), LocalState()
        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
                        device_token="synthetic-token", runtime_root=tmp_path), client, Executor(),
                        skill_registry=registry, capability_runtime=Runtime(), local_runtime_state=local_state)
        heartbeat = asyncio.create_task(worker._heartbeat_once())
        await asyncio.wait_for(first_report_started.wait(), 1)
        await worker._refresh_capabilities_if_due()
        concurrent_heartbeat = asyncio.create_task(worker._heartbeat_once())
        await asyncio.sleep(0)
        assert len(client.requests) == 1  # no newer request may overtake the old one
        release_first.set()
        await asyncio.wait_for(asyncio.gather(heartbeat, concurrent_heartbeat), 1)
        expected_first = ["system.echo"] + (["douyin.category_schema"] if initially_present else [])
        expected_second = ["system.echo"] + ([] if initially_present else ["douyin.category_schema"])
        assert client.snapshots == [expected_first, expected_second]
        assert worker._skill_snapshot_synced is True
        assert local_state.updates[-1] == (True, len(expected_second))

    asyncio.run(scenario())


def test_worker_main_loop_reports_installed_capability_when_first_report_is_delayed(tmp_path):
    async def scenario():
        first_started, installed, release_first, stop = (asyncio.Event() for _ in range(4))

        class Updater:
            async def sync_when_idle(self, *args, **kwargs):
                await first_started.wait()
                return True

        class Runtime:
            updater = Updater()
            current = ()

            def descriptors(self):
                return self.current

            def validate_entry(self, *args):
                pass

            def refresh(self):
                self.current = (descriptor("douyin.category_schema"),)
                installed.set()

        class Client:
            reports = []

            async def heartbeat(self, **kwargs):
                pass

            async def report_skill_capabilities(self, snapshot):
                selected = [item.skill_id for item in snapshot.skills]
                if not self.reports:
                    first_started.set()
                    await release_first.wait()
                self.reports.append(selected)
                if "douyin.category_schema" in selected:
                    stop.set()

            async def report_rpa_inventory(self, payload):
                pass

            async def claim(self):
                return None

            async def close(self):
                pass

        registry = SkillRegistry()
        registry.register(SkillDefinition(skill_id="system.echo", display_name="echo", version="1",
            input_model=BaseModel, runtime=SkillRuntime.PYTHON, timeout_seconds=1,
            handler=lambda _: {}, classification=SkillClassification.INTERNAL))
        client = Client()
        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
                        device_token="synthetic-token", runtime_root=tmp_path), client, Executor(),
                        skill_registry=registry, capability_runtime=Runtime())
        run = asyncio.create_task(worker.run(stop))
        await asyncio.wait_for(installed.wait(), 1)
        release_first.set()
        await asyncio.wait_for(run, 2)
        assert client.reports == [["system.echo"], ["system.echo", "douyin.category_schema"]]
        assert worker._skill_snapshot_synced is True

    asyncio.run(scenario())
