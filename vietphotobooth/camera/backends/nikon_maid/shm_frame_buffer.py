"""Shared Memory Frame Buffer with Per-Slot Seqlock Protocol for Nikon Isolated Driver.

Implements the 6 MiB (6,291,456 bytes) shared memory layout defined in
NIKON_D780_PROCESS_ISOLATED_DRIVER_ARCHITECTURE.md:
- GlobalControlHeader (Offset 0..255, 256 bytes, _pack_ = 8)
- Slot 0 (Offset 256..2,621,759, 2,621,504 bytes)
- Slot 1 (Offset 2,621,760..5,243,263, 2,621,504 bytes)
- Reserved Tail (Offset 5,243,264..6,291,455, 1,048,192 bytes)

Provides:
- Exact byte-offset and sizeof verification at import time and via verify_shm_layout().
- Windows x64 hardware atomic operations (LOCK XADD / InterlockedIncrement64,
  XCHG / InterlockedExchange, MFENCE / MemoryBarrier).
- Per-Slot Odd/Even Seqlock protocol ensuring Main Process never reads a torn frame,
  incomplete frame, corrupted JPEG, or stale worker generation frame.
- Collision-free SharedMemory naming across multiple concurrent instances.

NOTE: This module MUST NOT import maid_loader, maid_session, maid_types, or load any Nikon DLL.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import itertools
from multiprocessing import shared_memory
import os
import sys
import threading
import time
import uuid
import zlib
from typing import Callable, Dict, Optional

import numpy as np


# ============================================================================
# Constants & Byte Layout Specifications
# ============================================================================

SHM_MAGIC: int = 0x38393931  # ASCII "1998" in little-endian
SHM_SCHEMA_VERSION: int = 1

SHM_TOTAL_BYTES: int = 6 * 1024 * 1024  # 6,291,456 bytes (6 MiB)
GLOBAL_HEADER_BYTES: int = 256
SLOT_HEADER_BYTES: int = 64
SLOT_RGB_CAPACITY: int = 2 * 1024 * 1024  # 2,097,152 bytes (2 MiB)
SLOT_JPEG_CAPACITY: int = 512 * 1024  # 524,288 bytes (512 KiB)
FRAME_SLOT_BYTES: int = SLOT_HEADER_BYTES + SLOT_RGB_CAPACITY + SLOT_JPEG_CAPACITY  # 2,621,504 bytes

SLOT_COUNT: int = 2
SLOT_0_OFFSET: int = GLOBAL_HEADER_BYTES  # 256 (0x000100)
SLOT_1_OFFSET: int = SLOT_0_OFFSET + FRAME_SLOT_BYTES  # 2,621,760 (0x280140)
RESERVED_TAIL_OFFSET: int = SLOT_1_OFFSET + FRAME_SLOT_BYTES  # 5,243,264 (0x500180)
RESERVED_TAIL_BYTES: int = SHM_TOTAL_BYTES - RESERVED_TAIL_OFFSET  # 1,048,192 bytes

DEFAULT_LIVE_VIEW_WIDTH: int = 1024
DEFAULT_LIVE_VIEW_HEIGHT: int = 680
DEFAULT_RGB_BYTES_LEN: int = DEFAULT_LIVE_VIEW_WIDTH * DEFAULT_LIVE_VIEW_HEIGHT * 3  # 2,088,960 bytes
MIN_VALID_JPEG_BYTES: int = 64
DEFAULT_HEARTBEAT_TIMEOUT_NS: int = 1_500_000_000  # 1.5 seconds

JPEG_SOI_MARKER: bytes = b"\xff\xd8"
JPEG_EOI_MARKER: bytes = b"\xff\xd9"


class WriterState:
    """Worker writer state constants stored in GlobalControlHeader.writer_state."""

    IDLE: int = 0
    STREAMING: int = 1
    CAPTURING: int = 2
    DISCONNECTED: int = 3
    STOPPING: int = 4


class FrameValidState:
    """Slot frame validity flags stored in SlotHeader.frame_valid."""

    INVALID_OR_WRITING: int = 0
    VALID_COMMITTED: int = 1


# ============================================================================
# ctypes Structures (Exact Byte-Level Layout)
# ============================================================================


class GlobalControlHeader(ctypes.Structure):
    """Global Control Header at Offset 0..255 (256 bytes total)."""

    _pack_ = 8
    _fields_ = [
        ("magic", ctypes.c_uint32),               # Offset 0   (4B)
        ("schema_version", ctypes.c_uint32),      # Offset 4   (4B)
        ("published_slot", ctypes.c_uint32),      # Offset 8   (4B)
        ("writer_state", ctypes.c_uint32),        # Offset 12  (4B)
        ("worker_pid", ctypes.c_uint32),          # Offset 16  (4B)
        ("worker_generation", ctypes.c_uint32),   # Offset 20  (4B)
        ("latest_sequence_id", ctypes.c_uint64),  # Offset 24  (8B)
        ("worker_heartbeat_ns", ctypes.c_uint64), # Offset 32  (8B)
        ("source_fps", ctypes.c_float),           # Offset 40  (4B)
        ("battery_percent", ctypes.c_int32),      # Offset 44  (4B)
        ("reserved", ctypes.c_uint8 * 208),       # Offset 48  (208B) -> Total 256B
    ]


class SlotHeader(ctypes.Structure):
    """Per-Slot Control Header at Offset +0..+63 within each FrameSlot (64 bytes total)."""

    _pack_ = 8
    _fields_ = [
        ("slot_seq_lock", ctypes.c_uint64),    # Offset +0   (8B) - Odd=Writing, Even=Committed
        ("frame_valid", ctypes.c_uint32),      # Offset +8   (4B) - 0=Invalid/Writing, 1=Valid
        ("slot_worker_gen", ctypes.c_uint32),  # Offset +12  (4B) - Worker generation
        ("sequence_id", ctypes.c_uint64),      # Offset +16  (8B) - Monotonic frame sequence ID
        ("capture_ts", ctypes.c_double),       # Offset +24  (8B) - time.time()
        ("mono_ts", ctypes.c_double),          # Offset +32  (8B) - time.perf_counter()
        ("width", ctypes.c_uint32),            # Offset +40  (4B) - Frame width (e.g., 1024)
        ("height", ctypes.c_uint32),           # Offset +44  (4B) - Frame height (e.g., 680)
        ("rgb_bytes_len", ctypes.c_uint32),    # Offset +48  (4B) - Valid RGB byte length
        ("jpeg_bytes_len", ctypes.c_uint32),   # Offset +52  (4B) - Valid JPEG byte length
        ("jpeg_crc32", ctypes.c_uint32),       # Offset +56  (4B) - zlib.crc32(jpeg_bytes)
        ("header_pad", ctypes.c_uint32),       # Offset +60  (4B) -> Total 64B
    ]


class FrameSlot(ctypes.Structure):
    """Complete Frame Slot (64B SlotHeader + 2 MiB RGB buffer + 512 KiB JPEG buffer = 2,621,504B)."""

    _pack_ = 8
    _fields_ = [
        ("slot_seq_lock", ctypes.c_uint64),                     # Offset +0          (8B)
        ("frame_valid", ctypes.c_uint32),                       # Offset +8          (4B)
        ("slot_worker_gen", ctypes.c_uint32),                   # Offset +12         (4B)
        ("sequence_id", ctypes.c_uint64),                       # Offset +16         (8B)
        ("capture_ts", ctypes.c_double),                        # Offset +24         (8B)
        ("mono_ts", ctypes.c_double),                           # Offset +32         (8B)
        ("width", ctypes.c_uint32),                             # Offset +40         (4B)
        ("height", ctypes.c_uint32),                            # Offset +44         (4B)
        ("rgb_bytes_len", ctypes.c_uint32),                     # Offset +48         (4B)
        ("jpeg_bytes_len", ctypes.c_uint32),                    # Offset +52         (4B)
        ("jpeg_crc32", ctypes.c_uint32),                        # Offset +56         (4B)
        ("header_pad", ctypes.c_uint32),                        # Offset +60         (4B)
        ("rgb_buffer", ctypes.c_uint8 * SLOT_RGB_CAPACITY),     # Offset +64         (2,097,152B)
        ("jpeg_buffer", ctypes.c_uint8 * SLOT_JPEG_CAPACITY),   # Offset +2,097,216  (524,288B)
    ]


EXPECTED_GLOBAL_HEADER_OFFSETS: Dict[str, int] = {
    "magic": 0,
    "schema_version": 4,
    "published_slot": 8,
    "writer_state": 12,
    "worker_pid": 16,
    "worker_generation": 20,
    "latest_sequence_id": 24,
    "worker_heartbeat_ns": 32,
    "source_fps": 40,
    "battery_percent": 44,
    "reserved": 48,
}

EXPECTED_SLOT_OFFSETS: Dict[str, int] = {
    "slot_seq_lock": 0,
    "frame_valid": 8,
    "slot_worker_gen": 12,
    "sequence_id": 16,
    "capture_ts": 24,
    "mono_ts": 32,
    "width": 40,
    "height": 44,
    "rgb_bytes_len": 48,
    "jpeg_bytes_len": 52,
    "jpeg_crc32": 56,
    "header_pad": 60,
    "rgb_buffer": 64,
    "jpeg_buffer": 2_097_216,
}


def verify_shm_layout() -> Dict[str, object]:
    """Verify exact sizeof, field offsets, and alignment of Shared Memory ctypes structures.

    Raises AssertionError if any size or offset deviates from the specification.
    """
    global_size = ctypes.sizeof(GlobalControlHeader)
    if global_size != GLOBAL_HEADER_BYTES:
        raise AssertionError(
            f"GlobalControlHeader size mismatch: expected {GLOBAL_HEADER_BYTES}, got {global_size}"
        )

    slot_hdr_size = ctypes.sizeof(SlotHeader)
    if slot_hdr_size != SLOT_HEADER_BYTES:
        raise AssertionError(
            f"SlotHeader size mismatch: expected {SLOT_HEADER_BYTES}, got {slot_hdr_size}"
        )

    slot_size = ctypes.sizeof(FrameSlot)
    if slot_size != FRAME_SLOT_BYTES:
        raise AssertionError(
            f"FrameSlot size mismatch: expected {FRAME_SLOT_BYTES}, got {slot_size}"
        )

    for field_name, expected_offset in EXPECTED_GLOBAL_HEADER_OFFSETS.items():
        actual_offset = getattr(GlobalControlHeader, field_name).offset
        if actual_offset != expected_offset:
            raise AssertionError(
                f"GlobalControlHeader.{field_name} offset mismatch: "
                f"expected {expected_offset}, got {actual_offset}"
            )

    for field_name, expected_offset in EXPECTED_SLOT_OFFSETS.items():
        if hasattr(SlotHeader, field_name):
            hdr_offset = getattr(SlotHeader, field_name).offset
            if hdr_offset != expected_offset:
                raise AssertionError(
                    f"SlotHeader.{field_name} offset mismatch: "
                    f"expected {expected_offset}, got {hdr_offset}"
                )
        slot_offset = getattr(FrameSlot, field_name).offset
        if slot_offset != expected_offset:
            raise AssertionError(
                f"FrameSlot.{field_name} offset mismatch: "
                f"expected {expected_offset}, got {slot_offset}"
            )

    if SLOT_0_OFFSET != 256:
        raise AssertionError(f"SLOT_0_OFFSET mismatch: {SLOT_0_OFFSET}")
    if SLOT_1_OFFSET != 2_621_760:
        raise AssertionError(f"SLOT_1_OFFSET mismatch: {SLOT_1_OFFSET}")
    if RESERVED_TAIL_OFFSET != 5_243_264:
        raise AssertionError(f"RESERVED_TAIL_OFFSET mismatch: {RESERVED_TAIL_OFFSET}")
    if SHM_TOTAL_BYTES != 6_291_456:
        raise AssertionError(f"SHM_TOTAL_BYTES mismatch: {SHM_TOTAL_BYTES}")
    if GLOBAL_HEADER_BYTES + (SLOT_COUNT * FRAME_SLOT_BYTES) + RESERVED_TAIL_BYTES != SHM_TOTAL_BYTES:
        raise AssertionError("Total byte budget does not sum to SHM_TOTAL_BYTES")

    return {
        "total_bytes": SHM_TOTAL_BYTES,
        "global_header_bytes": global_size,
        "slot_header_bytes": slot_hdr_size,
        "frame_slot_bytes": slot_size,
        "slot_0_offset": SLOT_0_OFFSET,
        "slot_1_offset": SLOT_1_OFFSET,
        "reserved_tail_offset": RESERVED_TAIL_OFFSET,
        "reserved_tail_bytes": RESERVED_TAIL_BYTES,
        "global_header_offsets": dict(EXPECTED_GLOBAL_HEADER_OFFSETS),
        "slot_offsets": dict(EXPECTED_SLOT_OFFSETS),
    }


# Validate layout immediately at module import time
verify_shm_layout()


# ============================================================================
# Windows x64 Atomic & Memory Barrier Primitives (Interlocked API)
# ============================================================================


class _Win64AtomicPrimitives:
    """Windows x64 Interlocked atomic operations and full memory barrier.

    On 64-bit Windows, InterlockedIncrement64 and InterlockedExchange are compiler
    intrinsics (`LOCK XADD`, `XCHG`, `MFENCE`) rather than exported functions in
    kernel32.dll. We allocate a read-only executable stub page using W^X
    (VirtualAlloc PAGE_READWRITE -> write instructions -> VirtualProtect PAGE_EXECUTE_READ)
    so Python calls real CPU hardware atomic instructions (`LOCK XADD`, `XCHG`, `MFENCE`)
    directly on the SharedMemory addresses. If VirtualProtect is ever unavailable,
    falls back to Win32 RtlInterlockedFlushSList / FlushProcessWriteBuffers barriers.
    """

    def __init__(self) -> None:
        self._stub_addr: int = 0
        self._inc64_fn = None
        self._xchg32_fn = None
        self._xchg64_fn = None
        self._mfence_fn = None
        self._fallback_flush_fn = None
        self.using_native_interlocked: bool = False
        self._init_primitives()

    def _init_primitives(self) -> None:
        if sys.platform != "win32":
            return

        try:
            k32 = ctypes.windll.kernel32
            if hasattr(k32, "FlushProcessWriteBuffers"):
                k32.FlushProcessWriteBuffers.argtypes = []
                k32.FlushProcessWriteBuffers.restype = None
                self._fallback_flush_fn = k32.FlushProcessWriteBuffers
            else:
                self._fallback_flush_fn = None

            # Only build x64 native stub on 64-bit Python
            if ctypes.sizeof(ctypes.c_void_p) != 8:
                return

            # Machine code layout (64 bytes aligned):
            # Offset 0:  InterlockedIncrement64(int64_t* rcx) -> int64_t (rax)
            #   48 C7 C0 01 00 00 00    mov rax, 1
            #   F0 48 0F C1 01          lock xadd [rcx], rax
            #   48 FF C0                inc rax
            #   C3                      ret
            # Offset 16: InterlockedExchange32(uint32_t* rcx, uint32_t edx) -> uint32_t (eax)
            #   89 D0                   mov eax, edx
            #   87 01                   xchg [rcx], eax
            #   C3                      ret
            # Offset 32: InterlockedExchange64(uint64_t* rcx, uint64_t rdx) -> uint64_t (rax)
            #   48 89 D0                mov rax, rdx
            #   48 87 01                xchg [rcx], rax
            #   C3                      ret
            # Offset 48: MemoryBarrier() -> void
            #   0F AE F0                mfence
            #   C3                      ret
            code = bytearray(64)
            code[0:16] = b"\x48\xc7\xc0\x01\x00\x00\x00\xf0\x48\x0f\xc1\x01\x48\xff\xc0\xc3"
            code[16:21] = b"\x89\xd0\x87\x01\xc3"
            code[32:39] = b"\x48\x89\xd0\x48\x87\x01\xc3"
            code[48:52] = b"\x0f\xae\xf0\xc3"

            k32.VirtualAlloc.argtypes = [
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.c_uint32,
                ctypes.c_uint32,
            ]
            k32.VirtualAlloc.restype = ctypes.c_void_p
            k32.VirtualProtect.argtypes = [
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            k32.VirtualProtect.restype = ctypes.c_int

            MEM_COMMIT_RESERVE = 0x1000 | 0x2000
            PAGE_READWRITE = 0x04
            PAGE_EXECUTE_READ = 0x20

            addr = k32.VirtualAlloc(None, 4096, MEM_COMMIT_RESERVE, PAGE_READWRITE)
            if not addr:
                return

            ctypes.memmove(addr, bytes(code), len(code))
            old_prot = ctypes.c_uint32(0)
            if not k32.VirtualProtect(addr, 4096, PAGE_EXECUTE_READ, ctypes.byref(old_prot)):
                return

            self._stub_addr = int(addr)
            self._inc64_fn = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_void_p)(self._stub_addr + 0)
            self._xchg32_fn = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32)(
                self._stub_addr + 16
            )
            self._xchg64_fn = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint64)(
                self._stub_addr + 32
            )
            self._mfence_fn = ctypes.CFUNCTYPE(None)(self._stub_addr + 48)
            self.using_native_interlocked = True
        except Exception:
            self.using_native_interlocked = False

    def memory_barrier(self) -> None:
        """Execute a full hardware memory barrier (MFENCE)."""
        if self._mfence_fn is not None:
            self._mfence_fn()
            return
        if self._fallback_flush_fn is not None:
            self._fallback_flush_fn()

    def interlocked_increment64(self, struct_obj: ctypes.Structure, field_name: str) -> int:
        """Atomically increment a 64-bit unsigned integer field with a full memory barrier."""
        field_descriptor = getattr(type(struct_obj), field_name)
        addr = ctypes.addressof(struct_obj) + field_descriptor.offset
        if self._inc64_fn is not None:
            return int(self._inc64_fn(addr))
        self.memory_barrier()
        new_val = (int(getattr(struct_obj, field_name)) + 1) & 0xFFFFFFFFFFFFFFFF
        setattr(struct_obj, field_name, new_val)
        self.memory_barrier()
        return new_val

    def interlocked_exchange32(self, struct_obj: ctypes.Structure, field_name: str, value: int) -> int:
        """Atomically exchange a 32-bit unsigned integer field with a full memory barrier."""
        field_descriptor = getattr(type(struct_obj), field_name)
        addr = ctypes.addressof(struct_obj) + field_descriptor.offset
        val32 = int(value) & 0xFFFFFFFF
        if self._xchg32_fn is not None:
            return int(self._xchg32_fn(addr, val32))
        self.memory_barrier()
        old_val = int(getattr(struct_obj, field_name))
        setattr(struct_obj, field_name, val32)
        self.memory_barrier()
        return old_val

    def interlocked_exchange64(self, struct_obj: ctypes.Structure, field_name: str, value: int) -> int:
        """Atomically exchange a 64-bit unsigned integer field with a full memory barrier."""
        field_descriptor = getattr(type(struct_obj), field_name)
        addr = ctypes.addressof(struct_obj) + field_descriptor.offset
        val64 = int(value) & 0xFFFFFFFFFFFFFFFF
        if self._xchg64_fn is not None:
            return int(self._xchg64_fn(addr, val64))
        self.memory_barrier()
        old_val = int(getattr(struct_obj, field_name))
        setattr(struct_obj, field_name, val64)
        self.memory_barrier()
        return old_val


_ATOMICS = _Win64AtomicPrimitives()


# ============================================================================
# Validated Frame Return Object
# ============================================================================


@dataclass(frozen=True)
class SharedFrameData:
    """Immutable validated Live View frame read from NikonSharedFrameBuffer."""

    rgb: np.ndarray
    jpeg: bytes
    width: int
    height: int
    sequence_id: int
    timestamp: float
    mono_ts: float
    fps: float
    worker_generation: int
    battery_percent: int
    slot_index: int
    slot_seq_lock: int
    jpeg_crc32: int
    is_valid: bool = True


# ============================================================================
# Collision-Free Shared Memory Buffer Implementation
# ============================================================================

_INSTANCE_COUNTER = itertools.count(1)


def generate_unique_shm_name(prefix: str = "vpb_nikon_lv", pid: Optional[int] = None) -> str:
    """Generate a collision-free SharedMemory name safe for multi-instance execution."""
    owner_pid = os.getpid() if pid is None else int(pid)
    instance_seq = next(_INSTANCE_COUNTER)
    short_token = uuid.uuid4().hex[:8]
    return f"{prefix}_{owner_pid}_{instance_seq}_{short_token}"


class NikonSharedFrameBuffer:
    """6 MiB Shared Memory Frame Buffer with Per-Slot Odd/Even Seqlock Protocol.

    Ownership model:
    - Owner (Main Process): creates with `create=True`. Responsible for calling
      `close()` and `unlink()` on shutdown.
    - Attacher (Worker Process or secondary reader): attaches with `create=False`
      and the exact `name`. Responsible for calling `close()` only (must NOT unlink).
    """

    def __init__(
        self,
        name: Optional[str] = None,
        create: bool = True,
        worker_generation: int = 1,
        heartbeat_timeout_ns: int = DEFAULT_HEARTBEAT_TIMEOUT_NS,
    ) -> None:
        if create:
            self._name = name if name else generate_unique_shm_name()
        else:
            if not name:
                raise ValueError("SharedMemory name must be provided when create=False")
            self._name = name

        self._lock = threading.RLock()
        self._active_operations: int = 0
        self._is_owner: bool = bool(create)
        self._closed: bool = False
        self._unlinked: bool = False
        self._heartbeat_timeout_ns: int = int(heartbeat_timeout_ns)

        if create:
            self._shm = shared_memory.SharedMemory(
                name=self._name,
                create=True,
                size=SHM_TOTAL_BYTES,
            )
        else:
            self._shm = shared_memory.SharedMemory(
                name=self._name,
                create=False,
            )
            if self._shm.size < SHM_TOTAL_BYTES:
                self._shm.close()
                raise ValueError(
                    f"Attached SharedMemory '{self._name}' size {self._shm.size} "
                    f"is smaller than required {SHM_TOTAL_BYTES} bytes"
                )

        # Resolve base memory address without keeping an exported PEP 3118 buffer lock on _mmap
        buf = self._shm.buf
        if buf is None:
            raise RuntimeError("SharedMemory buffer is None")

        tmp_byte = ctypes.c_uint8.from_buffer(buf, 0)
        self._base_addr: int = ctypes.addressof(tmp_byte)
        del tmp_byte

        self._global_header: Optional[GlobalControlHeader] = GlobalControlHeader.from_address(
            self._base_addr
        )
        self._slot0: Optional[FrameSlot] = FrameSlot.from_address(
            self._base_addr + SLOT_0_OFFSET
        )
        self._slot1: Optional[FrameSlot] = FrameSlot.from_address(
            self._base_addr + SLOT_1_OFFSET
        )
        self._slots: tuple[FrameSlot, ...] = (self._slot0, self._slot1)

        if create:
            self._initialize_header(worker_generation=worker_generation)

    def _initialize_header(self, worker_generation: int) -> None:
        """Zero and initialize GlobalControlHeader and both Slot headers on creation."""
        with self._lock:
            self._ensure_open()
            assert self._global_header is not None
            assert self._slot0 is not None
            assert self._slot1 is not None
            ctypes.memset(ctypes.addressof(self._global_header), 0, GLOBAL_HEADER_BYTES)
            ctypes.memset(ctypes.addressof(self._slot0), 0, SLOT_HEADER_BYTES)
            ctypes.memset(ctypes.addressof(self._slot1), 0, SLOT_HEADER_BYTES)

            self._global_header.magic = SHM_MAGIC
            self._global_header.schema_version = SHM_SCHEMA_VERSION
            self._global_header.published_slot = 0
            self._global_header.writer_state = WriterState.IDLE
            self._global_header.worker_pid = 0
            self._global_header.worker_generation = int(worker_generation)
            self._global_header.latest_sequence_id = 0
            self._global_header.worker_heartbeat_ns = time.monotonic_ns()
            self._global_header.source_fps = 0.0
            self._global_header.battery_percent = -1
            _ATOMICS.memory_barrier()

    @classmethod
    def attach(
        cls,
        name: str,
        heartbeat_timeout_ns: int = DEFAULT_HEARTBEAT_TIMEOUT_NS,
    ) -> "NikonSharedFrameBuffer":
        """Attach to an existing NikonSharedFrameBuffer by name (`create=False`)."""
        return cls(
            name=name,
            create=False,
            heartbeat_timeout_ns=heartbeat_timeout_ns,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> int:
        return SHM_TOTAL_BYTES

    @property
    def is_owner(self) -> bool:
        return self._is_owner

    @property
    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def is_unlinked(self) -> bool:
        with self._lock:
            return self._unlinked

    @property
    def base_address(self) -> int:
        """Return current mapped base address, or 0 if closed."""
        with self._lock:
            return 0 if self._closed else self._base_addr

    @property
    def active_operations(self) -> int:
        """Return count of currently active SharedMemory access operations."""
        with self._lock:
            return self._active_operations

    @property
    def global_header(self) -> GlobalControlHeader:
        with self._lock:
            self._ensure_open()
            assert self._global_header is not None
            return self._global_header

    @property
    def slots(self) -> tuple[FrameSlot, FrameSlot]:
        with self._lock:
            self._ensure_open()
            return self._slots  # type: ignore[return-value]

    def _ensure_open(self) -> None:
        if self._closed or self._base_addr == 0 or self._global_header is None:
            raise RuntimeError(f"NikonSharedFrameBuffer '{self._name}' is already closed")

    # ------------------------------------------------------------------------
    # Worker / Metadata Control Operations
    # ------------------------------------------------------------------------

    def bind_worker(
        self,
        worker_pid: int,
        worker_generation: int,
        writer_state: int = WriterState.IDLE,
    ) -> None:
        """Bind a new Worker Process generation and reset heartbeat."""
        with self._lock:
            self._ensure_open()
            self._active_operations += 1
            try:
                gh = self._global_header
                assert gh is not None
                gh.worker_pid = int(worker_pid)
                _ATOMICS.interlocked_exchange32(
                    gh, "writer_state", int(writer_state)
                )
                _ATOMICS.interlocked_exchange64(
                    gh, "worker_heartbeat_ns", time.monotonic_ns()
                )
                _ATOMICS.interlocked_exchange32(
                    gh, "worker_generation", int(worker_generation)
                )
            finally:
                self._active_operations -= 1

    def update_heartbeat(
        self,
        worker_generation: Optional[int] = None,
        writer_state: Optional[int] = None,
        source_fps: Optional[float] = None,
        battery_percent: Optional[int] = None,
        now_ns: Optional[int] = None,
    ) -> bool:
        """Update worker_heartbeat_ns (and optional telemetry fields) if generation matches."""
        with self._lock:
            self._ensure_open()
            self._active_operations += 1
            try:
                gh = self._global_header
                assert gh is not None
                if (
                    worker_generation is not None
                    and int(gh.worker_generation) != int(worker_generation)
                ):
                    return False

                if writer_state is not None:
                    _ATOMICS.interlocked_exchange32(
                        gh, "writer_state", int(writer_state)
                    )
                if source_fps is not None:
                    gh.source_fps = float(source_fps)
                if battery_percent is not None:
                    gh.battery_percent = int(battery_percent)

                hb_ns = time.monotonic_ns() if now_ns is None else int(now_ns)
                _ATOMICS.interlocked_exchange64(
                    gh, "worker_heartbeat_ns", hb_ns
                )
                return True
            finally:
                self._active_operations -= 1

    # ------------------------------------------------------------------------
    # Seqlock Writer Protocol (Worker Process)
    # ------------------------------------------------------------------------

    def write_frame(
        self,
        rgb: np.ndarray | bytes | memoryview,
        jpeg_bytes: bytes | bytearray | memoryview,
        sequence_id: int,
        worker_generation: int,
        capture_ts: Optional[float] = None,
        mono_ts: Optional[float] = None,
        width: int = DEFAULT_LIVE_VIEW_WIDTH,
        height: int = DEFAULT_LIVE_VIEW_HEIGHT,
        source_fps: Optional[float] = None,
        battery_percent: Optional[int] = None,
        target_slot_override: Optional[int] = None,
    ) -> int:
        """Write a complete Live View frame using the Per-Slot Odd/Even Seqlock protocol.

        Returns the slot index (0 or 1) written to.
        """
        with self._lock:
            self._ensure_open()
            self._active_operations += 1
            try:
                if int(sequence_id) <= 0:
                    raise ValueError(f"sequence_id must be > 0, got {sequence_id}")
                if int(width) <= 0 or int(height) <= 0:
                    raise ValueError(f"Invalid dimensions {width}x{height}")

                expected_rgb_len = int(width) * int(height) * 3
                if expected_rgb_len > SLOT_RGB_CAPACITY:
                    raise ValueError(
                        f"RGB frame size {expected_rgb_len} exceeds SLOT_RGB_CAPACITY ({SLOT_RGB_CAPACITY})"
                    )

                if isinstance(rgb, np.ndarray):
                    rgb_contiguous = np.ascontiguousarray(rgb, dtype=np.uint8)
                    rgb_raw = rgb_contiguous.view(np.uint8).reshape(-1)
                    rgb_len = int(rgb_raw.nbytes)
                    rgb_ptr = rgb_raw.ctypes.data
                else:
                    rgb_mv = memoryview(rgb).cast("B")
                    rgb_len = len(rgb_mv)
                    rgb_ptr = None

                if rgb_len != expected_rgb_len:
                    raise ValueError(
                        f"RGB byte length mismatch: expected {expected_rgb_len} for {width}x{height}x3, got {rgb_len}"
                    )

                jpeg_raw = bytes(jpeg_bytes)
                jpeg_len = len(jpeg_raw)
                if not (MIN_VALID_JPEG_BYTES <= jpeg_len <= SLOT_JPEG_CAPACITY):
                    raise ValueError(
                        f"JPEG byte length {jpeg_len} out of bounds [{MIN_VALID_JPEG_BYTES}, {SLOT_JPEG_CAPACITY}]"
                    )

                gh = self._global_header
                assert gh is not None

                # 1. Select target slot (opposite of currently published slot unless overridden)
                if target_slot_override is not None:
                    target_slot_idx = int(target_slot_override) & 1
                else:
                    target_slot_idx = 1 - (int(gh.published_slot) & 1)

                slot = self._slots[target_slot_idx]

                # 2. Begin Write Phase (Finding M-01 fix):
                #    FIRST mark frame_valid = 0 atomically (with full barrier) BEFORE touching
                #    slot_seq_lock so slot_seq_lock is NEVER observed as EVEN while frame_valid != 0.
                #    If slot_seq_lock was EVEN, increment once (+1) to ODD.
                #    If slot_seq_lock was already ODD (previous writer crashed mid-write),
                #    advance by +2 (via two atomic increments AFTER frame_valid is already 0)
                #    or keep ODD so any reader sees an odd generation and frame_valid == 0.
                _ATOMICS.interlocked_exchange32(
                    slot, "frame_valid", FrameValidState.INVALID_OR_WRITING
                )
                current_seq = int(slot.slot_seq_lock)
                if (current_seq & 1) == 0:
                    odd_seq = _ATOMICS.interlocked_increment64(slot, "slot_seq_lock")
                else:
                    # Slot was left in ODD state by a crashed writer while frame_valid is now 0.
                    # Keep it in the ODD state with a full hardware memory barrier so it never
                    # transiently passes through an EVEN value before payload write completes.
                    _ATOMICS.memory_barrier()
                    odd_seq = int(slot.slot_seq_lock)
                assert (odd_seq & 1) == 1, f"Expected odd slot_seq_lock during write, got {odd_seq}"

                # 3. Write Payload (RGB + JPEG + Metadata + CRC32)
                slot_base_addr = ctypes.addressof(slot)
                rgb_dest_addr = slot_base_addr + FrameSlot.rgb_buffer.offset
                jpeg_dest_addr = slot_base_addr + FrameSlot.jpeg_buffer.offset

                if rgb_ptr is not None:
                    ctypes.memmove(rgb_dest_addr, rgb_ptr, rgb_len)
                else:
                    ctypes.memmove(rgb_dest_addr, bytes(rgb), rgb_len)

                ctypes.memmove(jpeg_dest_addr, jpeg_raw, jpeg_len)

                now_wall = time.time() if capture_ts is None else float(capture_ts)
                now_mono = time.perf_counter() if mono_ts is None else float(mono_ts)
                crc32_val = zlib.crc32(jpeg_raw) & 0xFFFFFFFF

                slot.slot_worker_gen = int(worker_generation)
                slot.sequence_id = int(sequence_id)
                slot.capture_ts = now_wall
                slot.mono_ts = now_mono
                slot.width = int(width)
                slot.height = int(height)
                slot.rgb_bytes_len = rgb_len
                slot.jpeg_bytes_len = jpeg_len
                slot.jpeg_crc32 = crc32_val

                # 4. Commit Phase (Finding M-02 Store-Release ordering):
                #    4a. Full barrier after payload & slot metadata writes.
                #    4b. Mark slot.frame_valid = 1 (atomic XCHG).
                #    4c. Increment slot.slot_seq_lock to EVEN (atomic LOCK XADD).
                #    4d. Update GlobalHeader telemetry & worker_generation.
                #    4e. Update worker_heartbeat_ns FIRST, then published_slot, and
                #        FINALLY latest_sequence_id LAST so any Reader observing the new
                #        latest_sequence_id is guaranteed to see fresh heartbeat & published_slot.
                _ATOMICS.memory_barrier()
                _ATOMICS.interlocked_exchange32(
                    slot, "frame_valid", FrameValidState.VALID_COMMITTED
                )
                even_seq = _ATOMICS.interlocked_increment64(slot, "slot_seq_lock")
                assert (even_seq & 1) == 0, f"Expected even slot_seq_lock on commit, got {even_seq}"

                if int(gh.worker_generation) != int(worker_generation):
                    _ATOMICS.interlocked_exchange32(
                        gh, "worker_generation", int(worker_generation)
                    )
                if source_fps is not None:
                    gh.source_fps = float(source_fps)
                if battery_percent is not None:
                    gh.battery_percent = int(battery_percent)

                _ATOMICS.interlocked_exchange64(
                    gh, "worker_heartbeat_ns", time.monotonic_ns()
                )
                _ATOMICS.interlocked_exchange32(
                    gh, "published_slot", target_slot_idx
                )
                _ATOMICS.interlocked_exchange64(
                    gh, "latest_sequence_id", int(sequence_id)
                )

                return target_slot_idx
            finally:
                self._active_operations -= 1

    # ------------------------------------------------------------------------
    # Seqlock Reader & Validation Protocol (Main Process)
    # ------------------------------------------------------------------------

    def read_latest_frame(
        self,
        last_seen_seq_id: int = 0,
        expected_worker_gen: Optional[int] = None,
        heartbeat_timeout_ns: Optional[int] = None,
        now_monotonic_ns: Optional[int] = None,
        _test_copy_hook: Optional[Callable[[int, FrameSlot], None]] = None,
    ) -> Optional[SharedFrameData]:
        """Read and validate the latest complete frame using Per-Slot Seqlock verification.

        Guarantees:
        - Protected by RLock against concurrent close()/unlink() unmapping (Finding H-01).
        - Uses Load-Acquire memory ordering paired with write_frame's Store-Release (Finding M-02).
        - Returns None if magic or schema_version is invalid.
        - Returns None if worker_generation does not match expected_worker_gen.
        - Returns None if worker_heartbeat_ns is older than heartbeat_timeout_ns.
        - Returns None if no frame newer than last_seen_seq_id exists.
        - Discards any slot where slot_seq_lock is 0 or ODD, or where gen1 != gen2 after copy.
        - Discards any slot where frame_valid != 1 before or after copy.
        - Discards any slot with invalid JPEG SOI/EOI markers or mismatched CRC32.
        """
        with self._lock:
            self._ensure_open()
            self._active_operations += 1
            try:
                gh = self._global_header
                assert gh is not None

                # Load-Acquire barrier before reading GlobalControlHeader state
                _ATOMICS.memory_barrier()

                # 1. Validate Global Header magic and schema_version
                if int(gh.magic) != SHM_MAGIC or int(gh.schema_version) != SHM_SCHEMA_VERSION:
                    return None

                # Read latest_sequence_id first (published last by Writer), then issue barrier
                latest_seq = int(gh.latest_sequence_id)
                _ATOMICS.memory_barrier()

                header_worker_gen = int(gh.worker_generation)
                if expected_worker_gen is not None and header_worker_gen != int(expected_worker_gen):
                    return None

                # 2. Validate Worker Heartbeat freshness
                timeout_ns = (
                    self._heartbeat_timeout_ns
                    if heartbeat_timeout_ns is None
                    else int(heartbeat_timeout_ns)
                )
                if timeout_ns > 0:
                    now_ns = time.monotonic_ns() if now_monotonic_ns is None else int(now_monotonic_ns)
                    hb_ns = int(gh.worker_heartbeat_ns)
                    if hb_ns <= 0 or (now_ns - hb_ns) > timeout_ns:
                        return None

                # 3. Check if any newer frame has been published
                if latest_seq <= int(last_seen_seq_id):
                    return None

                # 4. Try published_slot first; if torn or invalid, fallback to the secondary slot
                primary_idx = int(gh.published_slot) & 1
                candidate_indices = (primary_idx, 1 - primary_idx)

                for slot_idx in candidate_indices:
                    if self._closed or self._base_addr == 0:
                        return None
                    slot = self._slots[slot_idx]
                    for _attempt in range(2):
                        if self._closed or self._base_addr == 0:
                            return None

                        gen1 = int(slot.slot_seq_lock)
                        _ATOMICS.memory_barrier()

                        # Must be committed (non-zero EVEN)
                        if gen1 == 0 or (gen1 & 1) != 0:
                            break

                        if int(slot.frame_valid) != FrameValidState.VALID_COMMITTED:
                            break

                        slot_gen = int(slot.slot_worker_gen)
                        if expected_worker_gen is not None and slot_gen != int(expected_worker_gen):
                            break
                        if slot_gen != header_worker_gen:
                            break

                        seq_id = int(slot.sequence_id)
                        if seq_id <= int(last_seen_seq_id):
                            break

                        w = int(slot.width)
                        h = int(slot.height)
                        rgb_len = int(slot.rgb_bytes_len)
                        jpeg_len = int(slot.jpeg_bytes_len)
                        expected_crc = int(slot.jpeg_crc32) & 0xFFFFFFFF
                        cap_ts = float(slot.capture_ts)
                        m_ts = float(slot.mono_ts)

                        if (
                            w <= 0
                            or h <= 0
                            or rgb_len != (w * h * 3)
                            or rgb_len > SLOT_RGB_CAPACITY
                            or not (MIN_VALID_JPEG_BYTES <= jpeg_len <= SLOT_JPEG_CAPACITY)
                        ):
                            break

                        # Copy RGB and JPEG payloads into private Main Process memory
                        rgb_copy = (
                            np.frombuffer(slot.rgb_buffer, dtype=np.uint8, count=rgb_len)
                            .reshape((h, w, 3))
                            .copy()
                        )
                        jpeg_copy = bytes(
                            memoryview(slot.jpeg_buffer)[:jpeg_len]
                        )

                        # Optional deterministic fault-injection hook for unit testing concurrent overwrite
                        if _test_copy_hook is not None:
                            _test_copy_hook(slot_idx, slot)
                            # Guard against reentrant close() inside _test_copy_hook
                            if self._closed or self._base_addr == 0:
                                return None

                        # Seqlock Post-Copy Verification (full barrier before reading gen2 & frame_valid)
                        _ATOMICS.memory_barrier()
                        gen2 = int(slot.slot_seq_lock)
                        valid_after = int(slot.frame_valid)
                        slot_gen_after = int(slot.slot_worker_gen)

                        if (
                            gen1 != gen2
                            or (gen2 & 1) != 0
                            or valid_after != FrameValidState.VALID_COMMITTED
                            or slot_gen_after != slot_gen
                        ):
                            # Concurrent overwrite occurred during copy -> discard torn copy immediately!
                            continue

                        # Validate JPEG SOI/EOI markers and CRC32 checksum
                        if (
                            jpeg_copy[:2] != JPEG_SOI_MARKER
                            or jpeg_copy[-2:] != JPEG_EOI_MARKER
                        ):
                            break

                        actual_crc = zlib.crc32(jpeg_copy) & 0xFFFFFFFF
                        if actual_crc != expected_crc:
                            break

                        return SharedFrameData(
                            rgb=rgb_copy,
                            jpeg=jpeg_copy,
                            width=w,
                            height=h,
                            sequence_id=seq_id,
                            timestamp=cap_ts,
                            mono_ts=m_ts,
                            fps=float(gh.source_fps),
                            worker_generation=slot_gen,
                            battery_percent=int(gh.battery_percent),
                            slot_index=slot_idx,
                            slot_seq_lock=gen2,
                            jpeg_crc32=actual_crc,
                            is_valid=True,
                        )

                return None
            finally:
                self._active_operations -= 1

    # ------------------------------------------------------------------------
    # Resource Lifecycle Management (close & unlink)
    # ------------------------------------------------------------------------

    def close(self) -> None:
        """Close local SharedMemory mapping handle safely under RLock."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._base_addr = 0
            self._slots = ()
            self._slot0 = None
            self._slot1 = None
            self._global_header = None
            try:
                self._shm.close()
            except Exception:
                pass

    def unlink(self) -> None:
        """Unlink the SharedMemory segment (only executed by the creating owner)."""
        with self._lock:
            if self._unlinked:
                return
            if not self._is_owner:
                return
            self._unlinked = True
            if not self._closed:
                self.close()
            try:
                self._shm.unlink()
            except FileNotFoundError:
                pass
            except Exception:
                pass

    def __enter__(self) -> "NikonSharedFrameBuffer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
        if self._is_owner:
            self.unlink()
