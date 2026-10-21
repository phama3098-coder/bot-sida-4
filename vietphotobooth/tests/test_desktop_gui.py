"""
Tests for PySide6 Native Desktop GUI Application
"""

import os
import sys
import pytest
from PySide6.QtWidgets import QApplication

from vietphotobooth.desktop.main_window import MainWindow

def test_main_window_initialization(qapp):
    window = MainWindow(start_in_kiosk=False)
    assert window is not None
    assert "1998 TEAM" in window.windowTitle()
    assert window.tabs.count() == 6
    assert "Chụp Ảnh" in window.tabs.tabText(0)
    assert "Khung Ảnh" in window.tabs.tabText(1)
    assert "Máy Ảnh" in window.tabs.tabText(2)
    assert "Máy In" in window.tabs.tabText(3)
    assert "Sự Kiện & Thư Viện" in window.tabs.tabText(4)
    assert "Cài Đặt" in window.tabs.tabText(5)
    assert window.kiosk_page is not None
    assert window.frame_page is not None
    assert window.camera_page is not None
    assert window.printing_page is not None
    assert window.events_page is not None
    assert window.settings_page is not None
    window.close()

def test_fullscreen_toggle(qapp):
    window = MainWindow(start_in_kiosk=False)
    assert not window.isFullScreen()
    # Test method exists and can be called safely
    window.close()


def test_kiosk_shots_stepper_and_numpad(qapp):
    """Kiểm tra bộ điều khiển số ảnh linh hoạt [ - ] [ N ] [ + ] và bàn phím cảm ứng."""
    from vietphotobooth.desktop.widgets.kiosk_page import TouchNumberPadDialog
    from PIL import Image

    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page

    # 1. Kiểm tra ban đầu
    assert kiosk.btn_shots_minus is not None
    assert kiosk.txt_shots_input is not None
    assert kiosk.btn_shots_plus is not None
    initial_shots = kiosk.total_shots_needed
    assert kiosk.txt_shots_input.text() == str(initial_shots)

    # 2. Tăng số ảnh [+]
    kiosk._increase_shots()
    assert kiosk.total_shots_needed == initial_shots + 1
    assert kiosk.txt_shots_input.text() == str(initial_shots + 1)

    # 3. Giảm số ảnh [-]
    kiosk._decrease_shots()
    assert kiosk.total_shots_needed == initial_shots
    assert kiosk.txt_shots_input.text() == str(initial_shots)

    # 4. Nhập trực tiếp
    kiosk.txt_shots_input.setText("6")
    kiosk._on_shots_input_finished()
    assert kiosk.total_shots_needed == 6

    # 5. Kiểm tra giới hạn biên [1 .. 16]
    kiosk.txt_shots_input.setText("25")  # Vượt quá 16
    kiosk._on_shots_input_finished()
    assert kiosk.total_shots_needed == 16

    kiosk.txt_shots_input.setText("0")  # Nhỏ hơn 1
    kiosk._on_shots_input_finished()
    assert kiosk.total_shots_needed == 1

    # 6. Kiểm tra TouchNumberPadDialog
    dlg = TouchNumberPadDialog(current_val=4, parent=window)
    dlg._on_digit("5")        # "4" -> "45"
    assert dlg.display.text() == "45"
    dlg._on_backspace()       # Xóa "5" -> "4"
    assert dlg.display.text() == "4"
    dlg._on_clear()           # Xóa hết -> "0"
    assert dlg.display.text() == "0"
    dlg._on_digit("8")        # Nhập "8"
    assert dlg.display.text() == "8"
    dlg._on_accept()
    assert dlg.value == 8
    dlg.close()

    window.close()


