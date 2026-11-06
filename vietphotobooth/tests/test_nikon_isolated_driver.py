"""Unit Tests for Phase 1 of Nikon D780 Process-Isolated Driver Worker.

Covers:
1. Shared Memory layout and total size (6 MiB = 6,291,456 bytes).
2. Exact field offsets and alignments of GlobalControlHeader, SlotHeader, and FrameSlot.
3. Per-Slot Seqlock writer/reader normal round-trip & Windows Interlocked atomic primitives.
4. Reader encountering torn frames (odd slot_seq_lock and concurrent overwrite during copy).
5. Invalid CRC32 rejection.
6. Invalid JPEG SOI/EOI marker rejection.
7. Mismatched worker_generation rejection.
8. Stale sequence_id and stale worker_heartbeat_ns timeout rejection.
9. IPC Protocol v1 request/response correlation and schema validation (zero MAID imports).
10. Transaction cancellation and timeout state transitions.
11. Late event rejection (wrong generation, wrong instance_id, wrong tx_id, cancelled/timed-out tx_id).
12. Shared Memory close() and unlink() lifecycle (owner vs attacher).
13. Concurrent multi-instance execution without Shared Memory name collision or cross-talk.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
import time
import zlib

import numpy as np
import pytest

from vietphotobooth.camera.backends.nikon_maid import ipc_protocol, shm_frame_buffer
from vietphotobooth.camera.backends.nikon_maid.ipc_protocol import (
    DEFAULT_CAPTURE_TIMEOUT_S,
    IPCCommandMethod,
    IPCErrorCode,
    IPCEvent,
    IPCEventName,
    IPCMessageType,
    IPCProtocolError,
    IPCRequest,
    IPCResponse,
    IPCTransactionManager,
    PROTOCOL_VERSION,
    TransactionState,
    map_maid_result_to_ipc_error,
    validate_message_schema,
)
from vietphotobooth.camera.backends.nikon_maid.shm_frame_buffer import (
    DEFAULT_LIVE_VIEW_HEIGHT,
    DEFAULT_LIVE_VIEW_WIDTH,
    DEFAULT_RGB_BYTES_LEN,
    FRAME_SLOT_BYTES,
    FrameSlot,
    FrameValidState,
    GLOBAL_HEADER_BYTES,
    GlobalControlHeader,
    NikonSharedFrameBuffer,
    RESERVED_TAIL_BYTES,
    RESERVED_TAIL_OFFSET,
    SHM_MAGIC,
    SHM_SCHEMA_VERSION,
    SHM_TOTAL_BYTES,
    SLOT_0_OFFSET,
    SLOT_1_OFFSET,
    SLOT_HEADER_BYTES,
    SLOT_JPEG_CAPACITY,
    SLOT_RGB_CAPACITY,
    SlotHeader,
    WriterState,
    _ATOMICS,
    verify_shm_layout,
)


# ============================================================================
# Helpers for Synthetic Valid Frame Generation
# ============================================================================


def _make_synthetic_frame(
    seed: int = 1,
    width: int = DEFAULT_LIVE_VIEW_WIDTH,
    height: int = DEFAULT_LIVE_VIEW_HEIGHT,
) -> tuple[np.ndarray, bytes]:
    """Create a deterministic RGB array (680x1024x3) and valid JPEG byte payload."""
    rng = np.random.default_rng(seed)
    rgb = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    body = rng.bytes(1024)
    jpeg_bytes = b"\xff\xd8\xff\xe0" + seed.to_bytes(4, "little") + body + b"\xff\xd9"
    return rgb, jpeg_bytes


# ============================================================================
# 1 & 2. Shared Memory Layout, Total Size, Field Offsets & Alignments
# ============================================================================


def test_shm_layout_and_total_size() -> None:
    """Verify 6 MiB total size, structure sizes, and region offsets."""
    layout = verify_shm_layout()
    assert layout["total_bytes"] == 6 * 1024 * 1024 == 6_291_456
    assert SHM_TOTAL_BYTES == 6_291_456
    assert ctypes.sizeof(GlobalControlHeader) == GLOBAL_HEADER_BYTES == 256
    assert ctypes.sizeof(SlotHeader) == SLOT_HEADER_BYTES == 64
    assert ctypes.sizeof(FrameSlot) == FRAME_SLOT_BYTES == 2_621_504
    assert SLOT_RGB_CAPACITY == 2_097_152
    assert SLOT_JPEG_CAPACITY == 524_288
    assert SLOT_0_OFFSET == 256
    assert SLOT_1_OFFSET == 2_621_760
    assert RESERVED_TAIL_OFFSET == 5_243_264
    assert RESERVED_TAIL_BYTES == 1_048_192
    assert GLOBAL_HEADER_BYTES + 2 * FRAME_SLOT_BYTES + RESERVED_TAIL_BYTES == SHM_TOTAL_BYTES


def test_shm_field_offsets_and_alignments() -> None:
    """Verify exact byte offset and natural alignment of every field in GlobalControlHeader & FrameSlot."""
    # GlobalControlHeader field offsets
    assert GlobalControlHeader.magic.offset == 0
    assert GlobalControlHeader.schema_version.offset == 4
    assert GlobalControlHeader.published_slot.offset == 8
    assert GlobalControlHeader.writer_state.offset == 12
    assert GlobalControlHeader.worker_pid.offset == 16
    assert GlobalControlHeader.worker_generation.offset == 20
    assert GlobalControlHeader.latest_sequence_id.offset == 24
    assert GlobalControlHeader.worker_heartbeat_ns.offset == 32
    assert GlobalControlHeader.source_fps.offset == 40
    assert GlobalControlHeader.battery_percent.offset == 44
    assert GlobalControlHeader.reserved.offset == 48
    assert GlobalControlHeader.reserved.size == 208

    # Natural 8-byte alignment for 64-bit atomic fields
    assert GlobalControlHeader.latest_sequence_id.offset % 8 == 0
    assert GlobalControlHeader.worker_heartbeat_ns.offset % 8 == 0
    assert GlobalControlHeader.published_slot.offset % 4 == 0

    # SlotHeader & FrameSlot field offsets
    for cls in (SlotHeader, FrameSlot):
        assert cls.slot_seq_lock.offset == 0
        assert cls.frame_valid.offset == 8
        assert cls.slot_worker_gen.offset == 12
        assert cls.sequence_id.offset == 16
        assert cls.capture_ts.offset == 24
        assert cls.mono_ts.offset == 32
        assert cls.width.offset == 40
        assert cls.height.offset == 44
        assert cls.rgb_bytes_len.offset == 48
        assert cls.jpeg_bytes_len.offset == 52
        assert cls.jpeg_crc32.offset == 56
        assert cls.header_pad.offset == 60

        # 64-bit fields must be 8-byte aligned
        assert cls.slot_seq_lock.offset % 8 == 0
        assert cls.sequence_id.offset % 8 == 0
        assert cls.capture_ts.offset % 8 == 0
        assert cls.mono_ts.offset % 8 == 0

    assert FrameSlot.rgb_buffer.offset == 64
    assert FrameSlot.rgb_buffer.size == 2_097_152
    assert FrameSlot.jpeg_buffer.offset == 2_097_216
    assert FrameSlot.jpeg_buffer.size == 524_288


# ============================================================================
# 3. Seqlock Writer/Reader Normal Round-Trip & Atomic Primitives
# ============================================================================


def test_seqlock_writer_reader_normal_roundtrip() -> None:
    """Verify normal write/read round-trip across alternating slots and atomic primitives."""
    if sys.platform == "win32" and ctypes.sizeof(ctypes.c_void_p) == 8:
        assert _ATOMICS.using_native_interlocked is True

    with NikonSharedFrameBuffer(create=True, worker_generation=3) as owner_buf:
        worker_buf = NikonSharedFrameBuffer.attach(owner_buf.name)
        try:
            worker_buf.bind_worker(
                worker_pid=12345,
                worker_generation=3,
                writer_state=WriterState.STREAMING,
            )

            # Before any frame is written, read_latest_frame returns None
            assert owner_buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=3) is None

            # Write Frame 1 -> should go to Slot 1 (since initial published_slot is 0)
            rgb1, jpeg1 = _make_synthetic_frame(seed=101)
            slot_idx1 = worker_buf.write_frame(
                rgb=rgb1,
                jpeg_bytes=jpeg1,
                sequence_id=1,
                worker_generation=3,
                source_fps=27.73,
                battery_percent=60,
            )
            assert slot_idx1 == 1
            assert owner_buf.global_header.published_slot == 1
            assert owner_buf.slots[1].slot_seq_lock == 2  # Even committed
            assert owner_buf.slots[1].frame_valid == FrameValidState.VALID_COMMITTED

            frame1 = owner_buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=3)
            assert frame1 is not None
            assert frame1.is_valid is True
            assert frame1.sequence_id == 1
            assert frame1.worker_generation == 3
            assert frame1.slot_index == 1
            assert frame1.slot_seq_lock == 2
            assert frame1.width == DEFAULT_LIVE_VIEW_WIDTH
            assert frame1.height == DEFAULT_LIVE_VIEW_HEIGHT
            assert pytest.approx(frame1.fps, rel=1e-4) == 27.73
            assert frame1.battery_percent == 60
            assert frame1.jpeg == jpeg1
            assert np.array_equal(frame1.rgb, rgb1)

            # Write Frame 2 -> should flip to Slot 0
            rgb2, jpeg2 = _make_synthetic_frame(seed=202)
            slot_idx2 = worker_buf.write_frame(
                rgb=rgb2,
                jpeg_bytes=jpeg2,
                sequence_id=2,
                worker_generation=3,
                source_fps=28.10,
                battery_percent=59,
            )
            assert slot_idx2 == 0
            assert owner_buf.global_header.published_slot == 0
            assert owner_buf.slots[0].slot_seq_lock == 2

            frame2 = owner_buf.read_latest_frame(last_seen_seq_id=1, expected_worker_gen=3)
            assert frame2 is not None
            assert frame2.sequence_id == 2
            assert frame2.slot_index == 0
            assert frame2.jpeg == jpeg2
            assert np.array_equal(frame2.rgb, rgb2)
        finally:
            worker_buf.close()


# ============================================================================
# 4. Reader Encountering Torn Frame (Mid-Write Odd Seqlock & Overwrite During Copy)
# ============================================================================


def test_reader_detects_torn_frame_and_falls_back_or_rejects() -> None:
    """Verify Reader never returns a frame when a slot is torn during copy or left in odd state."""
    with NikonSharedFrameBuffer(create=True, worker_generation=1) as buf:
        rgb1, jpeg1 = _make_synthetic_frame(seed=1)
        rgb2, jpeg2 = _make_synthetic_frame(seed=2)

        # Write Frame 1 into Slot 1, Frame 2 into Slot 0
        buf.write_frame(rgb=rgb1, jpeg_bytes=jpeg1, sequence_id=1, worker_generation=1)
        buf.write_frame(rgb=rgb2, jpeg_bytes=jpeg2, sequence_id=2, worker_generation=1)
        assert buf.global_header.published_slot == 0

        # Case A: Simulate concurrent Writer starting to overwrite Slot 0 (published_slot)
        # right while Reader is in the middle of copying Slot 0.
        # Reader must discard Slot 0 and fall back to Slot 1 (Frame 1)!
        hook_triggered = {"count": 0}

        def simulate_concurrent_overwrite_on_slot0(slot_idx: int, slot_obj: FrameSlot) -> None:
            if slot_idx == 0 and hook_triggered["count"] == 0:
                hook_triggered["count"] += 1
                # Writer increments slot_seq_lock to ODD and sets frame_valid = 0
                slot_obj.frame_valid = FrameValidState.INVALID_OR_WRITING
                _ATOMICS.interlocked_increment64(slot_obj, "slot_seq_lock")

        fallback_frame = buf.read_latest_frame(
            last_seen_seq_id=0,
            expected_worker_gen=1,
            _test_copy_hook=simulate_concurrent_overwrite_on_slot0,
        )
        assert hook_triggered["count"] == 1
        assert fallback_frame is not None
        # Must NOT return torn Slot 0 (seq 2); must cleanly return fallback Slot 1 (seq 1)
        assert fallback_frame.slot_index == 1
        assert fallback_frame.sequence_id == 1
        assert fallback_frame.jpeg == jpeg1
        assert np.array_equal(fallback_frame.rgb, rgb1)

        # Case B: If last_seen_seq_id == 1 and Slot 0 is still ODD (mid-write),
        # Reader must return None (never return torn Slot 0 or already-seen Slot 1).
        assert (buf.slots[0].slot_seq_lock & 1) == 1
        assert buf.read_latest_frame(last_seen_seq_id=1, expected_worker_gen=1) is None

        # Case C: Simulate Writer completing a full overwrite during Reader's copy
        # (gen1=2 before copy -> Writer increments twice to gen2=4 during copy).
        # Even though gen2 is EVEN and frame_valid==1, gen1 != gen2 must reject that attempt!
        buf.write_frame(rgb=rgb2, jpeg_bytes=jpeg2, sequence_id=3, worker_generation=1)
        published_idx = buf.global_header.published_slot
        other_idx = 1 - published_idx
        # Invalidate the secondary slot so only published_idx has a newer frame
        buf.slots[other_idx].frame_valid = FrameValidState.INVALID_OR_WRITING

        def simulate_fast_double_increment(slot_idx: int, slot_obj: FrameSlot) -> None:
            # Every time Reader copies, Writer advances slot_seq_lock by +2 (even -> even)
            _ATOMICS.interlocked_increment64(slot_obj, "slot_seq_lock")
            _ATOMICS.interlocked_increment64(slot_obj, "slot_seq_lock")

        rejected = buf.read_latest_frame(
            last_seen_seq_id=2,
            expected_worker_gen=1,
            _test_copy_hook=simulate_fast_double_increment,
        )
        assert rejected is None


# ============================================================================
# 5. Invalid CRC32 Rejection
# ============================================================================


def test_reader_rejects_invalid_crc32() -> None:
    """Verify Reader rejects a frame whose JPEG payload fails CRC32 verification."""
    with NikonSharedFrameBuffer(create=True, worker_generation=1) as buf:
        rgb, jpeg = _make_synthetic_frame(seed=55)
        slot_idx = buf.write_frame(
            rgb=rgb,
            jpeg_bytes=jpeg,
            sequence_id=10,
            worker_generation=1,
        )
        # Corrupt a byte in the middle of the JPEG buffer without updating jpeg_crc32
        slot = buf.slots[slot_idx]
        slot.jpeg_buffer[10] ^= 0xFF

        assert buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1) is None


# ============================================================================
# 6. Invalid JPEG Marker (SOI / EOI) Rejection
# ============================================================================


def test_reader_rejects_invalid_jpeg_markers() -> None:
    """Verify Reader rejects frames missing SOI (0xFFD8) or EOI (0xFFD9) even if CRC32 matches."""
    with NikonSharedFrameBuffer(create=True, worker_generation=1) as buf:
        rgb, valid_jpeg = _make_synthetic_frame(seed=66)

        # Bad SOI marker (starts with 0x00 0x00 instead of 0xFF 0xD8), even with matching CRC32
        bad_soi_jpeg = b"\x00\x00" + valid_jpeg[2:]
        buf.write_frame(
            rgb=rgb,
            jpeg_bytes=bad_soi_jpeg,
            sequence_id=1,
            worker_generation=1,
        )
        assert buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1) is None

        # Bad EOI marker (ends with 0x00 0x00 instead of 0xFF 0xD9), even with matching CRC32
        bad_eoi_jpeg = valid_jpeg[:-2] + b"\x00\x00"
        buf.write_frame(
            rgb=rgb,
            jpeg_bytes=bad_eoi_jpeg,
            sequence_id=2,
            worker_generation=1,
        )
        assert buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1) is None


# ============================================================================
# 7. Mismatched worker_generation Rejection
# ============================================================================


def test_reader_rejects_mismatched_worker_generation() -> None:
    """Verify Reader rejects frames from an old or mismatched worker_generation."""
    with NikonSharedFrameBuffer(create=True, worker_generation=1) as buf:
        rgb, jpeg = _make_synthetic_frame(seed=77)
        buf.write_frame(rgb=rgb, jpeg_bytes=jpeg, sequence_id=1, worker_generation=1)

        # Reading with expected_worker_gen=2 must reject generation 1 frame
        assert buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=2) is None

        # Even if GlobalControlHeader.worker_generation is bumped to 2 by Supervisor,
        # the old slot still has slot_worker_gen == 1 and must be rejected!
        buf.bind_worker(worker_pid=9999, worker_generation=2)
        assert buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=2) is None

        # Once Worker generation 2 writes a fresh frame, it is accepted
        buf.write_frame(rgb=rgb, jpeg_bytes=jpeg, sequence_id=2, worker_generation=2)
        frame = buf.read_latest_frame(last_seen_seq_id=1, expected_worker_gen=2)
        assert frame is not None
        assert frame.worker_generation == 2
        assert frame.sequence_id == 2


# ============================================================================
# 8. Stale sequence_id and Stale Heartbeat Timeout Rejection
# ============================================================================


def test_reader_rejects_stale_sequence_id_and_stale_heartbeat() -> None:
    """Verify Reader rejects already-seen sequence_id and expired worker_heartbeat_ns."""
    with NikonSharedFrameBuffer(
        create=True,
        worker_generation=1,
        heartbeat_timeout_ns=1_500_000_000,
    ) as buf:
        rgb, jpeg = _make_synthetic_frame(seed=88)
        buf.write_frame(rgb=rgb, jpeg_bytes=jpeg, sequence_id=5, worker_generation=1)

        # First read with last_seen_seq_id=0 succeeds
        frame = buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1)
        assert frame is not None
        assert frame.sequence_id == 5

        # Reading again with last_seen_seq_id=5 or 6 returns None (no duplicate frames)
        assert buf.read_latest_frame(last_seen_seq_id=5, expected_worker_gen=1) is None
        assert buf.read_latest_frame(last_seen_seq_id=6, expected_worker_gen=1) is None

        # Simulate stale heartbeat (> 1.5s old) -> must return None even forlast_seen_seq_id=0
        future_ns = int(buf.global_header.worker_heartbeat_ns) + 2_000_000_000
        assert (
            buf.read_latest_frame(
                last_seen_seq_id=0,
                expected_worker_gen=1,
                now_monotonic_ns=future_ns,
            )
            is None
        )


# ============================================================================
# 9. IPC Request/Response Correlation, Schema Validation & Zero MAID Imports
# ============================================================================


def test_ipc_request_response_correlation_and_schema_validation() -> None:
    """Verify Protocol v1 schema validation, correlation, error mapping, and zero MAID imports."""
    # Ensure neither shm_frame_buffer nor ipc_protocol imported any Nikon MAID module
    for forbidden_mod in (
        "vietphotobooth.camera.backends.nikon_maid.maid_loader",
        "vietphotobooth.camera.backends.nikon_maid.maid_session",
    ):
        assert forbidden_mod not in shm_frame_buffer.__dict__.values()
        assert forbidden_mod not in ipc_protocol.__dict__.values()

    mgr = IPCTransactionManager(worker_generation=1, worker_instance_id="wrk_gen1_test01")
    req = mgr.create_request(
        method=IPCCommandMethod.START_LIVE_VIEW,
        params={"width": 1024, "height": 680},
        timeout_s=5.0,
        now_mono=100.0,
    )
    req_dict = req.to_dict()
    assert req_dict["protocol_version"] == PROTOCOL_VERSION == 1
    assert req_dict["msg_type"] == IPCMessageType.COMMAND.value
    assert req_dict["worker_generation"] == 1
    assert req_dict["worker_instance_id"] == "wrk_gen1_test01"
    assert req_dict["tx_id"] is None

    # Round-trip serialization
    parsed_req = IPCRequest.from_dict(req_dict)
    assert parsed_req == req

    # Unknown request_id response is rejected
    unknown_resp = IPCResponse(
        request_id="req_nonexistent",
        worker_generation=1,
        worker_instance_id="wrk_gen1_test01",
        ok=True,
    )
    outcome_unknown = mgr.validate_and_consume_response(unknown_resp, now_mono=101.0)
    assert outcome_unknown.accepted is False
    assert outcome_unknown.reason_code == IPCErrorCode.UNKNOWN_REQUEST_ID

    # Valid correlated response is accepted
    valid_resp = IPCResponse(
        request_id=req.request_id,
        worker_generation=1,
        worker_instance_id="wrk_gen1_test01",
        ok=True,
        result={"live_view": True},
    )
    outcome_ok = mgr.validate_and_consume_response(valid_resp, now_mono=101.0)
    assert outcome_ok.accepted is True
    assert outcome_ok.reason_code == IPCErrorCode.OK

    # Duplicate response for the same request_id is rejected
    outcome_dup = mgr.validate_and_consume_response(valid_resp, now_mono=101.5)
    assert outcome_dup.accepted is False
    assert outcome_dup.reason_code == IPCErrorCode.UNKNOWN_REQUEST_ID

    # Protocol version mismatch is rejected
    bad_ver_dict = valid_resp.to_dict()
    bad_ver_dict["protocol_version"] = 99
    outcome_bad_ver = mgr.validate_and_consume_response(bad_ver_dict, now_mono=101.0)
    assert outcome_bad_ver.accepted is False
    assert outcome_bad_ver.reason_code == IPCErrorCode.PROTOCOL_VERSION_MISMATCH

    # Verify MAID numeric error mapping
    assert map_maid_result_to_ipc_error(0) == (IPCErrorCode.OK, False)
    assert map_maid_result_to_ipc_error(137) == (IPCErrorCode.NIKON_OUT_OF_FOCUS, False)
    assert map_maid_result_to_ipc_error(152) == (IPCErrorCode.NIKON_DEVICE_BUSY, False)
    assert map_maid_result_to_ipc_error(147) == (IPCErrorCode.NIKON_BATTERY_EXHAUSTED, False)
    assert map_maid_result_to_ipc_error(-116) == (IPCErrorCode.NIKON_MAID_SESSION_CORRUPTED, True)
    assert map_maid_result_to_ipc_error(-119) == (IPCErrorCode.NIKON_MAID_SESSION_CORRUPTED, True)


# ============================================================================
# 10. Transaction Cancellation and Timeout
# ============================================================================


def test_transaction_cancellation_and_timeout() -> None:
    """Verify CaptureTransaction cancellation and timeout state transitions."""
    mgr = IPCTransactionManager(worker_generation=2, worker_instance_id="wrk_gen2_inst")

    # 1. Start Capture Transaction A and cancel it
    req_a, tx_a = mgr.begin_capture_transaction(timeout_s=DEFAULT_CAPTURE_TIMEOUT_S, now_mono=200.0)
    assert tx_a.state == TransactionState.PENDING
    assert mgr.active_capture_transaction is tx_a

    # Worker sends capture_started event -> transitions to STARTED
    evt_started = IPCEvent(
        event=IPCEventName.CAPTURE_STARTED.value,
        worker_generation=2,
        worker_instance_id="wrk_gen2_inst",
        tx_id=tx_a.tx_id,
    )
    assert mgr.validate_and_apply_event(evt_started, now_mono=201.0).accepted is True
    assert tx_a.state == TransactionState.STARTED

    # Cancel transaction A
    assert mgr.cancel_transaction(tx_a.tx_id, reason="User cancelled") is True
    assert tx_a.state == TransactionState.CANCELLED
    assert mgr.active_capture_transaction is None

    # Late response for cancelled transaction A is rejected and its raw_file_path is quarantined
    late_resp_a = IPCResponse(
        request_id=req_a.request_id,
        worker_generation=2,
        worker_instance_id="wrk_gen2_inst",
        ok=True,
        tx_id=tx_a.tx_id,
        result={"raw_file_path": f"C:/tmp/raw_{tx_a.tx_id}.jpg"},
    )
    out_cancel = mgr.validate_and_consume_response(late_resp_a, now_mono=202.0)
    assert out_cancel.accepted is False
    assert out_cancel.reason_code == IPCErrorCode.TRANSACTION_CANCELLED
    assert out_cancel.quarantine_file_path == f"C:/tmp/raw_{tx_a.tx_id}.jpg"

    # 2. Start Capture Transaction B and let it time out after 12.0s
    req_b, tx_b = mgr.begin_capture_transaction(timeout_s=12.0, now_mono=300.0)
    expired_ids = mgr.expire_timed_out(now_mono=312.5)
    assert tx_b.tx_id in expired_ids
    assert tx_b.state == TransactionState.TIMED_OUT
    assert mgr.active_capture_transaction is None

    # Late response after timeout is rejected
    late_resp_b = IPCResponse(
        request_id=req_b.request_id,
        worker_generation=2,
        worker_instance_id="wrk_gen2_inst",
        ok=True,
        tx_id=tx_b.tx_id,
        result={"raw_file_path": f"C:/tmp/raw_{tx_b.tx_id}.jpg"},
    )
    out_timeout = mgr.validate_and_consume_response(late_resp_b, now_mono=313.0)
    assert out_timeout.accepted is False
    assert out_timeout.reason_code in (
        IPCErrorCode.REQUEST_TIMED_OUT,
        IPCErrorCode.TRANSACTION_TIMED_OUT,
    )
    assert out_timeout.quarantine_file_path == f"C:/tmp/raw_{tx_b.tx_id}.jpg"


# ============================================================================
# 11. Late Event Rejection (Wrong Generation, Wrong tx_id, Cancelled/Timed-Out tx_id)
# ============================================================================


def test_late_event_rejection() -> None:
    """Verify late events from old worker generation, wrong instance, or wrong/dead tx_id are rejected."""
    mgr = IPCTransactionManager(worker_generation=1, worker_instance_id="wrk_gen1_alpha")
    req_1, tx_1 = mgr.begin_capture_transaction(timeout_s=12.0, now_mono=500.0)

    # Supervisor kills Worker Gen 1 and respawns Worker Gen 2
    new_gen, new_inst = mgr.advance_worker_generation(
        new_generation=2,
        new_instance_id="wrk_gen2_beta",
    )
    assert new_gen == 2
    assert new_inst == "wrk_gen2_beta"
    assert tx_1.state == TransactionState.CANCELLED

    # Start a new Capture Transaction in Generation 2
    req_2, tx_2 = mgr.begin_capture_transaction(timeout_s=12.0, now_mono=505.0)

    # 1. Late capture_completed event arriving from Worker Generation 1 -> REJECTED!
    late_gen1_evt = IPCEvent(
        event=IPCEventName.CAPTURE_COMPLETED.value,
        worker_generation=1,
        worker_instance_id="wrk_gen1_alpha",
        tx_id=tx_1.tx_id,
        data={"raw_file_path": f"C:/tmp/raw_{tx_1.tx_id}.jpg"},
    )
    res_gen1 = mgr.validate_and_apply_event(late_gen1_evt, now_mono=506.0)
    assert res_gen1.accepted is False
    assert res_gen1.reason_code == IPCErrorCode.STALE_WORKER_GENERATION
    assert res_gen1.quarantine_file_path == f"C:/tmp/raw_{tx_1.tx_id}.jpg"

    # 2. Event with matching generation=2 but wrong worker_instance_id -> REJECTED!
    wrong_inst_evt = IPCEvent(
        event=IPCEventName.CAPTURE_COMPLETED.value,
        worker_generation=2,
        worker_instance_id="wrk_gen2_impostor",
        tx_id=tx_2.tx_id,
        data={"raw_file_path": f"C:/tmp/raw_{tx_2.tx_id}.jpg"},
    )
    res_inst = mgr.validate_and_apply_event(wrong_inst_evt, now_mono=506.0)
    assert res_inst.accepted is False
    assert res_inst.reason_code == IPCErrorCode.WORKER_INSTANCE_MISMATCH

    # 3. Event with unknown tx_id -> REJECTED!
    wrong_tx_evt = IPCEvent(
        event=IPCEventName.CAPTURE_COMPLETED.value,
        worker_generation=2,
        worker_instance_id="wrk_gen2_beta",
        tx_id="cap_gen2_999999_unknown",
        data={"raw_file_path": "C:/tmp/raw_cap_gen2_999999_unknown.jpg"},
    )
    res_wrong_tx = mgr.validate_and_apply_event(wrong_tx_evt, now_mono=506.0)
    assert res_wrong_tx.accepted is False
    assert res_wrong_tx.reason_code == IPCErrorCode.TRANSACTION_MISMATCH

    # 4. Event whose raw_file_path does NOT contain tx_2.tx_id -> REJECTED!
    mismatched_file_evt = IPCEvent(
        event=IPCEventName.CAPTURE_COMPLETED.value,
        worker_generation=2,
        worker_instance_id="wrk_gen2_beta",
        tx_id=tx_2.tx_id,
        data={"raw_file_path": "C:/tmp/raw_some_other_tx.jpg"},
    )
    res_bad_file = mgr.validate_and_apply_event(mismatched_file_evt, now_mono=506.0)
    assert res_bad_file.accepted is False
    assert res_bad_file.reason_code == IPCErrorCode.TRANSACTION_MISMATCH
    assert res_bad_file.quarantine_file_path == "C:/tmp/raw_some_other_tx.jpg"

    # 5. Valid capture_completed event for tx_2 -> ACCEPTED!
    valid_evt = IPCEvent(
        event=IPCEventName.CAPTURE_COMPLETED.value,
        worker_generation=2,
        worker_instance_id="wrk_gen2_beta",
        tx_id=tx_2.tx_id,
        data={"raw_file_path": f"C:/tmp/raw_{tx_2.tx_id}.jpg"},
    )
    res_valid = mgr.validate_and_apply_event(valid_evt, now_mono=506.5)
    assert res_valid.accepted is True
    assert tx_2.raw_file_path == f"C:/tmp/raw_{tx_2.tx_id}.jpg"


# ============================================================================
# 12. Shared Memory close() and unlink() Lifecycle
# ============================================================================


def test_shm_close_and_unlink_lifecycle() -> None:
    """Verify owner vs attacher close() and unlink() lifecycle and idempotency."""
    owner = NikonSharedFrameBuffer(create=True, worker_generation=1)
    shm_name = owner.name
    assert owner.is_owner is True
    assert owner.is_closed is False
    assert owner.is_unlinked is False

    attacher = NikonSharedFrameBuffer.attach(shm_name)
    assert attacher.is_owner is False
    assert attacher.is_closed is False

    # Non-owner calling unlink() must be a safe no-op and must not destroy owner's mapping
    attacher.unlink()
    assert attacher.is_unlinked is False
    attacher.close()
    assert attacher.is_closed is True
    # Calling close() a second time is idempotent
    attacher.close()

    # Owner can still write and read after attacher closed
    rgb, jpeg = _make_synthetic_frame(seed=12)
    owner.write_frame(rgb=rgb, jpeg_bytes=jpeg, sequence_id=1, worker_generation=1)
    frame = owner.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1)
    assert frame is not None
    assert frame.sequence_id == 1

    # Owner close() and unlink()
    owner.close()
    owner.unlink()
    assert owner.is_closed is True
    assert owner.is_unlinked is True
    # Calling unlink() again is idempotent
    owner.unlink()

    # Accessing global_header after close raises RuntimeError
    with pytest.raises(RuntimeError):
        _ = owner.global_header


# ============================================================================
# 13. Concurrent Multi-Instance Shared Memory Isolation
# ============================================================================


def test_two_instances_running_without_shm_collision() -> None:
    """Verify two NikonSharedFrameBuffer instances generate distinct names and never overwrite each other."""
    with NikonSharedFrameBuffer(create=True, worker_generation=1) as buf_a, NikonSharedFrameBuffer(
        create=True, worker_generation=2
    ) as buf_b:
        assert buf_a.name != buf_b.name

        rgb_a, jpeg_a = _make_synthetic_frame(seed=1001)
        rgb_b, jpeg_b = _make_synthetic_frame(seed=2002)

        buf_a.write_frame(
            rgb=rgb_a,
            jpeg_bytes=jpeg_a,
            sequence_id=11,
            worker_generation=1,
            source_fps=27.5,
            battery_percent=80,
        )
        buf_b.write_frame(
            rgb=rgb_b,
            jpeg_bytes=jpeg_b,
            sequence_id=22,
            worker_generation=2,
            source_fps=29.0,
            battery_percent=45,
        )

        frame_a = buf_a.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1)
        frame_b = buf_b.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=2)

        assert frame_a is not None
        assert frame_b is not None
        assert frame_a.sequence_id == 11
        assert frame_b.sequence_id == 22
        assert frame_a.worker_generation == 1
        assert frame_b.worker_generation == 2
        assert frame_a.battery_percent == 80
        assert frame_b.battery_percent == 45
        assert frame_a.jpeg == jpeg_a
        assert frame_b.jpeg == jpeg_b
        assert np.array_equal(frame_a.rgb, rgb_a)
        assert np.array_equal(frame_b.rgb, rgb_b)
        assert not np.array_equal(frame_a.rgb, frame_b.rgb)


# ============================================================================
# 14. Phase 1.1 Audit Fixes Verification Tests (H-01, H-02, M-01..M-03, L-01..L-02)
# ============================================================================


def test_close_read_concurrent_race_and_pointer_invalidation() -> None:
    """Verify RLock serializes concurrent read_latest_frame() and close()/unlink() (Finding H-01).

    Proves:
    1. When Thread A is inside read_latest_frame() copying memory, Thread B calling close()
       waits until Thread A's read finishes before unmapping the view.
    2. Reentrant close() inside _test_copy_hook does not deadlock and safely aborts the read.
    3. After close(), base_address == 0, active_operations == 0, and no thread accesses pointers.
    """
    owner = NikonSharedFrameBuffer(create=True, worker_generation=1)
    rgb, jpeg = _make_synthetic_frame(seed=301)
    owner.write_frame(rgb=rgb, jpeg_bytes=jpeg, sequence_id=1, worker_generation=1)
    assert owner.base_address != 0

    in_copy_event = threading.Event()
    close_started_event = threading.Event()
    close_finished_event = threading.Event()
    state_during_copy: dict[str, object] = {}

    def copy_hook_with_concurrent_close(slot_idx: int, slot_obj: FrameSlot) -> None:
        in_copy_event.set()
        # Wait until closer thread has started and is attempting to acquire RLock
        close_started_event.wait(timeout=2.0)
        time.sleep(0.02)
        # While Reader is still inside read_latest_frame(), closer thread MUST be blocked on RLock
        state_during_copy["closed_during_read"] = close_finished_event.is_set()
        state_during_copy["raw_closed_flag"] = owner._closed
        state_during_copy["raw_base_addr"] = owner._base_addr

    def closer_worker() -> None:
        in_copy_event.wait(timeout=2.0)
        close_started_event.set()
        owner.close()
        owner.unlink()
        close_finished_event.set()

    closer_thread = threading.Thread(target=closer_worker, daemon=True)
    closer_thread.start()

    frame = owner.read_latest_frame(
        last_seen_seq_id=0,
        expected_worker_gen=1,
        _test_copy_hook=copy_hook_with_concurrent_close,
    )
    closer_thread.join(timeout=2.0)

    # The in-flight read completed safely BEFORE close() unmapped memory
    assert frame is not None
    assert frame.sequence_id == 1
    assert state_during_copy["closed_during_read"] is False
    assert state_during_copy["raw_closed_flag"] is False
    assert state_during_copy["raw_base_addr"] != 0

    # And immediately after read released RLock, close() completed and invalidated pointers
    assert close_finished_event.is_set() is True
    assert owner.is_closed is True
    assert owner.is_unlinked is True
    assert owner.base_address == 0
    assert owner.active_operations == 0

    with pytest.raises(RuntimeError):
        owner.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1)

    # Also test reentrant close() on the same thread (no deadlock, returns None)
    with NikonSharedFrameBuffer(create=True, worker_generation=1) as reentrant_buf:
        reentrant_buf.write_frame(rgb=rgb, jpeg_bytes=jpeg, sequence_id=1, worker_generation=1)

        def reentrant_close_hook(slot_idx: int, slot_obj: FrameSlot) -> None:
            reentrant_buf.close()

        aborted_frame = reentrant_buf.read_latest_frame(
            last_seen_seq_id=0,
            expected_worker_gen=1,
            _test_copy_hook=reentrant_close_hook,
        )
        assert aborted_frame is None
        assert reentrant_buf.is_closed is True
        assert reentrant_buf.base_address == 0
        assert reentrant_buf.active_operations == 0


def test_crashed_writer_odd_seqlock_recovery_never_exposes_even_invalid_state() -> None:
    """Verify recovery from an ODD slot_seq_lock never passes through an EVEN value before commit (Finding M-01)."""
    with NikonSharedFrameBuffer(create=True, worker_generation=1) as buf:
        rgb, jpeg = _make_synthetic_frame(seed=401)
        # Simulate crashed writer on target slot 1 leaving slot_seq_lock = 3 (ODD) and frame_valid = 1
        slot1 = buf.slots[1]
        slot1.slot_seq_lock = 3
        slot1.frame_valid = FrameValidState.VALID_COMMITTED

        # Reader must reject slot 1 while slot_seq_lock is ODD (3)
        buf.global_header.published_slot = 1
        buf.global_header.latest_sequence_id = 1
        assert buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1) is None

        # Now recover and write a valid frame directly to slot 1
        written_slot = buf.write_frame(
            rgb=rgb,
            jpeg_bytes=jpeg,
            sequence_id=2,
            worker_generation=1,
            target_slot_override=1,
        )
        assert written_slot == 1
        # Slot 1 transitioned directly from 3 (ODD) -> 4 (EVEN) on commit, never 3 -> 4 (invalid) -> 5 -> 6
        assert slot1.slot_seq_lock == 4
        assert slot1.frame_valid == FrameValidState.VALID_COMMITTED

        recovered = buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1)
        assert recovered is not None
        assert recovered.sequence_id == 2
        assert recovered.slot_seq_lock == 4


def test_store_release_load_acquire_metadata_publication_order() -> None:
    """Verify worker_heartbeat_ns and published_slot are updated before latest_sequence_id (Finding M-02)."""
    with NikonSharedFrameBuffer(
        create=True,
        worker_generation=1,
        heartbeat_timeout_ns=500_000_000,  # 0.5s timeout
    ) as buf:
        # Simulate an old heartbeat prior to write_frame()
        buf.global_header.worker_heartbeat_ns = 1_000
        rgb, jpeg = _make_synthetic_frame(seed=402)
        buf.write_frame(rgb=rgb, jpeg_bytes=jpeg, sequence_id=1, worker_generation=1)

        # Immediately after write_frame(), heartbeat_ns, published_slot, and latest_sequence_id are consistent
        assert buf.global_header.latest_sequence_id == 1
        assert buf.global_header.published_slot == 1
        assert buf.global_header.worker_heartbeat_ns > 1_000

        frame = buf.read_latest_frame(last_seen_seq_id=0, expected_worker_gen=1)
        assert frame is not None
        assert frame.sequence_id == 1


def test_response_raw_file_path_basename_and_event_consistency_validation() -> None:
    """Verify basename tx_id enforcement and event/response path consistency (Finding H-02)."""
    mgr = IPCTransactionManager(worker_generation=1, worker_instance_id="wrk_gen1_h02")

    # Case 1: tx_id is in parent folder name but NOT in filename basename -> REJECTED!
    req1, tx1 = mgr.begin_capture_transaction(now_mono=10.0)
    tricky_dir_path = f"C:/tmp/{tx1.tx_id}/raw_wrong_name.jpg"
    resp1 = IPCResponse(
        request_id=req1.request_id,
        worker_generation=1,
        worker_instance_id="wrk_gen1_h02",
        ok=True,
        tx_id=tx1.tx_id,
        result={"raw_file_path": tricky_dir_path},
    )
    out1 = mgr.validate_and_consume_response(resp1, now_mono=11.0)
    assert out1.accepted is False
    assert out1.reason_code == IPCErrorCode.TRANSACTION_MISMATCH
    assert out1.quarantine_file_path == tricky_dir_path

    # Case 2: Event capture_completed reports path A, but IPCResponse reports path B -> REJECTED!
    req2, tx2 = mgr.begin_capture_transaction(now_mono=20.0)
    path_a = f"C:/tmp/raw_{tx2.tx_id}_A.jpg"
    path_b = f"C:/tmp/raw_{tx2.tx_id}_B.jpg"
    evt2 = IPCEvent(
        event=IPCEventName.CAPTURE_COMPLETED.value,
        worker_generation=1,
        worker_instance_id="wrk_gen1_h02",
        tx_id=tx2.tx_id,
        data={"raw_file_path": path_a},
    )
    assert mgr.validate_and_apply_event(evt2, now_mono=21.0).accepted is True
    assert tx2.raw_file_path == path_a

    resp2_conflict = IPCResponse(
        request_id=req2.request_id,
        worker_generation=1,
        worker_instance_id="wrk_gen1_h02",
        ok=True,
        tx_id=tx2.tx_id,
        result={"raw_file_path": path_b},
    )
    out2 = mgr.validate_and_consume_response(resp2_conflict, now_mono=21.5)
    assert out2.accepted is False
    assert out2.reason_code == IPCErrorCode.TRANSACTION_MISMATCH
    assert out2.quarantine_file_path == path_b
    assert tx2.state == TransactionState.FAILED

    # Case 3: Event and IPCResponse report consistent paths (with slash normalization) -> ACCEPTED!
    req3, tx3 = mgr.begin_capture_transaction(now_mono=30.0)
    evt3 = IPCEvent(
        event=IPCEventName.CAPTURE_COMPLETED.value,
        worker_generation=1,
        worker_instance_id="wrk_gen1_h02",
        tx_id=tx3.tx_id,
        data={"raw_file_path": f"C:/tmp/raw_{tx3.tx_id}.jpg"},
    )
    assert mgr.validate_and_apply_event(evt3, now_mono=31.0).accepted is True

    resp3_ok = IPCResponse(
        request_id=req3.request_id,
        worker_generation=1,
        worker_instance_id="wrk_gen1_h02",
        ok=True,
        tx_id=tx3.tx_id,
        result={"raw_file_path": f"C:\\tmp\\raw_{tx3.tx_id}.jpg"},
    )
    out3 = mgr.validate_and_consume_response(resp3_ok, now_mono=31.2)
    assert out3.accepted is True
    assert tx3.state == TransactionState.COMPLETED


def test_strict_message_schema_validation_edge_cases() -> None:
    """Verify malformed payloads raise IPCProtocolError(INVALID_SCHEMA) rather than TypeError (Finding M-03)."""
    base_cmd = {
        "protocol_version": 1,
        "msg_type": "cmd",
        "worker_generation": 1,
        "worker_instance_id": "wrk_1",
        "request_id": "req_1",
        "tx_id": None,
        "timestamp": 1000.0,
        "method": "ping",
        "params": {},
        "timeout_s": 5.0,
    }

    for bad_timeout in (True, False, float("nan"), float("inf"), -1.0, 0.0, "5.0"):
        bad = dict(base_cmd, timeout_s=bad_timeout)
        with pytest.raises(IPCProtocolError) as exc_info:
            IPCRequest.from_dict(bad)
        assert exc_info.value.error_code == IPCErrorCode.INVALID_SCHEMA

    for bad_ts in (True, False, float("nan"), float("inf"), "1000"):
        bad = dict(base_cmd, timestamp=bad_ts)
        with pytest.raises(IPCProtocolError) as exc_info:
            IPCRequest.from_dict(bad)
        assert exc_info.value.error_code == IPCErrorCode.INVALID_SCHEMA

    base_resp = {
        "protocol_version": 1,
        "msg_type": "resp",
        "worker_generation": 1,
        "worker_instance_id": "wrk_1",
        "request_id": "req_1",
        "tx_id": None,
        "timestamp": 1000.0,
        "ok": True,
        "result": {},
        "error_code": "OK",
        "error_message": None,
    }

    # Non-mapping result, invalid raw_file_path type, invalid error_message, or ok=False with error_code='OK'
    invalid_responses = [
        dict(base_resp, result=None),
        dict(base_resp, result=12345),
        dict(base_resp, result=["not_a_dict"]),
        dict(base_resp, result={"raw_file_path": 12345}),
        dict(base_resp, result={"raw_file_path": "   "}),
        dict(base_resp, error_message=12345),
        dict(base_resp, ok=False, error_code="OK"),
    ]
    for bad_resp in invalid_responses:
        with pytest.raises(IPCProtocolError) as exc_info:
            IPCResponse.from_dict(bad_resp)
        assert exc_info.value.error_code == IPCErrorCode.INVALID_SCHEMA


def test_terminal_history_pruning_preserves_active_transactions() -> None:
    """Verify _prune_terminal_history() bounds terminal records and never drops active ones (Finding L-02)."""
    mgr = IPCTransactionManager(
        worker_generation=1,
        worker_instance_id="wrk_gen1_prune",
        max_terminal_history=10,
    )

    # Create 25 completed capture transactions and 25 completed ping requests
    for i in range(25):
        t_now = 1000.0 + i
        ping_req = mgr.create_request(method=IPCCommandMethod.PING, now_mono=t_now)
        ping_resp = IPCResponse(
            request_id=ping_req.request_id,
            worker_generation=1,
            worker_instance_id="wrk_gen1_prune",
            ok=True,
        )
        assert mgr.validate_and_consume_response(ping_resp, now_mono=t_now + 0.1).accepted is True

        cap_req, cap_tx = mgr.begin_capture_transaction(now_mono=t_now + 0.2)
        cap_resp = IPCResponse(
            request_id=cap_req.request_id,
            worker_generation=1,
            worker_instance_id="wrk_gen1_prune",
            ok=True,
            tx_id=cap_tx.tx_id,
            result={"raw_file_path": f"C:/tmp/raw_{cap_tx.tx_id}.jpg"},
        )
        assert mgr.validate_and_consume_response(cap_resp, now_mono=t_now + 0.3).accepted is True

    # Start 1 active capture transaction and 3 active pending requests
    active_cap_req, active_cap_tx = mgr.begin_capture_transaction(now_mono=2000.0)
    active_ping_reqs = [
        mgr.create_request(method=IPCCommandMethod.GET_STATUS, now_mono=2001.0 + j)
        for j in range(3)
    ]

    # Verify terminal transactions were pruned to <= 10 while active transaction is preserved!
    terminal_txs = [tx for tx in mgr._transactions.values() if tx.is_terminal]
    assert len(terminal_txs) <= 10
    assert active_cap_tx.tx_id in mgr._transactions
    assert mgr.active_capture_transaction is active_cap_tx
    assert active_cap_tx.is_active is True

    # Verify all active pending requests are still present and can be completed normally
    for p_req in active_ping_reqs:
        assert p_req.request_id in mgr._pending_requests
        out = mgr.validate_and_consume_response(
            IPCResponse(
                request_id=p_req.request_id,
                worker_generation=1,
                worker_instance_id="wrk_gen1_prune",
                ok=True,
            ),
            now_mono=2005.0,
        )
        assert out.accepted is True

    out_cap = mgr.validate_and_consume_response(
        IPCResponse(
            request_id=active_cap_req.request_id,
            worker_generation=1,
            worker_instance_id="wrk_gen1_prune",
            ok=True,
            tx_id=active_cap_tx.tx_id,
            result={"raw_file_path": f"C:/tmp/raw_{active_cap_tx.tx_id}.jpg"},
        ),
        now_mono=2006.0,
    )
    assert out_cap.accepted is True
    assert active_cap_tx.state == TransactionState.COMPLETED


def test_cross_process_shared_memory_200_frames() -> None:
    """Verify two independent OS processes writing and reading >= 200 frames over SharedMemory."""
    with NikonSharedFrameBuffer(create=True, worker_generation=2) as owner:
        worker_script = f"""
