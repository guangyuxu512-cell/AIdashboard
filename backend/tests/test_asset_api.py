import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.core.database import get_database_session
from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.assets.api import get_asset_authorized_actor, get_asset_service
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import (
    AssetNotFoundError,
    AssetStorageError,
    AssetStorageUnavailableError,
)
from app.modules.assets.models import Asset
from app.modules.workers.auth import get_worker_principal
from app.modules.workers.service import WorkerPrincipal
from tests.support import FakeSession


ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="素材接口用户",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="member",
    data_scope=DataScope.TEAM,
)


class ApiAssetService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.assets: dict[UUID, Asset] = {}
        self.allowed_device_id: UUID | None = None

    def upload(
        self,
        *,
        actor: ActorContext,
        original_filename: str | None,
        content_type: str | None,
        stream: object,
    ) -> Asset:
        asset_id = uuid4()
        payload = stream.read()  # type: ignore[attr-defined]
        path = self.root / f"{asset_id}.png"
        path.write_bytes(payload)
        now = datetime.now(UTC)
        asset = Asset(
            asset_id=asset_id,
            team_id=actor.team_id,
            created_by_user_id=actor.user_id,
            original_filename=original_filename or "unnamed.png",
            storage_key=path.name,
            media_type=AssetMediaType.IMAGE.value,
            source_type=AssetSourceType.UPLOAD.value,
            content_type=content_type or "image/png",
            size_bytes=len(payload),
            sha256="a" * 64,
        )
        asset.created_at = now
        asset.updated_at = now
        self.assets[asset_id] = asset
        return asset

    def list(
        self,
        *,
        actor: ActorContext,
        page: int,
        page_size: int,
        search: str | None,
    ) -> tuple[list[Asset], int]:
        values = [
            asset
            for asset in self.assets.values()
            if actor.data_scope is DataScope.ALL or asset.team_id == actor.team_id
        ]
        if search:
            values = [
                asset
                for asset in values
                if search.casefold() in asset.original_filename.casefold()
            ]
        start = (page - 1) * page_size
        return values[start : start + page_size], len(values)

    def get_content(
        self,
        actor: ActorContext,
        asset_id: UUID,
    ) -> tuple[Asset, BinaryIO]:
        asset = self.assets.get(asset_id)
        if asset is None or (
            actor.data_scope is not DataScope.ALL and asset.team_id != actor.team_id
        ):
            raise AssetNotFoundError()
        return asset, (self.root / asset.storage_key).open("rb")

    def delete(self, actor: ActorContext, asset_id: UUID) -> None:
        asset = self.assets.pop(asset_id, None)
        if asset is None or (
            actor.data_scope is not DataScope.ALL and asset.team_id != actor.team_id
        ):
            if asset is not None:
                self.assets[asset.asset_id] = asset
            raise AssetNotFoundError()
        (self.root / asset.storage_key).unlink()

    def get_worker_content(
        self,
        principal: WorkerPrincipal,
        *,
        task_id: UUID,
        asset_id: UUID,
    ) -> tuple[Asset, BinaryIO]:
        del task_id
        if self.allowed_device_id != principal.device_id:
            raise AssetNotFoundError()
        asset = self.assets.get(asset_id)
        if asset is None:
            raise AssetNotFoundError()
        return asset, (self.root / asset.storage_key).open("rb")


