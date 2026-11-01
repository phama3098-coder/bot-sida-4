"""
1998 TEAM — Photobooth v1.5.1 Viewport Stability Tests
Verifies that CameraPage Live View viewport remains rock-solid without size jitter,
layout recalculations, or aspect ratio distortion during continuous frame streaming.
"""

import time
import pytest
import numpy as np
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.desktop.widgets.camera_page import CameraPage, CameraLiveViewport


def test_camera_live_viewport_static_size_hints(qapp):
    vp = CameraLiveViewport()
    assert vp.sizeHint() == QSize(640, 425)
    assert vp.minimumSizeHint() == QSize(320, 213)
    assert vp.minimumHeight() <= 280

    # Feeding 60 frames must NOT alter sizeHint or minimumSizeHint
    initial_hint = vp.sizeHint()
    for _ in range(60):
        frame = np.zeros((680, 1024, 3), dtype=np.uint8)
        vp.set_frame_rgb(frame)
        assert vp.sizeHint() == initial_hint
        assert vp.minimumSizeHint() == QSize(320, 213)


def test_camera_live_viewport_aspect_ratio_preservation(qapp):
    vp = CameraLiveViewport()

    # Test various window / layout dimensions
    dimensions = [
        (600, 450),
        (800, 400),
        (1280, 720),
        (500, 700),
        (400, 280),
        (960, 600)
    ]

    expected_aspect = 1024.0 / 680.0 # Nikon D780 ratio: 1.50588

    for (w, h) in dimensions:
        vp.resize(w, h)
        vp._recalculate_target_rect()
        r = vp.target_rect

        # Target rect must fit entirely within viewport
        assert r.width() <= w
        assert r.height() <= h
        assert r.x() >= 0
        assert r.y() >= 0
        assert r.x() + r.width() <= w
        assert r.y() + r.height() <= h

        # Aspect ratio must match 1024:680 within 0.02
        actual_aspect = r.width() / r.height()
        assert abs(actual_aspect - expected_aspect) < 0.02

        # Image must be centered horizontally or vertically
        if r.width() == w:
            assert abs((h - r.height()) // 2 - r.y()) <= 1
        elif r.height() == h:
            assert abs((w - r.width()) // 2 - r.x()) <= 1


def test_camera_page_live_view_continuous_streaming_stability(qapp):
    cam_mgr = CameraManager(default_backend="simulator")
    page = CameraPage(camera_mgr=cam_mgr)
    if hasattr(page, "_initial_diag_timer") and page._initial_diag_timer.isActive():
        page._initial_diag_timer.stop()
    if hasattr(page, "_diag_worker") and page._diag_worker and page._diag_worker.isRunning():
        page._diag_worker.quit()
        page._diag_worker.wait(500)
    page.resize(1024, 768)
    page.show()
    for _ in range(5):
        qapp.processEvents()
        time.sleep(0.01)

    # Prime with initial frame to establish baseline layout
    prime_frame = np.full((680, 1024, 3), fill_value=0, dtype=np.uint8)
    page.lbl_viewport.set_frame_rgb(prime_frame)
    page._update_stats_display()
    qapp.processEvents()

    assert isinstance(page.lbl_viewport, CameraLiveViewport)
    initial_w = page.lbl_viewport.width()
    initial_h = page.lbl_viewport.height()
    initial_rect = page.lbl_viewport.target_rect

    assert initial_w > 100
    assert initial_h > 100

    # Simulate 60 consecutive frames arriving at 30 FPS (~2 seconds of real stream)
    for i in range(60):
        # Frame with slight content variation (like live camera)
        frame = np.full((680, 1024, 3), fill_value=(i % 255), dtype=np.uint8)
        page.lbl_viewport.set_frame_rgb(frame)
        qapp.processEvents()

        # Viewport dimensions and target rectangle must remain 100% constant
        assert page.lbl_viewport.width() == initial_w
        assert page.lbl_viewport.height() == initial_h
        assert page.lbl_viewport.target_rect == initial_rect

    # Toggle grid lines on and off
    page._toggle_grid()
    assert page.grid_enabled is True
    assert page.lbl_viewport._grid_enabled is True
    assert page.lbl_viewport.width() == initial_w
    assert page.lbl_viewport.height() == initial_h

    page._toggle_grid()
    assert page.grid_enabled is False
    assert page.lbl_viewport._grid_enabled is False

    page.close()
    qapp.processEvents()
    cam_mgr.disconnect()


def test_camera_live_viewport_message_state(qapp):
    vp = CameraLiveViewport()
    vp.set_message("TEST ERROR MESSAGE", color_hex="#EF4444", border_hex="#EF4444")
    assert vp.pixmap() is None
    assert "TEST ERROR MESSAGE" in vp.text()

    # Now set a frame
    frame = np.zeros((680, 1024, 3), dtype=np.uint8)
    vp.set_frame_rgb(frame)
    assert vp.pixmap() is not None
    assert vp.text() == ""