import time
import numpy as np
from vietphotobooth.camera.backends.nikon_maid.shm_frame_buffer import NikonSharedFrameBuffer, WriterState

buf = NikonSharedFrameBuffer.attach({owner.name!r})
try:
    buf.bind_worker(worker_pid=999, worker_generation=2, writer_state=WriterState.STREAMING)
    rgb = np.full((680, 1024, 3), 128, dtype=np.uint8)
    for seq in range(1, 205):
        jpeg = b"\\xff\\xd8\\xff\\xe0" + seq.to_bytes(4, "little") + (b"A" * 600) + b"\\xff\\xd9"
        buf.write_frame(
            rgb=rgb,
            jpeg_bytes=jpeg,
            sequence_id=seq,
            worker_generation=2,
            source_fps=28.5,
            battery_percent=75,
        )
        time.sleep(0.001)
finally:
    buf.close()
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", worker_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        last_seq = 0
        read_count = 0
        t0 = time.perf_counter()
        while (proc.poll() is None or last_seq < 204) and (time.perf_counter() - t0 < 12.0):
            f = owner.read_latest_frame(last_seen_seq_id=last_seq, expected_worker_gen=2)
            if f is not None:
                assert f.is_valid is True
                assert f.sequence_id > last_seq
                assert f.worker_generation == 2
                assert (f.slot_seq_lock & 1) == 0
                assert f.battery_percent == 75
                last_seq = f.sequence_id
                read_count += 1

        stdout, stderr = proc.communicate(timeout=5.0)
        assert proc.returncode == 0, f"Child worker failed: {stderr}"
        assert last_seq == 204
        assert read_count >= 50


