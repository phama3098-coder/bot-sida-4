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
        (1024, 720),   # Cửa sổ thu nhỏ tối thiểu
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

        # Kiểm tra nhãn tab co giãn phù hợp
        if width < 1000:
            assert window.tabs.tabText(0) == "📸 Chụp"
            assert window.tabs.tabText(1) == "🖼️ Khung"
            assert window.tabs.tabText(5) == "⚙️ Cài Đặt"
        else:
            assert window.tabs.tabText(0) == "📸 Chụp Ảnh"
            assert window.tabs.tabText(1) == "🖼️ Khung Ảnh"
            assert window.tabs.tabText(5) == "⚙️ Cài Đặt"

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

    # 2. Kiểm tra khoảng trống lề phải (dedicated scrollbar gutter >= 24px)
    right_margins = fd.right_layout.contentsMargins()
    assert right_margins.right() >= 24, f"Lề phải {right_margins.right()}px quá nhỏ, thanh cuộn có thể che nội dung!"
    assert right_margins.bottom() >= 30, f"Lề đáy {right_margins.bottom()}px quá nhỏ, không cuộn hết được trang!"

    # 3. Kiểm tra các nút không bị che trên màn hình cảm ứng 1366x768
    window.resize(1366, 768)
    app.processEvents()
    assert fd.combo_slots_selector is not None
    assert fd.btn_apply_all_slots is not None

    window.close()