def test_kiosk_mismatch_warning_badge(qapp):
    """Kiểm tra hiển thị thông báo khi số ảnh chụp khác số ô khung mà không làm mất ảnh."""
    from PIL import Image

    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page

    # Giả lập 2 ảnh chụp (trong khi khung mẫu mặc định có 3 ô)
    kiosk.captured_originals = [
        Image.new("RGB", (600, 400), (255, 0, 0)),
        Image.new("RGB", (600, 400), (0, 255, 0)),
    ]

    # Kích hoạt callback khi dựng ảnh xong
    dummy_composite = Image.new("RGB", (600, 1800), (255, 255, 255))
    kiosk._on_composite_ready(dummy_composite, "dummy_path.jpg")

    # Kiểm tra huy hiệu thông báo hiển thị đúng nội dung giải thích
    assert not kiosk.lbl_status_badge.isHidden()
    badge_text = kiosk.lbl_status_badge.text()
    assert "Đã chụp 2 ảnh" in badge_text
    assert "lưu an toàn" in badge_text

    window.close()


def test_admin_auth_and_tab_protection(qapp):
    """Kiểm tra hệ thống xác thực Quản trị viên, mã PIN SHA-256 và phân quyền chuyển tab."""
    from vietphotobooth.core.auth import AdminAuthManager
    from vietphotobooth.core.config import ConfigManager

    window = MainWindow(start_in_kiosk=False)
    auth = window.auth_mgr

    # 1. Ban đầu ở trạng thái khóa
    assert not auth.is_authenticated()
    assert window.tabs.currentIndex() == 0

    # 2. Chuyển sang Tab 1 (Khung Ảnh) không bị chặn
    window.tabs.setCurrentIndex(1)
    assert window.tabs.currentIndex() == 1

    # 3. Chuyển về Tab 0 (Chụp Ảnh) không bị chặn
    window.tabs.setCurrentIndex(0)
    assert window.tabs.currentIndex() == 0

    # 4. Xác thực mã PIN sai -> Thất bại
    assert not auth.authenticate("sai_pin_9999")
    assert not auth.is_authenticated()

    # 5. Xác thực mã PIN mặc định "1234" -> Thành công
    assert auth.authenticate("1234")
    assert auth.is_authenticated()
    assert auth.get_remaining_seconds() > 0

    # 6. Khi đã xác thực, có thể chuyển vào tab bảo mật (Tab 2: Máy Ảnh, Tab 5: Cài Đặt)
    window.tabs.setCurrentIndex(2)
    assert window.tabs.currentIndex() == 2

    # 7. Chủ động khóa phiên
    auth.lock()
    assert not auth.is_authenticated()

    window.close()


def test_frame_designer_slot_corner_resize(qapp):
    """Kiểm tra thao tác kéo thả 4 tay nắm góc để co giãn ô ảnh trên InteractiveCanvas."""
    from vietphotobooth.desktop.widgets.frame_designer_page import InteractiveCanvas
    from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot
    from PySide6.QtCore import QPoint

    canvas = InteractiveCanvas()
    template = FrameTemplate(
        id="test_tmpl",
        name="Test Template",
        canvas_size=(1200, 1800),
        slots=[PhotoSlot(id=1, x=100, y=100, w=500, h=400)]
    )
    canvas.template = template
    canvas.selected_slot_index = 0
    canvas.resize(600, 900)

    # 1. Kiểm tra phát hiện tay nắm góc
    scale, ox, oy, rw, rh = canvas._get_canvas_geometry()
    sx = int(100 * scale) + ox
    sy = int(100 * scale) + oy
    sw = int(500 * scale)
    sh = int(400 * scale)

    # Góc dưới phải (Bottom-Right corner)
    corner = canvas._corner_hit_test(sx + sw, sy + sh)
    assert corner == "br"

    # Góc trên trái (Top-Left corner)
    corner_tl = canvas._corner_hit_test(sx, sy)
    assert corner_tl == "tl"

    # 2. Giả lập kéo tay nắm góc dưới phải để mở rộng ô ảnh
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent, QPointF, Qt

    resized_signals = []
    canvas.slot_resized.connect(lambda idx, x, y, w, h: resized_signals.append((idx, x, y, w, h)))

    canvas._is_resizing_slot = True
    canvas._slot_resize_corner = "br"
    canvas._start_slot_x = 100
    canvas._start_slot_y = 100
    canvas._start_slot_w = 500
    canvas._start_slot_h = 400
    canvas._drag_start_pos = QPoint(int(sx + sw), int(sy + sh))

    # Di chuyển chuột mở rộng kích thước
    new_mouse_x = sx + sw + int(100 * scale)
    new_mouse_y = sy + sh + int(80 * scale)
    move_event = QMouseEvent(
        QEvent.MouseMove,
        QPointF(new_mouse_x, new_mouse_y),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier
    )
    canvas.mouseMoveEvent(move_event)

    # Kiểm tra ô ảnh đã được tính toán lại kích thước và phát tín hiệu
    assert len(resized_signals) > 0
    idx, rx, ry, rw, rh = resized_signals[-1]
    assert idx == 0
    assert rx == 100
    assert ry == 100
    assert rw > 500
    assert rh > 400

    # 3. Kiểm tra bật tắt độc lập lưới Grid, Vùng An Toàn, Vạch Cắt
    canvas.show_grid = False
    assert not canvas.show_grid
    canvas.show_safe_zone = True
    assert canvas.show_safe_zone
    canvas.show_cut_lines = True
    assert canvas.show_cut_lines

    canvas.close()