# ============================================================================
# 10. PHASE 2.1 TESTS — NikonSession Memory/Callback Safety, FIFO SDRAM,
#     Device-Lost Circuit Breaker, CAN_ACQUIRE Gate, Battery INTEGER_PTR,
#     Raw JPEG EXIF Preservation & NikonSDKLoader Main Process Guard
# ============================================================================


def test_phase21_persistent_callbacks_survive_gc_and_timeout() -> None:
    """Verify all CFUNCTYPE callbacks passed to MAID SDK survive timeout + gc.collect() and never point to freed memory."""
    import gc
    import weakref
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
    from vietphotobooth.camera.backends.nikon_maid.maid_types import (
        MAIDCompletionProc,
        MAIDDataProc,
        MAIDEventProc,
        NkMAIDCapability,
        NkMAIDCommand,
        NkMAIDDataType,
        NkMAIDFileInfo,
        NkMAIDObject,
        NkMAIDResult,
    )

    session = NikonSession()
    session._is_mod_open = True
    session._is_src_open = True
    session._mod_obj = NkMAIDObject()
    session._src_obj = NkMAIDObject()

    # Create weakrefs to all persistent callbacks registered on the session
    cb_attrs = [
        "_mod_event_cb_func",
        "_src_event_cb_func",
        "_lv_comp_cb_func",
        "_enum_comp_cb_func",
        "_af_comp_cb_func",
        "_cap_comp_cb_func",
        "_data_proc_cb_func",
        "_acq_comp_cb_func",
    ]
    weak_cbs = {name: weakref.ref(getattr(session, name)) for name in cb_attrs}

    captured_fn_addrs: Dict[str, int] = {}

    def fake_entry_point(obj_addr, ul_cmd, ul_param, ul_dt, data, fn_addr, ref_comp) -> int:
        if ul_cmd == int(NkMAIDCommand.CAP_START) and ul_param == int(NkMAIDCapability.AUTOFOCUS):
            captured_fn_addrs["af_comp"] = int(fn_addr)
            return int(NkMAIDResult.PENDING)
        if ul_cmd == int(NkMAIDCommand.CAP_START) and ul_param == int(NkMAIDCapability.CAPTURE):
            captured_fn_addrs["cap_comp"] = int(fn_addr)
            # Push 1 item so capture proceeds to _acquire_sdram_item and registers DATA_PROC + ACQUIRE
            session._on_source_event(0, 0, 0x2B000099)
            return int(NkMAIDResult.NO_ERROR)
        if ul_cmd == int(NkMAIDCommand.CAP_SET) and ul_param == int(NkMAIDCapability.DATA_PROC):
            # Read pProc from NkMAIDCallback struct at `data`
            from vietphotobooth.camera.backends.nikon_maid.maid_types import NkMAIDCallback
            cb_struct = NkMAIDCallback.from_address(int(data))
            if cb_struct.pProc:
                captured_fn_addrs["data_proc"] = int(cb_struct.pProc)
            return int(NkMAIDResult.NO_ERROR)
        if ul_cmd == int(NkMAIDCommand.CAP_START) and ul_param == int(NkMAIDCapability.ACQUIRE):
            captured_fn_addrs["acq_comp"] = int(fn_addr)
            return int(NkMAIDResult.PENDING)
        return int(NkMAIDResult.NO_ERROR)

    session._loader._entry_point = fake_entry_point

    # 1. Trigger OVF Autofocus that times out
    ok_af, _ = session.trigger_autofocus(timeout_sec=0.03)
    assert ok_af is False
    assert "af_comp" in captured_fn_addrs and captured_fn_addrs["af_comp"] != 0

    # 2. Trigger capture_photo that times out during ACQUIRE
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(time, "sleep", lambda _s: None)
        res_cap = session.capture_photo(timeout_sec=0.02)
    assert res_cap is None
    assert "cap_comp" in captured_fn_addrs and captured_fn_addrs["cap_comp"] != 0
    assert "data_proc" in captured_fn_addrs and captured_fn_addrs["data_proc"] != 0
    assert "acq_comp" in captured_fn_addrs and captured_fn_addrs["acq_comp"] != 0

    # 3. Force multiple full garbage collection cycles after timeouts
    gc.collect()
    gc.collect()

    # 4. Verify every single weakref is still alive
    for name, wref in weak_cbs.items():
        assert wref() is not None, f"Callback {name} was garbage-collected!"

    # 5. Invoke the raw C function pointers captured BEFORE timeout + gc.collect()
    # to prove the native function pointers still invoke valid Python callables safely.
    c_af_fn = MAIDCompletionProc(captured_fn_addrs["af_comp"])
    c_af_fn(0, int(NkMAIDCommand.CAP_START), int(NkMAIDCapability.AUTOFOCUS), 0, 0, 0, int(NkMAIDResult.NO_ERROR))
    assert session._af_comp_done is True

    c_cap_fn = MAIDCompletionProc(captured_fn_addrs["cap_comp"])
    c_cap_fn(0, int(NkMAIDCommand.CAP_START), int(NkMAIDCapability.CAPTURE), 0, 0, 0, int(NkMAIDResult.NO_ERROR))
    assert session._cap_comp_done is True

    sample_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\xff\xd9"
    c_buf = (ctypes.c_uint8 * len(sample_bytes)).from_buffer_copy(sample_bytes)
    finfo = NkMAIDFileInfo()
    finfo.ulTotalLength = len(sample_bytes)
    finfo.ulLength = len(sample_bytes)
    c_data_fn = MAIDDataProc(captured_fn_addrs["data_proc"])
    rc_data = c_data_fn(0, ctypes.addressof(finfo), ctypes.addressof(c_buf))
    assert rc_data == int(NkMAIDResult.NO_ERROR)
    assert b"".join(session._acq_chunks) == sample_bytes

    c_acq_fn = MAIDCompletionProc(captured_fn_addrs["acq_comp"])
    c_acq_fn(0, int(NkMAIDCommand.CAP_START), int(NkMAIDCapability.ACQUIRE), 0, 0, 0, int(NkMAIDResult.NO_ERROR))
    assert session._acq_comp_done is True


