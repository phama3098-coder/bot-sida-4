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
    try:
        app.closeAllWindows()
        app.processEvents()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def cleanup_qt():
    """Tự động dọn dẹp các cửa sổ và thu gom bộ nhớ Qt sau mỗi bài test để tránh lỗi 0xC0000005 khi thoát."""
    yield
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        try:
            for w in QApplication.allWidgets():
                try:
                    w.close()
                    w.deleteLater()
                except Exception:
                    pass
            app.processEvents()
        except Exception:
            pass
    import gc
    gc.collect()


_session_exitstatus = 0


def pytest_sessionfinish(session, exitstatus):
    global _session_exitstatus
    _session_exitstatus = exitstatus


def pytest_unconfigure(config):
    """
    Đảm bảo tiến trình pytest kết thúc sạch sẽ, tránh Windows C runtime DLL detach crash (0xC0000409)
    do các luồng ngầm Windows Media Foundation / WASAPI của PySide6.QtMultimedia khi Python tắt.
    """
    import sys
    import os
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(_session_exitstatus)




