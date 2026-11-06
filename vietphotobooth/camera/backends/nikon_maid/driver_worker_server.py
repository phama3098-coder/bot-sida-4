"""Nikon D780 Process-Isolated Driver Worker Server & Atomic Spooler (Phase 2.2 / Phase 2.2.1).

Implements:
1. ``AtomicCaptureSpooler``: Crash-safe, zero-overwrite atomic disk spooling
   (`raw_{tx_id}.jpg.part` -> `fsync` -> `os.rename` -> `raw_{tx_id}.jpg`
   and `raw_{tx_id}.meta.json.part` -> `fsync` -> `os.rename` -> `raw_{tx_id}.meta.json`)
   with strict `^[A-Za-z0-9_-]{1,128}$` allowlist validation (Audit I-7), SHA-256 checksum,
   JPEG SOI/EOI validation, and full entropy-scan decoding (`img.load()` / `cv2.imdecode`)
   (Audit P-2 & P-3).
2. ``NikonDriverWorkerServer``: Bidirectional IPC v1 Server managing ``NikonSession``,
   SharedMemory Live View frame streaming (`NikonSharedFrameBuffer`), heartbeat updates,
   request deduplication, mandatory deadline enforcement (Audit I-3), generation/instance
   verification, thread-join `is_alive()` verification (Audit M-2), and staged shutdown
   coordination that never closes transport/SharedMemory while an active request handler
   or writer thread is still running (Audit S-6 & M-2).

NOTE ON PYTHON IMPORTS VS. NATIVE DLL LOADING (Audit S-2):
Because ``vietphotobooth.camera.backends.nikon_maid.__init__`` imports package Python modules
at package import time, ``maid_loader`` and ``maid_session`` Python modules may already exist
in ``sys.modules`` before the Worker Startup Gate runs. However, NO Nikon native DLL
(`Type0026.md3`, `NkdPTP.dll`, `NkRoyalmile.dll`) is loaded into the process address space
until ``NikonSession.open_module()`` -> ``NikonSDKLoader.load()`` is invoked AFTER the
Startup Gate in ``driver_worker_main.py`` has verified parent process liveness and Windows
Job Object containment (`IsProcessInJob()` + `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Tuple

import cv2
import numpy as np
from PIL import Image, ImageFile

from vietphotobooth.camera.backends.nikon_maid.ipc_protocol import (
    IPCCommandMethod,
    IPCErrorCode,
    IPCEvent,
    IPCEventName,
    IPCMessageType,
    IPCProtocolError,
    IPCRequest,
    IPCResponse,
    PROTOCOL_VERSION,
    generate_request_id,
    validate_message_schema,
)
from vietphotobooth.camera.backends.nikon_maid.shm_frame_buffer import (
    DEFAULT_LIVE_VIEW_HEIGHT,
    DEFAULT_LIVE_VIEW_WIDTH,
    JPEG_EOI_MARKER,
    JPEG_SOI_MARKER,
    NikonSharedFrameBuffer,
    WriterState,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Constants, Allowlist Regex & Worker Shutdown Exit Codes
# ============================================================================

# Audit I-7: Strict identifier allowlist preventing path traversal, NTFS ADS (:), wildcards, control chars
SAFE_IDENTIFIER_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# Audit M-2 & S-6: Dedicated exit codes when a writer thread or request handler hangs
EXIT_SERVER_OK: int = 0
EXIT_WRITER_THREAD_JOIN_TIMEOUT: int = 76
EXIT_HANDLER_HUNG_ON_SHUTDOWN: int = 77


def validate_safe_identifier(value: Any, label: str) -> str:
    """Validate `tx_id` or `request_id` against `^[A-Za-z0-9_-]{1,128}$` (Audit I-7)."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string, got {type(value).__name__}")
    if not SAFE_IDENTIFIER_REGEX.fullmatch(value):
        raise ValueError(
            f"{label} {value!r} violates allowlist pattern '^[A-Za-z0-9_-]{{1,128}}$'"
        )
    return value


# ============================================================================
# 1. Atomic Capture Spooler (Crash-Safe Raw JPEG + JSON Manifest)
# ============================================================================

@dataclass(frozen=True)
class SpoolArtifact:
    """Verified on-disk capture artifact produced by AtomicCaptureSpooler."""

    tx_id: str
    request_id: str
    worker_generation: int
    worker_instance_id: str
    raw_file_path: str
    meta_file_path: str
    file_name: str
    file_size: int
    sha256: str
    width: int
    height: int
    captured_timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "tx_id": self.tx_id,
            "request_id": self.request_id,
            "worker_generation": self.worker_generation,
            "worker_instance_id": self.worker_instance_id,
            "raw_file_path": self.raw_file_path,
            "meta_file_path": self.meta_file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "width": self.width,
            "height": self.height,
            "captured_timestamp": self.captured_timestamp,
        }


class AtomicSpoolError(RuntimeError):
    """Raised when atomic spooling or JPEG validation fails."""