def test_phase21_fifo_sdram_queue_no_clear_and_strict_fifo_order() -> None:
    """Verify capture_photo does NOT clear pre-existing SDRAM items and processes items in strict FIFO order."""
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
    from vietphotobooth.camera.backends.nikon_maid.maid_types import (
        NkMAIDCapability,
        NkMAIDCommand,
        NkMAIDFileInfo,
        NkMAIDObject,
        NkMAIDResult,
    )

    session = NikonSession()
    session._is_mod_open = True
    session._is_src_open = True
    session._src_obj = NkMAIDObject()

    # Pre-existing items in camera SDRAM before capture_photo is called
    session._new_items = [0x2B000001, 0x2B000002]
    opened_item_order: list[int] = []
    current_opening_item = [0]

    def fake_entry_point(obj_addr, ul_cmd, ul_param, ul_dt, data, fn_addr, ref_comp) -> int:
        if ul_cmd == int(NkMAIDCommand.CAP_START) and ul_param == int(NkMAIDCapability.CAPTURE):
            # Simulate two new items arriving in SDRAM after shutter release
            session._on_source_event(0, 0, 0x2B000003)
            session._on_source_event(0, 0, 0x2B000004)
            session._on_cap_complete(obj_addr, ul_cmd, ul_param, ul_dt, data, ref_comp, int(NkMAIDResult.NO_ERROR))
            return int(NkMAIDResult.NO_ERROR)

        if ul_cmd == int(NkMAIDCommand.OPEN) and ul_param in (0x2B000001, 0x2B000002, 0x2B000003, 0x2B000004):
            opened_item_order.append(int(ul_param))
            current_opening_item[0] = int(ul_param)
            return int(NkMAIDResult.NO_ERROR)

        if ul_cmd == int(NkMAIDCommand.CAP_START) and ul_param == int(NkMAIDCapability.ACQUIRE):
            item_tag = current_opening_item[0].to_bytes(4, "big")
            payload = b"\xff\xd8\xff\xe0" + item_tag + (b"\x55" * 128) + b"\xff\xd9"
            c_buf = (ctypes.c_uint8 * len(payload)).from_buffer_copy(payload)
            finfo = NkMAIDFileInfo()
            finfo.ulTotalLength = len(payload)
            finfo.ulLength = len(payload)
            session._on_data_chunk(0, ctypes.addressof(finfo), ctypes.addressof(c_buf))
            session._on_acq_complete(obj_addr, ul_cmd, ul_param, ul_dt, data, ref_comp, int(NkMAIDResult.NO_ERROR))
            return int(NkMAIDResult.NO_ERROR)

        return int(NkMAIDResult.NO_ERROR)

    session._loader._entry_point = fake_entry_point

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(time, "sleep", lambda _s: None)
        captured_bytes = session.capture_photo(timeout_sec=1.0)

    # 1. Pre-existing items 0x2B000001 and 0x2B000002 were drained in FIFO order before the new capture
    recovered = session.recovered_sdram_items
    assert [r["item_id"] for r in recovered] == [0x2B000001, 0x2B000002]
    assert (0x2B000001).to_bytes(4, "big") in recovered[0]["raw_bytes"]
    assert (0x2B000002).to_bytes(4, "big") in recovered[1]["raw_bytes"]

    # 2. The newly captured item popped for capture_photo() was 0x2B000003 (FIFO pop(0)), NOT 0x2B000004 (LIFO pop())!
    assert opened_item_order == [0x2B000001, 0x2B000002, 0x2B000003]
    assert captured_bytes is not None
    assert (0x2B000003).to_bytes(4, "big") in captured_bytes

    # 3. Item 0x2B000004 remains at the front of _new_items and can be drained via drain_sdram_fifo()
    assert session._new_items == [0x2B000004]
    drained_after = session.drain_sdram_fifo(timeout_sec=1.0)
    assert len(drained_after) == 1
    assert (0x2B000004).to_bytes(4, "big") in drained_after[0]
    assert session._new_items == []


def test_phase21_sdram_drain_and_3_transfer_states_with_device_lost() -> None:
    """Verify the 3 transfer states (COMPLETE_IN_RAM, PARTIAL_USB_TRANSFER, SDRAM_PENDING) and no SDRAM drain after device_lost."""
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
    from vietphotobooth.camera.backends.nikon_maid.maid_types import (
        NkMAIDCapability,
        NkMAIDCommand,
        NkMAIDEvent,
        NkMAIDFileInfo,
        NkMAIDObject,
        NkMAIDResult,
    )

    # Case A: Partial USB transfer containing an embedded EXIF thumbnail (0xFFD8..0xFFD9)
    # cut off halfway when USB disconnects -> MUST be rejected as PARTIAL_USB_TRANSFER!
    session_partial = NikonSession()
    session_partial._is_mod_open = True
    session_partial._is_src_open = True
    session_partial._src_obj = NkMAIDObject()
    close_calls_partial = [0]

    def entry_partial(obj_addr, ul_cmd, ul_param, ul_dt, data, fn_addr, ref_comp) -> int:
        if ul_cmd == int(NkMAIDCommand.CLOSE):
            close_calls_partial[0] += 1
            return int(NkMAIDResult.NO_ERROR)
        if ul_cmd == int(NkMAIDCommand.CAP_START) and ul_param == int(NkMAIDCapability.ACQUIRE):
            # Chunk 1 has SOI + embedded EXIF thumbnail SOI..EOI + partial main image (500 bytes out of 2000 total)
            chunk1 = b"\xff\xd8\xff\xe1\x00\x20Exif\x00\x00\xff\xd8\x11\x22\xff\xd9" + (b"\xAA" * 480)
            c_buf = (ctypes.c_uint8 * len(chunk1)).from_buffer_copy(chunk1)
            finfo = NkMAIDFileInfo()
            finfo.ulTotalLength = 2000  # Expecting 2000 bytes total
            finfo.ulLength = len(chunk1)
            session_partial._on_data_chunk(0, ctypes.addressof(finfo), ctypes.addressof(c_buf))
            # USB unplug happens mid-transfer before Chunk 2 arrives!
            session_partial._on_module_event(0, int(NkMAIDEvent.REMOVE_CHILD), 1)
            return int(NkMAIDResult.HARDWARE_ERROR)
        return int(NkMAIDResult.NO_ERROR)

    session_partial._loader._entry_point = entry_partial
    res_partial = session_partial._acquire_sdram_item(0x2B000010, timeout_sec=0.2)
    assert res_partial is None
    assert session_partial.last_capture_transfer_state == "PARTIAL_USB_TRANSFER"
    assert session_partial.device_lost is True
    # Must NOT have called CLOSE on DataObj or ItemObj after device_lost!
    assert close_calls_partial[0] == 0

    # Case B: Complete image already in Worker RAM when USB disconnects right after ACQUIRE completes
    session_complete = NikonSession()
    session_complete._is_mod_open = True
    session_complete._is_src_open = True
    session_complete._src_obj = NkMAIDObject()
    close_calls_complete = [0]
    full_jpeg = b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00" + (b"\xBB" * 1024) + b"\xff\xd9"

    def entry_complete(obj_addr, ul_cmd, ul_param, ul_dt, data, fn_addr, ref_comp) -> int:
        if ul_cmd == int(NkMAIDCommand.CLOSE):
            close_calls_complete[0] += 1
            return int(NkMAIDResult.NO_ERROR)
        if ul_cmd == int(NkMAIDCommand.CAP_START) and ul_param == int(NkMAIDCapability.ACQUIRE):
            c_buf = (ctypes.c_uint8 * len(full_jpeg)).from_buffer_copy(full_jpeg)
            finfo = NkMAIDFileInfo()
            finfo.ulTotalLength = len(full_jpeg)
            finfo.ulLength = len(full_jpeg)
            session_complete._on_data_chunk(0, ctypes.addressof(finfo), ctypes.addressof(c_buf))
            session_complete._on_acq_complete(obj_addr, ul_cmd, ul_param, ul_dt, data, ref_comp, int(NkMAIDResult.NO_ERROR))
            # USB unplug happens right after all bytes are in Worker RAM
            session_complete._on_module_event(0, int(NkMAIDEvent.REMOVE_CHILD), 1)
            return int(NkMAIDResult.NO_ERROR)
        return int(NkMAIDResult.NO_ERROR)

    session_complete._loader._entry_point = entry_complete
    res_complete = session_complete._acquire_sdram_item(0x2B000011, timeout_sec=0.2)
    assert res_complete == full_jpeg
    assert session_complete.last_capture_transfer_state == "COMPLETE_IN_RAM"
    assert session_complete.device_lost is True
    assert close_calls_complete[0] == 0

    # Case C: Camera SDRAM items still pending when _device_lost == True -> drain_sdram_fifo MUST NOT call MAID
    session_complete._new_items = [0x2B000012, 0x2B000013]
    maid_calls_after_lost = [0]

    def counting_entry(*_args) -> int:
        maid_calls_after_lost[0] += 1
        return 0

    session_complete._loader._entry_point = counting_entry
    drained = session_complete.drain_sdram_fifo(timeout_sec=0.2)
    assert drained == []
    assert maid_calls_after_lost[0] == 0


@pytest.mark.parametrize("trigger_mode", ["REMOVE_CHILD", -116, -117, -119])
def test_phase21_device_lost_circuit_breaker_blocks_all_subsequent_maid_calls(trigger_mode) -> None:
    """Verify REMOVE_CHILD or -116/-117/-119 activates _device_lost and blocks all subsequent MAID calls."""
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
    from vietphotobooth.camera.backends.nikon_maid.maid_types import (
        NkMAIDCapability,
        NkMAIDEvent,
        NkMAIDObject,
    )

    session = NikonSession()
    session._is_mod_open = True
    session._is_src_open = True
    session._is_live_view_active = True
    session._mod_obj = NkMAIDObject()
    session._src_obj = NkMAIDObject()
    session._new_items = [0x2B000001]

    call_log: list[tuple[int, int]] = []

    def fake_entry_point(obj_addr, ul_cmd, ul_param, ul_dt, data, fn_addr, ref_comp) -> int:
        call_log.append((int(ul_cmd), int(ul_param)))
        if isinstance(trigger_mode, int):
            return trigger_mode
        return 0

    session._loader._entry_point = fake_entry_point

    if trigger_mode == "REMOVE_CHILD":
        session._on_module_event(0, int(NkMAIDEvent.REMOVE_CHILD), 1)
        assert session.device_lost is True
        expected_calls = 0
    else:
        # First call returns -116 / -117 / -119 and trips the circuit breaker
        val = session.get_unsigned_capability(NkMAIDCapability.FOCUS_MODE)
        assert val is None
        assert session.device_lost is True
        expected_calls = 1

    assert len(call_log) == expected_calls

    # Now invoke every session operation on the lost session: ZERO additional MAID calls may occur!
    session.pump_async()
    assert session.fetch_live_view_frame() is None
    assert session.get_string_capability(NkMAIDCapability.NAME) == ""
    assert session.get_integer_capability(NkMAIDCapability.BATTERY_LEVEL) is None
    assert session.get_battery_level() is None
    assert session.get_unsigned_capability(NkMAIDCapability.ISO_CONTROL) is None
    assert session.set_unsigned_capability(NkMAIDCapability.SAVE_MEDIA, 1) is False
    assert session.get_enum_capability(NkMAIDCapability.LIVE_VIEW_IMAGE_SIZE) is None
    assert session.set_enum_capability(NkMAIDCapability.LIVE_VIEW_IMAGE_SIZE, 3) is False
    assert session.start_live_view(timeout_sec=0.05) is False
    session.stop_live_view()
    assert session.trigger_autofocus(timeout_sec=0.05)[0] is False
    assert session.cancel_autofocus() is False
    assert session.drain_sdram_fifo(timeout_sec=0.05) == []
    assert session.capture_photo(timeout_sec=0.05) is None
    session.close_camera()
    session.close_module()

    assert len(call_log) == expected_calls, (
        f"Expected 0 MAID calls after device_lost, but saw {len(call_log) - expected_calls} extra calls!"
    )


def test_phase21_start_live_view_requires_can_acquire() -> None:
    """Verify start_live_view returns False when CAN_ACQUIRE is not reached and True when CAN_ACQUIRE is reached."""
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
    from vietphotobooth.camera.backends.nikon_maid.maid_types import (
        NkMAIDCapability,
        NkMAIDCommand,
        NkMAIDEnum,
        NkMAIDLiveViewImageStatus,
        NkMAIDObject,
        NkMAIDResult,
    )

    # 1. CANNOT_ACQUIRE (0) -> must return False and keep _is_live_view_active == False
    session_fail = NikonSession()
    session_fail._is_src_open = True
    session_fail._src_obj = NkMAIDObject()

    def entry_cannot_acquire(obj_addr, ul_cmd, ul_param, ul_dt, data, fn_addr, ref_comp) -> int:
        if ul_cmd == int(NkMAIDCommand.CAP_GET) and ul_param == int(NkMAIDCapability.LIVE_VIEW_IMAGE_STATUS):
            st = NkMAIDEnum.from_address(int(data))
            st.ulValue = int(NkMAIDLiveViewImageStatus.CANNOT_ACQUIRE)
            return int(NkMAIDResult.NO_ERROR)
        return int(NkMAIDResult.NO_ERROR)

    session_fail._loader._entry_point = entry_cannot_acquire
    ok_fail = session_fail.start_live_view(timeout_sec=0.06)
    assert ok_fail is False
    assert session_fail._is_live_view_active is False

    # 2. CAN_ACQUIRE (1) -> must return True and set _is_live_view_active == True
    session_ok = NikonSession()
    session_ok._is_src_open = True
    session_ok._src_obj = NkMAIDObject()

    def entry_can_acquire(obj_addr, ul_cmd, ul_param, ul_dt, data, fn_addr, ref_comp) -> int:
        if ul_cmd == int(NkMAIDCommand.CAP_GET) and ul_param == int(NkMAIDCapability.LIVE_VIEW_IMAGE_STATUS):
            st = NkMAIDEnum.from_address(int(data))
            st.ulValue = int(NkMAIDLiveViewImageStatus.CAN_ACQUIRE)
            return int(NkMAIDResult.NO_ERROR)
        return int(NkMAIDResult.NO_ERROR)

    session_ok._loader._entry_point = entry_can_acquire
    ok_success = session_ok.start_live_view(timeout_sec=0.2)
    assert ok_success is True
    assert session_ok._is_live_view_active is True


def test_phase21_battery_level_integer_ptr_reading() -> None:
    """Verify BATTERY_LEVEL (0x0031) is accurately read via NkMAIDDataType.INTEGER_PTR."""
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
    from vietphotobooth.camera.backends.nikon_maid.maid_types import (
        NkMAIDCapability,
        NkMAIDCommand,
        NkMAIDDataType,
        NkMAIDObject,
        NkMAIDResult,
    )

    session = NikonSession()
    session._is_src_open = True
    session._src_obj = NkMAIDObject()

    def entry_d780_battery(obj_addr, ul_cmd, ul_param, ul_dt, data, fn_addr, ref_comp) -> int:
        if ul_cmd == int(NkMAIDCommand.CAP_GET) and ul_param == int(NkMAIDCapability.BATTERY_LEVEL):
            # Real Nikon D780 Type0026 behavior: rejects UNSIGNED_PTR with -126, accepts INTEGER_PTR (5)
            if ul_dt == int(NkMAIDDataType.UNSIGNED_PTR):
                return int(NkMAIDResult.UNEXPECTED_DATA_TYPE)
            if ul_dt == int(NkMAIDDataType.INTEGER_PTR):
                c_val = ctypes.c_int32.from_address(int(data))
                c_val.value = 60
                return int(NkMAIDResult.NO_ERROR)
        return int(NkMAIDResult.NO_ERROR)

    session._loader._entry_point = entry_d780_battery

    assert session.get_integer_capability(NkMAIDCapability.BATTERY_LEVEL) == 60
    assert session.get_battery_level() == 60
    assert session.get_unsigned_capability(NkMAIDCapability.BATTERY_LEVEL) == 60


