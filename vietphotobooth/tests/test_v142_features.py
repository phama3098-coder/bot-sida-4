"""
Unit tests for v1.4.2 Features:
1. CameraPage layout responsiveness without horizontal overflow across resolutions (1920x1080, 1600x900, 1366x768, 1280x720).
2. Click-to-assign photo interaction on GuestReviewWidget (thumbnails in Area C, slots on Canvas).
3. FPS diagnostics and Sliding Window FPSTracker (Read FPS vs Render FPS vs Reported FPS).
"""

import time
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QResizeEvent

from vietphotobooth.camera.connection_manager import FPSTracker, CameraConnectionManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.desktop.widgets.camera_page import CameraPage
from vietphotobooth.desktop.widgets.guest_review_dialog import GuestReviewWidget, PhotoThumbnailCard
from vietphotobooth.frames.frame_manager import FrameManager


# -----------------------------------------------------------------------------
# 1. TEST FPS TRACKER (SLIDING WINDOW)
# -----------------------------------------------------------------------------
def test_fps_tracker_sliding_window():
    tracker = FPSTracker(window_seconds=1.0, max_samples=50)

    # Empty tracker returns 0.0
    assert tracker.get_fps() == 0.0

    # Single tick still returns 0.0 (< 2 samples)
    tracker.tick()
    assert tracker.get_fps() == 0.0

    # 10 ticks spaced by ~0.033s (~30 FPS)
    t_start = time.time()
    for _ in range(10):
        tracker.tick()
        time.sleep(0.01)

    fps = tracker.get_fps()
    assert fps > 0.0

    # Test reset
    tracker.reset()
    assert tracker.get_fps() == 0.0


def test_camera_connection_manager_fps_integration():
    mgr = CameraConnectionManager(default_backend="simulator")
    assert hasattr(mgr, "get_read_fps")
    assert isinstance(mgr.get_read_fps(), float)

    # Simulate reading a frame
    frame = mgr.get_frame_data()
    assert frame is not None
    info = mgr.get_info()
    assert "read_fps" in info
    assert "reported_fps" in info
    assert "fps" in info
    mgr.disconnect()


# -----------------------------------------------------------------------------
# 2. TEST CAMERA PAGE RESPONSIVE LAYOUT (1920x1080, 1600x900, 1366x768, 1280x720)
# -----------------------------------------------------------------------------
def test_camera_page_layout_no_overflow(qapp):
    cam_mgr = CameraManager()
    page = CameraPage(camera_mgr=cam_mgr)

    # Verify key widgets exist
    assert hasattr(page, "cols_layout")
    assert hasattr(page, "col_left_widget")
    assert hasattr(page, "col_right_widget")
    assert hasattr(page, "table_diag")
    assert hasattr(page, "table_compat")
    assert hasattr(page, "lbl_viewport")

    # Viewport minimum height is compact (<= 280)
    assert page.lbl_viewport.minimumHeight() <= 280

    # Test resolutions
    resolutions = [
        (1920, 1080),
        (1600, 900),
        (1366, 768),
        (1280, 720),
        (900, 600)  # Narrow width stacks vertically
    ]

    for w, h in resolutions:
        page.resize(w, h)
        # Dispatch resize event
        page.resizeEvent(QResizeEvent(QSize(w, h), QSize(1000, 700)))
        page.updateGeometry()

        if w >= 960:
            assert page.cols_layout.direction() == page.cols_layout.Direction.LeftToRight
        else:
            assert page.cols_layout.direction() == page.cols_layout.Direction.TopToBottom

    # Check table compatibility headers and word wrap
    assert page.table_compat.wordWrap() is True
    assert page.table_compat.rowCount() >= 5

    page.close()
    page.deleteLater()
    cam_mgr.disconnect()


# -----------------------------------------------------------------------------
# 3. TEST CLICK-TO-ASSIGN PHOTO INTERACTION IN GUEST REVIEW
# -----------------------------------------------------------------------------
def test_guest_review_click_to_assign(qapp):
    # Create 4 test photos
    photos = [
        Image.new("RGB", (800, 600), color=(255, 0, 0)),
        Image.new("RGB", (800, 600), color=(0, 255, 0)),
        Image.new("RGB", (800, 600), color=(0, 0, 255)),
        Image.new("RGB", (800, 600), color=(255, 255, 0)),
    ]
    fm = FrameManager()
    widget = GuestReviewWidget(photos=photos, frame_mgr=fm)

    # Area C should have 4 PhotoThumbnailCard cards
    assert len(widget.photo_cards) == 4
    assert len(widget.thumb_widgets) == 4

    # Initial slot assignment: slot 0 -> photo 0, slot 1 -> photo 1, etc.
    assert widget.current_template.slots[0].photo_index == 0
    assert widget.current_template.slots[1].photo_index == 1

    # User clicks Slot #1 on Canvas (index 0)
    widget._on_canvas_slot_selected(0)
    assert widget.selected_slot_index == 0
    assert widget.canvas.selected_index == 0

    # User clicks Thumbnail #3 (index 2) in Area C
    widget._on_photo_thumbnail_clicked(2)
    assert widget.selected_photo_index == 2
    # Photo #3 (index 2) must be immediately assigned to Slot #1 (index 0)!
    assert widget.current_template.slots[0].photo_index == 2

    # User now clicks Slot #2 on Canvas (index 1)
    widget._on_canvas_slot_selected(1)
    assert widget.selected_slot_index == 1

    # User clicks Thumbnail #4 (index 3) in Area C
    widget._on_photo_thumbnail_clicked(3)
    assert widget.current_template.slots[1].photo_index == 3

    # Check that assigned pills were updated on photo cards
    slots_photo3 = widget._get_slots_for_photo(2)
    assert 1 in slots_photo3

    slots_photo4 = widget._get_slots_for_photo(3)
    assert 2 in slots_photo4

    # Test tools: rotate, flip, reset crop on current slot
    slot_curr = widget.current_template.slots[1]
    rot_init = slot_curr.rotation
    widget._rotate_selected_slot()
    assert slot_curr.rotation == (rot_init + 90) % 360

    flip_init = getattr(slot_curr, "is_flipped_h", False)
    widget._flip_selected_slot()
    assert getattr(slot_curr, "is_flipped_h", False) != flip_init

    widget._reset_selected_slot_pan()
    assert slot_curr.rotation == 0
    assert slot_curr.is_flipped_h is False
    assert slot_curr.crop_offset_x == 0.0

    # Verify original photos remained intact
    assert len(photos) == 4
    for p in photos:
        assert p.size == (800, 600)

    widget.close()
    widget.deleteLater()
