"""Nikon D780 Process-Isolated Driver Worker Entrypoint & Startup Gate (Phase 2.2 / Phase 2.2.1).

Enforces the mandatory Worker Startup Gate before any Nikon MAID SDK native binary
(`Type0026.md3`, `NkdPTP.dll`, `NkRoyalmile.dll`, `dnssd.dll`) can be loaded into the process:

1. Receives `shm_name`, `parent_pid`, `worker_generation`, `worker_instance_id`, and `spool_dir`.
2. Note on Python imports vs. Native DLL loading (Audit S-2):
   Importing package modules under `vietphotobooth.camera.backends.nikon_maid` executes
   the package `__init__.py`, which imports Python modules (`maid_loader`, `maid_session`, etc.)
   into `sys.modules` WITHOUT calling `NikonSDKLoader.load()`. The mandatory isolation boundary
   is that NO native Nikon MAID DLL (`Type0026.md3`, `NkdPTP.dll`, `NkRoyalmile.dll`) is mapped
   into the Worker Process (`GetModuleHandleW == NULL` and `get_loader().is_loaded == False`)
   prior to completing the Startup Gate.
3. Verifies the Parent Process (`parent_pid`) is currently alive via Win32 `OpenProcess`
   + `WaitForSingleObject` / `GetExitCodeProcess`.
4. Verifies the Worker Process is contained inside a Windows Job Object via `IsProcessInJob()`
   AND verifies via `QueryInformationJobObject(NULL, JobObjectExtendedLimitInformation)` that
   the active Job Object has `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x00002000)` enabled (Audit S-3).
5. If NOT inside a Windows Job Object or if `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` is not set,
   refuses to load MAID and exits cleanly with `EXIT_NOT_IN_JOB_OBJECT = 72`.
6. Attaches to Main-created SharedMemory (`NikonSharedFrameBuffer.attach(shm_name)`),
   verifies `worker_generation`, and starts a `ParentWatchdogThread` that coordinates
   safe shutdown if the Parent Process terminates unexpectedly (Audit S-6 & M-2).
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import logging
import os
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence, Tuple

from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
    EXIT_HANDLER_HUNG_ON_SHUTDOWN,
    EXIT_WRITER_THREAD_JOIN_TIMEOUT,
    IPCTransport,
    NikonDriverWorkerServer,
    PipeConnectionTransport,
    StdioJsonLineTransport,
)
from vietphotobooth.camera.backends.nikon_maid.shm_frame_buffer import (
    NikonSharedFrameBuffer,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Exit Codes & Win32 Constants
# ============================================================================

EXIT_OK: int = 0
EXIT_INVALID_STARTUP_ARGS: int = 70
EXIT_PARENT_NOT_ALIVE: int = 71
EXIT_NOT_IN_JOB_OBJECT: int = 72
EXIT_PREMATURE_SDK_LOADED: int = 73
EXIT_SHM_ATTACH_FAILED: int = 74
EXIT_UNEXPECTED_ERROR: int = 75
# Re-exported from driver_worker_server for unified exit code reference:
# EXIT_WRITER_THREAD_JOIN_TIMEOUT = 76
# EXIT_HANDLER_HUNG_ON_SHUTDOWN = 77

SYNCHRONIZE: int = 0x00100000
PROCESS_QUERY_LIMITED_INFORMATION: int = 0x1000
WAIT_OBJECT_0: int = 0x00000000
WAIT_TIMEOUT: int = 0x00000102
STILL_ACTIVE: int = 259

# Win32 Job Object Constants (Audit S-3)
JobObjectExtendedLimitInformation: int = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: int = 0x00002000

NIKON_SDK_DLL_NAMES: Tuple[str, ...] = (
    "Type0026.md3",
    "NkdPTP.dll",
    "NkRoyalmile.dll",
)


# ============================================================================
# Win32 Job Object ctypes Structures (x64 & x86 compatible)
# ============================================================================

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


# ============================================================================
# Startup Configuration & Gate Result
# ============================================================================

@dataclass(frozen=True)
class WorkerStartupConfig:
    """Validated startup parameters for the Nikon Driver Worker Process.

    Note (Audit S-3): Does NOT accept an un-inherited raw parent handle integer.
    Instead, the Worker queries its own containing Windows Job Object directly via
    `QueryInformationJobObject(NULL, JobObjectExtendedLimitInformation, ...)`.
    """

    shm_name: str
    parent_pid: int
    worker_generation: int
    worker_instance_id: str
    spool_dir: str


@dataclass(frozen=True)
class StartupGateResult:
    """Outcome of the mandatory pre-MAID Worker Startup Gate."""

    passed: bool
    exit_code: int
    reason: str
    parent_handle: Optional[int] = None


class WorkerStartupGateError(RuntimeError):
    """Raised when the Worker Startup Gate rejects execution before MAID load."""

    def __init__(self, exit_code: int, message: str) -> None:
        super().__init__(message)
        self.exit_code = int(exit_code)


# ============================================================================
# Win32 Process, Job Object & Loaded-Module Inspection Helpers
# ============================================================================

def is_nikon_sdk_loaded_in_current_process() -> Tuple[bool, Optional[str]]:
    """Check whether any Nikon MAID native binary (`Type0026.md3`, etc.) is mapped into this process.

    Note (Audit S-2): Python modules (`maid_loader`, `maid_session`) may already be present in
    `sys.modules` due to package `__init__.py` imports. This function strictly checks whether
    the native SDK DLL has been loaded into the process address space.
    """
    loader_mod = sys.modules.get("vietphotobooth.camera.backends.nikon_maid.maid_loader")
    if loader_mod is not None:
        default_loader = getattr(loader_mod, "_default_loader", None)
        if default_loader is not None and getattr(default_loader, "is_loaded", False):
            return True, "NikonSDKLoader._default_loader.is_loaded == True"

    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_mod = kernel32.GetModuleHandleW
        get_mod.argtypes = [wintypes.LPCWSTR]
        get_mod.restype = wintypes.HMODULE
        for dll_name in NIKON_SDK_DLL_NAMES:
            h_mod = get_mod(dll_name)
            if h_mod:
                return True, dll_name

    return False, None


def open_and_check_parent_alive(parent_pid: int) -> Tuple[bool, Optional[int], str]:
    """Open a Win32 SYNCHRONIZE handle to `parent_pid` and verify it is currently alive."""
    if int(parent_pid) <= 0:
        return False, None, f"Invalid parent_pid={parent_pid}"

    if sys.platform != "win32":
        try:
            os.kill(int(parent_pid), 0)
            return True, None, "Parent alive (POSIX)"
        except OSError as exc:
            return False, None, f"Parent process {parent_pid} is not alive: {exc}"

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    open_proc = kernel32.OpenProcess
    open_proc.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_proc.restype = wintypes.HANDLE

    wait_single = kernel32.WaitForSingleObject
    wait_single.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_single.restype = wintypes.DWORD

    get_exit = kernel32.GetExitCodeProcess
    get_exit.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_exit.restype = wintypes.BOOL

    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    access = SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
    h_parent = open_proc(access, False, int(parent_pid))
    if not h_parent:
        err = ctypes.get_last_error()
        return False, None, f"OpenProcess(parent_pid={parent_pid}) failed with WinError={err}"

    wait_res = wait_single(h_parent, 0)
    if wait_res != WAIT_TIMEOUT:
        close_handle(h_parent)
        return (
            False,
            None,
            f"Parent process {parent_pid} has already exited (WaitForSingleObject={wait_res})",
        )

    exit_code = wintypes.DWORD(0)
    if get_exit(h_parent, ctypes.byref(exit_code)):
        if int(exit_code.value) != STILL_ACTIVE:
            close_handle(h_parent)
            return (
                False,
                None,
                f"Parent process {parent_pid} exit code is {exit_code.value} (!= STILL_ACTIVE)",
            )

    return True, int(h_parent), f"Parent process {parent_pid} verified alive"


def close_win32_handle(handle: Optional[int]) -> None:
    """Close a Win32 HANDLE safely."""
    if handle and sys.platform == "win32":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle(wintypes.HANDLE(int(handle)))
        except Exception:
            pass


def check_worker_in_job_object() -> Tuple[bool, str]:
    """Verify the current Worker Process is inside a Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.

    Audit S-3 Enforcement:
    1. Calls `IsProcessInJob(GetCurrentProcess(), NULL, &in_job)` and verifies `in_job == True`.
    2. Calls `QueryInformationJobObject(NULL, JobObjectExtendedLimitInformation, &ext_info, ...)`
       to inspect the actual Job Object containing the current process.
    3. Verifies `ext_info.BasicLimitInformation.LimitFlags & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE != 0`.
       If the Job Object does NOT enforce `KILL_ON_JOB_CLOSE`, returns `(False, reason)`.
    """
    force_not_in_job = os.environ.get("VIETPHOTOBOOTH_WORKER_FORCE_NOT_IN_JOB", "").strip().lower()
    if force_not_in_job in ("1", "true", "yes"):
        return (
            False,
            "IsProcessInJob returned False (forced via VIETPHOTOBOOTH_WORKER_FORCE_NOT_IN_JOB=1)",
        )

    if sys.platform != "win32":
        return False, f"Unsupported platform for Windows Job Object: {sys.platform}"

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    get_cur_proc = kernel32.GetCurrentProcess
    get_cur_proc.argtypes = []
    get_cur_proc.restype = wintypes.HANDLE

    is_in_job_fn = kernel32.IsProcessInJob
    is_in_job_fn.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.BOOL),
    ]
    is_in_job_fn.restype = wintypes.BOOL

    in_job = wintypes.BOOL(0)
    ok = is_in_job_fn(get_cur_proc(), wintypes.HANDLE(0), ctypes.byref(in_job))
    if not ok:
        err = ctypes.get_last_error()
        return False, f"IsProcessInJob Win32 call failed (WinError={err})"

    if not bool(in_job.value):
        return (
            False,
            "Worker process is NOT inside a Windows Job Object (IsProcessInJob == False). "
            "Refusing to load Nikon MAID SDK.",
        )

    # Step 2 (Audit S-3): Query the containing Job Object (hJob = NULL) for ExtendedLimitInformation
    query_job_fn = kernel32.QueryInformationJobObject
    query_job_fn.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    query_job_fn.restype = wintypes.BOOL

    ext_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    ret_len = wintypes.DWORD(0)
    q_ok = query_job_fn(
        wintypes.HANDLE(0),
        JobObjectExtendedLimitInformation,
        ctypes.byref(ext_info),
        wintypes.DWORD(ctypes.sizeof(ext_info)),
        ctypes.byref(ret_len),
    )
    if not q_ok:
        err = ctypes.get_last_error()
        return (
            False,
            f"QueryInformationJobObject(JobObjectExtendedLimitInformation) failed (WinError={err}). "
            "Refusing to load Nikon MAID SDK.",
        )

    limit_flags = int(ext_info.BasicLimitInformation.LimitFlags)
    if (limit_flags & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE) == 0:
        return (
            False,
            f"Containing Windows Job Object is missing JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE "
            f"(LimitFlags=0x{limit_flags:08X}). Refusing to load Nikon MAID SDK.",
        )

    return (
        True,
        f"Worker process verified inside Windows Job Object with "
        f"JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (LimitFlags=0x{limit_flags:08X})",
    )


# ============================================================================
# Startup Gate Execution & Parent Watchdog Thread
# ============================================================================

def execute_startup_gate(
    config: WorkerStartupConfig,
    *,
    job_check_fn: Optional[Callable[[], Tuple[bool, str]]] = None,
    parent_check_fn: Optional[Callable[[int], Tuple[bool, Optional[int], str]]] = None,
    sdk_loaded_check_fn: Optional[Callable[[], Tuple[bool, Optional[str]]]] = None,
) -> StartupGateResult:
    """Run all mandatory pre-MAID startup checks.

    Order of checks:
    1. Validate startup config fields (`shm_name`, `parent_pid`, `worker_generation`, `worker_instance_id`, `spool_dir`).
    2. Confirm NO Nikon SDK native DLL (`Type0026.md3`, `NkdPTP.dll`, `NkRoyalmile.dll`) has been loaded yet.
    3. Verify `parent_pid` is currently alive.
    4. Verify `IsProcessInJob()` AND `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` via `QueryInformationJobObject`.
       If False, close parent handle and return `EXIT_NOT_IN_JOB_OBJECT = 72`.
    5. Ensure `spool_dir` directory exists and is writable.
    """
    # 1. Config validation
    if not config.shm_name or not str(config.shm_name).strip():
        return StartupGateResult(
            passed=False,
            exit_code=EXIT_INVALID_STARTUP_ARGS,
            reason="shm_name must be a non-empty string",
        )
    if int(config.parent_pid) <= 0:
        return StartupGateResult(
            passed=False,
            exit_code=EXIT_INVALID_STARTUP_ARGS,
            reason=f"parent_pid must be > 0, got {config.parent_pid}",
        )
    if int(config.worker_generation) < 1:
        return StartupGateResult(
            passed=False,
            exit_code=EXIT_INVALID_STARTUP_ARGS,
            reason=f"worker_generation must be >= 1, got {config.worker_generation}",
        )
    if not config.worker_instance_id or not str(config.worker_instance_id).strip():
        return StartupGateResult(
            passed=False,
            exit_code=EXIT_INVALID_STARTUP_ARGS,
            reason="worker_instance_id must be a non-empty string",
        )
    if not config.spool_dir or not str(config.spool_dir).strip():
        return StartupGateResult(
            passed=False,
            exit_code=EXIT_INVALID_STARTUP_ARGS,
            reason="spool_dir must be a non-empty path",
        )

    # 2. Verify no Nikon native DLL is loaded before completing Startup Gate
    s_check = sdk_loaded_check_fn or is_nikon_sdk_loaded_in_current_process
    sdk_loaded, dll_name = s_check()
    if sdk_loaded:
        return StartupGateResult(
            passed=False,
            exit_code=EXIT_PREMATURE_SDK_LOADED,
            reason=f"Nikon SDK binary {dll_name!r} was loaded BEFORE Startup Gate completion!",
        )

    # 3. Verify Parent Process is alive
    p_check = parent_check_fn or open_and_check_parent_alive
    parent_alive, h_parent, parent_msg = p_check(int(config.parent_pid))
    if not parent_alive:
        return StartupGateResult(
            passed=False,
            exit_code=EXIT_PARENT_NOT_ALIVE,
            reason=parent_msg,
        )

    # 4. Verify Worker is inside a Windows Job Object with KILL_ON_JOB_CLOSE BEFORE loading MAID
    if job_check_fn is not None:
        in_job, job_msg = job_check_fn()
    else:
        in_job, job_msg = check_worker_in_job_object()

    if not in_job:
        close_win32_handle(h_parent)
        return StartupGateResult(
            passed=False,
            exit_code=EXIT_NOT_IN_JOB_OBJECT,
            reason=job_msg,
        )

    # 5. Prepare spool_dir and mark worker environment variable so NikonSDKLoader allows loading in Worker
    try:
        os.makedirs(os.path.abspath(config.spool_dir), exist_ok=True)
    except Exception as exc:
        close_win32_handle(h_parent)
        return StartupGateResult(
            passed=False,
            exit_code=EXIT_INVALID_STARTUP_ARGS,
            reason=f"Failed to create spool_dir {config.spool_dir!r}: {exc}",
        )

    os.environ["VIETPHOTOBOOTH_NIKON_WORKER_PROCESS"] = "1"

    return StartupGateResult(
        passed=True,
        exit_code=EXIT_OK,
        reason=(
            "Startup Gate passed (parent alive + Job Object KILL_ON_JOB_CLOSE verified "
            "+ zero premature native DLL load)"
        ),
        parent_handle=h_parent,
    )


class ParentWatchdogThread(threading.Thread):
    """Daemon thread that watches the Parent Process handle and triggers staged shutdown if Parent dies (Audit S-6)."""

    def __init__(
        self,
        parent_handle: Optional[int],
        on_parent_died: Callable[[], Any],
        poll_interval_ms: int = 200,
    ) -> None:
        super().__init__(name="NikonWorkerParentWatchdog", daemon=True)
        self._parent_handle = parent_handle
        self._on_parent_died = on_parent_died
        self._poll_interval_ms = max(20, int(poll_interval_ms))
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        if not self._parent_handle or sys.platform != "win32":
            return

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        wait_single = kernel32.WaitForSingleObject
        wait_single.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        wait_single.restype = wintypes.DWORD

        h_proc = wintypes.HANDLE(int(self._parent_handle))
        while not self._stop_event.is_set():
            res = wait_single(h_proc, self._poll_interval_ms)
            if res == WAIT_OBJECT_0:
                logger.warning(
                    "[ParentWatchdog] Parent process terminated (WAIT_OBJECT_0). Requesting staged Worker shutdown."
                )
                try:
                    self._on_parent_died()
                except Exception:
                    pass
                break
            elif res != WAIT_TIMEOUT:
                logger.warning(
                    "[ParentWatchdog] WaitForSingleObject returned %d. Requesting staged Worker shutdown.",
                    res,
                )
                try:
                    self._on_parent_died()
                except Exception:
                    pass
                break


# ============================================================================
# Worker Process Runner (In-Process / Pipe / CLI Subprocess)
# ============================================================================

def run_worker_process(
    config: WorkerStartupConfig,
    *,
    transport: Optional[IPCTransport] = None,
    session_factory: Optional[Callable[[], Any]] = None,
    job_check_fn: Optional[Callable[[], Tuple[bool, str]]] = None,
    parent_check_fn: Optional[Callable[[int], Tuple[bool, Optional[int], str]]] = None,
    sdk_loaded_check_fn: Optional[Callable[[], Tuple[bool, Optional[str]]]] = None,
    live_view_poll_interval_s: float = 0.010,
    heartbeat_interval_s: float = 0.100,
) -> int:
    """Execute the Startup Gate, attach SharedMemory, and run `NikonDriverWorkerServer`.

    Returns an integer process exit code (`EXIT_OK = 0` on clean shutdown, or a
    specific non-zero `EXIT_*` code if rejected by the Startup Gate or if a thread/handler
    hung during shutdown).
    """
    gate = execute_startup_gate(
        config,
        job_check_fn=job_check_fn,
        parent_check_fn=parent_check_fn,
        sdk_loaded_check_fn=sdk_loaded_check_fn,
    )
    if not gate.passed:
        sys.stderr.write(f"[NikonDriverWorker] STARTUP_GATE_REJECTED (code={gate.exit_code}): {gate.reason}\n")
        sys.stderr.flush()
        return gate.exit_code

    shm: Optional[NikonSharedFrameBuffer] = None
    watchdog: Optional[ParentWatchdogThread] = None
    server: Optional[NikonDriverWorkerServer] = None
    exit_code: int = EXIT_OK

    try:
        # Attach to SharedMemory created by Main Process (never create=True, never unlink)
        try:
            shm = NikonSharedFrameBuffer.attach(name=config.shm_name)
        except Exception as exc:
            sys.stderr.write(
                f"[NikonDriverWorker] Failed to attach SharedMemory {config.shm_name!r}: {exc}\n"
            )
            sys.stderr.flush()
            return EXIT_SHM_ATTACH_FAILED

        # Verify worker_generation in SharedMemory header matches
        header_gen = int(shm.global_header.worker_generation)
        if header_gen != int(config.worker_generation):
            shm.close()
            sys.stderr.write(
                f"[NikonDriverWorker] SharedMemory worker_generation mismatch: "
                f"shm={header_gen} != arg={config.worker_generation}\n"
            )
            sys.stderr.flush()
            return EXIT_SHM_ATTACH_FAILED

        active_transport: IPCTransport = (
            transport
            if transport is not None
            else StdioJsonLineTransport(sys.stdin, sys.stdout)
        )

        server = NikonDriverWorkerServer(
            worker_generation=config.worker_generation,
            worker_instance_id=config.worker_instance_id,
            shm_buffer=shm,
            spool_dir=config.spool_dir,
            transport=active_transport,
            session_factory=session_factory,
            live_view_poll_interval_s=live_view_poll_interval_s,
            heartbeat_interval_s=heartbeat_interval_s,
        )

        watchdog = ParentWatchdogThread(
            parent_handle=gate.parent_handle,
            on_parent_died=server.shutdown_and_close,
        )
        watchdog.start()

        exit_code = server.serve_forever(emit_ready_event=True)
        return exit_code

    except Exception as exc:
        logger.exception("[NikonDriverWorker] Fatal worker error: %s", exc)
        sys.stderr.write(f"[NikonDriverWorker] Fatal error: {exc}\n")
        sys.stderr.flush()
        return EXIT_UNEXPECTED_ERROR
    finally:
        if watchdog is not None:
            watchdog.stop()
            watchdog.join(timeout=1.0)
        if server is not None:
            shut_code = server.shutdown_and_close()
            if exit_code == EXIT_OK and shut_code != EXIT_OK:
                exit_code = shut_code
        elif shm is not None and not shm.is_closed:
            shm.close()
        close_win32_handle(gate.parent_handle)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vietphotobooth.camera.backends.nikon_maid.driver_worker_main",
        description="1998 TEAM — Nikon D780 Process-Isolated Driver Worker",
    )
    parser.add_argument("--shm-name", required=True, help="SharedMemory segment name created by Main Process")
    parser.add_argument("--parent-pid", required=True, type=int, help="Main Process PID to monitor")
    parser.add_argument("--worker-generation", required=True, type=int, help="Monotonic worker generation (>= 1)")
    parser.add_argument("--worker-instance-id", required=True, help="Unique worker instance identifier")
    parser.add_argument("--spool-dir", required=True, help="Directory for atomic raw capture spooling")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_INVALID_STARTUP_ARGS
        return code if code != 0 else EXIT_OK

    config = WorkerStartupConfig(
        shm_name=args.shm_name,
        parent_pid=int(args.parent_pid),
        worker_generation=int(args.worker_generation),
        worker_instance_id=args.worker_instance_id,
        spool_dir=args.spool_dir,
    )
    return run_worker_process(config)


if __name__ == "__main__":
    sys.exit(main())
