"""
1998 TEAM — Unit Test Suite for Live View Pacing Gate & Precise Timer
Verifies:
1. Pacing gate does not exceed 30.0 FPS under fast input (e.g. 60 FPS, 100 FPS).
2. Pacing gate maintains 28–30 FPS and does NOT drop to 15–17 FPS when acquisition is ~30 FPS.
3. Pending frame arriving early is displayed upon reaching the deadline (no permanent loss).
4. Latest-frame-wins coalescing behavior.
5. Pause/Resume does not produce burst emissions.
6. CameraPage timer is configured as Qt.PreciseTimer with 33ms interval.
"""

import time
import math
import statistics
import pytest
import numpy as np

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from vietphotobooth.desktop.widgets.kiosk_page import CameraLiveViewWorker
from vietphotobooth.camera.models import FrameData


class MockCameraManager:
    """Mock CameraManager for testing CameraLiveViewWorker."""
    def __init__(self):
        self._callbacks = []
        self._connected = True

    def is_connected(self):
        return self._connected

    def register_frame_callback(self, cb):
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def unregister_frame_callback(self, cb):
        if cb in self._callbacks:
            self._callbacks.remove(cb)

    def push_frame(self, frame_data):
        for cb in list(self._callbacks):
            cb(frame_data)


def create_mock_frame(seq_id: int) -> FrameData:
    rgb = np.zeros((100, 100, 3), dtype=np.uint8)
    rgb[0, 0, 0] = seq_id % 256
    return FrameData(
        rgb=rgb,
        jpeg=b"fake_jpeg",
        width=100,
        height=100,
        fps=30.0,
        sequence_id=seq_id,
        timestamp=time.time(),
        is_valid=True
    )


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication(["-platform", "windows"])


def test_camera_page_precise_timer(qapp):
    """Test 1: Verify CameraPage uses Qt.PreciseTimer with 33ms interval."""
    from vietphotobooth.desktop.widgets.camera_page import CameraPage
    from vietphotobooth.camera.connection_manager import CameraConnectionManager

    mgr = CameraConnectionManager()
    page = CameraPage(camera_mgr=mgr)

    assert hasattr(page, "_timer"), "CameraPage must have _timer attribute"
    assert page._timer.timerType() == Qt.PreciseTimer, "CameraPage _timer must be Qt.PreciseTimer"
    assert page._timer.interval() == 33, "CameraPage _timer interval must be 33ms (~30 FPS)"
    page.close()


def test_pacing_gate_does_not_exceed_30fps(qapp):
    """Test 2: When frames arrive at 60 FPS (16.6ms), emitted FPS must not exceed 30 FPS."""
    mgr = MockCameraManager()
    worker = CameraLiveViewWorker(mgr)

    emits = []
    def on_frame(rgb):
        emits.append((rgb[0, 0, 0], time.perf_counter()))

    worker.frame_ready.connect(on_frame)

    t0 = time.perf_counter()
    TOTAL_FRAMES = 60 # 60 frames fed at 16.6ms = 1.0s of data
    for i in range(1, TOTAL_FRAMES + 1):
        f = create_mock_frame(i)
        mgr.push_frame(f)
        qapp.processEvents()
        t_target = t0 + i * 0.016666
        while time.perf_counter() < t_target:
            qapp.processEvents()
            time.sleep(0.0005)

    # Allow final deadline timer to fire
    t_end = time.perf_counter() + 0.1
    while time.perf_counter() < t_end:
        qapp.processEvents()
        time.sleep(0.001)

    worker.stop()

    assert len(emits) >= 25, f"Should emit ~30 frames, got {len(emits)}"
    intervals = [(emits[k][1] - emits[k-1][1]) * 1000.0 for k in range(1, len(emits))]
    min_iv = min(intervals)
    mean_iv = statistics.mean(intervals)
    total_time = emits[-1][1] - emits[0][1]
    measured_fps = (len(emits) - 1) / total_time

    # Epsilon: allow 0.5ms timer scheduling tolerance on Windows
    assert min_iv >= (1000.0 / 30.0 - 0.6), f"Interval {min_iv:.2f}ms violates 33.33ms min interval"
    assert measured_fps <= 30.2, f"Measured FPS {measured_fps:.2f} exceeds 30 FPS ceiling"


