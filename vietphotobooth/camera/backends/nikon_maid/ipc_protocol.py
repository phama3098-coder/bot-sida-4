"""IPC Protocol v1, Transaction State Machine, and Late-Event Rejection for Nikon Isolated Driver.

Defines the message envelopes, schema validation, error mapping, request/response
correlation, and transaction lifecycle (`CaptureTransaction`) between the Photobooth
Main Process (`NikonIPCClient`) and the isolated `NikonDriverWorkerServer` subprocess.

Key Invariants:
1. Every message carries `protocol_version`, `worker_generation`, `worker_instance_id`,
   `request_id`, and `tx_id`.
2. Responses and asynchronous events from stale `worker_generation`, mismatched
   `worker_instance_id`, unknown `request_id`, or cancelled/timed-out `tx_id` are
   deterministically rejected with structured rejection reasons.
3. Zero Nikon MAID / ctypes DLL dependencies in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import itertools
import math
import os
import time
from typing import Any, Dict, Mapping, Optional, Tuple
import uuid


# ============================================================================
# Protocol Constants & Enumerations
# ============================================================================

PROTOCOL_VERSION: int = 1


class IPCMessageType(str, Enum):
    """Top-level IPC envelope message types."""

    COMMAND = "cmd"
    RESPONSE = "resp"
    EVENT = "evt"


class IPCCommandMethod(str, Enum):
    """Supported RPC command methods sent from Main Process to Worker Process."""

    PING = "ping"
    DISCOVER = "discover"
    CONNECT = "connect"
    START_LIVE_VIEW = "start_live_view"
    STOP_LIVE_VIEW = "stop_live_view"
    GET_LATEST_FRAME = "get_latest_frame"
    AUTOFOCUS = "autofocus"
    SET_AF_POINT = "set_af_point"
    CAPTURE = "capture"
    CANCEL_CAPTURE = "cancel_capture"
    GET_STATUS = "get_status"
    DISCONNECT = "disconnect"
    SHUTDOWN = "shutdown"


class IPCEventName(str, Enum):
    """Supported asynchronous events emitted from Worker Process to Main Process."""

    WORKER_READY = "worker_ready"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    LIVE_VIEW_STARTED = "live_view_started"
    LIVE_VIEW_STOPPED = "live_view_stopped"
    CAPTURE_STARTED = "capture_started"
    CAPTURE_COMPLETED = "capture_completed"
    CAPTURE_FAILED = "capture_failed"
    SDRAM_ITEM_RECOVERED = "sdram_item_recovered"
    DEVICE_ERROR = "device_error"
    HEARTBEAT = "heartbeat"


class IPCErrorCode(str, Enum):
    """Standardized IPC & camera error codes across the process boundary."""

    OK = "OK"
    INVALID_SCHEMA = "IPC_INVALID_SCHEMA"
    PROTOCOL_VERSION_MISMATCH = "IPC_PROTOCOL_VERSION_MISMATCH"
    STALE_WORKER_GENERATION = "IPC_STALE_WORKER_GENERATION"
    WORKER_INSTANCE_MISMATCH = "IPC_WORKER_INSTANCE_MISMATCH"
    UNKNOWN_REQUEST_ID = "IPC_UNKNOWN_REQUEST_ID"
    REQUEST_TIMED_OUT = "IPC_REQUEST_TIMED_OUT"
    TRANSACTION_CANCELLED = "IPC_TRANSACTION_CANCELLED"
    TRANSACTION_TIMED_OUT = "IPC_TRANSACTION_TIMED_OUT"
    TRANSACTION_MISMATCH = "IPC_TRANSACTION_MISMATCH"
    NIKON_OUT_OF_FOCUS = "NIKON_OUT_OF_FOCUS"
    NIKON_DEVICE_BUSY = "NIKON_DEVICE_BUSY"
    NIKON_BATTERY_EXHAUSTED = "NIKON_BATTERY_EXHAUSTED"
    NIKON_LV_CANNOT_ACQUIRE = "NIKON_LV_CANNOT_ACQUIRE"
    NIKON_MAID_SESSION_CORRUPTED = "NIKON_MAID_SESSION_CORRUPTED"
    NIKON_CAPTURE_SDRAM_TIMEOUT = "NIKON_CAPTURE_SDRAM_TIMEOUT"
    NIKON_WORKER_HANG_TIMEOUT = "NIKON_WORKER_HANG_TIMEOUT"
    NIKON_WORKER_CRASHED = "NIKON_WORKER_CRASHED"
    NIKON_DISCONNECTED = "NIKON_DISCONNECTED"
    NIKON_UNKNOWN_ERROR = "NIKON_UNKNOWN_ERROR"


class TransactionState(str, Enum):
    """Lifecycle states of a multi-step business transaction (e.g., Still Capture)."""

    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    FAILED = "FAILED"


TERMINAL_TRANSACTION_STATES = frozenset(
    {
        TransactionState.COMPLETED,
        TransactionState.CANCELLED,
        TransactionState.TIMED_OUT,
        TransactionState.FAILED,
    }
)

ACTIVE_TRANSACTION_STATES = frozenset(
    {
        TransactionState.PENDING,
        TransactionState.STARTED,
    }
)


# Standard default timeouts (seconds)
DEFAULT_COMMAND_TIMEOUT_S: float = 5.0
DEFAULT_CONNECT_TIMEOUT_S: float = 10.0
DEFAULT_CAPTURE_TIMEOUT_S: float = 12.0
DEFAULT_AF_TIMEOUT_S: float = 4.0


# ============================================================================
# ID Generators
# ============================================================================

_REQ_COUNTER = itertools.count(1)
_TX_COUNTER = itertools.count(1)


def generate_worker_instance_id(worker_generation: int) -> str:
    """Generate a unique worker_instance_id for a newly spawned Worker Process."""
    token = uuid.uuid4().hex[:8]
    return f"wrk_gen{int(worker_generation)}_{token}"


def generate_request_id(prefix: str = "req") -> str:
    """Generate a monotonically increasing unique request_id."""
    seq = next(_REQ_COUNTER)
    token = uuid.uuid4().hex[:6]
    return f"{prefix}_{seq:08d}_{token}"


def generate_tx_id(worker_generation: int, prefix: str = "cap") -> str:
    """Generate a unique transaction ID bound to a worker generation."""
    seq = next(_TX_COUNTER)
    token = uuid.uuid4().hex[:6]
    return f"{prefix}_gen{int(worker_generation)}_{seq:06d}_{token}"


# ============================================================================
#MAID Numeric Result Mapping (Pure int -> IPCErrorCode, Zero MAID imports)
# ============================================================================


def map_maid_result_to_ipc_error(maid_result_code: int) -> Tuple[IPCErrorCode, bool]:
    """Map raw numeric NkMAIDResult code to (IPCErrorCode, requires_worker_respawn).

    Does not import maid_types so Main Process remains 100% free of MAID definitions.
    """
    code = int(maid_result_code)
    if code == 0:
        return IPCErrorCode.OK, False
    if code == 137:  # NkMAIDResult.OUT_OF_FOCUS
        return IPCErrorCode.NIKON_OUT_OF_FOCUS, False
    if code == 152:  # NkMAIDResult.DEVICE_BUSY
        return IPCErrorCode.NIKON_DEVICE_BUSY, False
    if code == 147:  # NkMAIDResult.BATTERY_EXHAUSTED
        return IPCErrorCode.NIKON_BATTERY_EXHAUSTED, False
    if code in (-116, -117, -119):  # HARDWARE_ERROR, UNEXPECTED_ERROR, ZOMBIE_OBJECT
        return IPCErrorCode.NIKON_MAID_SESSION_CORRUPTED, True
    return IPCErrorCode.NIKON_UNKNOWN_ERROR, False


# ============================================================================
# IPC Message Dataclasses & Schema Validation
# ============================================================================


class IPCProtocolError(ValueError):
    """Raised when an IPC message violates Protocol v1 schema constraints."""

    def __init__(self, message: str, error_code: IPCErrorCode = IPCErrorCode.INVALID_SCHEMA) -> None:
        super().__init__(message)
        self.error_code = error_code


REQUIRED_ENVELOPE_FIELDS = (
    "protocol_version",
    "msg_type",
    "worker_generation",
    "worker_instance_id",
    "request_id",
    "tx_id",
    "timestamp",
)


def validate_message_schema(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate that a dictionary conforms to Protocol v1 envelope and payload rules.

    Raises IPCProtocolError if invalid. Returns a normalized shallow copy.
    """
    if not isinstance(raw, Mapping):
        raise IPCProtocolError(
            f"IPC message must be a mapping, got {type(raw).__name__}",
            IPCErrorCode.INVALID_SCHEMA,
        )

    for key in REQUIRED_ENVELOPE_FIELDS:
        if key not in raw:
            raise IPCProtocolError(
                f"Missing required envelope field '{key}'",
                IPCErrorCode.INVALID_SCHEMA,
            )

    protocol_version = raw["protocol_version"]
    if not isinstance(protocol_version, int) or isinstance(protocol_version, bool):
        raise IPCProtocolError(
            f"'protocol_version' must be int, got {type(protocol_version).__name__}",
            IPCErrorCode.INVALID_SCHEMA,
        )
    if protocol_version != PROTOCOL_VERSION:
        raise IPCProtocolError(
            f"Unsupported protocol_version {protocol_version} (expected {PROTOCOL_VERSION})",
            IPCErrorCode.PROTOCOL_VERSION_MISMATCH,
        )

    msg_type = raw["msg_type"]
    valid_types = {t.value for t in IPCMessageType}
    if not isinstance(msg_type, str) or msg_type not in valid_types:
        raise IPCProtocolError(
            f"Invalid msg_type '{msg_type}', expected one of {sorted(valid_types)}",
            IPCErrorCode.INVALID_SCHEMA,
        )

    worker_gen = raw["worker_generation"]
    if not isinstance(worker_gen, int) or isinstance(worker_gen, bool) or worker_gen < 1:
        raise IPCProtocolError(
            f"'worker_generation' must be int >= 1, got {worker_gen!r}",
            IPCErrorCode.INVALID_SCHEMA,
        )

    worker_instance_id = raw["worker_instance_id"]
    if not isinstance(worker_instance_id, str) or not worker_instance_id.strip():
        raise IPCProtocolError(
            "'worker_instance_id' must be a non-empty string",
            IPCErrorCode.INVALID_SCHEMA,
        )

    request_id = raw["request_id"]
    if not isinstance(request_id, str) or not request_id.strip():
        raise IPCProtocolError(
            "'request_id' must be a non-empty string",
            IPCErrorCode.INVALID_SCHEMA,
        )

    tx_id = raw["tx_id"]
    if tx_id is not None and (not isinstance(tx_id, str) or not tx_id.strip()):
        raise IPCProtocolError(
            "'tx_id' must be None or a non-empty string",
            IPCErrorCode.INVALID_SCHEMA,
        )

    timestamp = raw["timestamp"]
    if (
        not isinstance(timestamp, (int, float))
        or isinstance(timestamp, bool)
        or not math.isfinite(float(timestamp))
    ):
        raise IPCProtocolError(
            f"'timestamp' must be a finite float/int, got {timestamp!r}",
            IPCErrorCode.INVALID_SCHEMA,
        )

    if msg_type == IPCMessageType.COMMAND.value:
        method = raw.get("method")
        if not isinstance(method, str) or not method.strip():
            raise IPCProtocolError(
                "Command message requires non-empty string 'method'",
                IPCErrorCode.INVALID_SCHEMA,
            )
        params = raw.get("params", {})
        if not isinstance(params, Mapping):
            raise IPCProtocolError(
                "Command 'params' must be a mapping",
                IPCErrorCode.INVALID_SCHEMA,
            )
        timeout_s = raw.get("timeout_s", DEFAULT_COMMAND_TIMEOUT_S)
        if (
            not isinstance(timeout_s, (int, float))
            or isinstance(timeout_s, bool)
            or not math.isfinite(float(timeout_s))
            or float(timeout_s) <= 0
        ):
            raise IPCProtocolError(
                f"Command 'timeout_s' must be a finite number > 0, got {timeout_s!r}",
                IPCErrorCode.INVALID_SCHEMA,
            )

    elif msg_type == IPCMessageType.RESPONSE.value:
        if "ok" not in raw or not isinstance(raw["ok"], bool):
            raise IPCProtocolError(
                "Response message requires boolean 'ok'",
                IPCErrorCode.INVALID_SCHEMA,
            )
        result = raw.get("result", {})
        if not isinstance(result, Mapping):
            raise IPCProtocolError(
                "Response 'result' must be a mapping",
                IPCErrorCode.INVALID_SCHEMA,
            )
        if "raw_file_path" in result and result["raw_file_path"] is not None:
            rfp = result["raw_file_path"]
            if not isinstance(rfp, str) or not rfp.strip():
                raise IPCProtocolError(
                    "Response result['raw_file_path'] must be a non-empty string",
                    IPCErrorCode.INVALID_SCHEMA,
                )
        error_code = raw.get(
            "error_code",
            IPCErrorCode.OK.value if raw["ok"] else IPCErrorCode.NIKON_UNKNOWN_ERROR.value,
        )
        if not isinstance(error_code, str) or not error_code.strip():
            raise IPCProtocolError(
                "Response 'error_code' must be a non-empty string",
                IPCErrorCode.INVALID_SCHEMA,
            )
        if not raw["ok"] and error_code == IPCErrorCode.OK.value:
            raise IPCProtocolError(
                "Failed response (ok=False) cannot have error_code='OK'",
                IPCErrorCode.INVALID_SCHEMA,
            )
        error_message = raw.get("error_message")
        if error_message is not None and not isinstance(error_message, str):
            raise IPCProtocolError(
                "Response 'error_message' must be None or a string",
                IPCErrorCode.INVALID_SCHEMA,
            )

    elif msg_type == IPCMessageType.EVENT.value:
        event_name = raw.get("event")
        if not isinstance(event_name, str) or not event_name.strip():
            raise IPCProtocolError(
                "Event message requires non-empty string 'event'",
                IPCErrorCode.INVALID_SCHEMA,
            )
        data = raw.get("data", {})
        if not isinstance(data, Mapping):
            raise IPCProtocolError(
                "Event 'data' must be a mapping",
                IPCErrorCode.INVALID_SCHEMA,
            )
        if "raw_file_path" in data and data["raw_file_path"] is not None:
            efp = data["raw_file_path"]
            if not isinstance(efp, str) or not efp.strip():
                raise IPCProtocolError(
                    "Event data['raw_file_path'] must be a non-empty string",
                    IPCErrorCode.INVALID_SCHEMA,
                )

    return dict(raw)