def request(
    service: ApiAssetService,
    method: str,
    path: str,
    principal: WorkerPrincipal | None = None,
    actor: ActorContext | None = ACTOR,
    **kwargs: object,
) -> Response:
    application = create_app()
    application.dependency_overrides[get_asset_service] = lambda: service
    application.dependency_overrides[get_database_session] = lambda: FakeSession()
    if actor is not None:
        application.dependency_overrides[get_asset_authorized_actor] = lambda: actor
    if principal is not None:
        application.dependency_overrides[get_worker_principal] = lambda: principal

    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_asset_api_upload_list_read_and_delete(tmp_path: Path) -> None:
    service = ApiAssetService(tmp_path)
    upload = request(
        service,
        "POST",
        "/api/v1/assets",
        files={"file": ("test-02.png", b"\x89PNG\r\n\x1a\nfixture", "image/png")},
    )

    assert upload.status_code == 201
    asset_id = upload.json()["asset_id"]
    listing = request(
        service,
        "GET",
        "/api/v1/assets?page=1&page_size=20&search=test-02",
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["original_filename"] == "test-02.png"
    assert listing.json()["items"][0]["media_type"] == "image"
    assert listing.json()["items"][0]["source_type"] == "upload"
    assert "storage_key" not in listing.json()["items"][0]
    assert not any(str(tmp_path) in str(value) for value in upload.json().values())

    content = request(service, "GET", f"/api/v1/assets/{asset_id}/content")
    assert content.status_code == 200
    assert content.content == b"\x89PNG\r\n\x1a\nfixture"
    assert content.headers["content-type"] == "image/png"

    removed = request(service, "DELETE", f"/api/v1/assets/{asset_id}")
    assert removed.status_code == 204
    missing = request(service, "GET", f"/api/v1/assets/{asset_id}/content")
    assert missing.status_code == 404


def test_asset_upload_requires_multipart_file(tmp_path: Path) -> None:
    response = request(ApiAssetService(tmp_path), "POST", "/api/v1/assets")

    assert response.status_code == 422


def test_human_asset_api_requires_authenticated_actor(tmp_path: Path) -> None:
    response = request(
        ApiAssetService(tmp_path),
        "GET",
        "/api/v1/assets",
        actor=None,
    )

    assert response.status_code == 401
    assert response.json()["code"] == "HUMAN_AUTHENTICATION_REQUIRED"


def test_cross_team_asset_id_is_not_disclosed_or_deleted(tmp_path: Path) -> None:
    service = ApiAssetService(tmp_path)
    upload = request(
        service,
        "POST",
        "/api/v1/assets",
        files={"file": ("private.png", b"\x89PNG\r\n\x1a\nprivate", "image/png")},
    )
    asset_id = upload.json()["asset_id"]
    other_team_actor = ActorContext(
        user_id=uuid4(),
        user_display_name="其它团队用户",
        team_id=uuid4(),
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )

    content = request(
        service,
        "GET",
        f"/api/v1/assets/{asset_id}/content",
        actor=other_team_actor,
    )
    removed = request(
        service,
        "DELETE",
        f"/api/v1/assets/{asset_id}",
        actor=other_team_actor,
    )

    assert content.status_code == 404
    assert removed.status_code == 404
    assert content.json()["code"] == "ASSET_NOT_FOUND"
    assert removed.json()["code"] == "ASSET_NOT_FOUND"
    assert UUID(asset_id) in service.assets


def test_worker_download_keeps_authenticated_v1_http_contract(tmp_path: Path) -> None:
    service = ApiAssetService(tmp_path)
    device_id = uuid4()
    service.allowed_device_id = device_id
    upload = request(
        service,
        "POST",
        "/api/v1/assets",
        files={"file": ("worker.png", b"\x89PNG\r\n\x1a\nworker", "image/png")},
    )
    asset_id = upload.json()["asset_id"]
    task_id = uuid4()

    downloaded = request(
        service,
        "GET",
        f"/api/v1/worker/tasks/{task_id}/assets/{asset_id}",
        principal=WorkerPrincipal(device_id=device_id),
    )

    assert downloaded.status_code == 200
    assert downloaded.content == b"\x89PNG\r\n\x1a\nworker"
    assert downloaded.headers["content-type"] == "image/png"
    assert downloaded.headers["content-length"] == str(len(downloaded.content))
    assert "storage_key" not in downloaded.text
    assert str(tmp_path) not in downloaded.text

    unauthenticated = request(
        service,
        "GET",
        f"/api/v1/worker/tasks/{task_id}/assets/{asset_id}",
    )
    assert unauthenticated.status_code == 401

    forbidden = request(
        service,
        "GET",
        f"/api/v1/worker/tasks/{task_id}/assets/{asset_id}",
        principal=WorkerPrincipal(device_id=uuid4()),
    )
    assert forbidden.status_code == 404


def test_storage_errors_do_not_leak_backend_path(tmp_path: Path) -> None:
    class FailingContentService(ApiAssetService):
        def get_content(
            self,
            actor: ActorContext,
            asset_id: UUID,
        ) -> tuple[Asset, BinaryIO]:
            del actor
            del asset_id
            raise AssetStorageError()

    response = request(
        FailingContentService(tmp_path),
        "GET",
        f"/api/v1/assets/{uuid4()}/content",
    )

    assert response.status_code == 500
    assert response.json()["code"] == "ASSET_STORAGE_FAILED"
    assert str(tmp_path) not in response.text


def test_mounted_storage_unavailable_is_explicit_and_does_not_leak_path(
    tmp_path: Path,
) -> None:
    class UnavailableContentService(ApiAssetService):
        def get_content(
            self,
            actor: ActorContext,
            asset_id: UUID,
        ) -> tuple[Asset, BinaryIO]:
            del actor
            del asset_id
            raise AssetStorageUnavailableError()

    response = request(
        UnavailableContentService(tmp_path),
        "GET",
        f"/api/v1/assets/{uuid4()}/content",
    )

    assert response.status_code == 503
    assert response.json()["code"] == "ASSET_STORAGE_UNAVAILABLE"
    assert str(tmp_path) not in response.text
