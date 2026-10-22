"""
Global Pytest Fixtures for 1998 TEAM Photobooth
Ensures safe offscreen Qt application lifecycle and clean process termination.
"""

import os
import sys
import pytest

# Thiết lập chế độ offscreen cho toàn bộ test suite
os.environ["QT_QPA_PLATFORM"] = "offscreen"

@pytest.fixture(scope="session", autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    app.closeAllWindows()
    app.processEvents()
    import gc
    gc.collect()
    del app


@pytest.fixture(autouse=True)
def cleanup_qt():
    """Tự động dọn dẹp các cửa sổ và thu gom bộ nhớ Qt sau mỗi bài test để tránh lỗi 0xC0000005 khi thoát."""
    yield
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        app.closeAllWindows()
        app.processEvents()
    import gc
    gc.collect()




