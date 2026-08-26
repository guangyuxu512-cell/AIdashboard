import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.contracts import TaskAsset, WorkerTask
from app.task_images import (
    TaskImagePreparer,
    TaskImagePreparationError,
    allocate_task_filenames,
)


class FakeDownloader:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads
        self.paths: list[str] = []

    async def download_task_asset(self, download_path: str) -> bytes:
        self.paths.append(download_path)
        if download_path not in self.payloads:
            raise RuntimeError("download failed")
        return self.payloads[download_path]


def asset(filename: str, position: int, payload: bytes) -> TaskAsset:
    asset_id = uuid4()
    return TaskAsset(
        asset_id=asset_id,
        filename=filename,
        position=position,
        content_type="image/jpeg",
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        download_path=f"/api/v1/worker/tasks/task/assets/{asset_id}",
    )


def task(assets: list[TaskAsset]) -> WorkerTask:
    return WorkerTask(
        task_id=uuid4(),
        skill_id="yingdao.app.run",
        input={"app_id": "safe-app", "params": {}},
        lease_until="2026-08-26T12:00:00+00:00",
        assets=assets,
    )


def test_multi_image_download_is_ordered_and_hash_verified(tmp_path: Path) -> None:
    first_payload = b"first-image"
    second_payload = b"second-image"
    first = asset("同名.jpg", 1, first_payload)
    second = asset("同名.jpg", 0, second_payload)
    downloader = FakeDownloader(
        {
            first.download_path: first_payload,
            second.download_path: second_payload,
        },
    )
    preparer = TaskImagePreparer(tmp_path / "images", downloader)

    paths = asyncio.run(preparer.prepare(task([first, second])))

    assert [path.name for path in paths] == ["同名.jpg", "同名__2.jpg"]
    assert paths[0].read_bytes() == second_payload
    assert paths[1].read_bytes() == first_payload
    assert downloader.paths == [second.download_path, first.download_path]
    manifest = json.loads((tmp_path / "images" / ".ecommerce-worker-images.json").read_text("utf-8"))
    assert manifest == {"files": ["同名.jpg", "同名__2.jpg"]}


def test_single_image_is_written_with_its_original_filename(tmp_path: Path) -> None:
    payload = b"one-image"
    selected = asset("test-01.jpg", 0, payload)
    preparer = TaskImagePreparer(
        tmp_path / "images",
        FakeDownloader({selected.download_path: payload}),
    )

    paths = asyncio.run(preparer.prepare(task([selected])))

    assert [path.name for path in paths] == ["test-01.jpg"]
    assert paths[0].read_bytes() == payload


def test_empty_task_clears_previous_managed_images_only(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "old.jpg").write_bytes(b"old")
    (images / "manual.jpg").write_bytes(b"manual")
    (images / ".ecommerce-worker-images.json").write_text(
        json.dumps({"files": ["old.jpg"]}),
        encoding="utf-8",
    )
    preparer = TaskImagePreparer(images, FakeDownloader({}))

    result = asyncio.run(preparer.prepare(task([])))

    assert result == []
    assert not (images / "old.jpg").exists()
    assert (images / "manual.jpg").read_bytes() == b"manual"


def test_download_failure_removes_partial_task_files(tmp_path: Path) -> None:
    payload = b"first"
    first = asset("first.jpg", 0, payload)
    second = asset("second.jpg", 1, b"second")
    preparer = TaskImagePreparer(
        tmp_path / "images",
        FakeDownloader({first.download_path: payload}),
    )

    with pytest.raises(TaskImagePreparationError) as captured:
        asyncio.run(preparer.prepare(task([first, second])))

    assert captured.value.code == "TASK_IMAGE_DOWNLOAD_FAILED"
    assert not (tmp_path / "images" / "first.jpg").exists()


def test_hash_mismatch_fails_before_file_is_written(tmp_path: Path) -> None:
    expected = asset("bad.jpg", 0, b"expected")
    preparer = TaskImagePreparer(
        tmp_path / "images",
        FakeDownloader({expected.download_path: b"tampered"}),
    )

    with pytest.raises(TaskImagePreparationError) as captured:
        asyncio.run(preparer.prepare(task([expected])))

    assert captured.value.code in {
        "TASK_IMAGE_SIZE_MISMATCH",
        "TASK_IMAGE_HASH_MISMATCH",
    }
    assert not (tmp_path / "images" / "bad.jpg").exists()


def test_unwritable_destination_fails_safely(tmp_path: Path) -> None:
    payload = b"image"
    selected = asset("blocked.jpg", 0, payload)

    class UnwritablePreparer(TaskImagePreparer):
        def _write_atomic(self, destination: Path, payload: bytes) -> None:
            del payload
            raise TaskImagePreparationError(
                "TASK_IMAGE_WRITE_FAILED",
                f"图片准备失败：{destination.name}",
            )

    preparer = UnwritablePreparer(
        tmp_path / "images",
        FakeDownloader({selected.download_path: payload}),
    )

    with pytest.raises(TaskImagePreparationError) as captured:
        asyncio.run(preparer.prepare(task([selected])))

    assert captured.value.code == "TASK_IMAGE_WRITE_FAILED"
    assert not (tmp_path / "images" / "blocked.jpg").exists()


def test_filenames_are_sanitized_and_collisions_are_deterministic() -> None:
    payload = b"image"
    names = allocate_task_filenames(
        [
            asset("folder/CON.jpg", 0, payload),
            asset("folder\\CON.jpg", 1, payload),
            asset("normal.png", 2, payload),
        ],
    )

    assert names == ["_CON.jpg", "_CON__2.jpg", "normal.png"]