def test_phase21_raw_jpeg_preserves_exact_bytes_and_exif() -> None:
    """Verify capture_photo returns exact unmodified raw JPEG bytes with 100% EXIF preservation."""
    import hashlib
    import io
    from PIL import Image
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
    from vietphotobooth.camera.backends.nikon_maid.maid_types import (
        NkMAIDCapability,
        NkMAIDCommand,
        NkMAIDFileInfo,
        NkMAIDObject,
        NkMAIDResult,
    )

    # Create a real JPEG image with authentic EXIF tags (Make, Model, Software, DateTime)
    img = Image.new("RGB", (640, 424), color=(32, 64, 128))
    exif = img.getexif()
    exif[0x010F] = "NIKON CORPORATION"  # Make
    exif[0x0110] = "NIKON D780"         # Model
    exif[0x0131] = "Ver.01.03"          # Software
    exif[0x0132] = "2026:11:06 20:00:00"  # DateTime
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95, exif=exif.tobytes())
    original_jpeg_bytes = buf.getvalue()
    original_sha256 = hashlib.sha256(original_jpeg_bytes).hexdigest()

    session = NikonSession()
    session._is_mod_open = True
    session._is_src_open = True
    session._src_obj = NkMAIDObject()

    def entry_capture_with_exif(obj_addr, ul_cmd, ul_param, ul_dt, data, fn_addr, ref_comp) -> int:
        if ul_cmd == int(NkMAIDCommand.CAP_START) and ul_param == int(NkMAIDCapability.CAPTURE):
            session._on_source_event(0, 0, 0x2B000077)
            session._on_cap_complete(obj_addr, ul_cmd, ul_param, ul_dt, data, ref_comp, int(NkMAIDResult.NO_ERROR))
            return int(NkMAIDResult.NO_ERROR)
        if ul_cmd == int(NkMAIDCommand.CAP_START) and ul_param == int(NkMAIDCapability.ACQUIRE):
            # Deliver in 3 chunks via _on_data_chunk
            total_len = len(original_jpeg_bytes)
            step = max(1, total_len // 3)
            for offset in range(0, total_len, step):
                part = original_jpeg_bytes[offset:offset + step]
                c_part = (ctypes.c_uint8 * len(part)).from_buffer_copy(part)
                finfo = NkMAIDFileInfo()
                finfo.ulTotalLength = total_len
                finfo.ulLength = len(part)
                session._on_data_chunk(0, ctypes.addressof(finfo), ctypes.addressof(c_part))
            session._on_acq_complete(obj_addr, ul_cmd, ul_param, ul_dt, data, ref_comp, int(NkMAIDResult.NO_ERROR))
            return int(NkMAIDResult.NO_ERROR)
        return int(NkMAIDResult.NO_ERROR)

    session._loader._entry_point = entry_capture_with_exif

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(time, "sleep", lambda _s: None)
        returned_bytes = session.capture_photo(timeout_sec=1.0)

    assert returned_bytes is not None
    assert returned_bytes == original_jpeg_bytes
    assert hashlib.sha256(returned_bytes).hexdigest() == original_sha256
    assert session.get_last_captured_raw_bytes() == original_jpeg_bytes

    # Verify EXIF tags are 100% preserved
    decoded_img = Image.open(io.BytesIO(returned_bytes))
    decoded_exif = decoded_img.getexif()
    assert decoded_exif.get(0x010F) == "NIKON CORPORATION"
    assert decoded_exif.get(0x0110) == "NIKON D780"
    assert decoded_exif.get(0x0131) == "Ver.01.03"
    assert decoded_exif.get(0x0132) == "2026:11:06 20:00:00"


def test_phase21_maid_loader_main_process_isolation_guard() -> None:
    """Verify Main Process Isolation Guard in maid_loader blocks SDK loading when enabled and is off by default."""
    from vietphotobooth.camera.backends.nikon_maid.maid_loader import (
        NikonMainProcessSDKLoadForbiddenError,
        NikonSDKLoader,
        is_main_process_isolation_guard_enabled,
        set_main_process_isolation_guard,
    )
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession

    # 1. Default must be False (backward-compatible with existing in-process mode)
    assert is_main_process_isolation_guard_enabled() is False
    loader = NikonSDKLoader()
    assert loader.is_isolation_guard_active() is False

    try:
        # 2. Enable global Main Process Isolation Guard
        set_main_process_isolation_guard(True)
        assert is_main_process_isolation_guard_enabled() is True
        assert loader.is_isolation_guard_active() is True

        ok, msg = loader.load()
        assert ok is False
        assert "Main Process Isolation Guard" in msg
        assert loader.is_loaded is False

        with pytest.raises(NikonMainProcessSDKLoadForbiddenError):
            loader.assert_load_permitted()

        with pytest.raises(NikonMainProcessSDKLoadForbiddenError):
            loader.load(raise_on_guard=True)

        # Verify NikonSession.open_module() is also safely blocked when guard is active
        session = NikonSession()
        mod_ok, mod_msg = session.open_module()
        assert mod_ok is False
        assert "Main Process Isolation Guard" in mod_msg
    finally:
        set_main_process_isolation_guard(False)
        assert is_main_process_isolation_guard_enabled() is False


# ============================================================================
# PHASE 2.2 TESTS: Nikon Driver Worker Process, Startup Gate, IPC Server,
#                  Live View SharedMemory Streaming & Atomic Spooling
# ============================================================================

import io as _p22_io
import os
from typing import Any, Optional
import uuid as _p22_uuid
from PIL import Image as _P22Image
from vietphotobooth.camera.backends.nikon_maid.ipc_protocol import (
    generate_worker_instance_id,
)


def _unique_shm_name(prefix: str = "nsfb") -> str:
    return f"vp_{prefix}_{os.getpid()}_{_p22_uuid.uuid4().hex[:8]}"


def _make_synthetic_jpeg(width: int = 320, height: int = 213, seed: int = 1) -> bytes:
    xs = np.linspace(0, 255, width, dtype=np.int32)
    ys = np.linspace(0, 255, height, dtype=np.int32)
    grid_x, grid_y = np.meshgrid(xs, ys)
    r = ((grid_x + int(seed) * 17) & 0xFF).astype(np.uint8)
    g = ((grid_y + int(seed) * 31) & 0xFF).astype(np.uint8)
    b = (((grid_x ^ grid_y) + int(seed) * 7) & 0xFF).astype(np.uint8)
    rgb = np.stack([r, g, b], axis=-1)
    img = _P22Image.fromarray(rgb, mode="RGB")
    buf = _p22_io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


class _FakeNikonSessionForWorker:
    """Deterministic fake NikonSession for Worker IPC Server & cross-process tests."""

    def __init__(
        self,
        *,
        sources: Optional[list[int]] = None,
        can_acquire_lv: bool = True,
        lv_jpeg_bytes: Optional[bytes] = None,
        capture_jpeg_bytes: Optional[bytes] = None,
        fail_capture_timeout: bool = False,
        simulate_disconnect_on_capture: bool = False,
    ) -> None:
        self._sources = [1] if sources is None else list(sources)
        self._can_acquire_lv = bool(can_acquire_lv)
        self._lv_jpeg_bytes = lv_jpeg_bytes or _make_synthetic_jpeg(320, 213, 42)
        self._capture_jpeg_bytes = capture_jpeg_bytes or _make_synthetic_jpeg(640, 424, 99)
        self._fail_capture_timeout = bool(fail_capture_timeout)
        self._simulate_disconnect_on_capture = bool(simulate_disconnect_on_capture)

        self._is_mod_open = False
        self._is_src_open = False
        self._is_live_view_active = False
        self._device_lost = False
        self._device_lost_reason = ""
        self._last_capture_transfer_state = "NONE"

        self.discover_calls = 0
        self.connect_calls = 0
        self.start_lv_calls = 0
        self.stop_lv_calls = 0
        self.fetch_lv_calls = 0
        self.capture_calls = 0
        self.close_calls = 0
        self.calls_after_device_lost = 0

    @property
    def device_lost(self) -> bool:
        return self._device_lost

    @property
    def device_lost_reason(self) -> str:
        return self._device_lost_reason

    @property
    def last_capture_transfer_state(self) -> str:
        return self._last_capture_transfer_state

    def trip_device_lost(self, reason: str = "REMOVE_CHILD(source_id=0x1)") -> None:
        self._device_lost = True
        self._device_lost_reason = reason
        self._is_live_view_active = False

    def enumerate_cameras(self, timeout_sec: float = 1.5) -> list[int]:
        if self._device_lost:
            self.calls_after_device_lost += 1
            return []
        self.discover_calls += 1
        self._is_mod_open = True
        return list(self._sources)

    def open_camera(self, src_id: Optional[int] = None) -> tuple[bool, str]:
        if self._device_lost:
            self.calls_after_device_lost += 1
            return False, self._device_lost_reason
        self.connect_calls += 1
        if not self._sources:
            return False, "No camera found"
        self._is_mod_open = True
        self._is_src_open = True
        return True, "Connected Nikon D780"

    def get_battery_level(self) -> Optional[int]:
        if self._device_lost:
            self.calls_after_device_lost += 1
            return None
        return 75

    def start_live_view(self, timeout_sec: float = 3.0) -> bool:
        if self._device_lost:
            self.calls_after_device_lost += 1
            return False
        self.start_lv_calls += 1
        if not self._can_acquire_lv:
            self._is_live_view_active = False
            return False
        self._is_live_view_active = True
        return True

    def fetch_live_view_frame(self) -> Optional[bytes]:
        if self._device_lost:
            self.calls_after_device_lost += 1
            return None
        if not self._is_live_view_active:
            return None
        self.fetch_lv_calls += 1
        return self._lv_jpeg_bytes

    def stop_live_view(self) -> None:
        if self._device_lost:
            self.calls_after_device_lost += 1
            return
        self.stop_lv_calls += 1
        self._is_live_view_active = False

    def capture_photo(
        self,
        timeout_sec: float = 12.0,
        autofocus_first: bool = False,
        on_capture_start: Optional[Any] = None,
    ) -> Optional[bytes]:
        if self._device_lost:
            self.calls_after_device_lost += 1
            return None
        self.capture_calls += 1
        if on_capture_start is not None:
            on_capture_start()

        if self._simulate_disconnect_on_capture:
            self._last_capture_transfer_state = "PARTIAL_USB_TRANSFER"
            self.trip_device_lost("MAID result -116 (capture_photo)")
            return None

        if self._fail_capture_timeout:
            self._last_capture_transfer_state = "SDRAM_PENDING"
            return None

        self._last_capture_transfer_state = "COMPLETE_IN_RAM"
        return self._capture_jpeg_bytes

    def close_camera(self) -> None:
        if self._device_lost:
            return
        self._is_src_open = False
        self._is_live_view_active = False

    def close_module(self) -> None:
        if self._device_lost:
            return
        self.close_calls += 1
        self._is_src_open = False
        self._is_mod_open = False
        self._is_live_view_active = False


def test_phase22_worker_startup_gate_and_no_dll_loaded_before_gate(tmp_path) -> None:
    """Verify Worker startup gate checks parent liveness, Job Object, and loads zero Nikon DLLs beforehand."""
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_main import (
        EXIT_INVALID_STARTUP_ARGS,
        EXIT_OK,
        EXIT_PARENT_NOT_ALIVE,
        EXIT_PREMATURE_SDK_LOADED,
        WorkerStartupConfig,
        close_win32_handle,
        execute_startup_gate,
    )
    from vietphotobooth.camera.backends.nikon_maid.maid_loader import get_loader

    # Ensure _default_loader has no leftover mock _entry_point from earlier in-process unit tests
    get_loader().unload()

    # 1. Confirm no Nikon SDK DLL (Type0026.md3, NkdPTP.dll, NkRoyalmile.dll) is loaded in a clean subprocess
    #    importing driver_worker_main & driver_worker_server before Startup Gate completion (Audit S-2)
    check_proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from vietphotobooth.camera.backends.nikon_maid import driver_worker_main, driver_worker_server; "
                "from vietphotobooth.camera.backends.nikon_maid.maid_loader import get_loader; "
                "assert get_loader().is_loaded is False; "
                "loaded, dll = driver_worker_main.is_nikon_sdk_loaded_in_current_process(); "
                "assert loaded is False, f'Unexpected DLL loaded: {dll}'"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert check_proc.returncode == 0, f"Subprocess import check failed: {check_proc.stderr}"

    spool_dir = str(tmp_path / "spool_gate")

    # 2. Invalid startup args -> rejected with EXIT_INVALID_STARTUP_ARGS
    bad_cfg = WorkerStartupConfig(
        shm_name="",
        parent_pid=os.getpid(),
        worker_generation=1,
        worker_instance_id="w_gen1",
        spool_dir=spool_dir,
    )
    res_bad = execute_startup_gate(bad_cfg)
    assert res_bad.passed is False
    assert res_bad.exit_code == EXIT_INVALID_STARTUP_ARGS

    # 3. Dead/non-existent parent PID -> rejected with EXIT_PARENT_NOT_ALIVE
    dead_parent_cfg = WorkerStartupConfig(
        shm_name="nsfb_test_gate",
        parent_pid=99999999,
        worker_generation=1,
        worker_instance_id="w_gen1",
        spool_dir=spool_dir,
    )
    res_dead = execute_startup_gate(
        dead_parent_cfg,
        job_check_fn=lambda: (True, "In job"),
        sdk_loaded_check_fn=lambda: (False, None),
    )
    assert res_dead.passed is False
    assert res_dead.exit_code == EXIT_PARENT_NOT_ALIVE

    # 4. Premature SDK loaded detection -> rejected with EXIT_PREMATURE_SDK_LOADED
    valid_cfg = WorkerStartupConfig(
        shm_name="nsfb_test_gate",
        parent_pid=os.getpid(),
        worker_generation=1,
        worker_instance_id="w_gen1",
        spool_dir=spool_dir,
    )
    res_premature = execute_startup_gate(
        valid_cfg,
        sdk_loaded_check_fn=lambda: (True, "Type0026.md3"),
    )
    assert res_premature.passed is False
    assert res_premature.exit_code == EXIT_PREMATURE_SDK_LOADED

    # 5. Valid parent PID + Job Object check passing -> Startup Gate passes!
    res_ok = execute_startup_gate(
        valid_cfg,
        job_check_fn=lambda: (True, "Verified in Job"),
        sdk_loaded_check_fn=lambda: (False, None),
    )
    try:
        assert res_ok.passed is True
        assert res_ok.exit_code == EXIT_OK
        assert os.path.isdir(spool_dir)
    finally:
        close_win32_handle(res_ok.parent_handle)


def test_phase22_worker_rejects_startup_when_not_in_job_object_cross_process(tmp_path) -> None:
    """Verify Worker Process exits with EXIT_NOT_IN_JOB_OBJECT (72) and never loads MAID when not in Job Object."""
    import subprocess
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_main import (
        EXIT_NOT_IN_JOB_OBJECT,
        WorkerStartupConfig,
        execute_startup_gate,
    )

    spool_dir = str(tmp_path / "spool_no_job")
    cfg = WorkerStartupConfig(
        shm_name="nsfb_no_job",
        parent_pid=os.getpid(),
        worker_generation=1,
        worker_instance_id="w_gen1_nojob",
        spool_dir=spool_dir,
    )

    # 1. Direct unit test with job_check_fn returning False
    gate_res = execute_startup_gate(
        cfg,
        job_check_fn=lambda: (False, "Not in Windows Job Object"),
        sdk_loaded_check_fn=lambda: (False, None),
    )
    assert gate_res.passed is False
    assert gate_res.exit_code == EXIT_NOT_IN_JOB_OBJECT
    assert "Job Object" in gate_res.reason

    # 2. Real standalone subprocess test with VIETPHOTOBOOTH_WORKER_FORCE_NOT_IN_JOB=1
    env = os.environ.copy()
    env["VIETPHOTOBOOTH_WORKER_FORCE_NOT_IN_JOB"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "vietphotobooth.camera.backends.nikon_maid.driver_worker_main",
            "--shm-name",
            "nsfb_subproc_no_job",
            "--parent-pid",
            str(os.getpid()),
            "--worker-generation",
            "1",
            "--worker-instance-id",
            "w_subproc_nojob",
            "--spool-dir",
            spool_dir,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert proc.returncode == EXIT_NOT_IN_JOB_OBJECT
    assert "STARTUP_GATE_REJECTED" in proc.stderr
    assert "IsProcessInJob" in proc.stderr


def test_phase22_ipc_ping_discover_connect_and_cross_process_subprocess(tmp_path) -> None:
    """Verify IPC PING, DISCOVER, CONNECT in Worker Server AND across a real standalone Worker subprocess."""
    import json
    import multiprocessing
    import subprocess
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        NikonDriverWorkerServer,
        PipeConnectionTransport,
        parse_wire_message,
    )

    shm_name = _unique_shm_name("p22_ipc")
    spool_dir = str(tmp_path / "spool_ipc")
    gen = 2
    inst_id = generate_worker_instance_id(gen)

    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    worker_shm = NikonSharedFrameBuffer.attach(name=shm_name)
    main_conn, worker_conn = multiprocessing.Pipe(duplex=True)
    fake_session = _FakeNikonSessionForWorker(sources=[1])

    server = NikonDriverWorkerServer(
        worker_generation=gen,
        worker_instance_id=inst_id,
        shm_buffer=worker_shm,
        spool_dir=spool_dir,
        transport=PipeConnectionTransport(worker_conn),
        session_factory=lambda: fake_session,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    tx_mgr = IPCTransactionManager(worker_generation=gen, worker_instance_id=inst_id)

    def _recv_until_response(expected_req_id: str) -> tuple[list[IPCEvent], IPCResponse]:
        events: list[IPCEvent] = []
        while True:
            assert main_conn.poll(3.0), f"Timed out waiting for response to {expected_req_id}"
            raw_msg = main_conn.recv()
            parsed = parse_wire_message(raw_msg)
            if isinstance(parsed, IPCEvent):
                events.append(parsed)
            elif isinstance(parsed, IPCResponse):
                assert parsed.request_id == expected_req_id
                return events, parsed

    try:
        # 1. Receive initial WORKER_READY event
        assert main_conn.poll(3.0)
        ready_msg = parse_wire_message(main_conn.recv())
        assert isinstance(ready_msg, IPCEvent)
        assert ready_msg.event == IPCEventName.WORKER_READY.value
        assert tx_mgr.validate_and_apply_event(ready_msg).accepted is True

        # 2. PING (exempt from mandatory deadline_mono)
        ping_req = tx_mgr.create_request(IPCCommandMethod.PING)
        main_conn.send(ping_req.to_dict())
        _, ping_resp = _recv_until_response(ping_req.request_id)
        assert tx_mgr.validate_and_consume_response(ping_resp).accepted is True
        assert ping_resp.ok is True
        assert ping_resp.result["pong"] is True
        assert ping_resp.result["worker_generation"] == gen

        # 3. DISCOVER (includes deadline_mono per Audit I-3)
        disc_req = tx_mgr.create_request(
            IPCCommandMethod.DISCOVER,
            params={"deadline_mono": time.perf_counter() + 5.0},
        )
        main_conn.send(disc_req.to_dict())
        _, disc_resp = _recv_until_response(disc_req.request_id)
        assert tx_mgr.validate_and_consume_response(disc_resp).accepted is True
        assert disc_resp.ok is True
        assert disc_resp.result["sources"] == [1]
        assert fake_session.discover_calls == 1

        # 4. CONNECT (includes deadline_mono per Audit I-3)
        conn_req = tx_mgr.create_request(
            IPCCommandMethod.CONNECT,
            params={"source_id": 1, "deadline_mono": time.perf_counter() + 5.0},
        )
        main_conn.send(conn_req.to_dict())
        conn_events, conn_resp = _recv_until_response(conn_req.request_id)
        assert tx_mgr.validate_and_consume_response(conn_resp).accepted is True
        assert conn_resp.ok is True
        assert conn_resp.result["connected"] is True
        assert conn_resp.result["battery_percent"] == 75
        assert any(e.event == IPCEventName.CONNECTED.value for e in conn_events)

        # 5. SHUTDOWN
        shut_req = tx_mgr.create_request(IPCCommandMethod.SHUTDOWN)
        main_conn.send(shut_req.to_dict())
        _, shut_resp = _recv_until_response(shut_req.request_id)
        assert tx_mgr.validate_and_consume_response(shut_resp).accepted is True
        assert shut_resp.ok is True
        server_thread.join(timeout=3.0)
        assert not server_thread.is_alive()

        # 6. Also verify real standalone subprocess CLI startup + PING + SHUTDOWN over stdio JSON lines
        sub_gen = 3
        sub_inst = generate_worker_instance_id(sub_gen)
        main_shm.bind_worker(worker_pid=0, worker_generation=sub_gen)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vietphotobooth.camera.backends.nikon_maid.driver_worker_main",
                "--shm-name",
                shm_name,
                "--parent-pid",
                str(os.getpid()),
                "--worker-generation",
                str(sub_gen),
                "--worker-instance-id",
                sub_inst,
                "--spool-dir",
                spool_dir,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert proc.stdin is not None and proc.stdout is not None
            ready_line = proc.stdout.readline().strip()
            ready_evt = parse_wire_message(ready_line)
            assert isinstance(ready_evt, IPCEvent)
            assert ready_evt.event == IPCEventName.WORKER_READY.value
            assert ready_evt.worker_generation == sub_gen

            sub_tx_mgr = IPCTransactionManager(worker_generation=sub_gen, worker_instance_id=sub_inst)
            sub_ping = sub_tx_mgr.create_request(IPCCommandMethod.PING)
            proc.stdin.write(json.dumps(sub_ping.to_dict()) + "\n")
            proc.stdin.flush()
            ping_line = proc.stdout.readline().strip()
            sub_ping_resp = parse_wire_message(ping_line)
            assert isinstance(sub_ping_resp, IPCResponse)
            assert sub_ping_resp.ok is True
            assert sub_ping_resp.result["worker_pid"] == proc.pid

            sub_shut = sub_tx_mgr.create_request(IPCCommandMethod.SHUTDOWN)
            proc.stdin.write(json.dumps(sub_shut.to_dict()) + "\n")
            proc.stdin.flush()
            shut_line = proc.stdout.readline().strip()
            sub_shut_resp = parse_wire_message(shut_line)
            assert isinstance(sub_shut_resp, IPCResponse)
            assert sub_shut_resp.ok is True
            exit_code = proc.wait(timeout=5.0)
            assert exit_code == 0
        finally:
            if proc.poll() is None:
                proc.kill()
    finally:
        server.shutdown_and_close()
        main_conn.close()
        worker_conn.close()
        main_shm.close()
        main_shm.unlink()


def test_phase22_rejects_wrong_generation_wrong_instance_duplicate_and_expired_request(tmp_path) -> None:
    """Verify Worker rejects wrong worker_generation, wrong worker_instance_id, duplicate request_id, missing deadline, and expired request_id."""
    import multiprocessing
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        NikonDriverWorkerServer,
        PipeConnectionTransport,
    )

    shm_name = _unique_shm_name("p22_val")
    spool_dir = str(tmp_path / "spool_val")
    gen = 4
    inst_id = "worker_gen4_instance_abc"

    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    worker_shm = NikonSharedFrameBuffer.attach(name=shm_name)
    main_conn, worker_conn = multiprocessing.Pipe(duplex=True)

    server = NikonDriverWorkerServer(
        worker_generation=gen,
        worker_instance_id=inst_id,
        shm_buffer=worker_shm,
        spool_dir=spool_dir,
        transport=PipeConnectionTransport(worker_conn),
        session_factory=_FakeNikonSessionForWorker,
    )

    try:
        # 1. Wrong worker_generation -> STALE_WORKER_GENERATION
        req_wrong_gen = IPCRequest(
            method=IPCCommandMethod.PING.value,
            worker_generation=gen - 1,
            worker_instance_id=inst_id,
            request_id="req_wrong_gen_1",
        )
        resp_wrong_gen = server.dispatch_request(req_wrong_gen)
        assert resp_wrong_gen.ok is False
        assert resp_wrong_gen.error_code == IPCErrorCode.STALE_WORKER_GENERATION.value

        # 2. Wrong worker_instance_id -> WORKER_INSTANCE_MISMATCH
        req_wrong_inst = IPCRequest(
            method=IPCCommandMethod.PING.value,
            worker_generation=gen,
            worker_instance_id="worker_gen4_WRONG_INSTANCE",
            request_id="req_wrong_inst_1",
        )
        resp_wrong_inst = server.dispatch_request(req_wrong_inst)
        assert resp_wrong_inst.ok is False
        assert resp_wrong_inst.error_code == IPCErrorCode.WORKER_INSTANCE_MISMATCH.value

        # 3. Duplicate request_id -> First succeeds, second is rejected
        req_dup = IPCRequest(
            method=IPCCommandMethod.PING.value,
            worker_generation=gen,
            worker_instance_id=inst_id,
            request_id="req_duplicate_test_01",
        )
        resp_first = server.dispatch_request(req_dup)
        assert resp_first.ok is True

        resp_second = server.dispatch_request(req_dup)
        assert resp_second.ok is False
        assert resp_second.error_code == IPCErrorCode.INVALID_SCHEMA.value
        assert "Duplicate request_id" in (resp_second.error_message or "")

        # 4. Expired request_id (deadline_mono in the past or sent_at_mono + timeout_s exceeded)
        now = time.perf_counter()
        req_expired = IPCRequest(
            method=IPCCommandMethod.PING.value,
            worker_generation=gen,
            worker_instance_id=inst_id,
            request_id="req_expired_test_01",
            timeout_s=0.5,
            params={"deadline_mono": now - 0.1},
        )
        resp_expired = server.dispatch_request(req_expired, now_mono=now)
        assert resp_expired.ok is False
        assert resp_expired.error_code == IPCErrorCode.REQUEST_TIMED_OUT.value
    finally:
        server.shutdown_and_close()
        main_conn.close()
        worker_conn.close()
        main_shm.close()
        main_shm.unlink()


def test_phase22_live_view_shm_streaming_and_safe_shutdown_while_streaming(tmp_path) -> None:
    """Verify Worker streams Live View frames into SharedMemory and safely joins writer threads before closing SHM on shutdown."""
    import multiprocessing
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        NikonDriverWorkerServer,
        PipeConnectionTransport,
        parse_wire_message,
    )

    shm_name = _unique_shm_name("p22_lv_shm")
    spool_dir = str(tmp_path / "spool_lv")
    gen = 5
    inst_id = generate_worker_instance_id(gen)

    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    worker_shm = NikonSharedFrameBuffer.attach(name=shm_name)
    main_conn, worker_conn = multiprocessing.Pipe(duplex=True)

    fake_session = _FakeNikonSessionForWorker(
        lv_jpeg_bytes=_make_synthetic_jpeg(DEFAULT_LIVE_VIEW_WIDTH, DEFAULT_LIVE_VIEW_HEIGHT, 77)
    )
    server = NikonDriverWorkerServer(
        worker_generation=gen,
        worker_instance_id=inst_id,
        shm_buffer=worker_shm,
        spool_dir=spool_dir,
        transport=PipeConnectionTransport(worker_conn),
        session_factory=lambda: fake_session,
        live_view_poll_interval_s=0.005,
        heartbeat_interval_s=0.030,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    tx_mgr = IPCTransactionManager(worker_generation=gen, worker_instance_id=inst_id)

    def _recv_resp(req_id: str) -> IPCResponse:
        while True:
            assert main_conn.poll(3.0)
            msg = parse_wire_message(main_conn.recv())
            if isinstance(msg, IPCResponse) and msg.request_id == req_id:
                return msg

    try:
        # Connect & Start Live View (with explicit deadline_mono per Audit I-3)
        conn_req = tx_mgr.create_request(
            IPCCommandMethod.CONNECT,
            params={"deadline_mono": time.perf_counter() + 5.0},
        )
        main_conn.send(conn_req.to_dict())
        assert _recv_resp(conn_req.request_id).ok is True

        lv_req = tx_mgr.create_request(
            IPCCommandMethod.START_LIVE_VIEW,
            params={"deadline_mono": time.perf_counter() + 5.0},
        )
        main_conn.send(lv_req.to_dict())
        lv_resp = _recv_resp(lv_req.request_id)
        assert lv_resp.ok is True
        assert server.is_live_view_streaming is True

        # Wait for Worker to publish at least 5 frames into SharedMemory
        seen_seq = 0
        read_frames = []
        deadline = time.perf_counter() + 3.0
        while len(read_frames) < 5 and time.perf_counter() < deadline:
            frame = main_shm.read_latest_frame(
                last_seen_seq_id=seen_seq,
                expected_worker_gen=gen,
            )
            if frame is not None:
                assert frame.is_valid is True
                assert frame.sequence_id > seen_seq
                assert frame.width == DEFAULT_LIVE_VIEW_WIDTH
                assert frame.height == DEFAULT_LIVE_VIEW_HEIGHT
                assert frame.worker_generation == gen
                seen_seq = frame.sequence_id
                read_frames.append(frame)
            else:
                time.sleep(0.005)

        assert len(read_frames) >= 5, f"Expected >= 5 streamed frames in SHM, got {len(read_frames)}"

        # Trigger SHUTDOWN while Live View is actively streaming!
        shut_req = tx_mgr.create_request(IPCCommandMethod.SHUTDOWN)
        main_conn.send(shut_req.to_dict())
        shut_resp = _recv_resp(shut_req.request_id)
        assert shut_resp.ok is True

        server_thread.join(timeout=3.0)
        assert not server_thread.is_alive()
        assert server.is_live_view_streaming is False
        # Worker must have closed its view, but NEVER unlinked Main's SharedMemory
        assert worker_shm.is_closed is True
        assert main_shm.is_closed is False
        assert main_shm.is_unlinked is False
    finally:
        server.shutdown_and_close()
        main_conn.close()
        worker_conn.close()
        main_shm.close()
        main_shm.unlink()


def test_phase22_capture_atomic_spooling_and_never_auto_retries(tmp_path) -> None:
    """Verify Worker CAPTURE spools raw_{tx_id}.jpg + raw_{tx_id}.meta.json atomically and never auto-retries on timeout/failure."""
    import hashlib
    import io
    import json
    import multiprocessing
    from PIL import Image
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        AtomicCaptureSpooler,
        AtomicSpoolError,
        NikonDriverWorkerServer,
        PipeConnectionTransport,
        parse_wire_message,
    )

    shm_name = _unique_shm_name("p22_cap")
    spool_dir = str(tmp_path / "spool_cap")
    gen = 6
    inst_id = generate_worker_instance_id(gen)

    # Create a real JPEG with EXIF metadata
    pil_img = Image.new("RGB", (640, 424), color=(10, 120, 200))
    exif = pil_img.getexif()
    exif[0x010F] = "NIKON CORPORATION"
    exif[0x0110] = "NIKON D780"
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=94, exif=exif.tobytes())
    raw_exif_jpeg = buf.getvalue()
    expected_sha256 = hashlib.sha256(raw_exif_jpeg).hexdigest()

    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    worker_shm = NikonSharedFrameBuffer.attach(name=shm_name)
    main_conn, worker_conn = multiprocessing.Pipe(duplex=True)

    fake_session = _FakeNikonSessionForWorker(capture_jpeg_bytes=raw_exif_jpeg)
    server = NikonDriverWorkerServer(
        worker_generation=gen,
        worker_instance_id=inst_id,
        shm_buffer=worker_shm,
        spool_dir=spool_dir,
        transport=PipeConnectionTransport(worker_conn),
        session_factory=lambda: fake_session,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    tx_mgr = IPCTransactionManager(worker_generation=gen, worker_instance_id=inst_id)

    try:
        # Drain WORKER_READY
        assert main_conn.poll(3.0)
        _ = main_conn.recv()

        # 1. Execute successful CAPTURE transaction (with deadline_mono per Audit I-3)
        cap_req, cap_tx = tx_mgr.begin_capture_transaction(
            params={"deadline_mono": time.perf_counter() + 5.0},
            timeout_s=5.0,
        )
        main_conn.send(cap_req.to_dict())

        received_events: list[IPCEvent] = []
        cap_resp: Optional[IPCResponse] = None
        while cap_resp is None:
            assert main_conn.poll(3.0)
            msg = parse_wire_message(main_conn.recv())
            if isinstance(msg, IPCEvent):
                outcome = tx_mgr.validate_and_apply_event(msg)
                assert outcome.accepted is True, f"Event {msg.event} rejected: {outcome.reason_detail}"
                received_events.append(msg)
            elif isinstance(msg, IPCResponse):
                cap_resp = msg

        assert cap_resp is not None
        resp_outcome = tx_mgr.validate_and_consume_response(cap_resp)
        assert resp_outcome.accepted is True, f"Response rejected: {resp_outcome.reason_detail}"
        assert cap_resp.ok is True
        assert fake_session.capture_calls == 1

        event_names = [e.event for e in received_events]
        assert IPCEventName.CAPTURE_STARTED.value in event_names
        assert IPCEventName.CAPTURE_COMPLETED.value in event_names

        # Verify spooled files on disk
        raw_path = cap_resp.result["raw_file_path"]
        meta_path = cap_resp.result["meta_file_path"]
        assert os.path.isfile(raw_path)
        assert os.path.isfile(meta_path)
        assert os.path.basename(raw_path) == f"raw_{cap_tx.tx_id}.jpg"
        assert os.path.basename(meta_path) == f"raw_{cap_tx.tx_id}.meta.json"
        assert not os.path.exists(f"{raw_path}.part")
        assert not os.path.exists(f"{meta_path}.part")

        with open(raw_path, "rb") as f_jpg:
            disk_bytes = f_jpg.read()
        assert disk_bytes == raw_exif_jpeg
        assert hashlib.sha256(disk_bytes).hexdigest() == expected_sha256

        with open(meta_path, "r", encoding="utf-8") as f_meta:
            manifest = json.load(f_meta)
        assert manifest["tx_id"] == cap_tx.tx_id
        assert manifest["request_id"] == cap_req.request_id
        assert manifest["worker_generation"] == gen
        assert manifest["worker_instance_id"] == inst_id
        assert manifest["sha256"] == expected_sha256
        assert manifest["file_size"] == len(raw_exif_jpeg)
        assert manifest["width"] == 640
        assert manifest["height"] == 424

        # Verify zero-overwrite guarantee on AtomicCaptureSpooler
        spooler = AtomicCaptureSpooler(spool_dir)
        with pytest.raises(AtomicSpoolError, match="Refusing to overwrite"):
            spooler.spool_capture(
                tx_id=cap_tx.tx_id,
                request_id="req_overwrite_attempt",
                worker_generation=gen,
                worker_instance_id=inst_id,
                raw_jpeg=raw_exif_jpeg,
            )

        # 2. Verify Worker NEVER auto-retries CAPTURE when capture_photo times out / returns None
        fake_session._fail_capture_timeout = True
        calls_before_fail = fake_session.capture_calls
        fail_req, fail_tx = tx_mgr.begin_capture_transaction(
            params={"deadline_mono": time.perf_counter() + 2.0},
            timeout_s=2.0,
        )
        main_conn.send(fail_req.to_dict())

        fail_resp: Optional[IPCResponse] = None
        while fail_resp is None:
            assert main_conn.poll(3.0)
            msg = parse_wire_message(main_conn.recv())
            if isinstance(msg, IPCEvent):
                tx_mgr.validate_and_apply_event(msg)
            elif isinstance(msg, IPCResponse):
                fail_resp = msg

        assert fail_resp is not None
        assert fail_resp.ok is False
        assert fail_resp.error_code == IPCErrorCode.NIKON_CAPTURE_SDRAM_TIMEOUT.value
        # Strictly 1 call, NEVER retried!
        assert fake_session.capture_calls == calls_before_fail + 1
    finally:
        server.shutdown_and_close()
        server_thread.join(timeout=2.0)
        main_conn.close()
        worker_conn.close()
        main_shm.close()
        main_shm.unlink()


def test_phase22_worker_usb_disconnect_circuit_breaker_emits_events_and_stops_lv(tmp_path) -> None:
    """Verify USB disconnect (REMOVE_CHILD / -116) in Worker trips circuit breaker, emits DISCONNECTED, and stops MAID calls."""
    import multiprocessing
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        NikonDriverWorkerServer,
        PipeConnectionTransport,
        parse_wire_message,
    )

    shm_name = _unique_shm_name("p22_disc")
    spool_dir = str(tmp_path / "spool_disc")
    gen = 7
    inst_id = generate_worker_instance_id(gen)

    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    worker_shm = NikonSharedFrameBuffer.attach(name=shm_name)
    main_conn, worker_conn = multiprocessing.Pipe(duplex=True)

    fake_session = _FakeNikonSessionForWorker(simulate_disconnect_on_capture=True)
    server = NikonDriverWorkerServer(
        worker_generation=gen,
        worker_instance_id=inst_id,
        shm_buffer=worker_shm,
        spool_dir=spool_dir,
        transport=PipeConnectionTransport(worker_conn),
        session_factory=lambda: fake_session,
        live_view_poll_interval_s=0.005,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    tx_mgr = IPCTransactionManager(worker_generation=gen, worker_instance_id=inst_id)

    try:
        # Drain WORKER_READY
        assert main_conn.poll(3.0)
        _ = main_conn.recv()

        # Trigger CAPTURE which simulates -116 USB disconnect mid-transfer
        cap_req, _cap_tx = tx_mgr.begin_capture_transaction(
            params={"deadline_mono": time.perf_counter() + 3.0},
            timeout_s=3.0,
        )
        main_conn.send(cap_req.to_dict())

        events: list[IPCEvent] = []
        cap_resp: Optional[IPCResponse] = None
        while cap_resp is None:
            assert main_conn.poll(3.0)
            msg = parse_wire_message(main_conn.recv())
            if isinstance(msg, IPCEvent):
                events.append(msg)
            elif isinstance(msg, IPCResponse):
                cap_resp = msg

        assert cap_resp is not None
        assert cap_resp.ok is False
        assert cap_resp.error_code == IPCErrorCode.NIKON_DISCONNECTED.value

        evt_names = [e.event for e in events]
        assert IPCEventName.DEVICE_ERROR.value in evt_names
        assert IPCEventName.DISCONNECTED.value in evt_names
        assert IPCEventName.CAPTURE_FAILED.value in evt_names
        assert int(main_shm.global_header.writer_state) == int(WriterState.DISCONNECTED)

        # Subsequent commands to the disconnected Worker must immediately return NIKON_DISCONNECTED
        # without invoking any further MAID operations on fake_session!
        lv_req = tx_mgr.create_request(
            IPCCommandMethod.START_LIVE_VIEW,
            params={"deadline_mono": time.perf_counter() + 3.0},
        )
        main_conn.send(lv_req.to_dict())
        assert main_conn.poll(3.0)
        lv_resp = parse_wire_message(main_conn.recv())
        assert isinstance(lv_resp, IPCResponse)
        assert lv_resp.ok is False
        assert lv_resp.error_code == IPCErrorCode.NIKON_DISCONNECTED.value
        assert fake_session.calls_after_device_lost == 0
    finally:
        server.shutdown_and_close()
        server_thread.join(timeout=2.0)
        main_conn.close()
        worker_conn.close()
        main_shm.close()
        main_shm.unlink()


# ============================================================================
# Phase 2.2.1 Patch Scope A Tests (Audit S-3, I-7, M-2, P-2/P-3, S-2, I-3, S-6)
# ============================================================================

def test_phase221_real_win32_job_object_create_suspended_with_and_without_kill_on_close(tmp_path) -> None:
    """Audit S-3: Spawn real Worker child processes via CreateProcess(CREATE_SUSPENDED) -> AssignProcessToJobObject -> ResumeThread.

    Verifies:
    1. Real Windows Job Object WITHOUT `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` -> Worker rejects startup with
       `EXIT_NOT_IN_JOB_OBJECT = 72` and never loads any Nikon MAID DLL.
    2. Real Windows Job Object WITH `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000)` -> Worker passes Startup Gate,
       attaches to SharedMemory, responds to PING, and exits cleanly with `EXIT_OK = 0` on SHUTDOWN.
    """
    if sys.platform != "win32":
        pytest.skip("Windows Job Object test requires win32")

    import _winapi
    import json
    import subprocess
    from ctypes import wintypes
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_main import (
        EXIT_NOT_IN_JOB_OBJECT,
        EXIT_OK,
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        JobObjectExtendedLimitInformation,
    )
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        parse_wire_message,
    )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPCVOID, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPCVOID,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    CREATE_SUSPENDED = 0x00000004
    CREATE_BREAKAWAY_FROM_JOB = 0x01000000

    def _spawn_suspended_and_assign_job(cmd_args: list[str], limit_flags: int) -> tuple[int, int, str, str]:
        """Create a real Win32 Job Object with `limit_flags`, launch `cmd_args` with CREATE_SUSPENDED,
        assign to Job Object, resume primary thread via `ResumeThread`, and return `(exit_code, h_job, stdout, stderr)`.
        """
        h_job = kernel32.CreateJobObjectW(None, None)
        assert h_job, f"CreateJobObjectW failed: WinError={ctypes.get_last_error()}"

        ext_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        ext_info.BasicLimitInformation.LimitFlags = wintypes.DWORD(limit_flags)
        ok_set = kernel32.SetInformationJobObject(
            h_job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(ext_info),
            wintypes.DWORD(ctypes.sizeof(ext_info)),
        )
        assert ok_set, f"SetInformationJobObject failed: WinError={ctypes.get_last_error()}"

        stdout_file = tmp_path / f"job_stdout_{limit_flags}_{time.time_ns()}.txt"
        stderr_file = tmp_path / f"job_stderr_{limit_flags}_{time.time_ns()}.txt"

        # Use a wrapper command that runs driver_worker_main with an empty StringIO stdin so it exits cleanly on EOF
        runner_code = (
            "import io, sys; "
            "sys.stdin = io.StringIO(''); "
            f"sys.stdout = open({str(stdout_file)!r}, 'w', encoding='utf-8'); "
            f"sys.stderr = open({str(stderr_file)!r}, 'w', encoding='utf-8'); "
            "from vietphotobooth.camera.backends.nikon_maid.driver_worker_main import main; "
            f"rc = main({cmd_args!r}); "
            "sys.stdout.flush(); sys.stderr.flush(); "
            "sys.exit(rc)"
        )
        cmd_line = subprocess.list2cmdline([sys.executable, "-c", runner_code])

        # Try CREATE_SUSPENDED | CREATE_BREAKAWAY_FROM_JOB first; fall back to CREATE_SUSPENDED (nested job)
        try:
            hp, ht, _pid, _tid = _winapi.CreateProcess(
                sys.executable,
                cmd_line,
                None,
                None,
                False,
                CREATE_SUSPENDED | CREATE_BREAKAWAY_FROM_JOB,
                None,
                None,
                subprocess.STARTUPINFO(),
            )
        except OSError:
            hp, ht, _pid, _tid = _winapi.CreateProcess(
                sys.executable,
                cmd_line,
                None,
                None,
                False,
                CREATE_SUSPENDED,
                None,
                None,
                subprocess.STARTUPINFO(),
            )

        try:
            ok_assign = kernel32.AssignProcessToJobObject(h_job, wintypes.HANDLE(int(hp)))
            assert ok_assign, f"AssignProcessToJobObject failed: WinError={ctypes.get_last_error()}"

            prev_suspend_count = kernel32.ResumeThread(wintypes.HANDLE(int(ht)))
            assert prev_suspend_count == 1, f"Expected prev_suspend_count=1, got {prev_suspend_count}"

            wait_res = _winapi.WaitForSingleObject(hp, 10000)
            if wait_res != _winapi.WAIT_OBJECT_0:
                _winapi.TerminateProcess(hp, 99)
                assert False, f"Worker process timed out (wait_res={wait_res})"
            exit_code = int(_winapi.GetExitCodeProcess(hp))
        finally:
            _winapi.CloseHandle(ht)
            _winapi.CloseHandle(hp)

        out_text = stdout_file.read_text(encoding="utf-8") if stdout_file.exists() else ""
        err_text = stderr_file.read_text(encoding="utf-8") if stderr_file.exists() else ""
        return exit_code, int(h_job), out_text, err_text

    spool_dir = str(tmp_path / "spool_real_job")
    shm_name = _unique_shm_name("p221_job")
    gen = 1
    inst_id = generate_worker_instance_id(gen)

    worker_args = [
        "--shm-name",
        shm_name,
        "--parent-pid",
        str(os.getpid()),
        "--worker-generation",
        str(gen),
        "--worker-instance-id",
        inst_id,
        "--spool-dir",
        spool_dir,
    ]

    # Case 1: Real Windows Job Object WITHOUT JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (LimitFlags = 0)
    # Even though IsProcessInJob() is True, QueryInformationJobObject sees LimitFlags=0x0 and MUST reject!
    rc_no_kill, h_job_no_kill, _out1, err1 = _spawn_suspended_and_assign_job(worker_args, limit_flags=0)
    try:
        assert rc_no_kill == EXIT_NOT_IN_JOB_OBJECT, (
            f"Expected EXIT_NOT_IN_JOB_OBJECT (72) when Job lacks KILL_ON_JOB_CLOSE, got {rc_no_kill}. stderr={err1!r}"
        )
        assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in err1
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(h_job_no_kill))

    # Case 2: Real Windows Job Object WITH JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (LimitFlags = 0x2000)
    # Create SharedMemory so Worker passes Startup Gate, attaches SHM, emits WORKER_READY, and exits 0 on stdin EOF
    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    h_job_with_kill = 0
    try:
        rc_with_kill, h_job_with_kill, out2, err2 = _spawn_suspended_and_assign_job(
            worker_args,
            limit_flags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        )
        assert rc_with_kill == EXIT_OK, (
            f"Expected EXIT_OK (0) when Job has KILL_ON_JOB_CLOSE, got {rc_with_kill}. stderr={err2!r}"
        )
        ready_evt = parse_wire_message(out2.strip().splitlines()[0])
        assert isinstance(ready_evt, IPCEvent)
        assert ready_evt.event == IPCEventName.WORKER_READY.value
    finally:
        if h_job_with_kill:
            kernel32.CloseHandle(wintypes.HANDLE(h_job_with_kill))
        main_shm.close()
        main_shm.unlink()