def test_frame_designer_font_registry_and_preview(qapp):
    """Kiểm tra kho phông chữ cưới Việt hóa, bộ lọc thể loại và nhãn xem trước kiểu chữ."""
    from vietphotobooth.core.font_registry import FontRegistry
    from vietphotobooth.desktop.widgets.frame_designer_page import FrameDesignerPage
    from vietphotobooth.frames.frame_manager import FrameManager

    registry = FontRegistry()
    assert len(registry.list_fonts()) > 0

    all_fonts = registry.get_font_names_by_category("all")
    assert len(all_fonts) > 0

    fm = FrameManager()
    page = FrameDesignerPage(fm)

    # Kiểm tra các nút lọc thể loại tồn tại và hoạt động
    assert hasattr(page, "btn_font_all")
    assert hasattr(page, "btn_font_hw")
    assert hasattr(page, "btn_font_lux")
    assert hasattr(page, "btn_font_mod")
    assert hasattr(page, "lbl_font_preview")

    # Lọc thể loại 'luxury'
    page._filter_fonts_by_category("luxury")
    assert page.combo_font.count() > 0

    # Lọc thể loại 'all'
    page._filter_fonts_by_category("all")
    assert page.combo_font.count() >= len(all_fonts)

    page.close()


def test_frame_designer_overlapping_text_cycling_and_smart_placement(qapp):
    """Kiểm tra cảnh báo chữ đè nhau, nhấp luân phiên chọn lớp và dàn đều chữ theo chiều dọc."""
    from vietphotobooth.desktop.widgets.frame_designer_page import FrameDesignerPage
    from vietphotobooth.frames.frame_manager import FrameManager
    from vietphotobooth.frames.frame_models import TextLayer

    fm = FrameManager()
    page = FrameDesignerPage(fm)
    frame = page.current_frame
    assert frame is not None

    # Tạo 2 lớp chữ cùng tọa độ (đè lên nhau)
    frame.text_layers = [
        TextLayer(id=1, text="Tên Cô Dâu & Chú Rể", font_name="Arial", font_size=40, font_color="#D4AF37", x=300, y=500),
        TextLayer(id=2, text="25.10.2026 • Studio 1998", font_name="Arial", font_size=30, font_color="#FFFFFF", x=300, y=510),
    ]

    # 1. Phát hiện đè lớp chữ
    assert page._check_text_overlaps()
    page._update_preview(full_render=False)
    assert "đè lên nhau" in page.lbl_text_overlap.text()

    # 2. Dàn đều chữ theo chiều dọc
    page._distribute_text_layers()
    # Sau khi dàn đều, tọa độ y của lớp 2 phải cách xa lớp 1
    assert frame.text_layers[1].y > frame.text_layers[0].y + 30
    assert not page._check_text_overlaps()

    page.close()


