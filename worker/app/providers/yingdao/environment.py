from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.providers.yingdao.discovery import read_windows_file_version


SUPPORTED_EXECUTION_VERSIONS = ("6.3.6", "6.2.23")


@dataclass(frozen=True)
class YingdaoEnvironment:
    install_root: Path
    executable_path: Path
    discovery_cli_path: Path
    provider_version: str
    execution_available: bool
    execution_version: str | None
    execution_executable_path: Path | None
    execution_unavailable_reason: str | None


class YingdaoVersionResolver:
    def __init__(
        self,
        install_root: Path,
        *,
        version_reader: Callable[[Path], str] | None = None,
    ) -> None:
        self.install_root = install_root.resolve()
        self.version_reader = version_reader or read_windows_file_version

    def resolve(self) -> YingdaoEnvironment:
        executable = self.install_root / "ShadowBot.exe"
        if not executable.is_file():
            raise FileNotFoundError("ShadowBot.exe was not found")

        provider_version = self.version_reader(executable)
        executable_candidates: dict[str, Path] = {provider_version: executable}
        for directory in self.install_root.glob("shadowbot-*"):
            candidate = directory / "ShadowBot.exe"
            if not candidate.is_file():
                continue
            try:
                executable_candidates[self.version_reader(candidate)] = candidate
            except OSError:
                continue

        execution_version = next(
            (
                version
                for version in SUPPORTED_EXECUTION_VERSIONS
                if version in executable_candidates
            ),
            None,
        )
        execution_executable = (
            executable_candidates[execution_version] if execution_version else None
        )

        cli_639 = (
            self.install_root / "shadowbot-6.3.9" / "shadowbot.shell-cli.exe"
        )
        root_cli = self.install_root / "shadowbot.shell-cli.exe"
        if cli_639.is_file():
            discovery_cli = cli_639
        elif root_cli.is_file():
            discovery_cli = root_cli
        else:
            discovered = sorted(
                self.install_root.glob("shadowbot-*/shadowbot.shell-cli.exe"),
            )
            if not discovered:
                raise FileNotFoundError("shadowbot.shell-cli.exe was not found")
            discovery_cli = discovered[-1]

        return YingdaoEnvironment(
            install_root=self.install_root,
            executable_path=executable,
            discovery_cli_path=discovery_cli,
            provider_version=provider_version,
            execution_available=execution_version is not None,
            execution_version=execution_version,
            execution_executable_path=execution_executable,
            execution_unavailable_reason=(
                None
                if execution_version is not None
                else "当前影刀版本不在已验证执行白名单"
            ),
        )