def test_phase221_parent_exited_and_watchdog_triggers_safe_shutdown(tmp_path) -> None:
    """Audit S-5: Verify Startup Gate rejects an already-exited parent process AND ParentWatchdogThread stops Worker when parent exits."""
    import multiprocessing
    import subprocess
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_main import (
        EXIT_PARENT_NOT_ALIVE,
        ParentWatchdogThread,
        WorkerStartupConfig,
        close_win32_handle,
        execute_startup_gate,
        open_and_check_parent_alive,
    )
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        NikonDriverWorkerServer,
        PipeConnectionTransport,
    )

    # 1. Spawn a real short-lived process that exits immediately, hold its PID, and verify gate rejects it
    short_proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    short_proc.wait(timeout=15.0)
    exited_pid = short_proc.pid

    cfg = WorkerStartupConfig(
        shm_name="nsfb_exited_parent",
        parent_pid=exited_pid,
        worker_generation=1,
        worker_instance_id="w_gen1",
        spool_dir=str(tmp_path / "spool_parent_exit"),
    )
    gate_res = execute_startup_gate(
        cfg,
        job_check_fn=lambda: (True, "In Job"),
        sdk_loaded_check_fn=lambda: (False, None),
    )
    assert gate_res.passed is False
    assert gate_res.exit_code == EXIT_PARENT_NOT_ALIVE

    # 2. Spawn a live parent process, open its Win32 handle via open_and_check_parent_alive,
    #    attach ParentWatchdogThread to NikonDriverWorkerServer, then terminate the parent process
    live_parent = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    h_parent: Optional[int] = None
    shm_name = _unique_shm_name("p221_wdog")
    gen = 1
    inst_id = generate_worker_instance_id(gen)
    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    worker_shm = NikonSharedFrameBuffer.attach(name=shm_name)
    main_conn, worker_conn = multiprocessing.Pipe(duplex=True)

    server = NikonDriverWorkerServer(
        worker_generation=gen,
        worker_instance_id=inst_id,
        shm_buffer=worker_shm,
        spool_dir=str(tmp_path / "spool_wdog"),
        transport=PipeConnectionTransport(worker_conn),
        session_factory=_FakeNikonSessionForWorker,
    )

    try:
        alive, h_parent, _msg = open_and_check_parent_alive(live_parent.pid)
        assert alive is True
        assert h_parent is not None

        watchdog = ParentWatchdogThread(
            parent_handle=h_parent,
            on_parent_died=server.shutdown_and_close,
            poll_interval_ms=30,
        )
        watchdog.start()

        # Terminate the watched parent process
        live_parent.terminate()
        live_parent.wait(timeout=5.0)

        # Watchdog must detect WAIT_OBJECT_0 and shut down the server cleanly
        watchdog.join(timeout=3.0)
        assert not watchdog.is_alive()
        assert server.is_shutdown is True
        assert worker_shm.is_closed is True
    finally:
        if live_parent.poll() is None:
            live_parent.kill()
        close_win32_handle(h_parent)
        server.shutdown_and_close()
        main_conn.close()
        worker_conn.close()
        main_shm.close()
        main_shm.unlink()


