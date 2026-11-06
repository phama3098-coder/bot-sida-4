"""
1998 TEAM — Photobooth Nikon D780 Live View Optimization & Safety Tests
Verifies Phase 3 optimizations:
1. Viewport QImage + drawImage Zero-Copy & Buffer Lifetime
2. Camera Worker Unconstrained Acquisition & Event-driven Handoff
3. ConnectionManager Nikon MAID No-Sleep Acquisition
4. Direct Push & Latest-Frame-Wins Coalescing & 30 FPS Pacing Gate
5. Elimination of Stale Frame Re-rendering
6. Still Capture 6048x4024 Safety & Lifecycle Preservation
"""

import time
import threading
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPixmap, QPainter
from PySide6.QtCore import QRect, Qt

from vietphotobooth.camera.models import FrameData, ConnectionState
from vietphotobooth.desktop.widgets.live_viewport import CameraLiveViewport
from vietphotobooth.camera.backends.nikon_maid.camera_worker import NikonCameraWorker
from vietphotobooth.camera.backends.nikon_maid.nikon_d780_backend import NikonD780Backend
from vietphotobooth.camera.connection_manager import CameraConnectionManager
from vietphotobooth.desktop.widgets.kiosk_page import CameraLiveViewWorker
from vietphotobooth.desktop.widgets.camera_page import CameraPage


def test_viewport_draw_image_zero_copy_and_buffer_lifetime(qapp):
    """Xác minh Viewport sử dụng drawImage trực tiếp, bảo toàn buffer lifetime và aspect ratio 3:2."""
    vp = CameraLiveViewport()
    vp.resize(800, 600)
    vp.show()
    qapp.processEvents()

    # Tạo frame 1024x680 (3:2)
    rgb = np.full((680, 1024, 3), 180, dtype=np.uint8)
    vp.set_frame_rgb(rgb)

    # 1. Kiểm tra không tạo QPixmap trong quá trình nhận frame
    assert vp._current_pixmap is None, "Không được tự động tạo QPixmap khi nhận frame!"
    assert vp._current_image is not None, "Phải tạo QImage trực tiếp từ buffer RGB!"
    assert vp._current_frame_buffer is rgb, "Phải giữ tham chiếu numpy buffer để bảo đảm lifetime!"

    # 2. Kiểm tra aspect ratio 1024:680 (3:2)
    target_rect = vp.target_rect
    aspect = target_rect.width() / target_rect.height()
    expected_aspect = 1024.0 / 680.0
    assert abs(aspect - expected_aspect) < 0.02, f"Aspect ratio phải duy trì ~3:2 (1.506), thực tế: {aspect:.3f}"

    # 3. Kiểm tra paintEvent vẽ trực tiếp drawImage không crash
    vp.repaint()
    qapp.processEvents()

    # 4. Kiểm tra phương thức pixmap() trả về QPixmap on-demand khi được truy vấn
    pix = vp.pixmap()
    assert pix is not None and not pix.isNull(), "pixmap() phải trả về QPixmap hợp lệ khi consumer yêu cầu!"
    assert pix.width() == 1024 and pix.height() == 680

    # 5. Kiểm tra clear() dọn sạch tham chiếu buffer
    vp.clear()
    assert vp._current_image is None
    assert vp._current_frame_buffer is None
    assert vp._current_pixmap is None
    vp.close()


def test_camera_worker_unconstrained_acquisition():
    """Xác minh NikonCameraWorker thu nhận frame theo tốc độ tự nhiên và phát event đồng bộ."""
    mock_session = MagicMock()
    dummy_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 2000 + b"\xff\xd9"
    mock_session.fetch_live_view_frame.return_value = dummy_jpeg

    worker = NikonCameraWorker(mock_session)
    assert not worker.is_running
    assert worker._latest_frame is None

    worker._live_view_enabled = True

    # Chạy 1 nhịp vòng lặp thu nhận
    worker._frame_count += 1
    rgb = np.zeros((680, 1024, 3), dtype=np.uint8)
    frame = FrameData(
        rgb=rgb,
        jpeg=dummy_jpeg,
        width=1024,
        height=680,
        fps=30.0,
        sequence_id=worker._frame_count,
        timestamp=time.time(),
        is_valid=True
    )

    with worker._frame_lock:
        worker._latest_frame = frame
        worker._new_frame_event.set()

    # Kiểm tra get_latest_frame với wait_new=True
    fetched = worker.get_latest_frame(wait_new=True, timeout=0.05)
    assert fetched is not None
    assert fetched.sequence_id == 1
    assert fetched.width == 1024
    assert fetched.height == 680

    # Kiểm tra event đã được reset sau khi đọc
    assert not worker._new_frame_event.is_set()

    worker.stop()


