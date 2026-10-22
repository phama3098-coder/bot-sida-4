"""
Unit tests for v1.4.3:
1. Camera Live View Streamer lifecycle (start, stop, single-thread guarantee).
2. Honest FPS tracking: no fake 30 FPS when Live View is OFF, Tethered DSLR mode clearly reported.
3. Full resolution capture preserved (6000x4000) while preview is optimized.
4. Official SVG Logo resolution, aspect ratio (2:3) and widget accessibility.
5. CameraPage non-blocking background diagnostics and separated stats polling.
"""

import os
import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap

from vietphotobooth.camera.connection_manager import CameraConnectionManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.camera.models import ConnectionState, FrameData
from vietphotobooth.camera.backends.digicam_control import DigiCamControlBackend
from vietphotobooth.desktop.icons import (
    get_brand_logo_svg_path, get_brand_logo_pixmap, create_brand_logo_widget
)
from vietphotobooth.desktop.widgets.camera_page import CameraPage, DiagnosticWorker


# -----------------------------------------------------------------------------
# 1. STREAM WORKER LIFECYCLE & THREAD DEDUPLICATION
# -----------------------------------------------------------------------------
def test_camera_stream_worker_lifecycle():
    mgr = CameraConnectionManager(default_backend="simulator")
    assert mgr.is_connected() is True

    # Start stream
    mgr.start_stream()
    assert mgr._stream_running is True
    assert mgr._stream_thread is not None
    assert mgr._stream_thread.is_alive() is True

    # Calling start_stream again does not spawn a second thread
    orig_thread = mgr._stream_thread
    mgr.start_stream()
    assert mgr._stream_thread is orig_thread

    # Wait for at least one frame to be buffered
    time.sleep(0.1)
    rgb = mgr.get_liveview_rgb()
    assert rgb is not None
    assert rgb.shape[0] > 0
    assert rgb.shape[1] > 0

    # Stop stream
    mgr.stop_stream()
    assert mgr._stream_running is False
    assert mgr._stream_thread is None

    mgr.disconnect()


# -----------------------------------------------------------------------------
# 2. DIGICAM OFFLINE STREAM REPORTS ZERO / REALISTIC FPS (NO FAKE 30 FPS)
# -----------------------------------------------------------------------------
def test_digicam_offline_reports_no_fake_fps():
    with patch("os.path.exists", return_value=True):
        backend = DigiCamControlBackend()
        with patch("vietphotobooth.camera.backends.digicam_control.urllib.request.urlopen", side_effect=Exception("Offline")):
            backend.connect()
            frame = backend.read_frame()
            assert frame is None
            assert backend.get_status() == ConnectionState.CONNECTED_NO_FRAME

            mgr = CameraConnectionManager(default_backend="simulator")
            mgr.stop_stream()
            mgr._backend = backend
            mgr._current_backend_type = "digicam"
            mgr._read_fps_tracker.reset()

            info = mgr.get_info()
            # Must NOT display fake 30 FPS
            assert info["fps"] == 0.0
            assert info["read_fps"] == 0.0
            assert info["is_live_view_active"] is False
            assert "Tethered" in info["status"]
            assert info["capture_resolution"] == (6000, 4000)
            assert info["actual_resolution"] == (0, 0)
            mgr.disconnect()


# -----------------------------------------------------------------------------
# 3. PREVIEW RESIZING & FULL CAPTURE RESOLUTION INTEGRITY
# -----------------------------------------------------------------------------
def test_preview_resizing_and_full_capture_integrity(tmp_path):
    mgr = CameraConnectionManager(default_backend="simulator")
    # Capture photo returns full resolution
    save_path = str(tmp_path / "full_shot.jpg")
    ok, img = mgr.capture_photo(save_path)
    assert ok is True
    assert img is not None
    assert os.path.exists(save_path)
    assert img.size == (2400, 1600)

    # In simulator, preview size is 960x640 (sensible for UI)
    rgb = mgr.get_liveview_rgb()
    assert rgb is not None
    assert rgb.shape[1] <= 1280
    assert rgb.shape[0] <= 720
    mgr.disconnect()


# -----------------------------------------------------------------------------
# 4. OFFICIAL SVG LOGO RESOLUTION & RENDERING
# -----------------------------------------------------------------------------
def test_brand_logo_svg_loading_and_rendering():
    svg_path = get_brand_logo_svg_path()
    assert os.path.exists(svg_path), f"File logo SVG không tồn tại tại: {svg_path}"
    assert svg_path.endswith(".svg")

    # Render at height 36: aspect ratio 2:3 -> width should be 24
    pix = get_brand_logo_pixmap(height=36)
    assert not pix.isNull()
    assert pix.height() == 36
    assert pix.width() == 24

    # Render at height 90 -> width 60
    pix_large = get_brand_logo_pixmap(height=90)
    assert not pix_large.isNull()
    assert pix_large.height() == 90
    assert pix_large.width() == 60

    # Create widget
    w = create_brand_logo_widget(height=40)
    assert w is not None
    assert w.accessibleName() == "Logo 1998 TEAM Photobooth"
    assert "1998 TEAM" in w.toolTip()


# -----------------------------------------------------------------------------
# 5. CAMERA PAGE NON-BLOCKING DIAGNOSTICS & SEPARATED STATS TIMER
# -----------------------------------------------------------------------------
def test_camera_page_non_blocking_diagnostics_and_stats(qapp):
    cam_mgr = CameraManager()
    page = CameraPage(camera_mgr=cam_mgr)

    # Separate stats timer exists
    assert hasattr(page, "_stats_timer")
    assert page._stats_timer.interval() == 500

    # Diagnostic worker can be spawned without blocking UI
    worker = DiagnosticWorker(page)
    results = []
    worker.report_ready.connect(lambda rep: results.append(rep))

    # Mock full diagnostics to return quickly
    with patch("vietphotobooth.desktop.widgets.camera_page.run_full_camera_diagnostics", return_value={"directshow_devices": [], "digicam_status": {}}):
        worker.start()
        worker.wait(2000)
        qapp.processEvents()

    assert len(results) == 1
    page.close()
    cam_mgr.disconnect()
