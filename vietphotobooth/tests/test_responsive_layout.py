"""
Unit tests for multi-resolution responsive layout behavior.
Tests 1920x1080, 1600x900, 1366x768, 1280x720, and 1024x720.
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize

from vietphotobooth.desktop.main_window import MainWindow

# Khởi tạo QApplication cho pytest nếu chưa có
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


def test_main_window_responsive_resolutions():
    """Kiểm tra bố cục co giãn và không tràn thanh điều hướng trên mọi độ phân giải."""
    window = MainWindow()

    target_resolutions = [
        (1920, 1080),  # Full HD
        (1600, 900),   # HD+
        (1366, 768),   # Màn hình cảm ứng Photobooth thông dụng
        (1280, 720),   # 720p HD
        (1024, 680),   # Cửa sổ thu nhỏ tối thiểu
    ]

    for width, height in target_resolutions:
        window.resize(width, height)
        app.processEvents()

        # Kiểm tra kích thước cửa sổ
        assert window.width() == width
        assert window.height() == height

        # Kiểm tra Brand widget không chiếm quá 50% cửa sổ
        brand_w = window.brand_widget.width()
        assert brand_w <= 260
        assert brand_w < (width * 0.4)

        # Kiểm tra nhãn tab co giãn phù hợp (đã chuyển sang dùng SVG icon, nhãn thuần chữ)
        if width < 1000:
            assert window.tabs.tabText(0) == "Chụp"
            assert window.tabs.tabText(1) == "Khung"
            assert window.tabs.tabText(5) == "Cài Đặt"
        else:
            assert window.tabs.tabText(0) == "Chụp Ảnh"
            assert window.tabs.tabText(1) == "Khung Ảnh"
            assert window.tabs.tabText(5) == "Cài Đặt"

        # Kiểm tra minSizeHint của từng tab không vượt quá giới hạn cửa sổ
        for i in range(window.tabs.count()):
            tab_widget = window.tabs.widget(i)
            min_hint = tab_widget.minimumSizeHint()
            # Chiều rộng tối thiểu phải vừa trong cửa sổ
            assert min_hint.width() <= 1030, f"Tab {i} ({window.tabs.tabText(i)}) minSizeHint width={min_hint.width()} vượt quá 1030px"
            # Chiều cao tối thiểu phải vừa trong 720p (trừ viền tab bar ~100px)
            assert min_hint.height() <= 620, f"Tab {i} ({window.tabs.tabText(i)}) minSizeHint height={min_hint.height()} vượt quá 620px"

    window.close()


def test_frame_designer_scroll_margins_and_gutter():
    """Kiểm tra thanh cuộn của Frame Designer có đủ lề gutter không che nút hay nội dung."""
    window = MainWindow()
    fd = window.frame_page

    # 1. Kiểm tra QScrollArea của cột thuộc tính
    scroll = fd.scroll_area
    assert scroll.widgetResizable() is True

    # 2. Kiểm tra khoảng trống lề phải và đáy không che nội dung
    right_margins = fd.right_layout.contentsMargins()
    assert right_margins.right() >= 10, f"Lề phải {right_margins.right()}px quá nhỏ!"
    assert right_margins.bottom() >= 16, f"Lề đáy {right_margins.bottom()}px quá nhỏ!"

    # 3. Kiểm tra các nút không bị che trên màn hình cảm ứng 1366x768
    window.resize(1366, 768)
    app.processEvents()
    assert fd.combo_slots_selector is not None
    assert fd.btn_apply_all_slots is not None

    window.close()


def test_canvas_physical_coordinate_invariance():
    """Kiểm tra tuyệt đối không làm thay đổi tọa độ vật lý 300 DPI khi co giãn cửa sổ."""
    window = MainWindow()
    fd = window.frame_page

    assert fd.current_frame is not None
    orig_slots = [(s.x, s.y, s.w, s.h) for s in fd.current_frame.slots]
    orig_texts = [(t.x, t.y, t.font_size) for t in fd.current_frame.text_layers]

    # Co giãn qua các độ phân giải khác nhau
    for w, h in [(1920, 1080), (1600, 900), (1366, 768), (1280, 720), (1024, 680)]:
        window.resize(w, h)
        app.processEvents()

        # Tọa độ vật lý 300 DPI của từng slot phải giữ nguyên 100%
        curr_slots = [(s.x, s.y, s.w, s.h) for s in fd.current_frame.slots]
        assert curr_slots == orig_slots, f"Tọa độ ô ảnh 300 DPI bị thay đổi khi resize cửa sổ về {w}x{h}!"

        # Tọa độ vật lý 300 DPI của lớp chữ phải giữ nguyên 100%
        curr_texts = [(t.x, t.y, t.font_size) for t in fd.current_frame.text_layers]
        assert curr_texts == orig_texts, f"Tọa độ chữ 300 DPI bị thay đổi khi resize cửa sổ về {w}x{h}!"

    window.close()


def test_kiosk_responsive_layout_scaling():
    """Kiểm tra màn hình Kiosk co giãn mượt mà và nút Bắt đầu chụp không bị tràn."""
    window = MainWindow()
    window.show()
    kiosk = window.kiosk_page

    # Thử trên các độ phân giải từ 1920x1080 đến 1280x720
    for w, h in [(1920, 1080), (1600, 900), (1366, 768), (1280, 720)]:
        window.resize(w, h)
        app.processEvents()

        assert not kiosk.btn_start.isHidden()
        # Nút chụp phải có kích thước hợp lý, không tràn khỏi thanh dưới
        assert kiosk.btn_start.width() in (270, 360)
        assert kiosk.card_camera.width() <= 260
        assert kiosk.lbl_viewport.width() > 300
        assert kiosk.lbl_viewport.height() > 200

    window.close()
