"""
Unit tests for In-Window Guest Review flow within KioskPage and Cleaned Top Navigation.
Tests verify:
1. KioskPage embeds GuestReviewWidget in a QStackedWidget (index 0: Capture, index 1: Review).
2. No top-level modal dialog is opened when capture completes; view switches automatically to Review.
3. 'Chụp lại' (Retake) returns to Capture view (index 0) and resets state for a new session.
4. 'Hoàn tất' (Finish) returns to Capture view (index 0) without opening any new windows.
5. 'Lưu ảnh' (Save Photo) saves 300 DPI composite into the Event's Final folder.
6. 'Tiến hành in' (Print) renders composite, prints via PrintManager, and returns to Capture view.
7. Top navigation bar in MainWindow has update and lock buttons removed from top-right corner.
"""

import os
import shutil
import pytest
from PIL import Image
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from vietphotobooth.desktop.widgets.guest_review_dialog import GuestReviewWidget
from vietphotobooth.desktop.main_window import MainWindow
from vietphotobooth.core.config import get_user_data_dir


@pytest.fixture
def sample_photos():
    """Tạo 4 ảnh chụp mẫu."""
    colors = [(220, 38, 38), (37, 99, 235), (22, 163, 74), (202, 138, 4)]
    photos = []
    for c in colors:
        im = Image.new("RGB", (1200, 800), color=c)
        photos.append(im)
    return photos


def test_kiosk_page_has_stacked_widget_structure(qapp):
    """Kiểm tra KioskPage sở hữu QStackedWidget với 2 trang: Chụp ảnh (0) và Hoàn thiện (1)."""
    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page

    assert hasattr(kiosk, "kiosk_stack")
    assert kiosk.kiosk_stack.count() == 2
    assert kiosk.kiosk_stack.currentIndex() == 0

    assert kiosk.kiosk_stack.widget(0) == kiosk.capture_container
    assert kiosk.kiosk_stack.widget(1) == kiosk.review_widget
    assert isinstance(kiosk.review_widget, GuestReviewWidget)

    window.close()
    window.deleteLater()


def test_kiosk_automatic_transition_to_review_on_capture_complete(qapp, sample_photos):
    """Kiểm tra khi hoàn thành lượt chụp, KioskPage tự động chuyển sang trang Hoàn thiện ảnh, không mở dialog."""
    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page
    kiosk.current_event = "SuKien_Test_Auto"
    kiosk.captured_originals = list(sample_photos)

    # Kích hoạt chuyển trang sau chụp
    kiosk._enter_review_state()

    # Trang hiện tại trong stack phải là trang 1 (Hoàn thiện ảnh)
    assert kiosk.kiosk_stack.currentIndex() == 1
    assert len(kiosk.review_widget.photos) == len(sample_photos)
    assert kiosk.review_widget.current_template is not None

    window.close()
    window.deleteLater()


def test_kiosk_retake_button_returns_to_capture_idle(qapp, sample_photos):
    """Kiểm tra nút 'Chụp lại' trên màn hình hoàn thiện đưa về màn hình chụp và sẵn sàng lượt mới."""
    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page
    kiosk.current_event = "SuKien_Test_Retake"
    kiosk.captured_originals = list(sample_photos)
    kiosk._enter_review_state()
    assert kiosk.kiosk_stack.currentIndex() == 1

    # Khách bấm 'Chụp lại'
    kiosk.review_widget.btn_back.click()

    # Phải quay về index 0 (Chụp ảnh), trạng thái idle
    assert kiosk.kiosk_stack.currentIndex() == 0
    assert kiosk.current_state == "IDLE"
    assert len(kiosk.captured_originals) == 0

    window.close()
    window.deleteLater()


