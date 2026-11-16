from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamDeviceAccess
from app.core.config import Settings
from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskSkillId, TaskStatus
from app.modules.tasks.exceptions import (
    TaskApplicationNotAvailableError,
    TaskInputInvalidError,
    TaskProviderNotReadyError,
    TaskWorkerOfflineError,
)
from app.modules.tasks.models import Task, TaskEvent
from app.modules.tasks.schemas import (
    TaskComplete,
    TaskCreate,
    TaskEventBatchWrite,
    TaskFail,
)
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workers.models import (
    DeviceProviderInventory,
    DeviceRuntime,
    DeviceSkillCapability,
    WorkerDeviceCredential,
)
from app.modules.workers.exceptions import WorkerAuthenticationError
from app.modules.workers.schemas import (
    SkillCapabilitySnapshotUpsert,
    WorkerHeartbeat,
)
from app.modules.workers.service import WorkerPrincipal, WorkerService


pytestmark = pytest.mark.integration


def _cleanup(
    engine: Engine,
    device_ids: set[UUID],
    *,
    team_id: UUID,
    user_id: UUID,
) -> None:
    with Session(engine) as session:
        session.execute(
            delete(TaskEvent).where(
                TaskEvent.task_id.in_(
                    select(Task.task_id).where(
                        Task.target_device_id.in_(device_ids),
                    ),
                ),
            ),
        )
        session.execute(delete(Task).where(Task.target_device_id.in_(device_ids)))
        session.execute(
            delete(DeviceSkillCapability).where(
                DeviceSkillCapability.device_id.in_(device_ids),
            ),
        )
        session.execute(
            delete(DeviceProviderInventory).where(
                DeviceProviderInventory.device_id.in_(device_ids),
            ),
        )
        session.execute(
            delete(DeviceRuntime).where(DeviceRuntime.device_id.in_(device_ids)),
        )
        session.execute(
            delete(WorkerDeviceCredential).where(
                WorkerDeviceCredential.device_id.in_(device_ids),
            ),
        )
        session.execute(
            delete(TeamDeviceAccess).where(TeamDeviceAccess.team_id == team_id),
        )
        session.execute(delete(Device).where(Device.device_id.in_(device_ids)))
        session.execute(delete(User).where(User.user_id == user_id))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.commit()


def _fixture_actor() -> tuple[UUID, UUID, ActorContext]:
    team_id = uuid4()
    user_id = uuid4()
    return team_id, user_id, ActorContext(
        user_id=user_id,
        user_display_name="Worker Integration User",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )


def test_worker_credential_lifecycle_uses_hash_and_isolates_devices(
    postgresql_engine: Engine,
) -> None:
    device_a = uuid4()
    device_b = uuid4()
    device_ids = {device_a, device_b}
    team_id, user_id, _ = _fixture_actor()
    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Worker Credential Integration Team"),
                    User(
                        user_id=user_id,
                        display_name="Worker Credential Integration User",
                    ),
                    Device(
                        device_id=device_a,
                        team_id=team_id,
                        display_name="credential-a",
                    ),
                    Device(
                        device_id=device_b,
                        team_id=team_id,
                        display_name="credential-b",
                    ),
                ],
            )
            session.flush()
            session.add_all(
                [
                    TeamDeviceAccess(team_id=team_id, device_id=device_id)
                    for device_id in device_ids
                ],
            )
            session.commit()

            service = WorkerService(session)
            first_token = service.issue_token(device_a)
            credential = session.scalar(
                select(WorkerDeviceCredential).where(
                    WorkerDeviceCredential.device_id == device_a,
                ),
            )
            assert credential is not None
            assert credential.token_hash != first_token
            assert len(credential.token_hash) == 64
            principal = service.authenticate_token(first_token)
            assert principal.device_id == device_a
            assert service.get_provisioning(principal).device_id == device_a
            with pytest.raises(WorkerAuthenticationError):
                service.authenticate(device_b, first_token)

            second_token = service.rotate_token(device_a)
            assert second_token != first_token
            with pytest.raises(WorkerAuthenticationError):
                service.authenticate_token(first_token)
            assert service.authenticate(device_a, second_token).device_id == device_a

            service.disable_token(device_a)
            assert service.get_credential(device_a).status == "revoked"
            with pytest.raises(WorkerAuthenticationError):
                service.authenticate_token(second_token)

            replacement_token = service.issue_token(device_a)
            assert service.authenticate_token(replacement_token).device_id == device_a
    finally:
        _cleanup(
            postgresql_engine,
            device_ids,
            team_id=team_id,
            user_id=user_id,
        )