@dataclass(frozen=True)
class IPCRequest:
    """RPC Request sent from Main Process to Worker Process."""

    method: str
    worker_generation: int
    worker_instance_id: str
    request_id: str = field(default_factory=generate_request_id)
    tx_id: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S
    protocol_version: int = PROTOCOL_VERSION
    timestamp: float = field(default_factory=time.time)

    @property
    def msg_type(self) -> str:
        return IPCMessageType.COMMAND.value

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "protocol_version": int(self.protocol_version),
            "msg_type": IPCMessageType.COMMAND.value,
            "worker_generation": int(self.worker_generation),
            "worker_instance_id": str(self.worker_instance_id),
            "request_id": str(self.request_id),
            "tx_id": self.tx_id,
            "timestamp": float(self.timestamp),
            "method": str(self.method),
            "params": dict(self.params),
            "timeout_s": float(self.timeout_s),
        }
        return validate_message_schema(payload)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "IPCRequest":
        validated = validate_message_schema(raw)
        if validated["msg_type"] != IPCMessageType.COMMAND.value:
            raise IPCProtocolError(f"Expected msg_type 'cmd', got {validated['msg_type']!r}")
        return cls(
            method=validated["method"],
            worker_generation=validated["worker_generation"],
            worker_instance_id=validated["worker_instance_id"],
            request_id=validated["request_id"],
            tx_id=validated["tx_id"],
            params=dict(validated.get("params", {})),
            timeout_s=float(validated.get("timeout_s", DEFAULT_COMMAND_TIMEOUT_S)),
            protocol_version=validated["protocol_version"],
            timestamp=float(validated["timestamp"]),
        )


