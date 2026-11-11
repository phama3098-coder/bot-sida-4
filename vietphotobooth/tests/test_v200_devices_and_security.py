"""
Test suite for 1998 TEAM Photobooth v2.0.0
Phase 5 & 6 — Devices Telemetry, Offline QR Sharing & Touch PIN Security
"""

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.auth import AdminAuthManager
from vietphotobooth.desktop.widgets.touch_pin_dialog import TouchPinDialog
from vietphotobooth.desktop.widgets.devices_page import DevicesPage, DeviceChannelCard
from vietphotobooth.desktop.widgets.qr_sharing_page import QRSharingPage
from vietphotobooth.desktop.main_window import MainWindow


def test_touch_pin_keypad_and_dots(qapp):
    """Kiểm tra bàn phím số cảm ứng, 4 chấm chỉ báo và xóa lùi."""
    cfg = ConfigManager()
    auth = AdminAuthManager(cfg)
    dlg = TouchPinDialog(auth_mgr=auth)

    assert len(dlg.dot_labels) == 4
    assert len(dlg.num_buttons) == 12

    # Nhấn số 1, 2, 3
    dlg._on_keypad_clicked("1")
    dlg._on_keypad_clicked("2")
    dlg._on_keypad_clicked("3")
    assert dlg.entered_pin == "123"

    # Nhấn xóa lùi (⌫)
    dlg._on_keypad_clicked("⌫")
    assert dlg.entered_pin == "12"

    # Nhấn xóa toàn bộ (Xóa)
    dlg._on_keypad_clicked("Xóa")
    assert dlg.entered_pin == ""

    dlg.close()


def test_touch_pin_authentication_and_lockout(qapp):
    """Kiểm tra thẩm định mã PIN, rung lắc và tự động khóa 30 giây khi sai 3 lần."""
    cfg = ConfigManager()
    auth = AdminAuthManager(cfg)
    dlg = TouchPinDialog(auth_mgr=auth)

    # 1. Nhập mã PIN sai lần 1
    dlg.entered_pin = "9999"
    dlg._verify_pin()
    assert dlg.failed_attempts == 1
    assert dlg.entered_pin == ""
    assert not auth.is_authenticated()

    # 2. Nhập mã PIN sai lần 2
    dlg.entered_pin = "8888"
    dlg._verify_pin()
    assert dlg.failed_attempts == 2

    # 3. Nhập mã PIN sai lần 3 -> Kích hoạt khóa 30 giây
    dlg.entered_pin = "7777"
    dlg._verify_pin()
    assert dlg.failed_attempts == 3
    assert dlg.lockout_remaining == 30
    assert not dlg.num_buttons[0].isEnabled()  # Các phím bị vô hiệu hóa

    # Giả lập đếm ngược tick
    dlg._on_lockout_tick()
    assert dlg.lockout_remaining == 29

    # Dừng timer và phục hồi
    dlg._lockout_timer.stop()
    dlg.lockout_remaining = 0
    dlg._on_lockout_tick()
    assert dlg.num_buttons[0].isEnabled()
    assert dlg.failed_attempts == 0

    # 4. Nhập mã PIN đúng ("1234") -> Thành công
    dlg.entered_pin = "1234"
    dlg._verify_pin()
    assert auth.is_authenticated()

    dlg.close()


def test_devices_telemetry_page_channels(qapp):
    """Kiểm tra trang Giám sát thiết bị đa kênh hiển thị đủ 4 kênh phần cứng."""
    dev_page = DevicesPage()
    assert hasattr(dev_page, "card_camera")
    assert hasattr(dev_page, "card_printer")
    assert hasattr(dev_page, "card_network")
    assert hasattr(dev_page, "card_system")

    # Kiểm tra phương thức refresh_telemetry
    dev_page.refresh_telemetry()
    assert dev_page.card_camera.lbl_pill.text() != ""
    assert dev_page.card_printer.lbl_pill.text() != ""
    assert dev_page.card_network.lbl_pill.text() != ""
    assert dev_page.card_system.lbl_pill.text() != ""

    dev_page._poll_timer.stop()
    dev_page.close()


def test_qr_sharing_page_offline_lan(qapp):
    """Kiểm tra trang Chia sẻ QR mạng nội bộ Offline LAN."""
    qr_page = QRSharingPage()
    assert hasattr(qr_page, "lbl_qr_display")
    assert hasattr(qr_page, "lbl_url_display")
    assert qr_page.lbl_qr_display.pixmap() is not None
    assert "http://" in qr_page.lbl_url_display.text()

    # Thử tạo lại mã
    qr_page.generate_demo_qr()
    assert qr_page.lbl_qr_display.pixmap() is not None

    qr_page.close()


def test_main_window_v200_extended_navigation(qapp):
    """Kiểm tra tích hợp DevicesPage và QRSharingPage vào stack cửa sổ chính."""
    window = MainWindow(start_in_kiosk=False)
    assert hasattr(window, "devices_page")
    assert hasattr(window, "qr_page")
    assert window.window_stack.count() >= 5

    # Xác thực quyền quản trị
    window.auth_mgr.authenticate("1234")

    # Chuyển sang Devices (index 3)
    window.show_devices()
    assert window.window_stack.currentIndex() == 3

    # Bấm nút Quay lại trên DevicesPage
    assert hasattr(window.devices_page, "btn_back")
    window.devices_page.btn_back.click()
    assert window.window_stack.currentIndex() == 0

    # Chuyển sang QR Sharing (index 4)
    window.show_qr_sharing()
    assert window.window_stack.currentIndex() == 4

    # Bấm nút Quay lại trên QRSharingPage
    assert hasattr(window.qr_page, "btn_back")
    window.qr_page.btn_back.click()
    assert window.window_stack.currentIndex() == 0

    # Quay lại Dashboard (tích hợp trong Cài Đặt -> Tổng quan hệ thống)
    window.show_dashboard()
    assert window.window_stack.currentIndex() == 0
    assert window.tabs.currentIndex() == 5

    # Quay lại Tabs gốc (index 0)
    window.switch_to_tab(0)
    assert window.window_stack.currentIndex() == 0

    window.close()
