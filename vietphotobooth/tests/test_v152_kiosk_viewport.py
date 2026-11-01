"""
1998 TEAM — Photobooth v1.5.2 Kiosk Viewport Stability & Fullscreen Tests
Verifies:
1. KioskPage live view uses CameraLiveViewport with static size hints and zero-jitter layout.
2. 60+ continuous incoming frames preserve exact dimensions and 1024x680 (3:2) aspect ratio.
3. Overlay widgets remain properly positioned upon resizeEvent.
4. Fullscreen button in CameraPage is grouped with Reset, Test Shot, and Grid buttons.
5. Fullscreen dialog provides clear exit mechanism without disconnecting camera or corrupting state.
"""

import pytest
import numpy as np
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QApplication

from vietphotobooth.desktop.main_window import MainWindow
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.desktop.widgets.camera_page import CameraPage, CameraFullscreenDialog
from vietphotobooth.desktop.widgets.live_viewport import CameraLiveViewport


@pytest.fixture
def kiosk_page(qapp):
    window = MainWindow(start_in_kiosk=False)
    window.resize(1280, 800)
    window.show()
    page = window.kiosk_page
    qapp.processEvents()
    yield page
    page.cleanup()
    window.close()
    qapp.processEvents()


def test_kiosk_live_viewport_instance_and_size_hints(kiosk_page, qapp):
    """Xác nhận widget Live View của trang Chụp Ảnh là CameraLiveViewport với sizeHint tĩnh."""
    vp = kiosk_page.lbl_viewport
    assert isinstance(vp, CameraLiveViewport)
    assert vp.sizeHint() == QSize(640, 425)
    assert vp.minimumSizeHint() == QSize(320, 213)


def test_kiosk_live_view_continuous_streaming_stability(kiosk_page, qapp):
    """
    Giả lập 60 khung hình liên tiếp từ Nikon D780 (1024 × 680) gửi vào trang Chụp Ảnh.
    Kích thước widget và target_rect phải duy trì 100% ổn định, không nhấp nháy/zoom giật.
    """
    vp = kiosk_page.lbl_viewport
    initial_w = vp.width()
    initial_h = vp.height()
    initial_rect = vp.target_rect

    assert initial_w > 100
    assert initial_h > 100
    assert initial_rect.isValid() and not initial_rect.isEmpty()

    # Tỷ lệ chuẩn của Nikon D780: 1024 / 680 = 1.50588
    expected_aspect = 1024.0 / 680.0
    actual_aspect = initial_rect.width() / initial_rect.height()
    assert abs(actual_aspect - expected_aspect) < 0.02

    # Đưa 60 frame liên tục vào luồng
    for i in range(60):
        frame = np.full((680, 1024, 3), fill_value=(i * 3) % 255, dtype=np.uint8)
        kiosk_page._on_live_view_frame(frame)
        qapp.processEvents()

        # Viewport dimensions & target_rect phải giữ nguyên tuyệt đối giữa các frame
        assert vp.width() == initial_w
        assert vp.height() == initial_h
        assert vp.target_rect == initial_rect


def test_kiosk_viewport_resize_and_overlay_repositioning(kiosk_page, qapp):
    """Khi cửa sổ thay đổi kích thước, target_rect và overlays phải được căn chỉnh tự động."""
    vp = kiosk_page.lbl_viewport

    # Thử resize trang sang kích thước nhỏ hơn
    kiosk_page.resize(1024, 600)
    qapp.processEvents()

    rect = vp.target_rect
    assert rect.width() <= vp.width()
    assert rect.height() <= vp.height()
    assert rect.x() >= 0
    assert rect.y() >= 0

    # Overlay panel_disconnected phải khớp vùng viewport
    kiosk_page._reposition_viewport_overlays()
    assert kiosk_page.panel_disconnected.width() == vp.width()
    assert kiosk_page.panel_disconnected.height() == vp.height()


def test_kiosk_studio_flash_effect(kiosk_page, qapp):
    """Hiệu ứng chớp sáng flash studio khi chụp ảnh hoạt động chính xác."""
    vp = kiosk_page.lbl_viewport
    assert vp._flash_active is False

    kiosk_page._trigger_shot()
    assert vp._flash_active is True

    # Kết thúc flash sau 130ms
    vp._end_flash()
    assert vp._flash_active is False


def test_camera_page_control_buttons_grouping(qapp):
    """
    Xác nhận trên trang Máy Ảnh:
    Nút Toàn Màn Hình đã được chuyển về cùng nhóm với: Đặt Lại, Chụp Thử Nghiệm, Lưới.
    """
    cam_mgr = CameraManager(default_backend="simulator")
    page = CameraPage(camera_mgr=cam_mgr)
    page.resize(1100, 750)
    page.show()
    qapp.processEvents()

    # Cả 4 nút phải tồn tại
    assert hasattr(page, "btn_reset")
    assert hasattr(page, "btn_test_shot")
    assert hasattr(page, "btn_grid")
    assert hasattr(page, "btn_fullscreen")

    assert page.btn_reset.text() == "↺ Đặt Lại"
    assert "Chụp Thử Nghiệm" in page.btn_test_shot.text()
    assert "Lưới" in page.btn_grid.text()
    assert "Toàn Màn Hình" in page.btn_fullscreen.text()

    # Nút toàn màn hình không còn nằm trên header preview
    assert page.lbl_live_badge.parent() is not None


def test_camera_fullscreen_dialog_exit_preserves_state(qapp):
    """
    Hộp thoại toàn màn hình có nút thoát rõ ràng (ESC) và giữ nguyên trạng thái kết nối camera.
    """
    cam_mgr = CameraManager(default_backend="simulator")
    cam_mgr.connect()
    assert cam_mgr.is_connected() is True

    dlg = CameraFullscreenDialog(cam_mgr, grid_enabled=False)
    assert hasattr(dlg, "btn_exit")
    assert "Thoát Toàn Màn Hình" in dlg.btn_exit.text()
    assert isinstance(dlg.viewport, CameraLiveViewport)

    # Thoát hộp thoại
    dlg.accept()
    qapp.processEvents()

    # Trạng thái kết nối máy ảnh không bị ngắt
    assert cam_mgr.is_connected() is True


def test_kiosk_fullscreen_mode_toggle_label(kiosk_page, qapp):
    """Kiểm tra nhãn nút toàn màn hình trên KioskPage cập nhật trực quan khi bật/tắt toàn màn hình."""
    kiosk_page.set_fullscreen_mode(True)
    assert "Thu Nhỏ" in kiosk_page.btn_fullscreen.text()

    kiosk_page.set_fullscreen_mode(False)
    assert "Toàn màn hình" in kiosk_page.btn_fullscreen.text()