@dataclass(frozen=True)
class IPCResponse:
    """RPC Response returned from Worker Process to Main Process."""

    request_id: str
    worker_generation: int
    worker_instance_id: str
    ok: bool
    tx_id: Optional[str] = None
    result: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    protocol_version: int = PROTOCOL_VERSION
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.error_code is None:
            default_code = (
                IPCErrorCode.OK.value
                if self.ok
                else IPCErrorCode.NIKON_UNKNOWN_ERROR.value
            )
            object.__setattr__(self, "error_code", default_code)

    @property
    def msg_type(self) -> str:
        return IPCMessageType.RESPONSE.value

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "protocol_version": int(self.protocol_version),
            "msg_type": IPCMessageType.RESPONSE.value,
            "worker_generation": int(self.worker_generation),
            "worker_instance_id": str(self.worker_instance_id),
            "request_id": str(self.request_id),
            "tx_id": self.tx_id,
            "timestamp": float(self.timestamp),
            "ok": bool(self.ok),
            "result": dict(self.result),
            "error_code": str(self.error_code),
            "error_message": self.error_message,
        }
        return validate_message_schema(payload)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "IPCResponse":
        validated = validate_message_schema(raw)
        if validated["msg_type"] != IPCMessageType.RESPONSE.value:
            raise IPCProtocolError(f"Expected msg_type 'resp', got {validated['msg_type']!r}")
        return cls(
            request_id=validated["request_id"],
            worker_generation=validated["worker_generation"],
            worker_instance_id=validated["worker_instance_id"],
            ok=validated["ok"],
            tx_id=validated["tx_id"],
            result=dict(validated.get("result", {})),
            error_code=validated.get(
                "error_code",
                IPCErrorCode.OK.value if validated["ok"] else IPCErrorCode.NIKON_UNKNOWN_ERROR.value,
            ),
            error_message=validated.get("error_message"),
            protocol_version=validated["protocol_version"],
            timestamp=float(validated["timestamp"]),
        )