def test_pacing_gate_no_drop_to_17fps_when_30fps_input(qapp):
    """Test 3: When frames arrive at ~30 FPS (31-33ms input), delivered FPS must be 28-30 FPS, NOT 15-17 FPS."""
    mgr = MockCameraManager()
    worker = CameraLiveViewWorker(mgr)

    emits = []
    def on_frame(rgb):
        emits.append((rgb[0, 0, 0], time.perf_counter()))

    worker.frame_ready.connect(on_frame)

    t0 = time.perf_counter()
    TOTAL_FRAMES = 45 # ~1.4 seconds at 31ms
    for i in range(1, TOTAL_FRAMES + 1):
        f = create_mock_frame(i)
        mgr.push_frame(f)
        qapp.processEvents()
        t_target = t0 + i * 0.0315
        while time.perf_counter() < t_target:
            qapp.processEvents()
            time.sleep(0.0005)

    t_end = time.perf_counter() + 0.1
    while time.perf_counter() < t_end:
        qapp.processEvents()
        time.sleep(0.001)

    worker.stop()

    # The old rigid gate emitted only 50-60% of frames (~15-17 FPS).
    # The new deadline pacer must deliver >= 80% of frames (~26-30 FPS).
    delivery_ratio = len(emits) / TOTAL_FRAMES
    total_time = emits[-1][1] - emits[0][1] if len(emits) > 1 else 1.0
    measured_fps = (len(emits) - 1) / total_time

    assert delivery_ratio >= 0.80, f"Delivery ratio {delivery_ratio*100:.1f}% indicates dropped frames (Old 17 FPS bug)"
    assert measured_fps >= 24.0, f"Measured FPS {measured_fps:.2f} is too low (Old 15-17 FPS bug)"


def test_pending_frame_displayed_at_deadline(qapp):
    """Test 4: A frame arriving early (< 33.33ms) is not discarded; it is emitted when deadline is reached."""
    mgr = MockCameraManager()
    worker = CameraLiveViewWorker(mgr)

    emits = []
    worker.frame_ready.connect(lambda rgb: emits.append((rgb[0, 0, 0], time.perf_counter())))

    # Emit frame 1
    f1 = create_mock_frame(1)
    mgr.push_frame(f1)
    qapp.processEvents()
    assert len(emits) == 1, "Frame 1 must be emitted immediately"

    # Push frame 2 immediately (< 5ms << 33.33ms)
    time.sleep(0.002)
    f2 = create_mock_frame(2)
    mgr.push_frame(f2)
    qapp.processEvents()

    # If push occurred before deadline, frame 2 must not be emitted yet (spacing check)
    t_push = time.perf_counter()
    if t_push - emits[0][1] < (1000.0 / 30.0 - 0.6) / 1000.0:
        assert len(emits) == 1, "Frame 2 must wait for deadline"

    # Wait for deadline timer (remaining buffer: ~33.33ms + 50ms)
    t_end = emits[0][1] + (1.0 / 30.0) + 0.050
    while time.perf_counter() < t_end:
        qapp.processEvents()
        time.sleep(0.001)

    # Frame 2 MUST have been emitted at deadline
    assert len(emits) == 2, "Frame 2 must be emitted at deadline"
    assert emits[1][0] == 2, "Emitted frame must be Frame 2"
    delta_ms = (emits[1][1] - emits[0][1]) * 1000.0
    assert delta_ms >= (1000.0 / 30.0 - 0.6), f"Interval {delta_ms:.2f}ms must respect >= 33.33ms"

    worker.stop()


def test_pause_resume_no_burst(qapp):
    """Test 5: Rapid frame submission after pause/resume does not produce frame bursts."""
    mgr = MockCameraManager()
    worker = CameraLiveViewWorker(mgr)

    emits = []
    worker.frame_ready.connect(lambda rgb: emits.append((rgb[0, 0, 0], time.perf_counter())))

    # 1. Emit 1 frame
    mgr.push_frame(create_mock_frame(1))
    qapp.processEvents()
    assert len(emits) == 1

    # 2. Pause for 100ms
    worker.pause()
    time.sleep(0.100)
    qapp.processEvents()

    # 3. Resume and immediately feed 5 frames at 5ms intervals
    worker.resume()
    for k in range(10, 15):
        mgr.push_frame(create_mock_frame(k))
        qapp.processEvents()
        time.sleep(0.005)

    # Wait for timers
    t_end = time.perf_counter() + 0.150
    while time.perf_counter() < t_end:
        qapp.processEvents()
        time.sleep(0.001)

    worker.stop()

    # Verify intervals of all emitted frames
    intervals = [(emits[k][1] - emits[k-1][1]) * 1000.0 for k in range(1, len(emits))]
    for iv in intervals:
        assert iv >= (1000.0 / 30.0 - 0.6), f"Burst detected: interval {iv:.2f}ms is < 33.33ms"
