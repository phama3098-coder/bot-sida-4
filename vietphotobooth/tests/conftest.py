"""
Global Pytest Fixtures for 1998 TEAM Photobooth
Ensures safe offscreen Qt application lifecycle and clean process termination.
"""

import os
import sys
import pytest

# Thiết lập chế độ offscreen cho toàn bộ test suite
os.environ["QT_QPA_PLATFORM"] = "offscreen"

@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    app.processEvents()