def test_phase221_tx_id_and_request_id_allowlist_blocks_ntfs_ads_and_special_chars(tmp_path) -> None:
    """Audit I-7: Verify server and AtomicCaptureSpooler enforce `^[A-Za-z0-9_-]{1,128}$` and reject `:`, `?`, `*`, control chars."""
    import multiprocessing
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        AtomicCaptureSpooler,
        AtomicSpoolError,
        NikonDriverWorkerServer,
        PipeConnectionTransport,
    )

    spool_dir = str(tmp_path / "spool_allowlist")
    spooler = AtomicCaptureSpooler(spool_dir)
    valid_jpeg = _make_synthetic_jpeg(160, 120, 55)

    forbidden_ids = [
        "tx_ntfs:stream",
        "tx_wild*card",
        "tx_question?mark",
        "tx_ctrl\x07char",
        "tx_newline\nid",
        "tx_quote\"id",
        "tx_angle<id>",
        "tx_pipe|id",
        "../tx_traversal",
        "a\\b",
        "a/b",
        "tx space",
        "a" * 129,
    ]

    # 1. Verify AtomicCaptureSpooler rejects every forbidden tx_id and creates zero files
    for bad_tx_id in forbidden_ids:
        with pytest.raises(AtomicSpoolError, match="allowlist"):
            spooler.spool_capture(
                tx_id=bad_tx_id,
                request_id="req_valid_01",
                worker_generation=1,
                worker_instance_id="w_gen1",
                raw_jpeg=valid_jpeg,
            )
    assert os.listdir(spool_dir) == []

    # 2. Verify NikonDriverWorkerServer rejects forbidden tx_id and request_id before executing handler
    shm_name = _unique_shm_name("p221_allow")
    gen = 1
    inst_id = "w_gen1_allow"
    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    worker_shm = NikonSharedFrameBuffer.attach(name=shm_name)
    main_conn, worker_conn = multiprocessing.Pipe(duplex=True)
    fake_session = _FakeNikonSessionForWorker()

    server = NikonDriverWorkerServer(
        worker_generation=gen,
        worker_instance_id=inst_id,
        shm_buffer=worker_shm,
        spool_dir=spool_dir,
        transport=PipeConnectionTransport(worker_conn),
        session_factory=lambda: fake_session,
    )

    try:
        for idx, bad_tx in enumerate(["cap_ads:stream", "cap_wild*", "cap_q?mark", "cap_ctrl\x1f"]):
            req = IPCRequest(
                method=IPCCommandMethod.CAPTURE.value,
                worker_generation=gen,
                worker_instance_id=inst_id,
                request_id=f"req_ok_{idx}",
                tx_id=bad_tx,
                params={"deadline_mono": time.perf_counter() + 5.0},
            )
            resp = server.dispatch_request(req)
            assert resp.ok is False
            assert resp.error_code == IPCErrorCode.INVALID_SCHEMA.value
            assert "allowlist" in (resp.error_message or "")

        bad_req = IPCRequest(
            method=IPCCommandMethod.PING.value,
            worker_generation=gen,
            worker_instance_id=inst_id,
            request_id="req:invalid:colon",
        )
        bad_resp = server.dispatch_request(bad_req)
        assert bad_resp.ok is False
        assert bad_resp.error_code == IPCErrorCode.INVALID_SCHEMA.value
        assert fake_session.capture_calls == 0
        assert os.listdir(spool_dir) == []
    finally:
        server.shutdown_and_close()
        main_conn.close()
        worker_conn.close()
        main_shm.close()
        main_shm.unlink()


def test_phase221_mandatory_deadline_and_falsy_zero_deadline_handling(tmp_path) -> None:
    """Audit I-3: Verify non-exempt requests without deadline_mono/sent_at_mono are rejected, and falsy 0.0 is NOT ignored."""
    import multiprocessing
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        NikonDriverWorkerServer,
        PipeConnectionTransport,
    )

    shm_name = _unique_shm_name("p221_dl")
    spool_dir = str(tmp_path / "spool_dl")
    gen = 1
    inst_id = "w_gen1_dl"
    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    worker_shm = NikonSharedFrameBuffer.attach(name=shm_name)
    main_conn, worker_conn = multiprocessing.Pipe(duplex=True)
    fake_session = _FakeNikonSessionForWorker()

    server = NikonDriverWorkerServer(
        worker_generation=gen,
        worker_instance_id=inst_id,
        shm_buffer=worker_shm,
        spool_dir=spool_dir,
        transport=PipeConnectionTransport(worker_conn),
        session_factory=lambda: fake_session,
    )

    try:
        # 1. Non-exempt command (DISCOVER / CAPTURE) missing both deadline_mono and sent_at_mono -> rejected
        req_no_dl = IPCRequest(
            method=IPCCommandMethod.DISCOVER.value,
            worker_generation=gen,
            worker_instance_id=inst_id,
            request_id="req_missing_deadline_01",
            params={},
        )
        resp_no_dl = server.dispatch_request(req_no_dl)
        assert resp_no_dl.ok is False
        assert resp_no_dl.error_code == IPCErrorCode.INVALID_SCHEMA.value
        assert "deadline_mono" in (resp_no_dl.error_message or "")
        assert fake_session.discover_calls == 0

        # 2. Falsy deadline_mono = 0.0 when now_mono = 10.0 -> must NOT be skipped, must fail with REQUEST_TIMED_OUT
        req_zero_dl = IPCRequest(
            method=IPCCommandMethod.DISCOVER.value,
            worker_generation=gen,
            worker_instance_id=inst_id,
            request_id="req_zero_deadline_02",
            params={"deadline_mono": 0.0},
        )
        resp_zero_dl = server.dispatch_request(req_zero_dl, now_mono=10.0)
        assert resp_zero_dl.ok is False
        assert resp_zero_dl.error_code == IPCErrorCode.REQUEST_TIMED_OUT.value

        # 3. Falsy sent_at_mono = 0.0 with timeout_s = 1.0 when now_mono = 5.0 -> must fail with REQUEST_TIMED_OUT
        req_zero_sent = IPCRequest(
            method=IPCCommandMethod.DISCOVER.value,
            worker_generation=gen,
            worker_instance_id=inst_id,
            request_id="req_zero_sent_03",
            timeout_s=1.0,
            params={"sent_at_mono": 0.0},
        )
        resp_zero_sent = server.dispatch_request(req_zero_sent, now_mono=5.0)
        assert resp_zero_sent.ok is False
        assert resp_zero_sent.error_code == IPCErrorCode.REQUEST_TIMED_OUT.value

        # 4. Valid sent_at_mono within timeout_s -> succeeds
        now = time.perf_counter()
        req_valid_sent = IPCRequest(
            method=IPCCommandMethod.DISCOVER.value,
            worker_generation=gen,
            worker_instance_id=inst_id,
            request_id="req_valid_sent_04",
            timeout_s=3.0,
            params={"sent_at_mono": now},
        )
        resp_valid_sent = server.dispatch_request(req_valid_sent, now_mono=now + 0.1)
        assert resp_valid_sent.ok is True
        assert fake_session.discover_calls == 1
    finally:
        server.shutdown_and_close()
        main_conn.close()
        worker_conn.close()
        main_shm.close()
        main_shm.unlink()


def test_phase221_corrupted_entropy_scan_jpeg_with_valid_eoi_rejected_and_crash_injection(tmp_path, monkeypatch) -> None:
    """Audit P-2, P-3 & P-6:
    1. JPEG with valid SOI (0xFFD8) and EOI (0xFFD9) but corrupted entropy scan is rejected by full `img.load()` decode.
    2. Crash injection between Step 1 (`raw_{tx_id}.jpg` committed) and Step 2 (`raw_{tx_id}.meta.json` rename)
       leaves `.jpg` intact, leaves `.meta.json.part` on disk, never emits `CAPTURE_COMPLETED`, and refuses overwrite on retry.
    """
    import io
    from PIL import Image
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        AtomicCaptureSpooler,
        AtomicSpoolError,
    )

    spool_dir = str(tmp_path / "spool_p236")
    spooler = AtomicCaptureSpooler(spool_dir)

    # 1. Construct a JPEG with valid SOI + valid headers + corrupted entropy scan + valid EOI (0xFFD9)
    valid_img = Image.new("RGB", (256, 256), color=(120, 40, 200))
    buf = io.BytesIO()
    valid_img.save(buf, format="JPEG", quality=90)
    valid_jpeg = buf.getvalue()

    sos_idx = valid_jpeg.find(b"\xff\xda")
    assert sos_idx > 0
    corrupt_scan_jpeg = valid_jpeg[: sos_idx + 14] + b"\xff\xc0\x00\x00\xff\xd9"
    assert corrupt_scan_jpeg[:2] == b"\xff\xd8"
    assert corrupt_scan_jpeg[-2:] == b"\xff\xd9"

    with pytest.raises(AtomicSpoolError, match="entropy-scan decoding"):
        spooler.spool_capture(
            tx_id="tx_corrupt_scan_01",
            request_id="req_corrupt_scan_01",
            worker_generation=1,
            worker_instance_id="w_gen1",
            raw_jpeg=corrupt_scan_jpeg,
        )
    assert os.listdir(spool_dir) == []

    # 2. Crash injection between JPEG commit and manifest commit
    real_rename = os.rename
    rename_calls: list[tuple[str, str]] = []

    def _crash_on_manifest_rename(src: str, dst: str) -> None:
        rename_calls.append((src, dst))
        if dst.endswith(".meta.json"):
            raise OSError("Simulated Worker crash right before manifest rename")
        real_rename(src, dst)

    monkeypatch.setattr(os, "rename", _crash_on_manifest_rename)

    tx_crash = "tx_crash_mid_spool_02"
    with pytest.raises(AtomicSpoolError, match="Atomic rename failed"):
        spooler.spool_capture(
            tx_id=tx_crash,
            request_id="req_crash_02",
            worker_generation=1,
            worker_instance_id="w_gen1",
            raw_jpeg=valid_jpeg,
        )

    # Verify Step 1 (.jpg) succeeded and is intact on disk, while Step 2 left .meta.json.part and no .meta.json
    jpg_final = os.path.join(spool_dir, f"raw_{tx_crash}.jpg")
    meta_final = os.path.join(spool_dir, f"raw_{tx_crash}.meta.json")
    meta_part = os.path.join(spool_dir, f"raw_{tx_crash}.meta.json.part")

    assert os.path.isfile(jpg_final)
    assert open(jpg_final, "rb").read() == valid_jpeg
    assert not os.path.exists(meta_final)
    assert os.path.isfile(meta_part)

    # Restore os.rename and confirm zero-overwrite protection refuses any attempt to overwrite the partial/committed artifacts
    monkeypatch.setattr(os, "rename", real_rename)
    with pytest.raises(AtomicSpoolError, match="Refusing to overwrite"):
        spooler.spool_capture(
            tx_id=tx_crash,
            request_id="req_crash_retry_02",
            worker_generation=1,
            worker_instance_id="w_gen1",
            raw_jpeg=valid_jpeg,
        )