class AtomicCaptureSpooler:
    """Crash-safe atomic spooler for Nikon D780 captured JPEG buffers.

    Guarantees (Architecture Section 4.1, Phase 2.2 Spec E & Phase 2.2.1 Audit I-7/P-2/P-3):
    - Enforces `^[A-Za-z0-9_-]{1,128}$` on `tx_id` and `request_id` (prevents NTFS ADS `:`,
      path separators, wildcards, control characters).
    - Uses `tx_id` in filenames: `raw_{tx_id}.jpg` and `raw_{tx_id}.meta.json`.
    - Writes to `.part` files using `os.O_WRONLY | os.O_CREAT | os.O_EXCL` so existing
      files are NEVER overwritten.
    - Commits `.part` -> final path via `os.rename()` (which on Windows raises `FileExistsError`
      if the destination exists, eliminating any TOCTOU overwrite window).
    - Flushes and `os.fsync(fd)`s both `.jpg.part` and `.meta.json.part` before `os.rename()`.
    - Validates non-empty JPEG bytes, SOI (`0xFFD8`) and EOI (`0xFFD9`) markers,
      and performs FULL entropy-scan pixel decoding via `img.load()` (with
      `ImageFile.LOAD_TRUNCATED_IMAGES = False`) before committing.
    - Never deletes any file in `spool_dir`.
    """

    def __init__(self, spool_dir: str) -> None:
        if not spool_dir or not str(spool_dir).strip():
            raise ValueError("spool_dir must be a non-empty directory path")
        self._spool_dir = os.path.abspath(str(spool_dir).strip())
        os.makedirs(self._spool_dir, exist_ok=True)

    @property
    def spool_dir(self) -> str:
        return self._spool_dir

    @staticmethod
    def _sanitize_token(token: Any, label: str) -> str:
        try:
            return validate_safe_identifier(token, label)
        except ValueError as exc:
            raise AtomicSpoolError(str(exc)) from exc

    @staticmethod
    def validate_jpeg_bytes(raw_jpeg: bytes) -> Tuple[int, int, str]:
        """Validate JPEG SOI/EOI markers, perform full entropy-scan decode via PIL `load()`, and compute SHA-256."""
        if not isinstance(raw_jpeg, (bytes, bytearray, memoryview)):
            raise AtomicSpoolError("Captured payload must be bytes-like")
        data = bytes(raw_jpeg)
        if len(data) < 4:
            raise AtomicSpoolError(f"Captured JPEG is too short ({len(data)} bytes)")
        if data[:2] != JPEG_SOI_MARKER:
            raise AtomicSpoolError(
                f"Captured JPEG missing SOI marker 0xFFD8 (got {data[:2].hex()})"
            )
        if data[-2:] != JPEG_EOI_MARKER:
            raise AtomicSpoolError(
                f"Captured JPEG missing EOI marker 0xFFD9 (got {data[-2:].hex()})"
            )

        # Audit P-3: Full entropy-scan decoding via img.load() with LOAD_TRUNCATED_IMAGES=False
        # (Image.verify() only checks headers/tables and misses corrupted scan data before EOI)
        prev_truncated = ImageFile.LOAD_TRUNCATED_IMAGES
        ImageFile.LOAD_TRUNCATED_IMAGES = False
        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
            with Image.open(io.BytesIO(data)) as img_decode:
                img_decode.load()
                width, height = img_decode.size
        except Exception as exc:
            raise AtomicSpoolError(
                f"Captured JPEG failed full entropy-scan decoding: {exc}"
            ) from exc
        finally:
            ImageFile.LOAD_TRUNCATED_IMAGES = prev_truncated

        if width <= 0 or height <= 0:
            raise AtomicSpoolError(f"Invalid decoded JPEG dimensions: {width}x{height}")

        digest = hashlib.sha256(data).hexdigest()
        return int(width), int(height), digest

    @staticmethod
    def _write_exclusive_and_fsync(part_path: str, payload: bytes) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        try:
            fd = os.open(part_path, flags, 0o600)
        except FileExistsError as exc:
            raise AtomicSpoolError(
                f"Refusing to overwrite existing spool part file: {part_path!r}"
            ) from exc

        try:
            view = memoryview(payload)
            total_written = 0
            while total_written < len(view):
                written = os.write(fd, view[total_written:])
                if written <= 0:
                    raise AtomicSpoolError(f"Short write to {part_path!r}")
                total_written += written
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _atomic_rename_no_overwrite(part_path: str, final_path: str) -> None:
        """Atomically rename `part_path` to `final_path` using `os.rename` (never overwrites on Windows)."""
        if os.path.exists(final_path):
            raise AtomicSpoolError(
                f"Refusing to overwrite existing spool file: {final_path!r}"
            )
        try:
            os.rename(part_path, final_path)
        except FileExistsError as exc:
            raise AtomicSpoolError(
                f"Refusing to overwrite existing spool file: {final_path!r}"
            ) from exc
        except OSError as exc:
            raise AtomicSpoolError(
                f"Atomic rename failed from {part_path!r} to {final_path!r}: {exc}"
            ) from exc

    def spool_capture(
        self,
        *,
        tx_id: str,
        request_id: str,
        worker_generation: int,
        worker_instance_id: str,
        raw_jpeg: bytes,
        captured_timestamp: Optional[float] = None,
    ) -> SpoolArtifact:
        """Atomically spool raw JPEG and JSON manifest to disk before any IPC completion."""
        safe_tx_id = self._sanitize_token(tx_id, "tx_id")
        safe_req_id = self._sanitize_token(request_id, "request_id")
        os.makedirs(self._spool_dir, exist_ok=True)

        width, height, sha256_hex = self.validate_jpeg_bytes(raw_jpeg)
        jpeg_bytes = bytes(raw_jpeg)
        file_size = len(jpeg_bytes)
        cap_ts = time.time() if captured_timestamp is None else float(captured_timestamp)

        jpg_name = f"raw_{safe_tx_id}.jpg"
        meta_name = f"raw_{safe_tx_id}.meta.json"

        jpg_final_path = os.path.join(self._spool_dir, jpg_name)
        jpg_part_path = os.path.join(self._spool_dir, f"{jpg_name}.part")
        meta_final_path = os.path.join(self._spool_dir, meta_name)
        meta_part_path = os.path.join(self._spool_dir, f"{meta_name}.part")

        # Pre-flight zero-overwrite check on all 4 paths
        for existing_target in (jpg_final_path, meta_final_path, jpg_part_path, meta_part_path):
            if os.path.exists(existing_target):
                raise AtomicSpoolError(
                    f"Refusing to overwrite existing spool file: {existing_target!r}"
                )

        # Step 1: Write raw_{tx_id}.jpg.part -> fsync -> os.rename -> raw_{tx_id}.jpg
        self._write_exclusive_and_fsync(jpg_part_path, jpeg_bytes)
        self._atomic_rename_no_overwrite(jpg_part_path, jpg_final_path)

        # Step 2: Write raw_{tx_id}.meta.json.part -> fsync -> os.rename -> raw_{tx_id}.meta.json
        manifest_dict = {
            "schema_version": 1,
            "tx_id": safe_tx_id,
            "request_id": safe_req_id,
            "worker_generation": int(worker_generation),
            "worker_instance_id": str(worker_instance_id),
            "file_name": jpg_name,
            "raw_file_path": jpg_final_path,
            "file_size": file_size,
            "sha256": sha256_hex,
            "width": width,
            "height": height,
            "captured_timestamp": cap_ts,
        }
        manifest_bytes = json.dumps(
            manifest_dict, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8")

        self._write_exclusive_and_fsync(meta_part_path, manifest_bytes)
        self._atomic_rename_no_overwrite(meta_part_path, meta_final_path)

        return SpoolArtifact(
            tx_id=safe_tx_id,
            request_id=safe_req_id,
            worker_generation=int(worker_generation),
            worker_instance_id=str(worker_instance_id),
            raw_file_path=jpg_final_path,
            meta_file_path=meta_final_path,
            file_name=jpg_name,
            file_size=file_size,
            sha256=sha256_hex,
            width=width,
            height=height,
            captured_timestamp=cap_ts,
        )


# ============================================================================
# 2. Bidirectional IPC Transport Abstraction & Wire Message Parser
# ============================================================================

def parse_wire_message(
    raw: Mapping[str, Any] | str | bytes,
) -> IPCRequest | IPCResponse | IPCEvent:
    """Decode and schema-validate a wire message into `IPCRequest`, `IPCResponse`, or `IPCEvent`."""
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
            decoded = json.loads(text)
        except Exception as exc:
            raise IPCProtocolError(
                f"Malformed JSON wire message: {exc}",
                IPCErrorCode.INVALID_SCHEMA,
            ) from exc
    elif isinstance(raw, Mapping):
        decoded = raw
    else:
        raise IPCProtocolError(
            f"Unsupported wire message type: {type(raw).__name__}",
            IPCErrorCode.INVALID_SCHEMA,
        )

    validated = validate_message_schema(decoded)
    msg_type = validated["msg_type"]
    if msg_type == IPCMessageType.COMMAND.value:
        return IPCRequest.from_dict(validated)
    if msg_type == IPCMessageType.RESPONSE.value:
        return IPCResponse.from_dict(validated)
    if msg_type == IPCMessageType.EVENT.value:
        return IPCEvent.from_dict(validated)
    raise IPCProtocolError(
        f"Unknown msg_type: {msg_type!r}",
        IPCErrorCode.INVALID_SCHEMA,
    )


class IPCTransport(Protocol):
    """Bidirectional wire message transport for the Worker IPC Server."""

    def recv_message(self) -> Optional[Dict[str, Any] | str | bytes]:
        """Block until next message arrives, or return None on EOF."""

    def send_message(self, payload: Dict[str, Any]) -> None:
        """Send a dictionary message to the Main Process."""

    def close(self) -> None:
        """Close underlying transport channel."""


class PipeConnectionTransport:
    """IPCTransport over a `multiprocessing.connection.Connection` (Pipe)."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn
        self._send_lock = threading.Lock()
        self._closed = False

    def recv_message(self) -> Optional[Dict[str, Any] | str | bytes]:
        if self._closed:
            return None
        try:
            msg = self._conn.recv()
            return msg
        except (EOFError, BrokenPipeError, OSError):
            return None

    def send_message(self, payload: Dict[str, Any]) -> None:
        with self._send_lock:
            if self._closed:
                raise BrokenPipeError("PipeConnectionTransport is closed")
            self._conn.send(payload)

    def close(self) -> None:
        with self._send_lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._conn.close()
            except Exception:
                pass


class StdioJsonLineTransport:
    """IPCTransport over newline-delimited JSON on binary/text streams (e.g. stdin/stdout)."""

    def __init__(self, input_stream: Any, output_stream: Any) -> None:
        self._in = input_stream
        self._out = output_stream
        self._send_lock = threading.Lock()
        self._closed = False

    def recv_message(self) -> Optional[str]:
        if self._closed:
            return None
        try:
            line = self._in.readline()
            if not line:
                return None
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            return line.strip()
        except (EOFError, BrokenPipeError, OSError, ValueError):
            return None

    def send_message(self, payload: Dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._send_lock:
            if self._closed:
                raise BrokenPipeError("StdioJsonLineTransport is closed")
            if hasattr(self._out, "write"):
                try:
                    self._out.write(line)
                except TypeError:
                    self._out.write(line.encode("utf-8"))
                self._out.flush()

    def close(self) -> None:
        with self._send_lock:
            self._closed = True


# ============================================================================
# 3. Nikon Driver Worker IPC Server
# ============================================================================

@dataclass
class _SeenRequestEntry:
    """Tracks request deduplication state in the Worker Process."""

    request_id: str
    method: str
    received_at_mono: float
    state: str  # "IN_FLIGHT" | "COMPLETED"
    response: Optional[IPCResponse] = None


# Commands exempt from mandatory deadline_mono / sent_at_mono requirement (Audit I-3)
_DEADLINE_EXEMPT_METHODS = frozenset({
    IPCCommandMethod.PING.value,
    IPCCommandMethod.SHUTDOWN.value,
})


class NikonDriverWorkerServer:
    """Isolated Worker Process IPC Server managing `NikonSession` and SharedMemory.

    Enforces all Phase 2.2 & Phase 2.2.1 architectural invariants:
    - Validates `protocol_version == 1`, `worker_generation`, and `worker_instance_id`.
    - Validates `request_id` and `tx_id` against `^[A-Za-z0-9_-]{1,128}$` (Audit I-7).
    - Requires `deadline_mono` or `sent_at_mono`/`created_at_mono` for all time-bounded
      requests (except `PING` and `SHUTDOWN`), properly handling `0.0` without falsy `or` bugs,
      and rejects expired requests before execution (Audit I-3).
    - Deduplicates `request_id` and never automatically retries `CAPTURE` commands.
    - Streams Live View frames into `NikonSharedFrameBuffer` with monotonically
      increasing `sequence_id` and regular heartbeat updates.
    - Checks `thread.is_alive()` after every `join()` (Audit M-2): if the Live View producer
      or Heartbeat thread fails to stop within the join timeout, logs CRITICAL, sets
      `writer_state = WriterState.STOPPING`, refuses to call `close_module()` or `shm.close()`,
      and returns `EXIT_WRITER_THREAD_JOIN_TIMEOUT = 76`.
    - Coordinates staged shutdown (Audit S-6): stops accepting new requests -> waits for any
      in-flight request handler to finish -> stops & joins writer/heartbeat threads -> closes
      `NikonSession` -> closes SharedMemory -> closes transport. If an in-flight handler hangs,
      refuses to close SharedMemory/session/transport under the running handler and returns
      `EXIT_HANDLER_HUNG_ON_SHUTDOWN = 77`.
    """

    def __init__(
        self,
        *,
        worker_generation: int,
        worker_instance_id: str,
        shm_buffer: NikonSharedFrameBuffer,
        spool_dir: str,
        transport: IPCTransport,
        session_factory: Optional[Callable[[], Any]] = None,
        live_view_poll_interval_s: float = 0.010,
        heartbeat_interval_s: float = 0.100,
        writer_join_timeout_s: float = 3.0,
        handler_shutdown_timeout_s: float = 5.0,
        require_explicit_deadline: bool = True,
        max_seen_requests: int = 512,
    ) -> None:
        if int(worker_generation) < 1:
            raise ValueError("worker_generation must be >= 1")
        if not worker_instance_id or not str(worker_instance_id).strip():
            raise ValueError("worker_instance_id must be a non-empty string")

        self._worker_generation: int = int(worker_generation)
        self._worker_instance_id: str = str(worker_instance_id).strip()
        self._shm: NikonSharedFrameBuffer = shm_buffer
        self._spooler = AtomicCaptureSpooler(spool_dir)
        self._transport: IPCTransport = transport
        self._session_factory = session_factory
        self._lv_poll_interval_s = max(0.001, float(live_view_poll_interval_s))
        self._heartbeat_interval_s = max(0.020, float(heartbeat_interval_s))
        self._writer_join_timeout_s = max(0.05, float(writer_join_timeout_s))
        self._handler_shutdown_timeout_s = max(0.05, float(handler_shutdown_timeout_s))
        self._require_explicit_deadline = bool(require_explicit_deadline)
        self._max_seen_requests = max(32, int(max_seen_requests))

        self._session: Optional[Any] = None
        self._session_lock = threading.RLock()
        self._state_lock = threading.RLock()

        # Monotonic frame sequence counter (starts at 1 on first write_frame)
        self._sequence_id: int = 0
        self._source_fps: float = 0.0
        self._battery_percent: int = -1

        # Request deduplication table
        self._seen_requests: Dict[str, _SeenRequestEntry] = {}
        # Seen capture tx_ids (never auto-retry or re-execute a capture tx_id)
        self._seen_capture_tx_ids: set[str] = set()

        # Thread control events & handles
        self._shutdown_event = threading.Event()
        self._lv_stop_event = threading.Event()
        self._lv_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._device_lost_notified = False
        self._closed = False
        self._shutdown_exit_code: int = EXIT_SERVER_OK

        # Audit S-6: Track active request handlers so watchdog/shutdown never closes resources mid-handler
        self._active_handlers_count: int = 0
        self._no_active_handlers_event = threading.Event()
        self._no_active_handlers_event.set()
        self._shutdown_serialize_lock = threading.Lock()

        # Bind this worker generation into SharedMemory GlobalControlHeader
        self._shm.bind_worker(
            worker_pid=os.getpid(),
            worker_generation=self._worker_generation,
            writer_state=WriterState.IDLE,
        )

    @property
    def worker_generation(self) -> int:
        return self._worker_generation

    @property
    def worker_instance_id(self) -> str:
        return self._worker_instance_id

    @property
    def sequence_id(self) -> int:
        with self._state_lock:
            return self._sequence_id

    @property
    def is_live_view_streaming(self) -> bool:
        t = self._lv_thread
        return t is not None and t.is_alive() and not self._lv_stop_event.is_set()

    @property
    def is_shutdown(self) -> bool:
        return self._shutdown_event.is_set()

    @property
    def shutdown_exit_code(self) -> int:
        with self._state_lock:
            return self._shutdown_exit_code

    def _set_shutdown_exit_code(self, code: int) -> None:
        with self._state_lock:
            if self._shutdown_exit_code == EXIT_SERVER_OK and code != EXIT_SERVER_OK:
                self._shutdown_exit_code = int(code)

    def _enter_handler(self) -> bool:
        """Mark a request handler as active if the server is not already shutting down (Audit S-6)."""
        with self._state_lock:
            if self._closed:
                return False
            self._active_handlers_count += 1
            self._no_active_handlers_event.clear()
            return True

    def _leave_handler(self) -> None:
        with self._state_lock:
            self._active_handlers_count = max(0, self._active_handlers_count - 1)
            if self._active_handlers_count == 0:
                self._no_active_handlers_event.set()

    def request_shutdown(self) -> None:
        """Signal the server to stop accepting new requests and stop Live View streaming."""
        self._shutdown_event.set()
        self._lv_stop_event.set()

    def _get_or_create_session(self) -> Any:
        """Lazily instantiate NikonSession only inside Worker after Startup Gate."""
        with self._session_lock:
            if self._session is None:
                if self._session_factory is not None:
                    self._session = self._session_factory()
                else:
                    from vietphotobooth.camera.backends.nikon_maid.maid_session import (
                        NikonSession,
                    )

                    self._session = NikonSession()
            return self._session

    # ------------------------------------------------------------------------
    # Outbound IPC Messaging
    # ------------------------------------------------------------------------

    def send_event(
        self,
        event: IPCEventName | str,
        *,
        tx_id: Optional[str] = None,
        request_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit an asynchronous IPCEvent to Main Process."""
        evt_req_id = (
            str(request_id).strip()
            if request_id and str(request_id).strip()
            else generate_request_id("evt")
        )
        evt_obj = IPCEvent(
            event=event.value if isinstance(event, IPCEventName) else str(event),
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            tx_id=tx_id,
            request_id=evt_req_id,
            data=dict(data) if data else {},
        )
        try:
            self._transport.send_message(evt_obj.to_dict())
            return True
        except (BrokenPipeError, EOFError, OSError) as exc:
            logger.warning("[WorkerServer] Broken pipe while sending event %s: %s", evt_obj.event, exc)
            self._shutdown_event.set()
            return False

    def _send_response(self, response: IPCResponse) -> bool:
        try:
            self._transport.send_message(response.to_dict())
            return True
        except (BrokenPipeError, EOFError, OSError) as exc:
            logger.warning(
                "[WorkerServer] Broken pipe while sending response for request_id=%s: %s",
                response.request_id,
                exc,
            )
            self._shutdown_event.set()
            return False

    # ------------------------------------------------------------------------
    # Background Threads: Heartbeat & Live View Producer
    # ------------------------------------------------------------------------

    def start_background_threads(self) -> None:
        """Start the periodic SharedMemory heartbeat updater thread."""
        with self._state_lock:
            if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
                return
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name=f"NikonWorkerHeartbeat-gen{self._worker_generation}",
                daemon=True,
            )
            self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._shutdown_event.wait(timeout=self._heartbeat_interval_s):
            try:
                if self._shm.is_closed or self._shutdown_event.is_set():
                    break
                self._shm.update_heartbeat(
                    worker_generation=self._worker_generation,
                    source_fps=self._source_fps,
                    battery_percent=self._battery_percent,
                )
                self._check_and_notify_device_lost()
            except Exception as exc:
                logger.debug("[WorkerServer] Heartbeat loop exception: %s", exc)
                break

    def _start_live_view_producer_thread(self) -> bool:
        """Stop any prior producer thread and start a fresh Live View producer thread.

        Returns False if a prior producer thread hung and failed to join (Audit M-2).
        """
        with self._state_lock:
            if not self._stop_live_view_producer_thread(join_timeout_s=self._writer_join_timeout_s):
                return False
            self._lv_stop_event.clear()
            self._lv_thread = threading.Thread(
                target=self._live_view_producer_loop,
                name=f"NikonWorkerLiveView-gen{self._worker_generation}",
                daemon=True,
            )
            self._lv_thread.start()
            return True

    def _stop_live_view_producer_thread(self, join_timeout_s: Optional[float] = None) -> bool:
        """Signal the Live View producer thread to stop, join it, and verify `not t.is_alive()` (Audit M-2).

        Returns True if the thread is stopped (or was not running), False if it is STILL ALIVE after join.
        If still alive: logs CRITICAL, transitions SharedMemory `writer_state` to `WriterState.STOPPING`,
        records `EXIT_WRITER_THREAD_JOIN_TIMEOUT`, and triggers Worker shutdown so it never continues
        operating on pointers while the hung writer thread exists.
        """
        timeout = self._writer_join_timeout_s if join_timeout_s is None else max(0.01, float(join_timeout_s))
        self._lv_stop_event.set()
        t = self._lv_thread
        if t is None:
            return True

        if t.is_alive() and t is not threading.current_thread():
            t.join(timeout=timeout)

        if t.is_alive():
            logger.critical(
                "[WorkerServer] CRITICAL (M-2): LiveViewProducerThread %r is still alive after %.2fs join timeout! "
                "Transitioning writer_state to STOPPING and refusing to close SharedMemory or continue MAID calls.",
                t.name,
                timeout,
            )
            try:
                if not self._shm.is_closed:
                    self._shm.update_heartbeat(
                        worker_generation=self._worker_generation,
                        writer_state=WriterState.STOPPING,
                    )
            except Exception:
                pass
            self._set_shutdown_exit_code(EXIT_WRITER_THREAD_JOIN_TIMEOUT)
            self._shutdown_event.set()
            return False

        self._lv_thread = None
        return True

    @staticmethod
    def _decode_jpeg_to_rgb(jpeg_bytes: bytes) -> Optional[np.ndarray]:
        """Decode Live View JPEG bytes into a contiguous (H, W, 3) RGB24 numpy array."""
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is not None and bgr.ndim == 3 and bgr.shape[2] == 3:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            return np.ascontiguousarray(rgb, dtype=np.uint8)

        try:
            with Image.open(io.BytesIO(jpeg_bytes)) as img:
                rgb_img = img.convert("RGB")
                return np.ascontiguousarray(np.asarray(rgb_img, dtype=np.uint8))
        except Exception:
            return None

    def _live_view_producer_loop(self) -> None:
        """Continuously fetch Live View frames from NikonSession and publish to SharedMemory."""
        fps_window_start = time.perf_counter()
        fps_frame_count = 0

        try:
            if not self._shm.is_closed and not self._shutdown_event.is_set():
                self._shm.update_heartbeat(
                    worker_generation=self._worker_generation,
                    writer_state=WriterState.STREAMING,
                )
        except Exception:
            return

        while not self._shutdown_event.is_set() and not self._lv_stop_event.is_set():
            session = self._session
            if session is None:
                break

            if getattr(session, "device_lost", False):
                self._check_and_notify_device_lost()
                break

            try:
                jpeg_bytes = session.fetch_live_view_frame()
            except Exception as exc:
                logger.error("[WorkerServer] Exception in fetch_live_view_frame: %s", exc)
                if getattr(session, "device_lost", False):
                    self._check_and_notify_device_lost()
                    break
                time.sleep(self._lv_poll_interval_s)
                continue

            if self._shutdown_event.is_set() or self._lv_stop_event.is_set():
                break

            if getattr(session, "device_lost", False):
                self._check_and_notify_device_lost()
                break

            if not jpeg_bytes:
                try:
                    if not self._shm.is_closed and not self._shutdown_event.is_set():
                        self._shm.update_heartbeat(worker_generation=self._worker_generation)
                except Exception:
                    break
                time.sleep(self._lv_poll_interval_s)
                continue

            rgb = self._decode_jpeg_to_rgb(jpeg_bytes)
            if rgb is None:
                time.sleep(self._lv_poll_interval_s)
                continue

            h, w, _ = rgb.shape
            fps_frame_count += 1
            now_mono = time.perf_counter()
            elapsed = now_mono - fps_window_start
            if elapsed >= 0.25:
                self._source_fps = fps_frame_count / elapsed
                fps_frame_count = 0
                fps_window_start = now_mono
            elif self._source_fps == 0.0 and elapsed > 0:
                self._source_fps = fps_frame_count / elapsed

            with self._state_lock:
                if self._shutdown_event.is_set() or self._lv_stop_event.is_set() or self._shm.is_closed:
                    break
                self._sequence_id += 1
                seq_id = self._sequence_id

            try:
                self._shm.write_frame(
                    rgb=rgb,
                    jpeg_bytes=jpeg_bytes,
                    sequence_id=seq_id,
                    worker_generation=self._worker_generation,
                    capture_ts=time.time(),
                    mono_ts=now_mono,
                    width=w,
                    height=h,
                    source_fps=self._source_fps,
                    battery_percent=self._battery_percent,
                )
            except Exception as exc:
                logger.error("[WorkerServer] Failed writing frame seq=%d to SHM: %s", seq_id, exc)
                break

            time.sleep(self._lv_poll_interval_s)

        # Update writer_state when leaving Live View producer loop (only if not shutting down / closed)
        try:
            if not self._shm.is_closed and not self._shutdown_event.is_set():
                session = self._session
                new_state = (
                    WriterState.DISCONNECTED
                    if (session is not None and getattr(session, "device_lost", False))
                    else WriterState.IDLE
                )
                self._shm.update_heartbeat(
                    worker_generation=self._worker_generation,
                    writer_state=new_state,
                )
        except Exception:
            pass

    def _check_and_notify_device_lost(self, tx_id: Optional[str] = None, request_id: Optional[str] = None) -> bool:
        """If NikonSession tripped its device_lost circuit breaker, update SHM and emit DISCONNECTED once."""
        session = self._session
        if session is None or not getattr(session, "device_lost", False):
            return False

        with self._state_lock:
            already_notified = self._device_lost_notified
            self._device_lost_notified = True

        self._lv_stop_event.set()
        try:
            if not self._shm.is_closed:
                self._shm.update_heartbeat(
                    worker_generation=self._worker_generation,
                    writer_state=WriterState.DISCONNECTED,
                )
        except Exception:
            pass

        if not already_notified:
            reason = getattr(session, "device_lost_reason", "") or "Nikon device lost"
            self.send_event(
                IPCEventName.DEVICE_ERROR,
                tx_id=tx_id,
                request_id=request_id,
                data={
                    "error_code": IPCErrorCode.NIKON_DISCONNECTED.value,
                    "error_message": reason,
                    "device_lost": True,
                },
            )
            self.send_event(
                IPCEventName.DISCONNECTED,
                tx_id=tx_id,
                request_id=request_id,
                data={
                    "reason": reason,
                    "device_lost": True,
                },
            )
        return True

    # ------------------------------------------------------------------------
    # Request Validation & Deduplication
    # ------------------------------------------------------------------------

    def _prune_seen_requests(self) -> None:
        if len(self._seen_requests) <= self._max_seen_requests:
            return
        completed_ids = [
            rid for rid, entry in self._seen_requests.items() if entry.state == "COMPLETED"
        ]
        excess = len(self._seen_requests) - self._max_seen_requests
        for old_id in completed_ids[:excess]:
            self._seen_requests.pop(old_id, None)

    def handle_raw_message(self, raw: Mapping[str, Any] | str | bytes) -> Optional[IPCResponse]:
        """Parse, validate, and execute one incoming IPC message, sending the IPCResponse."""
        try:
            parsed = parse_wire_message(raw)
        except IPCProtocolError as exc:
            req_id = "unknown"
            gen = self._worker_generation
            inst = self._worker_instance_id
            if isinstance(raw, Mapping):
                req_id = str(raw.get("request_id") or "unknown")
            resp = IPCResponse(
                worker_generation=gen,
                worker_instance_id=inst,
                request_id=req_id,
                ok=False,
                error_code=exc.error_code.value,
                error_message=str(exc),
            )
            self._send_response(resp)
            return resp

        if not isinstance(parsed, IPCRequest):
            resp = IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=getattr(parsed, "request_id", None) or "unknown",
                ok=False,
                error_code=IPCErrorCode.INVALID_SCHEMA.value,
                error_message=f"Worker expected IPCRequest, got {type(parsed).__name__}",
            )
            self._send_response(resp)
            return resp

        resp = self.dispatch_request(parsed)
        self._send_response(resp)
        return resp

    def dispatch_request(self, req: IPCRequest, now_mono: Optional[float] = None) -> IPCResponse:
        """Validate and execute an `IPCRequest`, returning an `IPCResponse`."""
        now = time.perf_counter() if now_mono is None else float(now_mono)

        # 1. Verify worker_generation
        if int(req.worker_generation) != self._worker_generation:
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=req.tx_id,
                ok=False,
                error_code=IPCErrorCode.STALE_WORKER_GENERATION.value,
                error_message=(
                    f"Request worker_generation={req.worker_generation} != "
                    f"worker_generation={self._worker_generation}"
                ),
            )

        # 2. Verify worker_instance_id
        if str(req.worker_instance_id) != self._worker_instance_id:
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=req.tx_id,
                ok=False,
                error_code=IPCErrorCode.WORKER_INSTANCE_MISMATCH.value,
                error_message=(
                    f"Request worker_instance_id={req.worker_instance_id!r} != "
                    f"worker_instance_id={self._worker_instance_id!r}"
                ),
            )

        # 3. Audit I-7: Strict allowlist validation on request_id and tx_id (`^[A-Za-z0-9_-]{1,128}$`)
        try:
            validate_safe_identifier(req.request_id, "request_id")
            if req.tx_id is not None:
                validate_safe_identifier(req.tx_id, "tx_id")
        except ValueError as exc:
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=req.tx_id,
                ok=False,
                error_code=IPCErrorCode.INVALID_SCHEMA.value,
                error_message=str(exc),
            )

        # 4. Check request_id deduplication & Audit I-3 deadline enforcement
        with self._state_lock:
            existing = self._seen_requests.get(req.request_id)
            if existing is not None:
                return IPCResponse(
                    worker_generation=self._worker_generation,
                    worker_instance_id=self._worker_instance_id,
                    request_id=req.request_id,
                    tx_id=req.tx_id,
                    ok=False,
                    error_code=IPCErrorCode.INVALID_SCHEMA.value,
                    error_message=f"Duplicate request_id={req.request_id!r} rejected",
                )

            # Audit I-3: Properly extract deadline_mono / sent_at_mono / created_at_mono without falsy `or` bugs
            deadline_param = req.params.get("deadline_mono") if "deadline_mono" in req.params else None
            if "sent_at_mono" in req.params and req.params["sent_at_mono"] is not None:
                sent_param = req.params["sent_at_mono"]
            elif "created_at_mono" in req.params and req.params["created_at_mono"] is not None:
                sent_param = req.params["created_at_mono"]
            else:
                sent_param = None

            if (
                self._require_explicit_deadline
                and req.method not in _DEADLINE_EXEMPT_METHODS
                and deadline_param is None
                and sent_param is None
            ):
                return IPCResponse(
                    worker_generation=self._worker_generation,
                    worker_instance_id=self._worker_instance_id,
                    request_id=req.request_id,
                    tx_id=req.tx_id,
                    ok=False,
                    error_code=IPCErrorCode.INVALID_SCHEMA.value,
                    error_message=(
                        f"Request {req.request_id!r} (method={req.method!r}) requires "
                        f"'deadline_mono' or 'sent_at_mono' in params"
                    ),
                )

            effective_deadline = now + float(req.timeout_s)
            if deadline_param is not None:
                try:
                    dl_val = float(deadline_param)
                except (TypeError, ValueError):
                    return IPCResponse(
                        worker_generation=self._worker_generation,
                        worker_instance_id=self._worker_instance_id,
                        request_id=req.request_id,
                        tx_id=req.tx_id,
                        ok=False,
                        error_code=IPCErrorCode.INVALID_SCHEMA.value,
                        error_message=f"Invalid deadline_mono value: {deadline_param!r}",
                    )
                if now > dl_val:
                    return IPCResponse(
                        worker_generation=self._worker_generation,
                        worker_instance_id=self._worker_instance_id,
                        request_id=req.request_id,
                        tx_id=req.tx_id,
                        ok=False,
                        error_code=IPCErrorCode.REQUEST_TIMED_OUT.value,
                        error_message=(
                            f"Request {req.request_id!r} expired before execution "
                            f"(now={now:.3f} > deadline={dl_val:.3f})"
                        ),
                    )
                effective_deadline = min(effective_deadline, dl_val)

            if sent_param is not None:
                try:
                    sent_val = float(sent_param)
                except (TypeError, ValueError):
                    return IPCResponse(
                        worker_generation=self._worker_generation,
                        worker_instance_id=self._worker_instance_id,
                        request_id=req.request_id,
                        tx_id=req.tx_id,
                        ok=False,
                        error_code=IPCErrorCode.INVALID_SCHEMA.value,
                        error_message=f"Invalid sent_at_mono value: {sent_param!r}",
                    )
                if (now - sent_val) > float(req.timeout_s):
                    return IPCResponse(
                        worker_generation=self._worker_generation,
                        worker_instance_id=self._worker_instance_id,
                        request_id=req.request_id,
                        tx_id=req.tx_id,
                        ok=False,
                        error_code=IPCErrorCode.REQUEST_TIMED_OUT.value,
                        error_message=(
                            f"Request {req.request_id!r} exceeded timeout_s={req.timeout_s:.3f}s "
                            f"before execution (now={now:.3f}, sent_at={sent_val:.3f})"
                        ),
                    )
                effective_deadline = min(effective_deadline, sent_val + float(req.timeout_s))

            entry = _SeenRequestEntry(
                request_id=req.request_id,
                method=req.method,
                received_at_mono=now,
                state="IN_FLIGHT",
            )
            self._seen_requests[req.request_id] = entry
            self._prune_seen_requests()

        # 5. Track active handler (Audit S-6) and execute command handler
        if not self._enter_handler():
            resp = IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=req.tx_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_WORKER_HANG_TIMEOUT.value,
                error_message="Worker is shutting down",
            )
            with self._state_lock:
                entry.state = "COMPLETED"
                entry.response = resp
            return resp

        try:
            resp = self._execute_method(req, deadline_mono=effective_deadline)
        except Exception as exc:
            logger.exception("[WorkerServer] Unhandled error executing %s: %s", req.method, exc)
            resp = IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=req.tx_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_UNKNOWN_ERROR.value,
                error_message=str(exc),
            )
        finally:
            self._leave_handler()

        with self._state_lock:
            entry.state = "COMPLETED"
            entry.response = resp

        return resp

    # ------------------------------------------------------------------------
    # Command Handlers
    # ------------------------------------------------------------------------

    def _execute_method(self, req: IPCRequest, deadline_mono: float) -> IPCResponse:
        method = req.method

        if method == IPCCommandMethod.PING.value:
            return self._handle_ping(req)
        if method == IPCCommandMethod.DISCOVER.value:
            return self._handle_discover(req)
        if method == IPCCommandMethod.CONNECT.value:
            return self._handle_connect(req)
        if method == IPCCommandMethod.START_LIVE_VIEW.value:
            return self._handle_start_live_view(req, deadline_mono=deadline_mono)
        if method == IPCCommandMethod.STOP_LIVE_VIEW.value:
            return self._handle_stop_live_view(req)
        if method == IPCCommandMethod.CAPTURE.value:
            return self._handle_capture(req, deadline_mono=deadline_mono)
        if method == IPCCommandMethod.SHUTDOWN.value:
            return self._handle_shutdown(req)
        if method == IPCCommandMethod.DISCONNECT.value:
            return self._handle_disconnect(req)
        if method == IPCCommandMethod.GET_STATUS.value:
            return self._handle_get_status(req)
        if method == IPCCommandMethod.AUTOFOCUS.value:
            return self._handle_autofocus(req, deadline_mono=deadline_mono)
        if method == IPCCommandMethod.SET_AF_POINT.value:
            return self._handle_set_af_point(req)

        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            tx_id=req.tx_id,
            ok=False,
            error_code=IPCErrorCode.INVALID_SCHEMA.value,
            error_message=f"Unsupported IPC method: {method!r}",
        )

    def _handle_ping(self, req: IPCRequest) -> IPCResponse:
        if not self._shm.is_closed:
            self._shm.update_heartbeat(worker_generation=self._worker_generation)
        session = self._session
        device_lost = bool(session is not None and getattr(session, "device_lost", False))
        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=True,
            result={
                "pong": True,
                "worker_pid": os.getpid(),
                "worker_generation": self._worker_generation,
                "worker_instance_id": self._worker_instance_id,
                "live_view_streaming": self.is_live_view_streaming,
                "sequence_id": self._sequence_id,
                "device_lost": device_lost,
            },
        )

    def _handle_discover(self, req: IPCRequest) -> IPCResponse:
        session = self._get_or_create_session()
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(request_id=req.request_id)
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", "Device lost"),
            )

        timeout_s = max(0.2, min(float(req.timeout_s), 5.0))
        sources = session.enumerate_cameras(timeout_sec=timeout_s)
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(request_id=req.request_id)
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", "Device lost during discover"),
            )

        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=True,
            result={
                "sources": [int(s) for s in sources],
                "count": len(sources),
            },
        )

    def _handle_connect(self, req: IPCRequest) -> IPCResponse:
        session = self._get_or_create_session()
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(request_id=req.request_id)
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", "Device lost"),
            )

        src_id = req.params.get("source_id")
        src_id_int = int(src_id) if src_id is not None else None
        ok, msg = session.open_camera(src_id=src_id_int)
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(request_id=req.request_id)
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", msg),
            )

        if not ok:
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_MAID_SESSION_CORRUPTED.value,
                error_message=msg,
            )

        battery = session.get_battery_level() if hasattr(session, "get_battery_level") else None
        if battery is not None:
            self._battery_percent = int(battery)

        if not self._shm.is_closed:
            self._shm.update_heartbeat(
                worker_generation=self._worker_generation,
                writer_state=WriterState.IDLE,
                battery_percent=self._battery_percent,
            )

        self.send_event(
            IPCEventName.CONNECTED,
            request_id=req.request_id,
            data={
                "message": msg,
                "battery_percent": self._battery_percent,
            },
        )
        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=True,
            result={
                "connected": True,
                "message": msg,
                "battery_percent": self._battery_percent,
            },
        )

    def _handle_start_live_view(self, req: IPCRequest, deadline_mono: float) -> IPCResponse:
        session = self._get_or_create_session()
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(request_id=req.request_id)
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", "Device lost"),
            )

        remaining_s = max(0.1, deadline_mono - time.perf_counter())
        lv_timeout_s = min(float(req.params.get("timeout_sec", remaining_s)), remaining_s)

        # NikonSession.start_live_view() strictly verifies CAN_ACQUIRE before returning True
        lv_ok = session.start_live_view(timeout_sec=lv_timeout_s)
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(request_id=req.request_id)
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", "Device lost during start_live_view"),
            )

        if not lv_ok:
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_LV_CANNOT_ACQUIRE.value,
                error_message="Live View failed to reach CAN_ACQUIRE state",
            )

        if not self._start_live_view_producer_thread():
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_WORKER_HANG_TIMEOUT.value,
                error_message="Previous Live View producer thread hung and failed to join",
            )

        self.send_event(
            IPCEventName.LIVE_VIEW_STARTED,
            request_id=req.request_id,
            data={"shm_name": self._shm.name},
        )
        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=True,
            result={
                "live_view_active": True,
                "shm_name": self._shm.name,
            },
        )

    def _handle_stop_live_view(self, req: IPCRequest) -> IPCResponse:
        # Stop and join the producer thread FIRST so no concurrent fetch/write happens (Audit M-2)
        if not self._stop_live_view_producer_thread(join_timeout_s=self._writer_join_timeout_s):
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_WORKER_HANG_TIMEOUT.value,
                error_message="Live View producer thread failed to join within timeout; Worker shutting down",
            )

        session = self._session
        if session is not None and not getattr(session, "device_lost", False):
            try:
                session.stop_live_view()
            except Exception as exc:
                logger.warning("[WorkerServer] Error in session.stop_live_view(): %s", exc)

        if not self._shm.is_closed:
            self._shm.update_heartbeat(
                worker_generation=self._worker_generation,
                writer_state=WriterState.IDLE,
            )

        self.send_event(
            IPCEventName.LIVE_VIEW_STOPPED,
            request_id=req.request_id,
            data={"sequence_id": self._sequence_id},
        )
        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=True,
            result={
                "live_view_active": False,
                "sequence_id": self._sequence_id,
            },
        )

    def _handle_capture(self, req: IPCRequest, deadline_mono: float) -> IPCResponse:
        """Execute a single still capture transaction (NEVER auto-retried by Worker)."""
        tx_id = req.tx_id
        if not tx_id or not str(tx_id).strip():
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=tx_id,
                ok=False,
                error_code=IPCErrorCode.INVALID_SCHEMA.value,
                error_message="CAPTURE command requires a non-empty tx_id",
            )

        try:
            tx_id = validate_safe_identifier(tx_id, "tx_id")
        except ValueError as exc:
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=tx_id,
                ok=False,
                error_code=IPCErrorCode.INVALID_SCHEMA.value,
                error_message=str(exc),
            )

        with self._state_lock:
            if tx_id in self._seen_capture_tx_ids:
                return IPCResponse(
                    worker_generation=self._worker_generation,
                    worker_instance_id=self._worker_instance_id,
                    request_id=req.request_id,
                    tx_id=tx_id,
                    ok=False,
                    error_code=IPCErrorCode.TRANSACTION_MISMATCH.value,
                    error_message=f"Capture transaction tx_id={tx_id!r} was already executed; Worker never retries capture",
                )
            self._seen_capture_tx_ids.add(tx_id)

        session = self._get_or_create_session()
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(tx_id=tx_id, request_id=req.request_id)
            self.send_event(
                IPCEventName.CAPTURE_FAILED,
                tx_id=tx_id,
                request_id=req.request_id,
                data={
                    "error_code": IPCErrorCode.NIKON_DISCONNECTED.value,
                    "error_message": getattr(session, "device_lost_reason", "Device lost before capture"),
                },
            )
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=tx_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", "Device lost before capture"),
            )

        # Audit M-2: Pause Live View producer thread cleanly BEFORE still capture and verify it joined!
        was_streaming = self.is_live_view_streaming or (
            self._lv_thread is not None and self._lv_thread.is_alive()
        )
        if was_streaming:
            if not self._stop_live_view_producer_thread(join_timeout_s=self._writer_join_timeout_s):
                err_msg = (
                    "LiveViewProducerThread hung and failed to join before CAPTURE; "
                    "refusing to execute MAID capture while writer thread is still alive"
                )
                self.send_event(
                    IPCEventName.CAPTURE_FAILED,
                    tx_id=tx_id,
                    request_id=req.request_id,
                    data={
                        "error_code": IPCErrorCode.NIKON_WORKER_HANG_TIMEOUT.value,
                        "error_message": err_msg,
                    },
                )
                return IPCResponse(
                    worker_generation=self._worker_generation,
                    worker_instance_id=self._worker_instance_id,
                    request_id=req.request_id,
                    tx_id=tx_id,
                    ok=False,
                    error_code=IPCErrorCode.NIKON_WORKER_HANG_TIMEOUT.value,
                    error_message=err_msg,
                )

        if not self._shm.is_closed:
            self._shm.update_heartbeat(
                worker_generation=self._worker_generation,
                writer_state=WriterState.CAPTURING,
            )

        remaining_s = max(0.2, deadline_mono - time.perf_counter())
        cap_timeout_s = min(float(req.params.get("timeout_sec", remaining_s)), remaining_s)
        autofocus_first = bool(req.params.get("autofocus_first", False))

        capture_started_sent = False

        def _on_shutter_started() -> None:
            nonlocal capture_started_sent
            if not capture_started_sent:
                capture_started_sent = True
                self.send_event(
                    IPCEventName.CAPTURE_STARTED,
                    tx_id=tx_id,
                    request_id=req.request_id,
                    data={"tx_id": tx_id},
                )

        # Execute capture_photo ONCE (strictly no auto-retry on failure/timeout)
        raw_jpeg: Optional[bytes] = None
        capture_exc: Optional[Exception] = None
        try:
            raw_jpeg = session.capture_photo(
                timeout_sec=cap_timeout_s,
                autofocus_first=autofocus_first,
                on_capture_start=_on_shutter_started,
            )
        except Exception as exc:
            capture_exc = exc

        device_lost_after = bool(getattr(session, "device_lost", False))
        transfer_state = getattr(session, "last_capture_transfer_state", "NONE")

        if raw_jpeg is None:
            if device_lost_after:
                self._check_and_notify_device_lost(tx_id=tx_id, request_id=req.request_id)
                err_code = IPCErrorCode.NIKON_DISCONNECTED
                err_msg = (
                    getattr(session, "device_lost_reason", "")
                    or f"USB disconnected during capture (transfer_state={transfer_state})"
                )
            elif capture_exc is not None:
                err_code = IPCErrorCode.NIKON_UNKNOWN_ERROR
                err_msg = f"Exception during capture_photo: {capture_exc}"
            else:
                err_code = IPCErrorCode.NIKON_CAPTURE_SDRAM_TIMEOUT
                err_msg = f"Capture failed or timed out after {cap_timeout_s:.2f}s (transfer_state={transfer_state})"

            if (
                was_streaming
                and not self._shutdown_event.is_set()
                and not device_lost_after
                and getattr(session, "_is_live_view_active", False)
            ):
                self._start_live_view_producer_thread()
            elif not self._shm.is_closed and not self._shutdown_event.is_set():
                self._shm.update_heartbeat(
                    worker_generation=self._worker_generation,
                    writer_state=WriterState.DISCONNECTED if device_lost_after else WriterState.IDLE,
                )

            self.send_event(
                IPCEventName.CAPTURE_FAILED,
                tx_id=tx_id,
                request_id=req.request_id,
                data={
                    "error_code": err_code.value,
                    "error_message": err_msg,
                    "transfer_state": transfer_state,
                },
            )
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=tx_id,
                ok=False,
                error_code=err_code.value,
                error_message=err_msg,
            )

        # Ensure CAPTURE_STARTED was emitted before CAPTURE_COMPLETED
        if not capture_started_sent:
            _on_shutter_started()

        # Atomically spool raw_{tx_id}.jpg and raw_{tx_id}.meta.json to disk BEFORE emitting completion!
        try:
            artifact = self._spooler.spool_capture(
                tx_id=tx_id,
                request_id=req.request_id,
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                raw_jpeg=raw_jpeg,
            )
        except Exception as exc:
            err_msg = f"Atomic spooling failed for tx_id={tx_id!r}: {exc}"
            logger.error("[WorkerServer] %s", err_msg)
            if (
                was_streaming
                and not self._shutdown_event.is_set()
                and not device_lost_after
                and getattr(session, "_is_live_view_active", False)
            ):
                self._start_live_view_producer_thread()
            self.send_event(
                IPCEventName.CAPTURE_FAILED,
                tx_id=tx_id,
                request_id=req.request_id,
                data={
                    "error_code": IPCErrorCode.NIKON_UNKNOWN_ERROR.value,
                    "error_message": err_msg,
                },
            )
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                tx_id=tx_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_UNKNOWN_ERROR.value,
                error_message=err_msg,
            )

        if device_lost_after:
            self._check_and_notify_device_lost(tx_id=tx_id, request_id=req.request_id)
        elif (
            was_streaming
            and not self._shutdown_event.is_set()
            and getattr(session, "_is_live_view_active", False)
        ):
            self._start_live_view_producer_thread()
        elif not self._shm.is_closed and not self._shutdown_event.is_set():
            self._shm.update_heartbeat(
                worker_generation=self._worker_generation,
                writer_state=WriterState.IDLE,
            )

        result_payload = artifact.to_dict()
        self.send_event(
            IPCEventName.CAPTURE_COMPLETED,
            tx_id=tx_id,
            request_id=req.request_id,
            data=result_payload,
        )
        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            tx_id=tx_id,
            ok=True,
            result=result_payload,
        )

    def _handle_autofocus(self, req: IPCRequest, deadline_mono: float) -> IPCResponse:
        session = self._get_or_create_session()
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(request_id=req.request_id)
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", "Device lost"),
            )

        remaining_s = max(0.2, deadline_mono - time.perf_counter())
        af_timeout_s = min(float(req.params.get("timeout_sec", remaining_s)), remaining_s)
        tp = req.params.get("target_point")
        fs = req.params.get("frame_size")
        target_pt = (float(tp[0]), float(tp[1])) if isinstance(tp, (list, tuple)) and len(tp) == 2 else None
        frame_sz = (float(fs[0]), float(fs[1])) if isinstance(fs, (list, tuple)) and len(fs) == 2 else None

        ok, msg = session.trigger_autofocus(
            target_point=target_pt,
            frame_size=frame_sz,
            timeout_sec=af_timeout_s,
        )
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(request_id=req.request_id)
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", msg),
            )

        if not ok:
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_OUT_OF_FOCUS.value,
                error_message=msg,
            )

        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=True,
            result={"focused": True, "message": msg},
        )

    def _handle_set_af_point(self, req: IPCRequest) -> IPCResponse:
        session = self._get_or_create_session()
        if getattr(session, "device_lost", False):
            self._check_and_notify_device_lost(request_id=req.request_id)
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_DISCONNECTED.value,
                error_message=getattr(session, "device_lost_reason", "Device lost"),
            )

        x = float(req.params.get("x", 0.5))
        y = float(req.params.get("y", 0.5))
        sw = req.params.get("src_width")
        sh = req.params.get("src_height")
        ok = session.set_contrast_af_area(
            x=x,
            y=y,
            src_width=float(sw) if sw is not None else None,
            src_height=float(sh) if sh is not None else None,
        )
        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=bool(ok),
            error_code=IPCErrorCode.OK.value if ok else IPCErrorCode.NIKON_DEVICE_BUSY.value,
            error_message=None if ok else "Failed to set Contrast AF area",
            result={"set": bool(ok)} if ok else None,
        )

    def _handle_get_status(self, req: IPCRequest) -> IPCResponse:
        session = self._session
        device_lost = bool(session is not None and getattr(session, "device_lost", False))
        if session is not None and not device_lost and hasattr(session, "get_battery_level"):
            bat = session.get_battery_level()
            if bat is not None:
                self._battery_percent = int(bat)

        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=True,
            result={
                "worker_pid": os.getpid(),
                "worker_generation": self._worker_generation,
                "worker_instance_id": self._worker_instance_id,
                "live_view_streaming": self.is_live_view_streaming,
                "sequence_id": self._sequence_id,
                "source_fps": self._source_fps,
                "battery_percent": self._battery_percent,
                "device_lost": device_lost,
                "device_lost_reason": getattr(session, "device_lost_reason", "") if session else "",
            },
        )

    def _handle_disconnect(self, req: IPCRequest) -> IPCResponse:
        if not self._stop_live_view_producer_thread(join_timeout_s=self._writer_join_timeout_s):
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_WORKER_HANG_TIMEOUT.value,
                error_message="Live View producer thread hung during disconnect",
            )
        session = self._session
        if session is not None:
            try:
                session.close_module()
            except Exception as exc:
                logger.warning("[WorkerServer] Error closing session on disconnect: %s", exc)
        if not self._shm.is_closed:
            self._shm.update_heartbeat(
                worker_generation=self._worker_generation,
                writer_state=WriterState.IDLE,
            )
        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=True,
            result={"disconnected": True},
        )

    def _handle_shutdown(self, req: IPCRequest) -> IPCResponse:
        # Stop Live View producer thread FIRST before acknowledging shutdown (Audit M-2)
        lv_stopped = self._stop_live_view_producer_thread(join_timeout_s=self._writer_join_timeout_s)
        self._shutdown_event.set()
        if not lv_stopped:
            return IPCResponse(
                worker_generation=self._worker_generation,
                worker_instance_id=self._worker_instance_id,
                request_id=req.request_id,
                ok=False,
                error_code=IPCErrorCode.NIKON_WORKER_HANG_TIMEOUT.value,
                error_message="Live View producer thread failed to join on SHUTDOWN",
            )
        return IPCResponse(
            worker_generation=self._worker_generation,
            worker_instance_id=self._worker_instance_id,
            request_id=req.request_id,
            ok=True,
            result={
                "shutting_down": True,
                "worker_pid": os.getpid(),
                "sequence_id": self._sequence_id,
            },
        )

    # ------------------------------------------------------------------------
    # Main Loop & Deterministic Staged Shutdown Ordering (Audit M-2 & S-6)
    # ------------------------------------------------------------------------

    def serve_forever(self, emit_ready_event: bool = True) -> int:
        """Run the main IPC command loop until `SHUTDOWN` or Pipe EOF, then clean up safely.

        Returns the server exit code (`EXIT_SERVER_OK = 0`, `EXIT_WRITER_THREAD_JOIN_TIMEOUT = 76`,
        or `EXIT_HANDLER_HUNG_ON_SHUTDOWN = 77`).
        """
        self.start_background_threads()
        if emit_ready_event:
            self.send_event(
                IPCEventName.WORKER_READY,
                data={
                    "worker_pid": os.getpid(),
                    "shm_name": self._shm.name,
                    "spool_dir": self._spooler.spool_dir,
                },
            )

        try:
            while not self._shutdown_event.is_set():
                raw = self._transport.recv_message()
                if raw is None:
                    # Pipe EOF / BrokenPipeError -> trigger graceful shutdown
                    logger.info("[WorkerServer] IPC Pipe EOF detected; initiating graceful shutdown.")
                    self._shutdown_event.set()
                    break
                if self._shutdown_event.is_set():
                    break
                self.handle_raw_message(raw)
        finally:
            self.shutdown_and_close()

        return self.shutdown_exit_code

    def shutdown_and_close(
        self,
        *,
        writer_join_timeout_s: Optional[float] = None,
        handler_wait_timeout_s: Optional[float] = None,
    ) -> int:
        """Staged, race-free Worker shutdown (Audit M-2 & S-6).

        Strict sequence:
        1. Stop accepting new requests (`_shutdown_event.set()`, `_lv_stop_event.set()`).
        2. Wait for any in-flight request handler (`_no_active_handlers_event`) to finish.
           If an active handler is hung after `handler_wait_timeout_s`:
           - Log CRITICAL.
           - Transition `writer_state = WriterState.STOPPING`.
           - Do NOT close `NikonSession`, SharedMemory, or transport while the handler thread is using them.
           - Return `EXIT_HANDLER_HUNG_ON_SHUTDOWN = 77`.
        3. Stop and join `LiveViewProducerThread` and `HeartbeatThread`, checking `thread.is_alive()`
           after `join()`. If any writer thread is still alive:
           - Log CRITICAL.
           - Transition `writer_state = WriterState.STOPPING`.
           - Do NOT call `session.close_module()` and do NOT call `shm.close()`.
           - Return `EXIT_WRITER_THREAD_JOIN_TIMEOUT = 76`.
        4. Close `NikonSession` safely (skips MAID calls if `device_lost == True`).
        5. Transition `writer_state = WriterState.STOPPING` and call `shm.close()` (NEVER `shm.unlink()`).
        6. Close IPC transport.
        """
        with self._shutdown_serialize_lock:
            with self._state_lock:
                if self._closed:
                    return self._shutdown_exit_code

            w_timeout = (
                self._writer_join_timeout_s
                if writer_join_timeout_s is None
                else max(0.01, float(writer_join_timeout_s))
            )
            h_timeout = (
                self._handler_shutdown_timeout_s
                if handler_wait_timeout_s is None
                else max(0.01, float(handler_wait_timeout_s))
            )

            # Stage 1: Stop accepting requests and signal background threads to stop
            self._shutdown_event.set()
            self._lv_stop_event.set()

            # Stage 2 (Audit S-6): Wait for any in-flight request handler to complete before freeing resources
            handlers_done = self._no_active_handlers_event.wait(timeout=h_timeout)
            if not handlers_done:
                logger.critical(
                    "[WorkerServer] CRITICAL (S-6): In-flight request handler is still running after %.2fs "
                    "shutdown wait! Refusing to close NikonSession, SharedMemory, or transport under active thread.",
                    h_timeout,
                )
                try:
                    if not self._shm.is_closed:
                        self._shm.update_heartbeat(
                            worker_generation=self._worker_generation,
                            writer_state=WriterState.STOPPING,
                        )
                except Exception:
                    pass
                self._set_shutdown_exit_code(EXIT_HANDLER_HUNG_ON_SHUTDOWN)
                with self._state_lock:
                    self._closed = True
                return self.shutdown_exit_code

            # Stage 3 (Audit M-2): Join Live View producer thread and Heartbeat thread, verifying not is_alive()
            lv_thread = self._lv_thread
            if lv_thread is not None and lv_thread.is_alive() and lv_thread is not threading.current_thread():
                lv_thread.join(timeout=w_timeout)

            hb_thread = self._heartbeat_thread
            if hb_thread is not None and hb_thread.is_alive() and hb_thread is not threading.current_thread():
                hb_thread.join(timeout=min(2.0, w_timeout))

            lv_still_alive = bool(
                lv_thread is not None and lv_thread.is_alive() and lv_thread is not threading.current_thread()
            )
            hb_still_alive = bool(
                hb_thread is not None and hb_thread.is_alive() and hb_thread is not threading.current_thread()
            )

            if lv_still_alive or hb_still_alive:
                logger.critical(
                    "[WorkerServer] CRITICAL (M-2): Writer/Heartbeat thread still alive after join "
                    "(lv_alive=%s, hb_alive=%s)! Setting writer_state=STOPPING and refusing to call "
                    "close_module() or shm.close().",
                    lv_still_alive,
                    hb_still_alive,
                )
                try:
                    if not self._shm.is_closed:
                        self._shm.update_heartbeat(
                            worker_generation=self._worker_generation,
                            writer_state=WriterState.STOPPING,
                        )
                except Exception:
                    pass
                self._set_shutdown_exit_code(EXIT_WRITER_THREAD_JOIN_TIMEOUT)
                with self._state_lock:
                    self._closed = True
                try:
                    self._transport.close()
                except Exception:
                    pass
                return self.shutdown_exit_code

            self._lv_thread = None
            self._heartbeat_thread = None

            with self._state_lock:
                self._closed = True

            # Stage 4: Close NikonSession safely (NikonSession skips MAID calls if device_lost == True)
            with self._session_lock:
                session = self._session
                self._session = None
                if session is not None:
                    try:
                        session.close_module()
                    except Exception as exc:
                        logger.warning("[WorkerServer] Error closing NikonSession during shutdown: %s", exc)

            # Stage 5: Update writer_state to STOPPING and close Worker's SharedMemory view (NEVER unlink!)
            try:
                if not self._shm.is_closed:
                    self._shm.update_heartbeat(
                        worker_generation=self._worker_generation,
                        writer_state=WriterState.STOPPING,
                    )
                    self._shm.close()
            except Exception as exc:
                logger.debug("[WorkerServer] Exception closing SharedMemory view: %s", exc)

            # Stage 6: Close IPC transport
            try:
                self._transport.close()
            except Exception:
                pass

            return self.shutdown_exit_code