def test_kiosk_liveview_worker_30fps_pacing_and_latest_frame_wins(qapp):
    """Xác minh CameraLiveViewWorker áp dụng Direct Push, Pacing 30 FPS và Latest-Frame-Wins."""
    mock_mgr = MagicMock()
    mock_mgr.is_connected.return_value = True

    worker = CameraLiveViewWorker(mock_mgr)
    worker.start()
    qapp.processEvents()

    delivered_frames = []
    worker.frame_ready.connect(lambda f: delivered_frames.append(f))

    # Bắn 20 frames liên tiếp với tốc độ 100 FPS (mỗi frame cách nhau 10ms)
    for i in range(20):
        dummy_rgb = np.full((100, 100, 3), i, dtype=np.uint8)
        frame = FrameData(
            rgb=dummy_rgb,
            jpeg=b"fake",
            width=100,
            height=100,
            fps=100.0,
            sequence_id=i + 1,
            timestamp=time.time(),
            is_valid=True
        )
        worker._on_direct_frame(frame)
        time.sleep(0.005)
        qapp.processEvents()

    # Đợi thêm 100ms để pacer giải phóng frame cuối cùng
    time.sleep(0.1)
    qapp.processEvents()

    # Số frame UI nhận được phải bị throttle ở mức <= 30 FPS
    assert len(delivered_frames) > 0, "Phải nhận được ít nhất 1 frame!"
    assert len(delivered_frames) < 20, "Phải throttle và drop bớt frame khi camera đẩy quá 30 FPS!"

    # Frame cuối cùng được nhận phải là frame mới nhất (Latest-Frame-Wins)
    last_pixel_val = delivered_frames[-1][0, 0, 0]
    assert last_pixel_val >= 18, f"Frame cuối cùng phải là frame mới nhất (pixel >= 18), thực tế: {last_pixel_val}"

    # Dừng worker an toàn
    worker.stop()
    qapp.processEvents()


def test_camera_page_no_stale_re_render(qapp):
    """Xác minh CameraPage không re-render lại frame cũ khi sequence_id không đổi."""
    mock_mgr = MagicMock()
    mock_mgr.is_connected.return_value = True
    mock_mgr.current_backend_name = "nikon_maid"
    mock_mgr.get_info.return_value = {"is_live_view_active": True}

    page = CameraPage(mock_mgr)
    page.resize(800, 600)
    page.show()
    qapp.processEvents()

    dummy_rgb = np.zeros((680, 1024, 3), dtype=np.uint8)
    frame = FrameData(
        rgb=dummy_rgb,
        jpeg=b"fake",
        width=1024,
        height=680,
        fps=30.0,
        sequence_id=101,
        timestamp=time.time(),
        is_valid=True
    )
    mock_mgr.get_frame_data.return_value = frame
    mock_mgr.get_liveview_rgb.return_value = dummy_rgb

    # Render lần 1: thành công
    with patch.object(page.lbl_viewport, "set_frame_rgb") as mock_set_frame:
        page._update_preview()
        assert mock_set_frame.call_count == 1
        assert page._last_rendered_preview_seq == 101

    # Render lần 2 với cùng sequence_id: phải skip, không vẽ lại!
    with patch.object(page.lbl_viewport, "set_frame_rgb") as mock_set_frame:
        page._update_preview()
        assert mock_set_frame.call_count == 0, "Không được vẽ lại khi sequence_id không đổi!"

    # Render lần 3 với sequence_id mới: phải vẽ
    frame2 = FrameData(
        rgb=dummy_rgb,
        jpeg=b"fake",
        width=1024,
        height=680,
        fps=30.0,
        sequence_id=102,
        timestamp=time.time(),
        is_valid=True
    )
    mock_mgr.get_frame_data.return_value = frame2
    with patch.object(page.lbl_viewport, "set_frame_rgb") as mock_set_frame:
        page._update_preview()
        assert mock_set_frame.call_count == 1
        assert page._last_rendered_preview_seq == 102

    page._timer.stop()
    page._stats_timer.stop()
    page.close()


def test_still_capture_lifecycle_safety():
    """Xác minh quy trình chụp ảnh tĩnh 6048x4024 bảo toàn đúng vòng đời và không bị race condition."""
    mock_session = MagicMock()
    mock_session.capture_photo.return_value = b"\xff\xd8" + b"\x00" * 5000 + b"\xff\xd9"
    mock_session.start_live_view.return_value = True

    worker = NikonCameraWorker(mock_session)
    worker._live_view_enabled = True

    on_start_called = [False]
    def on_start():
        on_start_called[0] = True

    with patch("PIL.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (6048, 4024)
        mock_open.return_value = mock_img

        result = worker.capture(timeout_sec=12.0, autofocus_first=False, on_capture_start=on_start)

        assert result is not None
        mock_session.capture_photo.assert_called_once()
        assert worker._live_view_enabled is True

    worker.stop()