def test_phase221_pipe_eof_broken_pipe_and_shutdown_during_capture(tmp_path) -> None:
    """Audit I-4, I-6 & S-6:
    1. Pipe EOF causes Worker Server to exit cleanly and close its SharedMemory view.
    2. BrokenPipeError on send_message sets shutdown_event and stops the server cleanly.
    3. SHUTDOWN arriving while CAPTURE is executing waits for in-flight CAPTURE + atomic spooling
       to finish before closing NikonSession or SharedMemory (zero mid-handler resource teardown).
    """
    import multiprocessing
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        EXIT_SERVER_OK,
        NikonDriverWorkerServer,
        PipeConnectionTransport,
        parse_wire_message,
    )

    # --- Part 1: Pipe EOF ---
    shm_eof = _unique_shm_name("p221_eof")
    main_shm1 = NikonSharedFrameBuffer(name=shm_eof, create=True, worker_generation=1)
    worker_shm1 = NikonSharedFrameBuffer.attach(name=shm_eof)
    main_c1, worker_c1 = multiprocessing.Pipe(duplex=True)

    srv1 = NikonDriverWorkerServer(
        worker_generation=1,
        worker_instance_id="w_eof_1",
        shm_buffer=worker_shm1,
        spool_dir=str(tmp_path / "spool_eof"),
        transport=PipeConnectionTransport(worker_c1),
        session_factory=_FakeNikonSessionForWorker,
    )
    t1 = threading.Thread(target=srv1.serve_forever, daemon=True)
    t1.start()

    try:
        assert main_c1.poll(3.0)
        _ = main_c1.recv()  # WORKER_READY
        # Close Main's pipe endpoint -> triggers EOF in Worker recv_message()
        main_c1.close()
        t1.join(timeout=3.0)
        assert not t1.is_alive()
        assert srv1.shutdown_exit_code == EXIT_SERVER_OK
        assert worker_shm1.is_closed is True
    finally:
        srv1.shutdown_and_close()
        worker_c1.close()
        main_shm1.close()
        main_shm1.unlink()

    # --- Part 2: BrokenPipeError during send ---
    class _BrokenSendTransport:
        def __init__(self) -> None:
            self.closed = False

        def recv_message(self) -> Optional[dict]:
            return None

        def send_message(self, payload: dict) -> None:
            raise BrokenPipeError("Simulated broken pipe on send")

        def close(self) -> None:
            self.closed = True

    shm_bp = _unique_shm_name("p221_bp")
    main_shm2 = NikonSharedFrameBuffer(name=shm_bp, create=True, worker_generation=1)
    worker_shm2 = NikonSharedFrameBuffer.attach(name=shm_bp)
    bp_transport = _BrokenSendTransport()
    srv2 = NikonDriverWorkerServer(
        worker_generation=1,
        worker_instance_id="w_bp_1",
        shm_buffer=worker_shm2,
        spool_dir=str(tmp_path / "spool_bp"),
        transport=bp_transport,
        session_factory=_FakeNikonSessionForWorker,
    )
    try:
        rc2 = srv2.serve_forever(emit_ready_event=True)
        assert rc2 == EXIT_SERVER_OK
        assert srv2.is_shutdown is True
        assert worker_shm2.is_closed is True
        assert bp_transport.closed is True
    finally:
        main_shm2.close()
        main_shm2.unlink()

    # --- Part 3: SHUTDOWN / watchdog shutdown triggered while CAPTURE is in-flight ---
    shm_cap = _unique_shm_name("p221_shut_cap")
    main_shm3 = NikonSharedFrameBuffer(name=shm_cap, create=True, worker_generation=1)
    worker_shm3 = NikonSharedFrameBuffer.attach(name=shm_cap)
    main_c3, worker_c3 = multiprocessing.Pipe(duplex=True)

    capture_entered = threading.Event()
    allow_capture_finish = threading.Event()
    shm_was_open_during_capture = False

    class _SlowCaptureSession(_FakeNikonSessionForWorker):
        def capture_photo(self, timeout_sec: float = 12.0, autofocus_first: bool = False, on_capture_start: Any = None) -> Optional[bytes]:
            nonlocal shm_was_open_during_capture
            self.capture_calls += 1
            if on_capture_start:
                on_capture_start()
            capture_entered.set()
            allow_capture_finish.wait(timeout=3.0)
            shm_was_open_during_capture = not worker_shm3.is_closed
            self._last_capture_transfer_state = "COMPLETE_IN_RAM"
            return self._capture_jpeg_bytes

    slow_session = _SlowCaptureSession()
    srv3 = NikonDriverWorkerServer(
        worker_generation=1,
        worker_instance_id="w_shut_cap_1",
        shm_buffer=worker_shm3,
        spool_dir=str(tmp_path / "spool_shut_cap"),
        transport=PipeConnectionTransport(worker_c3),
        session_factory=lambda: slow_session,
    )
    t3 = threading.Thread(target=srv3.serve_forever, daemon=True)
    t3.start()

    tx_mgr3 = IPCTransactionManager(worker_generation=1, worker_instance_id="w_shut_cap_1")
    try:
        assert main_c3.poll(3.0)
        _ = main_c3.recv()  # WORKER_READY

        cap_req, cap_tx = tx_mgr3.begin_capture_transaction(
            params={"deadline_mono": time.perf_counter() + 5.0},
            timeout_s=5.0,
        )
        shut_req = tx_mgr3.create_request(IPCCommandMethod.SHUTDOWN)

        # Send CAPTURE followed immediately by SHUTDOWN while CAPTURE is in-flight
        main_c3.send(cap_req.to_dict())
        assert capture_entered.wait(timeout=2.0)
        main_c3.send(shut_req.to_dict())

        # Also invoke shutdown_and_close concurrently from a separate thread (simulating watchdog trigger mid-capture)
        concurrent_shut_codes: list[int] = []
        wdog_thread = threading.Thread(
            target=lambda: concurrent_shut_codes.append(srv3.shutdown_and_close(handler_wait_timeout_s=3.0)),
            daemon=True,
        )
        wdog_thread.start()
        time.sleep(0.05)
        # While capture handler is still blocked, worker_shm3 MUST NOT have been closed under it!
        assert worker_shm3.is_closed is False

        # Now let capture finish
        allow_capture_finish.set()
        wdog_thread.join(timeout=3.0)
        t3.join(timeout=3.0)

        assert shm_was_open_during_capture is True
        assert concurrent_shut_codes == [EXIT_SERVER_OK]
        assert os.path.isfile(os.path.join(str(tmp_path / "spool_shut_cap"), f"raw_{cap_tx.tx_id}.jpg"))
        assert os.path.isfile(os.path.join(str(tmp_path / "spool_shut_cap"), f"raw_{cap_tx.tx_id}.meta.json"))
    finally:
        allow_capture_finish.set()
        srv3.shutdown_and_close()
        main_c3.close()
        worker_c3.close()
        main_shm3.close()
        main_shm3.unlink()


def test_phase221_writer_thread_join_timeout_and_no_shm_writes_after_shutdown(tmp_path) -> None:
    """Audit M-2 & S-6:
    1. If LiveViewProducerThread hangs and `thread.is_alive()` is True after `join()`, Worker logs CRITICAL,
       sets `writer_state = WriterState.STOPPING`, does NOT call `close_module()` or `shm.close()`,
       refuses CAPTURE, and returns `EXIT_WRITER_THREAD_JOIN_TIMEOUT = 76`.
    2. After normal Worker shutdown, zero SharedMemory writes or heartbeat updates occur.
    """
    import multiprocessing
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        EXIT_WRITER_THREAD_JOIN_TIMEOUT,
        NikonDriverWorkerServer,
        PipeConnectionTransport,
    )

    shm_name = _unique_shm_name("p221_hang")
    spool_dir = str(tmp_path / "spool_hang")
    gen = 8
    inst_id = "w_hang_8"

    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)
    worker_shm = NikonSharedFrameBuffer.attach(name=shm_name)
    main_conn, worker_conn = multiprocessing.Pipe(duplex=True)

    hang_entered = threading.Event()
    release_hang = threading.Event()

    class _HangingLvSession(_FakeNikonSessionForWorker):
        def fetch_live_view_frame(self) -> Optional[bytes]:
            hang_entered.set()
            release_hang.wait(timeout=5.0)
            return None

    hang_session = _HangingLvSession()
    server = NikonDriverWorkerServer(
        worker_generation=gen,
        worker_instance_id=inst_id,
        shm_buffer=worker_shm,
        spool_dir=spool_dir,
        transport=PipeConnectionTransport(worker_conn),
        session_factory=lambda: hang_session,
        writer_join_timeout_s=0.08,
    )

    try:
        # Start Live View so producer thread enters the blocking fetch_live_view_frame()
        lv_req = IPCRequest(
            method=IPCCommandMethod.START_LIVE_VIEW.value,
            worker_generation=gen,
            worker_instance_id=inst_id,
            request_id="req_lv_hang_1",
            params={"deadline_mono": time.perf_counter() + 5.0},
        )
        assert server.dispatch_request(lv_req).ok is True
        assert hang_entered.wait(timeout=2.0)

        # Attempt CAPTURE while LV producer thread is hung -> must fail before calling capture_photo!
        cap_req = IPCRequest(
            method=IPCCommandMethod.CAPTURE.value,
            worker_generation=gen,
            worker_instance_id=inst_id,
            request_id="req_cap_hang_2",
            tx_id="tx_cap_hang_2",
            params={"deadline_mono": time.perf_counter() + 5.0},
        )
        cap_resp = server.dispatch_request(cap_req)
        assert cap_resp.ok is False
        assert cap_resp.error_code == IPCErrorCode.NIKON_WORKER_HANG_TIMEOUT.value
        assert hang_session.capture_calls == 0
        assert int(main_shm.global_header.writer_state) == int(WriterState.STOPPING)

        # Now run shutdown_and_close() while producer thread is STILL alive:
        # Must return EXIT_WRITER_THREAD_JOIN_TIMEOUT (76), must NOT call close_module(), and must NOT close worker_shm!
        exit_code = server.shutdown_and_close(writer_join_timeout_s=0.05)
        assert exit_code == EXIT_WRITER_THREAD_JOIN_TIMEOUT
        assert hang_session.close_calls == 0
        assert worker_shm.is_closed is False
        assert int(main_shm.global_header.writer_state) == int(WriterState.STOPPING)
    finally:
        release_hang.set()
        if server._lv_thread is not None:
            server._lv_thread.join(timeout=2.0)
        if not worker_shm.is_closed:
            worker_shm.close()
        main_conn.close()
        worker_conn.close()
        main_shm.close()
        main_shm.unlink()

    # --- Part 2: Verify zero SharedMemory writes or heartbeat changes after clean shutdown ---
    shm_clean = _unique_shm_name("p221_nowrite")
    main_shm_c = NikonSharedFrameBuffer(name=shm_clean, create=True, worker_generation=1)
    worker_shm_c = NikonSharedFrameBuffer.attach(name=shm_clean)
    mc, wc = multiprocessing.Pipe(duplex=True)
    srv_c = NikonDriverWorkerServer(
        worker_generation=1,
        worker_instance_id="w_clean_1",
        shm_buffer=worker_shm_c,
        spool_dir=str(tmp_path / "spool_clean"),
        transport=PipeConnectionTransport(wc),
        session_factory=_FakeNikonSessionForWorker,
        live_view_poll_interval_s=0.005,
        heartbeat_interval_s=0.020,
    )
    srv_c.start_background_threads()
    try:
        lv_ok = srv_c.dispatch_request(
            IPCRequest(
                method=IPCCommandMethod.START_LIVE_VIEW.value,
                worker_generation=1,
                worker_instance_id="w_clean_1",
                request_id="req_lv_clean",
                params={"deadline_mono": time.perf_counter() + 5.0},
            )
        )
        assert lv_ok.ok is True
        time.sleep(0.05)
        assert srv_c.shutdown_and_close() == 0
        assert worker_shm_c.is_closed is True

        seq_after_shut = srv_c.sequence_id
        hb_after_shut = int(main_shm_c.global_header.worker_heartbeat_ns)
        slot0_seq_after = int(main_shm_c.slots[0].slot_seq_lock)
        slot1_seq_after = int(main_shm_c.slots[1].slot_seq_lock)

        time.sleep(0.10)
        assert srv_c.sequence_id == seq_after_shut
        assert int(main_shm_c.global_header.worker_heartbeat_ns) == hb_after_shut
        assert int(main_shm_c.slots[0].slot_seq_lock) == slot0_seq_after
        assert int(main_shm_c.slots[1].slot_seq_lock) == slot1_seq_after
    finally:
        mc.close()
        wc.close()
        main_shm_c.close()
        main_shm_c.unlink()


def test_phase221_cross_process_worker_server_live_view_shm_streaming(tmp_path) -> None:
    """Audit M-4: Verify real cross-process NikonDriverWorkerServer subprocess streaming Live View frames into SharedMemory."""
    import json
    import subprocess
    from vietphotobooth.camera.backends.nikon_maid.driver_worker_server import (
        parse_wire_message,
    )

    shm_name = _unique_shm_name("p221_xproc_lv")
    spool_dir = str(tmp_path / "spool_xproc_lv")
    gen = 9
    inst_id = generate_worker_instance_id(gen)

    main_shm = NikonSharedFrameBuffer(name=shm_name, create=True, worker_generation=gen)

    # Launch a real standalone child Python process running run_worker_process with _FakeNikonSessionForWorker
    child_code = (
        "import sys; "
        "from vietphotobooth.camera.backends.nikon_maid.driver_worker_main import WorkerStartupConfig, run_worker_process; "
        "from vietphotobooth.tests.test_nikon_isolated_driver import _FakeNikonSessionForWorker, _make_synthetic_jpeg; "
        "from vietphotobooth.camera.backends.nikon_maid.shm_frame_buffer import DEFAULT_LIVE_VIEW_WIDTH, DEFAULT_LIVE_VIEW_HEIGHT; "
        f"cfg = WorkerStartupConfig(shm_name={shm_name!r}, parent_pid={os.getpid()}, worker_generation={gen}, "
        f"worker_instance_id={inst_id!r}, spool_dir={spool_dir!r}); "
        "lv_jpeg = _make_synthetic_jpeg(DEFAULT_LIVE_VIEW_WIDTH, DEFAULT_LIVE_VIEW_HEIGHT, 88); "
        "rc = run_worker_process(cfg, session_factory=lambda: _FakeNikonSessionForWorker(lv_jpeg_bytes=lv_jpeg), "
        "live_view_poll_interval_s=0.004, heartbeat_interval_s=0.030); "
        "sys.exit(rc)"
    )

    proc = subprocess.Popen(
        [sys.executable, "-c", child_code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    tx_mgr = IPCTransactionManager(worker_generation=gen, worker_instance_id=inst_id)

    def _send_and_wait_resp(req: IPCRequest) -> IPCResponse:
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps(req.to_dict()) + "\n")
        proc.stdin.flush()
        while True:
            line = proc.stdout.readline().strip()
            assert line, f"Unexpected EOF from worker subprocess; stderr={proc.stderr.read() if proc.stderr else ''}"
            msg = parse_wire_message(line)
            if isinstance(msg, IPCResponse) and msg.request_id == req.request_id:
                return msg

    try:
        assert proc.stdout is not None
        ready_line = proc.stdout.readline().strip()
        ready_evt = parse_wire_message(ready_line)
        assert isinstance(ready_evt, IPCEvent)
        assert ready_evt.event == IPCEventName.WORKER_READY.value

        conn_req = tx_mgr.create_request(
            IPCCommandMethod.CONNECT,
            params={"deadline_mono": time.perf_counter() + 5.0},
        )
        assert _send_and_wait_resp(conn_req).ok is True

        lv_req = tx_mgr.create_request(
            IPCCommandMethod.START_LIVE_VIEW,
            params={"deadline_mono": time.perf_counter() + 5.0},
        )
        assert _send_and_wait_resp(lv_req).ok is True

        # Read >= 25 frames across process boundary from SharedMemory
        seen_seq = 0
        frames_read = 0
        deadline = time.perf_counter() + 5.0
        while frames_read < 25 and time.perf_counter() < deadline:
            frame = main_shm.read_latest_frame(
                last_seen_seq_id=seen_seq,
                expected_worker_gen=gen,
            )
            if frame is not None:
                assert frame.is_valid is True
                assert frame.sequence_id > seen_seq
                assert frame.worker_generation == gen
                assert frame.width == DEFAULT_LIVE_VIEW_WIDTH
                assert frame.height == DEFAULT_LIVE_VIEW_HEIGHT
                seen_seq = frame.sequence_id
                frames_read += 1
            else:
                time.sleep(0.003)

        assert frames_read >= 25, f"Expected >= 25 cross-process frames, got {frames_read}"

        shut_req = tx_mgr.create_request(IPCCommandMethod.SHUTDOWN)
        assert _send_and_wait_resp(shut_req).ok is True
        exit_code = proc.wait(timeout=5.0)
        assert exit_code == 0

        # Confirm zero writes after subprocess exits
        seq_final = int(main_shm.slots[main_shm.global_header.published_slot].sequence_id)
        hb_final = int(main_shm.global_header.worker_heartbeat_ns)
        time.sleep(0.08)
        assert int(main_shm.slots[main_shm.global_header.published_slot].sequence_id) == seq_final
        assert int(main_shm.global_header.worker_heartbeat_ns) == hb_final
    finally:
        if proc.poll() is None:
            proc.kill()
        main_shm.close()
        main_shm.unlink()