@dataclass(frozen=True)
class IPCEvent:
    """Asynchronous Event emitted from Worker Process to Main Process."""

    event: str
    worker_generation: int
    worker_instance_id: str
    request_id: str = field(default_factory=lambda: generate_request_id("evt"))
    tx_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    protocol_version: int = PROTOCOL_VERSION
    timestamp: float = field(default_factory=time.time)

    @property
    def msg_type(self) -> str:
        return IPCMessageType.EVENT.value

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "protocol_version": int(self.protocol_version),
            "msg_type": IPCMessageType.EVENT.value,
            "worker_generation": int(self.worker_generation),
            "worker_instance_id": str(self.worker_instance_id),
            "request_id": str(self.request_id),
            "tx_id": self.tx_id,
            "timestamp": float(self.timestamp),
            "event": str(self.event),
            "data": dict(self.data),
        }
        return validate_message_schema(payload)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "IPCEvent":
        validated = validate_message_schema(raw)
        if validated["msg_type"] != IPCMessageType.EVENT.value:
            raise IPCProtocolError(f"Expected msg_type 'evt', got {validated['msg_type']!r}")
        return cls(
            event=validated["event"],
            worker_generation=validated["worker_generation"],
            worker_instance_id=validated["worker_instance_id"],
            request_id=validated["request_id"],
            tx_id=validated["tx_id"],
            data=dict(validated.get("data", {})),
            protocol_version=validated["protocol_version"],
            timestamp=float(validated["timestamp"]),
        )


# ============================================================================
# Transaction & Request Tracking State Machine
# ============================================================================


@dataclass
class PendingRequestRecord:
    """Tracks an in-flight RPC request awaiting an IPCResponse."""

    request_id: str
    method: str
    worker_generation: int
    worker_instance_id: str
    tx_id: Optional[str]
    created_at_mono: float
    deadline_mono: float
    state: str = "PENDING"  # PENDING | COMPLETED | CANCELLED | TIMED_OUT


@dataclass
class CaptureTransaction:
    """Tracks a multi-step Capture or Autofocus transaction across IPC events and responses."""

    tx_id: str
    request_id: str
    worker_generation: int
    worker_instance_id: str
    created_at_mono: float
    deadline_mono: float
    state: TransactionState = TransactionState.PENDING
    raw_file_path: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_TRANSACTION_STATES

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_TRANSACTION_STATES

    def check_expired(self, now_mono: Optional[float] = None) -> bool:
        """Transition to TIMED_OUT if deadline_mono has passed while still active."""
        now = time.perf_counter() if now_mono is None else float(now_mono)
        if self.is_active and now > self.deadline_mono:
            self.state = TransactionState.TIMED_OUT
            self.error_code = IPCErrorCode.TRANSACTION_TIMED_OUT.value
            return True
        return self.state == TransactionState.TIMED_OUT


