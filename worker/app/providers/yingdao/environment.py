from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.providers.yingdao.discovery import read_windows_file_version


SUPPORTED_EXECUTION_VERSIONS = ("6.3.6", "6.2.23")


@dataclass(frozen=True)
class YingdaoEnvironment:
    install_root: Path
    executable_path: Path
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
        root_executable = self.install_root / "ShadowBot.exe"
        candidates = [root_executable] if root_executable.is_file() else []
        candidates.extend(
            candidate
            for directory in self.install_root.glob("shadowbot-*")
            if (
                candidate := self._version_executable(directory)
            ) is not None
        )
        if not candidates:
            raise FileNotFoundError("ShadowBot.exe was not found")

        executable_candidates: dict[str, Path] = {}
        versioned_candidates: list[tuple[str, Path]] = []
        for candidate in candidates:
            try:
                version = self.version_reader(candidate)
            except OSError:
                continue
            versioned_candidates.append((version, candidate))
            executable_candidates.setdefault(version, candidate)
        if not versioned_candidates:
            raise OSError("ShadowBot version metadata could not be read")

        root_candidate = next(
            (
                item
                for item in versioned_candidates
                if item[1] == root_executable
            ),
            None,
        )
        provider_version, executable = root_candidate or max(
            versioned_candidates,
            key=lambda item: self._version_key(item[0]),
        )

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

        return YingdaoEnvironment(
            install_root=self.install_root,
            executable_path=executable,
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

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        try:
            return tuple(int(part) for part in version.split("."))
        except ValueError:
            return (0,)

    @staticmethod
    def _version_executable(directory: Path) -> Path | None:
        for name in ("ShadowBot.Shell.exe", "ShadowBot.exe"):
            candidate = directory / name
            if candidate.is_file():
                return candidate
        return None
