"""
Test suite for 1998 TEAM Photobooth v2.0.0
Phase 2 — Core UI & Operator Dashboard Navigation
"""

import pytest
from PySide6.QtWidgets import QApplication
from vietphotobooth.desktop.main_window import MainWindow
from vietphotobooth.desktop.widgets.dashboard_page import DashboardPage


def test_dashboard_page_components(qapp):
    window = MainWindow(start_in_kiosk=False)
    assert hasattr(window, "dashboard_page")
    assert isinstance(window.dashboard_page, DashboardPage)
    assert window.dashboard_page.btn_start_kiosk is not None
    assert window.dashboard_page.viewport is not None
    assert window.btn_dashboard is not None
    window.close()


def test_dashboard_navigation_switch(qapp):
    window = MainWindow(start_in_kiosk=False)
    # Default stack is 0 (tabs)
    assert window.window_stack.currentIndex() == 0

    # Chuyển sang Dashboard
    window.show_dashboard()
    assert window.window_stack.currentIndex() == 2

    # Chuyển tab quay lại tabs container
    window.switch_to_tab(1)
    assert window.window_stack.currentIndex() == 0
    assert window.tabs.currentIndex() == 1

    # Chuyển lại Dashboard
    window.show_dashboard()
    assert window.window_stack.currentIndex() == 2

    window.close()


def test_dashboard_signals(qapp):
    window = MainWindow(start_in_kiosk=False)
    # Xác thực quyền quản trị để chuyển vào các tab bảo vệ không bị dialog chặn
    window.auth_mgr.authenticate("1234")

    window.show_dashboard()
    assert window.window_stack.currentIndex() == 2

    # Bấm Open Studio -> Chuyển sang Tab Máy Ảnh (index 2)
    window.dashboard_page.open_studio_requested.emit()
    assert window.window_stack.currentIndex() == 0
    assert window.tabs.currentIndex() == 2

    # Chuyển lại Dashboard rồi bấm Open Templates -> Chuyển sang Tab Khung Ảnh (index 1)
    window.show_dashboard()
    window.dashboard_page.open_templates_requested.emit()
    assert window.window_stack.currentIndex() == 0
    assert window.tabs.currentIndex() == 1

    window.close()
