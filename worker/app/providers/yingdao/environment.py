from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.providers.yingdao.discovery import read_windows_file_version


REQUIRED_YINGDAO_VERSION = "6.3.6"


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
        candidates = self._executable_candidates()
        if not candidates:
            raise FileNotFoundError("ShadowBot.exe was not found")

        versioned_candidates: list[tuple[str, Path]] = []
        for candidate in candidates:
            try:
                version = self.version_reader(candidate)
            except OSError:
                continue
            versioned_candidates.append((version, candidate))
        if not versioned_candidates:
            raise OSError("ShadowBot version metadata could not be read")

        required_candidate = next(
            (
                item
                for item in versioned_candidates
                if item[0] == REQUIRED_YINGDAO_VERSION
                and item[1].parent.name.lower()
                == f"shadowbot-{REQUIRED_YINGDAO_VERSION}"
            ),
            None,
        )
        required_candidate = required_candidate or next(
            (
                item
                for item in versioned_candidates
                if item[0] == REQUIRED_YINGDAO_VERSION
            ),
            None,
        )
        if required_candidate is not None:
            _, executable = required_candidate
            return YingdaoEnvironment(
                install_root=self.install_root,
                executable_path=executable,
                provider_version=REQUIRED_YINGDAO_VERSION,
                execution_available=True,
                execution_version=REQUIRED_YINGDAO_VERSION,
                execution_executable_path=executable,
                execution_unavailable_reason=None,
            )

        provider_version, executable = max(
            versioned_candidates,
            key=lambda item: self._version_key(item[0]),
        )
        return YingdaoEnvironment(
            install_root=self.install_root,
            executable_path=executable,
            provider_version=provider_version,
            execution_available=False,
            execution_version=None,
            execution_executable_path=None,
            execution_unavailable_reason="Worker currently requires Yingdao 6.3.6",
        )

    def _executable_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        for name in ("ShadowBot.Shell.exe", "ShadowBot.exe"):
            candidate = self.install_root / name
            if candidate.is_file():
                candidates.append(candidate)
        candidates.extend(
            candidate
            for directory in self.install_root.glob("shadowbot-*")
            if (candidate := self._version_executable(directory)) is not None
        )
        return list(dict.fromkeys(candidates))

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