def test_worker_identity_runtime_claim_result_and_lost(
    postgresql_engine: Engine,
) -> None:
    device_ids = {uuid4(), uuid4()}
    device_a, device_b = tuple(device_ids)
    team_id, user_id, actor = _fixture_actor()
    base_time = datetime.now(UTC)
    settings = Settings(
        worker_online_timeout_seconds=45,
        worker_task_lease_seconds=60,
    )

    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Worker Core Integration Team"),
                    User(
                        user_id=user_id,
                        display_name="Worker Core Integration User",
                    ),
                    Device(
                        device_id=device_a,
                        team_id=team_id,
                        display_name="worker-lite-a",
                    ),
                    Device(
                        device_id=device_b,
                        team_id=team_id,
                        display_name="worker-lite-b",
                    ),
                ],
            )
            session.flush()
            session.add_all(
                [
                    TeamDeviceAccess(team_id=team_id, device_id=device_id)
                    for device_id in device_ids
                ],
            )
            session.commit()

        with Session(postgresql_engine, expire_on_commit=False) as session:
            worker_service = WorkerService(session, settings=settings)
            token_a = worker_service.issue_token(device_a)
            token_b = worker_service.issue_token(device_b)
            credential_hashes = list(
                session.scalars(
                    select(WorkerDeviceCredential.token_hash).where(
                        WorkerDeviceCredential.device_id.in_(device_ids),
                    ),
                ),
            )
            assert token_a not in credential_hashes
            assert token_b not in credential_hashes
            principal_a = worker_service.authenticate(device_a, token_a)
            principal_b = worker_service.authenticate(device_b, token_b)
            skill_snapshot = SkillCapabilitySnapshotUpsert.model_validate(
                {
                    "skills": [
                        {
                            "skill_id": "system.echo",
                            "display_name": "Echo",
                            "runtime": "python",
                            "provider": None,
                            "version": "1",
                            "classification": "internal",
                        },
                        {
                            "skill_id": "system.sleep",
                            "display_name": "Sleep",
                            "runtime": "python",
                            "provider": None,
                            "version": "1",
                            "classification": "internal",
                        },
                        {
                            "skill_id": "yingdao.test",
                            "display_name": "影刀测试",
                            "runtime": "rpa",
                            "provider": "yingdao",
                            "version": "1",
                            "classification": "internal",
                        },
                    ],
                },
            )
            worker_service.sync_skill_capabilities(
                principal_a,
                skill_snapshot,
                now=base_time,
            )
            echo_only = SkillCapabilitySnapshotUpsert(
                skills=[skill_snapshot.skills[0]],
            )
            assert [
                item.skill_id
                for item in worker_service.sync_skill_capabilities(
                    principal_a,
                    echo_only,
                    now=base_time,
                )
            ] == ["system.echo"]
            worker_service.sync_skill_capabilities(
                principal_a,
                skill_snapshot,
                now=base_time,
            )
            assert worker_service.get_skill_capability_reads(device_b) == []
            online = worker_service.heartbeat(
                principal_a,
                WorkerHeartbeat(worker_version="0.1.0", started_at=base_time),
                now=base_time,
            )
            assert online.connection_status == "online"
            stored_runtime = session.get(DeviceRuntime, device_a)
            assert stored_runtime is not None
            assert worker_service.reconcile_offline_devices(
                now=base_time + timedelta(seconds=46),
            ) >= 1
            session.refresh(stored_runtime)
            assert stored_runtime.connection_status == "offline"
            assert {
                item.skill_id
                for item in worker_service.get_skill_capability_reads(device_a)
            } == {"system.echo", "system.sleep"}
            assert {
                item.classification
                for item in worker_service.get_skill_capability_reads(device_a)
            } == {"internal"}
            with pytest.raises(TaskWorkerOfflineError):
                TaskService(session, settings=settings).create(
                    TaskCreate(
                        target_device_id=device_a,
                        skill_id=TaskSkillId.SYSTEM_ECHO,
                        input={"message": "offline"},
                    ),
                    actor,
                )
            restarted = worker_service.heartbeat(
                principal_a,
                WorkerHeartbeat(
                    worker_version="0.1.0",
                    started_at=base_time + timedelta(seconds=47),
                ),
                now=base_time + timedelta(seconds=47),
            )
            assert restarted.connection_status == "online"

            task_service = TaskService(session, settings=settings)
            echo = task_service.create(
                TaskCreate(
                    target_device_id=device_a,
                    skill_id=TaskSkillId.SYSTEM_ECHO,
                    input={"message": "hello"},
                ),
                actor,
            )
            assert echo.status == TaskStatus.PENDING.value
            assert task_service.claim(principal_b, now=base_time) is None
            claimed = task_service.claim(principal_a, now=base_time)
            assert claimed is not None
            assert claimed.task_id == echo.task_id
            assert claimed.status == TaskStatus.RUNNING.value
            assert task_service.claim(principal_a, now=base_time) is None
            renewed = task_service.renew(
                principal_a,
                echo.task_id,
                now=base_time + timedelta(seconds=20),
            )
            assert renewed.lease_until == base_time + timedelta(seconds=80)
            event_batch = TaskEventBatchWrite.model_validate(
                {
                    "events": [
                        {
                            "seq": 1,
                            "event_type": "status",
                            "level": "worker",
                            "message": "running",
                            "event_at": (base_time + timedelta(seconds=20)).isoformat(),
                            "metadata": {},
                        },
                    ],
                },
            )
            assert task_service.append_events(
                principal_a,
                echo.task_id,
                event_batch,
                now=base_time + timedelta(seconds=20),
            ).accepted_count == 1
            assert task_service.append_events(
                principal_a,
                echo.task_id,
                event_batch,
                now=base_time + timedelta(seconds=20),
            ).accepted_count == 0
            assert task_service.list_events(
                actor,
                echo.task_id,
                after_seq=0,
                limit=10,
            ).next_after_seq == 1
            completed = task_service.complete(
                principal_a,
                echo.task_id,
                TaskComplete(result={"message": "hello"}),
                now=base_time + timedelta(seconds=21),
            )
            assert completed.status == TaskStatus.SUCCESS.value
            assert completed.result_json == {"message": "hello"}

            sleep = task_service.create(
                TaskCreate(
                    target_device_id=device_a,
                    skill_id=TaskSkillId.SYSTEM_SLEEP,
                    input={"seconds": 45},
                ),
                actor,
            )
            assert task_service.claim(principal_a, now=base_time) is not None
            assert task_service.reconcile_expired(
                now=base_time + timedelta(seconds=61),
            ) == 1
            session.refresh(sleep)
            assert sleep.status == TaskStatus.LOST.value
            assert sleep.error_code == "WORKER_LEASE_EXPIRED"

            with pytest.raises(TaskInputInvalidError):
                task_service.create(
                    TaskCreate(target_device_id=device_a, skill_id=TaskSkillId.YINGDAO_TEST, input={}),
                    actor,
                )
    finally:
        _cleanup(
            postgresql_engine,
            device_ids,
            team_id=team_id,
            user_id=user_id,
        )
