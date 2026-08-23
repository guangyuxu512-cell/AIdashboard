import asyncio
from pathlib import Path
import subprocess

import httpx
import pytest

from app.providers.yingdao import (
    WindowsYingdaoRuntimeLocator,
    YingdaoApplicationAdapter,
    YingdaoProcess,
    YingdaoRuntimeEndpoint,
    YingdaoSession,
    YingdaoSessionAccount,
    YingdaoSessionAdapter,
    YingdaoSessionError,
)
from app.providers.yingdao.api_response import normalize_shadowbot_api_envelope


class StubLocator:
    async def resolve(self, *, start_if_missing: bool = True) -> YingdaoRuntimeEndpoint:
        assert start_if_missing is True
        return YingdaoRuntimeEndpoint(
            YingdaoProcess(1234, Path("ShadowBot.Shell.exe"), "6.3.6"),
            "http://127.0.0.1:42500",
        )


def test_current_session_and_cloud_application_contracts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/account/current":
            return httpx.Response(
                200,
                json={
                    "Code": 0,
                    "Message": "ok",
                    "Data": {
                        "LoggedIn": True,
                        "UserName": "GY00999",
                        "DisplayName": "GY00999",
                        "UserId": "906515367141965826",
                        "AccountType": "PersonalBasic",
                    },
                },
            )
        if request.url.path == "/api/v1/apps":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "items": [
                            {
                                "appId": f"app-{index}",
                                "appName": f"应用{index}",
                                "versionId": f"version-{index}",
                                "updateTime": "2026-08-23T00:00:00Z",
                                "appType": "developed",
                                "groupId": "group-1",
                            }
                            for index in range(10)
                        ],
                    },
                },
            )
        if request.url.path == "/api/v1/apps/app-0/detail":
            return httpx.Response(200, json={"Code": 0, "Data": {"appId": "app-0"}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    session_adapter = YingdaoSessionAdapter(StubLocator(), transport=transport)  # type: ignore[arg-type]
    application_adapter = YingdaoApplicationAdapter(transport=transport)

    current = asyncio.run(session_adapter.current())
    applications = asyncio.run(application_adapter.list(current))
    detail = asyncio.run(application_adapter.detail(current, "app-0"))

    assert current.account.display_name == "GY00999"
    assert current.account.user_id == "906515367141965826"
    assert len(applications) == 10
    assert applications[0].version_id == "version-0"
    assert detail == {"appId": "app-0"}


def test_running_other_version_is_not_stopped_or_replaced(tmp_path: Path) -> None:
    locator = WindowsYingdaoRuntimeLocator(tmp_path, version_reader=lambda _: "6.3.9")
    process = YingdaoProcess(1234, tmp_path / "ShadowBot.exe", "6.3.9")
    locator._list_shadowbot_processes = lambda: [process]  # type: ignore[method-assign]

    with pytest.raises(YingdaoSessionError) as error:
        asyncio.run(locator.resolve(start_if_missing=True))

    assert error.value.code == "YINGDAO_VERSION_UNSUPPORTED"
    assert error.value.provider_version == "6.3.9"


def test_locator_reports_missing_supported_installation(tmp_path: Path) -> None:
    locator = WindowsYingdaoRuntimeLocator(tmp_path)
    locator._list_shadowbot_processes = lambda: []  # type: ignore[method-assign]

    with pytest.raises(YingdaoSessionError) as error:
        asyncio.run(locator.resolve(start_if_missing=True))

    assert error.value.code == "YINGDAO_NOT_INSTALLED"


def test_session_reports_need_login() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={"Code": 0, "Data": {"LoggedIn": False}},
        ),
    )
    adapter = YingdaoSessionAdapter(StubLocator(), transport=transport)  # type: ignore[arg-type]

    with pytest.raises(YingdaoSessionError) as error:
        asyncio.run(adapter.current())

    assert error.value.code == "YINGDAO_NOT_LOGGED_IN"


def test_shadowbot_envelope_normalizes_only_observed_case_variants() -> None:
    upper = normalize_shadowbot_api_envelope(
        {"Code": 0, "Data": {"LoggedIn": True}},
    )
    lower = normalize_shadowbot_api_envelope(
        {"code": 0, "data": {"loggedIn": True}},
    )

    assert upper.code == lower.code == 0
    assert upper.data == {"LoggedIn": True}
    assert lower.data == {"loggedIn": True}

    with pytest.raises(ValueError, match="code/Code"):
        normalize_shadowbot_api_envelope({"Data": {}})
    with pytest.raises(ValueError, match="data/Data"):
        normalize_shadowbot_api_envelope({"Code": 0})


def test_current_session_accepts_observed_camel_case_account_fields() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={
                "code": 0,
                "data": {
                    "loggedIn": True,
                    "userName": "GY00999",
                    "displayName": "GY00999",
                    "userId": "906515367141965826",
                    "accountType": "PersonalBasic",
                },
            },
        ),
    )
    adapter = YingdaoSessionAdapter(StubLocator(), transport=transport)  # type: ignore[arg-type]

    session = asyncio.run(adapter.current())

    assert session.account.logged_in is True
    assert session.account.user_name == "GY00999"