@dataclass(frozen=True)
class ValidationOutcome:
    """Structured result of validating an incoming IPCResponse or IPCEvent."""

    accepted: bool
    reason_code: IPCErrorCode = IPCErrorCode.OK
    reason_detail: str = ""
    quarantine_file_path: Optional[str] = None


class IPCTransactionManager:
    """Manages RPC request correlation, CaptureTransaction state, and Late-Event Rejection.

    Enforces the 5-step verification protocol specified in Section 4.2 of the
    architecture design:
    1. `protocol_version == 1`.
    2. `worker_generation == current_generation` and `worker_instance_id == current_instance_id`.
    3. `request_id` matches an active pending request (and has not timed out or been cancelled).
    4. For transactional messages (`tx_id` present or capture events/responses):
       `tx_id` must match the active transaction, and its state must be in `("PENDING", "STARTED")`.
       Late events arriving after `CANCELLED`, `TIMED_OUT`, or from an old generation are rejected,
       and any late `raw_file_path` is flagged for quarantine/recovery rather than mixed into
       a new customer session.
    """

    def __init__(
        self,
        worker_generation: int = 1,
        worker_instance_id: Optional[str] = None,
        max_terminal_history: int = 512,
    ) -> None:
        if int(worker_generation) < 1:
            raise ValueError("worker_generation must be >= 1")
        if int(max_terminal_history) < 1:
            raise ValueError("max_terminal_history must be >= 1")
        self._current_generation: int = int(worker_generation)
        self._current_instance_id: str = (
            worker_instance_id
            if worker_instance_id
            else generate_worker_instance_id(self._current_generation)
        )
        self._max_terminal_history: int = int(max_terminal_history)
        self._pending_requests: Dict[str, PendingRequestRecord] = {}
        self._transactions: Dict[str, CaptureTransaction] = {}
        self._active_capture_tx_id: Optional[str] = None

    @property
    def current_generation(self) -> int:
        return self._current_generation

    @property
    def current_instance_id(self) -> str:
        return self._current_instance_id

    @property
    def active_capture_transaction(self) -> Optional[CaptureTransaction]:
        if self._active_capture_tx_id is None:
            return None
        return self._transactions.get(self._active_capture_tx_id)

    def _prune_terminal_history(self) -> None:
        """Prune oldest terminal requests and transactions while preserving all active state (Finding L-02)."""
        terminal_tx_ids = [
            tx_id
            for tx_id, tx in self._transactions.items()
            if tx.is_terminal and tx_id != self._active_capture_tx_id
        ]
        if len(terminal_tx_ids) > self._max_terminal_history:
            excess = len(terminal_tx_ids) - self._max_terminal_history
            for old_tx_id in terminal_tx_ids[:excess]:
                tx_obj = self._transactions.get(old_tx_id)
                if tx_obj is not None and tx_obj.is_terminal and old_tx_id != self._active_capture_tx_id:
                    del self._transactions[old_tx_id]

        terminal_req_ids = [
            req_id
            for req_id, req in self._pending_requests.items()
            if req.state != "PENDING"
            and (
                req.tx_id is None
                or req.tx_id not in self._transactions
                or self._transactions[req.tx_id].is_terminal
            )
        ]
        if len(terminal_req_ids) > self._max_terminal_history:
            excess = len(terminal_req_ids) - self._max_terminal_history
            for old_req_id in terminal_req_ids[:excess]:
                req_obj = self._pending_requests.get(old_req_id)
                if req_obj is not None and req_obj.state != "PENDING":
                    del self._pending_requests[old_req_id]

    @staticmethod
    def _normalize_path_for_compare(path_str: str) -> str:
        normalized = path_str.replace("\\", "/").strip()
        return os.path.normcase(os.path.normpath(normalized))

    def _validate_capture_file_path(
        self,
        raw_file_path: Any,
        tx: CaptureTransaction,
        source_label: str,
    ) -> Optional[ValidationOutcome]:
        """Verify raw_file_path basename contains tx.tx_id and matches any prior path on tx (Finding H-02).

        NOTE: Never moves or deletes files on disk; only populates quarantine_file_path in ValidationOutcome.
        """
        if raw_file_path is None:
            return None
        if not isinstance(raw_file_path, str) or not raw_file_path.strip():
            return ValidationOutcome(
                accepted=False,
                reason_code=IPCErrorCode.INVALID_SCHEMA,
                reason_detail=f"{source_label} raw_file_path must be a non-empty string",
            )

        path_str = raw_file_path.strip()
        basename = os.path.basename(path_str.replace("\\", "/"))
        if not basename or tx.tx_id not in basename:
            return ValidationOutcome(
                accepted=False,
                reason_code=IPCErrorCode.TRANSACTION_MISMATCH,
                reason_detail=(
                    f"{source_label} raw_file_path basename {basename!r} "
                    f"(from {path_str!r}) does not contain tx_id {tx.tx_id!r}"
                ),
                quarantine_file_path=path_str,
            )

        if tx.raw_file_path is not None:
            if self._normalize_path_for_compare(path_str) != self._normalize_path_for_compare(tx.raw_file_path):
                tx.state = TransactionState.FAILED
                tx.error_code = IPCErrorCode.TRANSACTION_MISMATCH.value
                tx.error_message = (
                    f"Inconsistent raw_file_path between event ({tx.raw_file_path!r}) "
                    f"and {source_label} ({path_str!r})"
                )
                if self._active_capture_tx_id == tx.tx_id:
                    self._active_capture_tx_id = None
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_MISMATCH,
                    reason_detail=tx.error_message,
                    quarantine_file_path=path_str,
                )

        return None

    def advance_worker_generation(
        self,
        new_generation: Optional[int] = None,
        new_instance_id: Optional[str] = None,
    ) -> Tuple[int, str]:
        """Advance to a new Worker Process generation and cancel all in-flight state from old worker."""
        next_gen = (
            self._current_generation + 1
            if new_generation is None
            else int(new_generation)
        )
        if next_gen <= self._current_generation:
            raise ValueError(
                f"New worker_generation {next_gen} must be > current {self._current_generation}"
            )

        # Cancel all pending requests and active transactions from previous generation
        for req in self._pending_requests.values():
            if req.state == "PENDING":
                req.state = "CANCELLED"

        for tx in self._transactions.values():
            if tx.is_active:
                tx.state = TransactionState.CANCELLED
                tx.error_code = IPCErrorCode.STALE_WORKER_GENERATION.value

        self._active_capture_tx_id = None
        self._current_generation = next_gen
        self._current_instance_id = (
            new_instance_id
            if new_instance_id
            else generate_worker_instance_id(next_gen)
        )
        self._prune_terminal_history()
        return self._current_generation, self._current_instance_id

    def create_request(
        self,
        method: str | IPCCommandMethod,
        params: Optional[Dict[str, Any]] = None,
        timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S,
        tx_id: Optional[str] = None,
        now_mono: Optional[float] = None,
    ) -> IPCRequest:
        """Create and register an outbound IPCRequest."""
        method_str = method.value if isinstance(method, IPCCommandMethod) else str(method)
        now = time.perf_counter() if now_mono is None else float(now_mono)
        req_id = generate_request_id()

        req = IPCRequest(
            method=method_str,
            worker_generation=self._current_generation,
            worker_instance_id=self._current_instance_id,
            request_id=req_id,
            tx_id=tx_id,
            params=dict(params) if params else {},
            timeout_s=float(timeout_s),
        )
        self._pending_requests[req_id] = PendingRequestRecord(
            request_id=req_id,
            method=method_str,
            worker_generation=self._current_generation,
            worker_instance_id=self._current_instance_id,
            tx_id=tx_id,
            created_at_mono=now,
            deadline_mono=now + float(timeout_s),
            state="PENDING",
        )
        self._prune_terminal_history()
        return req

    def begin_capture_transaction(
        self,
        params: Optional[Dict[str, Any]] = None,
        timeout_s: float = DEFAULT_CAPTURE_TIMEOUT_S,
        now_mono: Optional[float] = None,
    ) -> Tuple[IPCRequest, CaptureTransaction]:
        """Start a new exclusive CaptureTransaction and register its IPCRequest."""
        now = time.perf_counter() if now_mono is None else float(now_mono)

        # If an older transaction is still active, check if it expired or cancel it
        if self._active_capture_tx_id is not None:
            prev_tx = self._transactions.get(self._active_capture_tx_id)
            if prev_tx is not None and prev_tx.is_active:
                prev_tx.check_expired(now_mono=now)
                if prev_tx.is_active:
                    self.cancel_transaction(prev_tx.tx_id, reason="Superseded by new capture")

        tx_id = generate_tx_id(self._current_generation, prefix="cap")
        req = self.create_request(
            method=IPCCommandMethod.CAPTURE,
            params=params,
            timeout_s=timeout_s,
            tx_id=tx_id,
            now_mono=now,
        )
        tx = CaptureTransaction(
            tx_id=tx_id,
            request_id=req.request_id,
            worker_generation=self._current_generation,
            worker_instance_id=self._current_instance_id,
            created_at_mono=now,
            deadline_mono=now + float(timeout_s),
            state=TransactionState.PENDING,
        )
        self._transactions[tx_id] = tx
        self._active_capture_tx_id = tx_id
        self._prune_terminal_history()
        return req, tx

    def cancel_transaction(self, tx_id: str, reason: str = "Cancelled by caller") -> bool:
        """Cancel a transaction by tx_id and mark its associated request as CANCELLED."""
        tx = self._transactions.get(tx_id)
        if tx is None:
            return False
        if tx.is_terminal:
            return False

        tx.state = TransactionState.CANCELLED
        tx.error_code = IPCErrorCode.TRANSACTION_CANCELLED.value
        tx.error_message = reason

        req_rec = self._pending_requests.get(tx.request_id)
        if req_rec is not None and req_rec.state == "PENDING":
            req_rec.state = "CANCELLED"

        if self._active_capture_tx_id == tx_id:
            self._active_capture_tx_id = None
        self._prune_terminal_history()
        return True

    def expire_timed_out(self, now_mono: Optional[float] = None) -> list[str]:
        """Sweep and mark any requests or transactions past their deadline as TIMED_OUT."""
        now = time.perf_counter() if now_mono is None else float(now_mono)
        expired_tx_ids: list[str] = []

        for req_rec in self._pending_requests.values():
            if req_rec.state == "PENDING" and now > req_rec.deadline_mono:
                req_rec.state = "TIMED_OUT"

        for tx_id, tx in self._transactions.items():
            if tx.is_active and tx.check_expired(now_mono=now):
                expired_tx_ids.append(tx_id)
                req_rec = self._pending_requests.get(tx.request_id)
                if req_rec is not None and req_rec.state == "PENDING":
                    req_rec.state = "TIMED_OUT"
                if self._active_capture_tx_id == tx_id:
                    self._active_capture_tx_id = None

        self._prune_terminal_history()
        return expired_tx_ids

    def _validate_worker_identity(
        self,
        msg_gen: int,
        msg_instance_id: str,
        raw_file_path: Optional[str] = None,
    ) -> Optional[ValidationOutcome]:
        if int(msg_gen) != self._current_generation:
            return ValidationOutcome(
                accepted=False,
                reason_code=IPCErrorCode.STALE_WORKER_GENERATION,
                reason_detail=(
                    f"Message worker_generation={msg_gen} != "
                    f"current_generation={self._current_generation}"
                ),
                quarantine_file_path=raw_file_path,
            )
        if str(msg_instance_id) != self._current_instance_id:
            return ValidationOutcome(
                accepted=False,
                reason_code=IPCErrorCode.WORKER_INSTANCE_MISMATCH,
                reason_detail=(
                    f"Message worker_instance_id={msg_instance_id!r} != "
                    f"current_instance_id={self._current_instance_id!r}"
                ),
                quarantine_file_path=raw_file_path,
            )
        return None

    def validate_and_consume_response(
        self,
        response: IPCResponse | Mapping[str, Any],
        now_mono: Optional[float] = None,
    ) -> ValidationOutcome:
        """Validate an incoming IPCResponse against active generation, request_id, and tx_id."""
        now = time.perf_counter() if now_mono is None else float(now_mono)
        try:
            resp = (
                response
                if isinstance(response, IPCResponse)
                else IPCResponse.from_dict(response)
            )
        except IPCProtocolError as exc:
            return ValidationOutcome(
                accepted=False,
                reason_code=exc.error_code,
                reason_detail=str(exc),
            )

        raw_file_path = resp.result.get("raw_file_path") if isinstance(resp.result, Mapping) else None

        # Step 1: Check worker_generation and worker_instance_id
        identity_err = self._validate_worker_identity(
            resp.worker_generation,
            resp.worker_instance_id,
            raw_file_path=raw_file_path,
        )
        if identity_err is not None:
            return identity_err

        # Step 2: Check request_id correlation
        req_rec = self._pending_requests.get(resp.request_id)
        if req_rec is None:
            return ValidationOutcome(
                accepted=False,
                reason_code=IPCErrorCode.UNKNOWN_REQUEST_ID,
                reason_detail=f"Unknown request_id={resp.request_id!r}",
                quarantine_file_path=raw_file_path,
            )

        # Check request timeout
        if req_rec.state == "PENDING" and now > req_rec.deadline_mono:
            req_rec.state = "TIMED_OUT"
            if req_rec.tx_id and req_rec.tx_id in self._transactions:
                self._transactions[req_rec.tx_id].check_expired(now_mono=now)

        if req_rec.state == "TIMED_OUT":
            return ValidationOutcome(
                accepted=False,
                reason_code=IPCErrorCode.REQUEST_TIMED_OUT,
                reason_detail=f"Request {resp.request_id!r} already timed out",
                quarantine_file_path=raw_file_path,
            )

        if req_rec.state == "CANCELLED":
            return ValidationOutcome(
                accepted=False,
                reason_code=IPCErrorCode.TRANSACTION_CANCELLED,
                reason_detail=f"Request {resp.request_id!r} was cancelled",
                quarantine_file_path=raw_file_path,
            )

        if req_rec.state != "PENDING":
            return ValidationOutcome(
                accepted=False,
                reason_code=IPCErrorCode.UNKNOWN_REQUEST_ID,
                reason_detail=f"Duplicate response for already-completed request {resp.request_id!r}",
                quarantine_file_path=raw_file_path,
            )

        # Step 3: Validate tx_id correlation if transactional
        if req_rec.tx_id is not None or resp.tx_id is not None:
            if resp.tx_id != req_rec.tx_id:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_MISMATCH,
                    reason_detail=(
                        f"Response tx_id={resp.tx_id!r} does not match "
                        f"request tx_id={req_rec.tx_id!r}"
                    ),
                    quarantine_file_path=raw_file_path,
                )

            tx = self._transactions.get(str(resp.tx_id))
            if tx is None:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_MISMATCH,
                    reason_detail=f"Unknown transaction tx_id={resp.tx_id!r}",
                    quarantine_file_path=raw_file_path,
                )

            tx.check_expired(now_mono=now)
            if tx.state == TransactionState.CANCELLED:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_CANCELLED,
                    reason_detail=f"Transaction {tx.tx_id!r} was cancelled",
                    quarantine_file_path=raw_file_path,
                )
            if tx.state == TransactionState.TIMED_OUT:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_TIMED_OUT,
                    reason_detail=f"Transaction {tx.tx_id!r} timed out",
                    quarantine_file_path=raw_file_path,
                )
            if not tx.is_active:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_MISMATCH,
                    reason_detail=f"Transaction {tx.tx_id!r} in non-active state {tx.state.value}",
                    quarantine_file_path=raw_file_path,
                )

            # Finding H-02 fix: Verify raw_file_path basename contains tx.tx_id and matches prior event path
            if raw_file_path is not None:
                path_err = self._validate_capture_file_path(
                    raw_file_path=raw_file_path,
                    tx=tx,
                    source_label="Response",
                )
                if path_err is not None:
                    req_rec.state = "CANCELLED"
                    self._prune_terminal_history()
                    return path_err

            # Update transaction terminal state
            if resp.ok:
                tx.state = TransactionState.COMPLETED
                if raw_file_path:
                    tx.raw_file_path = str(raw_file_path)
            else:
                tx.state = TransactionState.FAILED
                tx.error_code = str(resp.error_code)
                tx.error_message = resp.error_message

            if self._active_capture_tx_id == tx.tx_id:
                self._active_capture_tx_id = None

        req_rec.state = "COMPLETED"
        self._prune_terminal_history()
        return ValidationOutcome(accepted=True, reason_code=IPCErrorCode.OK)

    def validate_and_apply_event(
        self,
        event: IPCEvent | Mapping[str, Any],
        now_mono: Optional[float] = None,
    ) -> ValidationOutcome:
        """Validate an incoming asynchronous IPCEvent and reject late or mismatched events."""
        now = time.perf_counter() if now_mono is None else float(now_mono)
        try:
            evt = event if isinstance(event, IPCEvent) else IPCEvent.from_dict(event)
        except IPCProtocolError as exc:
            return ValidationOutcome(
                accepted=False,
                reason_code=exc.error_code,
                reason_detail=str(exc),
            )

        raw_file_path = evt.data.get("raw_file_path") if isinstance(evt.data, Mapping) else None

        # Step 1: Check worker_generation and worker_instance_id
        identity_err = self._validate_worker_identity(
            evt.worker_generation,
            evt.worker_instance_id,
            raw_file_path=raw_file_path,
        )
        if identity_err is not None:
            return identity_err

        # Step 2: Capture-lifecycle events MUST carry a valid active tx_id
        capture_events = {
            IPCEventName.CAPTURE_STARTED.value,
            IPCEventName.CAPTURE_COMPLETED.value,
            IPCEventName.CAPTURE_FAILED.value,
        }

        if evt.event in capture_events or evt.tx_id is not None:
            if not evt.tx_id:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_MISMATCH,
                    reason_detail=f"Event {evt.event!r} missing required tx_id",
                    quarantine_file_path=raw_file_path,
                )

            tx = self._transactions.get(evt.tx_id)
            if tx is None:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_MISMATCH,
                    reason_detail=f"Event {evt.event!r} references unknown tx_id={evt.tx_id!r}",
                    quarantine_file_path=raw_file_path,
                )

            tx.check_expired(now_mono=now)
            if tx.state == TransactionState.CANCELLED:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_CANCELLED,
                    reason_detail=f"Late event {evt.event!r} rejected for cancelled tx_id={evt.tx_id!r}",
                    quarantine_file_path=raw_file_path,
                )
            if tx.state == TransactionState.TIMED_OUT:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_TIMED_OUT,
                    reason_detail=f"Late event {evt.event!r} rejected for timed-out tx_id={evt.tx_id!r}",
                    quarantine_file_path=raw_file_path,
                )
            if not tx.is_active:
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_MISMATCH,
                    reason_detail=(
                        f"Late event {evt.event!r} rejected for transaction {evt.tx_id!r} "
                        f"in terminal state {tx.state.value}"
                    ),
                    quarantine_file_path=raw_file_path,
                )

            # Enforce active_capture_tx_id match for capture events
            if (
                evt.event in capture_events
                and self._active_capture_tx_id is not None
                and evt.tx_id != self._active_capture_tx_id
            ):
                return ValidationOutcome(
                    accepted=False,
                    reason_code=IPCErrorCode.TRANSACTION_MISMATCH,
                    reason_detail=(
                        f"Event tx_id={evt.tx_id!r} != active_capture_tx_id={self._active_capture_tx_id!r}"
                    ),
                    quarantine_file_path=raw_file_path,
                )

            # Apply state transitions
            if evt.event == IPCEventName.CAPTURE_STARTED.value:
                tx.state = TransactionState.STARTED
            elif evt.event == IPCEventName.CAPTURE_COMPLETED.value:
                # Finding H-02 fix: Verify basename contains tx_id and matches any prior path
                path_err = self._validate_capture_file_path(
                    raw_file_path=raw_file_path,
                    tx=tx,
                    source_label="Event(capture_completed)",
                )
                if path_err is not None:
                    return path_err
                if raw_file_path:
                    tx.raw_file_path = str(raw_file_path)
            elif evt.event == IPCEventName.CAPTURE_FAILED.value:
                tx.state = TransactionState.FAILED
                tx.error_code = str(evt.data.get("error_code", IPCErrorCode.NIKON_UNKNOWN_ERROR.value))
                tx.error_message = evt.data.get("error_message")
                if self._active_capture_tx_id == tx.tx_id:
                    self._active_capture_tx_id = None
                self._prune_terminal_history()

        return ValidationOutcome(accepted=True, reason_code=IPCErrorCode.OK)