def test_kiosk_finish_button_returns_to_capture_idle(qapp, sample_photos):
    """Kiểm tra nút 'Hoàn tất' đưa về màn hình chụp để đón khách tiếp theo, không mở cửa sổ mới."""
    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page
    kiosk.current_event = "SuKien_Test_Finish"
    kiosk.captured_originals = list(sample_photos)
    kiosk._enter_review_state()
    assert kiosk.kiosk_stack.currentIndex() == 1

    # Khách hoặc kỹ thuật viên bấm 'Hoàn tất'
    kiosk.review_widget.btn_finish.click()

    # Phải quay về index 0 (Chụp ảnh), trạng thái idle
    assert kiosk.kiosk_stack.currentIndex() == 0
    assert kiosk.current_state == "IDLE"

    window.close()
    window.deleteLater()


def test_kiosk_save_photo_flow(qapp, sample_photos):
    """Kiểm tra nút 'Lưu ảnh' lưu file ảnh 300 DPI thành phẩm vào thư mục Final của sự kiện."""
    event_name = "SuKien_Test_Save"
    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page
    kiosk.current_event = event_name
    kiosk.captured_originals = list(sample_photos)
    kiosk._enter_review_state()

    saved_paths = []
    kiosk.review_widget.photo_saved.connect(lambda p: saved_paths.append(p))

    # Bấm 'Lưu ảnh'
    kiosk.review_widget.btn_save.click()

    assert len(saved_paths) == 1
    saved_file = saved_paths[0]
    assert os.path.exists(saved_file)
    assert event_name in saved_file

    # Kiểm tra kích thước và DPI
    with Image.open(saved_file) as im:
        assert im.info.get("dpi") == (300, 300)

    # Dọn dẹp thư mục test
    try:
        final_dir = os.path.dirname(saved_file)
        shutil.rmtree(os.path.dirname(final_dir), ignore_errors=True)
    except Exception:
        pass

    window.close()
    window.deleteLater()


def test_kiosk_print_flow_returns_to_capture(qapp, sample_photos):
    """Kiểm tra nút 'Tiến hành in' gửi lệnh in qua PrintManager và đưa về màn hình chụp sẵn sàng lượt mới."""
    event_name = "SuKien_Test_Print"
    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page
    kiosk.current_event = event_name
    kiosk.captured_originals = list(sample_photos)

    # Giả lập PrintManager
    mock_print_mgr = MagicMock()
    mock_print_mgr.print_image.return_value = True
    kiosk.print_mgr = mock_print_mgr

    kiosk._enter_review_state()
    assert kiosk.kiosk_stack.currentIndex() == 1

    # Bấm 'Tiến hành in'
    kiosk.review_widget.btn_confirm.click()

    # Kiểm tra print_mgr được gọi
    assert mock_print_mgr.print_image.called

    # Kiểm tra quay về trang chụp ảnh
    assert kiosk.kiosk_stack.currentIndex() == 0
    assert kiosk.current_state == "IDLE"

    window.close()
    window.deleteLater()


def test_main_window_top_navigation_bar_cleaned(qapp):
    """Kiểm tra thanh điều hướng chính trong MainWindow: nút Cập nhật và Khóa quản trị đã ẩn khỏi góc trên phải."""
    win = MainWindow(start_in_kiosk=False)

    # Không còn corner widget làm rối thanh điều hướng
    corner_w = win.tabs.cornerWidget(Qt.TopRightCorner)
    assert corner_w is None

    # Nhưng các tab chính vẫn đầy đủ 6 tab: Chụp Ảnh, Khung Ảnh, Máy Ảnh, Máy In, Sự Kiện, Cài Đặt
    assert win.tabs.count() == 6
    tab_texts = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    assert any("Chụp" in t for t in tab_texts)
    assert any("Khung" in t for t in tab_texts)
    assert any("Máy Ảnh" in t for t in tab_texts)
    assert any("Máy In" in t for t in tab_texts)
    assert any("Sự Kiện" in t for t in tab_texts)
    assert any("Cài Đặt" in t for t in tab_texts)

    # Bảo toàn tham chiếu review_page
    assert hasattr(win, "review_page")
    assert win.review_page == win.kiosk_page.review_widget

    win.close()
    win.deleteLater()