def test_current_session_rejects_missing_login_status() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={"Code": 0, "Data": {"UserName": "GY00999"}},
        ),
    )
    adapter = YingdaoSessionAdapter(StubLocator(), transport=transport)  # type: ignore[arg-type]

    with pytest.raises(YingdaoSessionError) as error:
        asyncio.run(adapter.current())

    assert error.value.code == "YINGDAO_SESSION_INVALID"


def test_application_empty_list_and_error_envelopes_are_distinct() -> None:
    responses = iter(
        (
            {"Code": 0, "Data": {"items": []}},
            {"code": 5010, "data": None},
        ),
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, request=request, json=next(responses)),
    )
    session = YingdaoSession(
        endpoint=YingdaoRuntimeEndpoint(
            YingdaoProcess(1234, Path("ShadowBot.Shell.exe"), "6.3.6"),
            "http://127.0.0.1:42500",
        ),
        account=YingdaoSessionAccount(
            True,
            "GY00999",
            "GY00999",
            "906515367141965826",
            "PersonalBasic",
            None,
        ),
    )
    adapter = YingdaoApplicationAdapter(transport=transport)

    assert asyncio.run(adapter.list(session)) == []
    with pytest.raises(YingdaoSessionError) as error:
        asyncio.run(adapter.list(session))

    assert error.value.code == "YINGDAO_APPLICATION_INTERFACE_UNAVAILABLE"


def test_locator_finds_only_exact_636_installation(tmp_path: Path) -> None:
    root = tmp_path / "ShadowBot"
    for version in ("6.2.23", "6.3.6", "6.3.9"):
        directory = root / f"shadowbot-{version}"
        directory.mkdir(parents=True)
        (directory / "ShadowBot.Shell.exe").touch()
    locator = WindowsYingdaoRuntimeLocator(
        root,
        version_reader=lambda path: path.parent.name.removeprefix("shadowbot-"),
    )

    assert locator._find_supported_executable() == (
        root / "shadowbot-6.3.6" / "ShadowBot.Shell.exe"
    ).resolve()


def test_locator_auto_starts_636_only_when_no_shadowbot_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "shadowbot-6.3.6" / "ShadowBot.Shell.exe"
    executable.parent.mkdir()
    executable.touch()
    process = YingdaoProcess(636, executable, "6.3.6")
    locator = WindowsYingdaoRuntimeLocator(
        tmp_path,
        version_reader=lambda _: "6.3.6",
        startup_timeout_seconds=1,
    )
    scans = iter(([], [process]))
    locator._list_shadowbot_processes = lambda: next(scans, [process])  # type: ignore[method-assign]

    async def resolve_running(processes: list[YingdaoProcess]) -> YingdaoRuntimeEndpoint:
        assert processes == [process]
        return YingdaoRuntimeEndpoint(process, "http://127.0.0.1:31500")

    locator._resolve_running = resolve_running  # type: ignore[method-assign]
    launches: list[tuple[list[str], str | None]] = []

    def fake_popen(command: list[str], **kwargs: object) -> object:
        launches.append((command, kwargs.get("cwd") if isinstance(kwargs.get("cwd"), str) else None))
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    async def resolve_twice() -> tuple[YingdaoRuntimeEndpoint, YingdaoRuntimeEndpoint]:
        first, second = await asyncio.gather(
            locator.resolve(start_if_missing=True),
            locator.resolve(start_if_missing=True),
        )
        return first, second

    endpoint, second_endpoint = asyncio.run(resolve_twice())

    assert endpoint.process == process
    assert second_endpoint.process == process
    assert launches == [([str(executable.resolve())], str(executable.parent.resolve()))]


def test_locator_resolves_dynamic_loopback_endpoint(tmp_path: Path) -> None:
    process = YingdaoProcess(636, tmp_path / "ShadowBot.Shell.exe", "6.3.6")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.port == 31500 and request.url.path == "/api/v1/account/current":
            return httpx.Response(200, json={"LoggedIn": True})
        return httpx.Response(404)

    locator = WindowsYingdaoRuntimeLocator(
        tmp_path,
        version_reader=lambda _: "6.3.6",
        probe_transport=httpx.MockTransport(handler),
    )
    locator._list_shadowbot_processes = lambda: [process]  # type: ignore[method-assign]
    locator._list_loopback_ports = lambda pids: [(31499, 636), (31500, 636)]  # type: ignore[method-assign]

    endpoint = asyncio.run(locator.resolve())

    assert endpoint.base_url == "http://127.0.0.1:31500"
    assert endpoint.process.pid == 636


def test_locator_reports_unreachable_dynamic_endpoint(tmp_path: Path) -> None:
    process = YingdaoProcess(636, tmp_path / "ShadowBot.Shell.exe", "6.3.6")
    locator = WindowsYingdaoRuntimeLocator(
        tmp_path,
        version_reader=lambda _: "6.3.6",
        probe_transport=httpx.MockTransport(
            lambda request: httpx.Response(404, request=request),
        ),
    )
    locator._list_shadowbot_processes = lambda: [process]  # type: ignore[method-assign]
    locator._list_loopback_ports = lambda pids: [(31500, 636)]  # type: ignore[method-assign]

    with pytest.raises(YingdaoSessionError) as error:
        asyncio.run(locator.resolve())

    assert error.value.code == "YINGDAO_INTERFACE_UNREACHABLE"
