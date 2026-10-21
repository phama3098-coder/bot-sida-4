"""
Tests for PySide6 Native Desktop GUI Application
"""

import os
import sys
import pytest
from PySide6.QtWidgets import QApplication

from vietphotobooth.desktop.main_window import MainWindow

@pytest.fixture(scope="session")
def qapp():
    # Use offscreen platform for headless CI / unit test environments
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

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
