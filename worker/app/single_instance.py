import ctypes
import os
from types import TracebackType
from uuid import UUID


ERROR_ALREADY_EXISTS = 183


class WorkerAlreadyRunningError(RuntimeError):
    """Raised when the same Device identity already owns the local mutex."""


class WorkerSingleInstance:
    def __init__(self, device_id: UUID) -> None:
        self.device_id = device_id
        self._handle: int | None = None

    def __enter__(self) -> "WorkerSingleInstance":
        if os.name != "nt":
            return self
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(
            None,
            True,
            f"Global\\EcommerceAIWorker-{self.device_id}",
        )
        if not handle:
            raise OSError(ctypes.get_last_error(), "Worker mutex could not be created")
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            raise WorkerAlreadyRunningError(str(self.device_id))
        self._handle = int(handle)
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if os.name != "nt" or self._handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.ReleaseMutex(ctypes.c_void_p(self._handle))
        kernel32.CloseHandle(ctypes.c_void_p(self._handle))
        self._handle = None
