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
    assert window.windowTitle().startswith("VietPhotoBooth")
    assert window.tabs.count() == 7
    assert window.kiosk_page is not None
    assert window.filter_page is not None
    assert window.frame_page is not None
    assert window.camera_page is not None
    assert window.printing_page is not None
    assert window.events_page is not None
    assert window.settings_page is not None

def test_fullscreen_toggle(qapp):
    window = MainWindow(start_in_kiosk=False)
    assert not window.isFullScreen()
    # Test method exists and can be called safely
    window.kiosk_page.stop_live_view()
    window.camera_mgr.close()
