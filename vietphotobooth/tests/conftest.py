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
    from vietphotobooth.core.font_registry import FontRegistry
    FontRegistry.initialize()
    app.setFont(FontRegistry.get_default_application_font(point_size=10))
    yield app
    try:
        app.closeAllWindows()
        app.processEvents()
    except Exception:
        pass


def _install_worker_trackers():
    """Gắn WeakSet tracker nhẹ vào các lớp worker/service khi module đã được nạp."""
    import weakref
    import functools

    if not hasattr(_install_worker_trackers, "_tracked"):
        _install_worker_trackers._tracked = weakref.WeakSet()
        _install_worker_trackers._patched = set()

    tracked = _install_worker_trackers._tracked
    targets = (
        ("vietphotobooth.cloud.sync_manager", "SyncManager"),
        ("vietphotobooth.desktop.widgets.kiosk_page", "CameraLiveViewWorker"),
    )
    for mod_name, cls_name in targets:
        key = (mod_name, cls_name)
        if key in _install_worker_trackers._patched:
            continue
        mod = sys.modules.get(mod_name)
        if mod is None or not hasattr(mod, cls_name):
            continue
        cls = getattr(mod, cls_name)
        orig_init = cls.__init__

        @functools.wraps(orig_init)
        def _wrapped_init(self, *args, __orig=orig_init, **kwargs):
            __orig(self, *args, **kwargs)
            tracked.add(self)

        cls.__init__ = _wrapped_init
        _install_worker_trackers._patched.add(key)

    return tracked


@pytest.fixture(autouse=True)
def cleanup_qt():
    """Tự động dọn dẹp các cửa sổ, timer, luồng nền và thu gom bộ nhớ Qt sau mỗi bài test."""
    _install_worker_trackers()
    yield
    import gc
    import threading
    from PySide6.QtWidgets import QApplication

    tracked = _install_worker_trackers()

    app = QApplication.instance()
    if app:
        try:
            _timer_attrs = (
                "_timer", "status_timer", "_poll_timer", "auth_timer",
                "guest_idle_timer", "countdown_timer", "camera_poll_timer",
                "_af_watchdog_timer", "_initial_diag_timer", "_stats_timer",
                "_af_diag_watchdog", "_timeout_timer", "_lockout_timer", "_deadline_timer",
            )
            # 1. Dọn dẹp widget chưa được đánh dấu cleaned (tránh gọi lại trên đối tượng đã đóng)
            for w in list(QApplication.allWidgets()):
                try:
                    if getattr(w, "_conftest_cleaned", False):
                        continue
                    for attr in _timer_attrs:
                        t = getattr(w, attr, None)
                        if t is not None and hasattr(t, "isActive") and t.isActive():
                            t.stop()
                    if hasattr(w, "cleanup") and callable(w.cleanup):
                        w.cleanup()
                    setattr(w, "_conftest_cleaned", True)
                except Exception:
                    pass

            # 2. Đóng các cửa sổ cấp cao trước để closeEvent dọn cây con
            for w in list(QApplication.topLevelWidgets()):
                try:
                    if not getattr(w, "_conftest_closed", False):
                        w.close()
                        setattr(w, "_conftest_closed", True)
                except Exception:
                    pass
            app.processEvents()
        except Exception:
            pass

    # 3. Dọn dẹp mọi luồng nền Python chưa đóng (CameraConnectionManager, PrintManager, FaceDetectionService)
    for t in list(threading.enumerate()):
        if not t.is_alive() or t.name == "MainThread":
            continue
        target = getattr(t, "_target", None)
        owner = getattr(target, "__self__", None)
        if owner is None or getattr(owner, "_conftest_cleaned", False):
            continue
        cls_name = type(owner).__name__
        try:
            if cls_name in ("CameraConnectionManager", "CameraManager") and hasattr(owner, "close"):
                owner.close()
                setattr(owner, "_conftest_cleaned", True)
            elif cls_name == "PrintManager" and hasattr(owner, "stop"):
                owner.stop()
                setattr(owner, "_conftest_cleaned", True)
            elif cls_name == "FaceDetectionService" and hasattr(owner, "stop"):
                owner.stop()
                setattr(owner, "_conftest_cleaned", True)
        except Exception:
            pass

    # 4. Dừng QThread worker trước khi gọi deleteLater() trên widget cha
    for obj in list(tracked):
        try:
            if getattr(obj, "_conftest_cleaned", False):
                continue
            if hasattr(obj, "close"):
                obj.close()
            elif hasattr(obj, "isRunning") and obj.isRunning() and hasattr(obj, "stop"):
                obj.stop()
            setattr(obj, "_conftest_cleaned", True)
        except Exception:
            pass
    tracked.clear()

    if app:
        try:
            for w in list(QApplication.topLevelWidgets()):
                try:
                    if not getattr(w, "_conftest_deleted", False):
                        setattr(w, "_conftest_deleted", True)
                        w.deleteLater()
                except Exception:
                    pass
            app.processEvents()
        except Exception:
            pass

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




