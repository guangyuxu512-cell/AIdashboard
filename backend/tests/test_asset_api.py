import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.main import create_app
from app.modules.assets.api import get_asset_service
from app.modules.assets.exceptions import AssetNotFoundError
from app.modules.assets.models import Asset


class ApiAssetService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.assets: dict[UUID, Asset] = {}

    def upload(
        self,
        *,
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
            original_filename=original_filename or "unnamed.png",
            storage_key=path.name,
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
        page: int,
        page_size: int,
        search: str | None,
    ) -> tuple[list[Asset], int]:
        values = list(self.assets.values())
        if search:
            values = [
                asset
                for asset in values
                if search.casefold() in asset.original_filename.casefold()
            ]
        start = (page - 1) * page_size
        return values[start : start + page_size], len(values)

    def get_content(self, asset_id: UUID) -> tuple[Asset, Path]:
        asset = self.assets.get(asset_id)
        if asset is None:
            raise AssetNotFoundError()
        return asset, self.root / asset.storage_key

    def delete(self, asset_id: UUID) -> None:
        asset = self.assets.pop(asset_id, None)
        if asset is None:
            raise AssetNotFoundError()
        (self.root / asset.storage_key).unlink()


def request(
    service: ApiAssetService,
    method: str,
    path: str,
    **kwargs: object,
) -> Response:
    application = create_app()
    application.dependency_overrides[get_asset_service] = lambda: service

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
