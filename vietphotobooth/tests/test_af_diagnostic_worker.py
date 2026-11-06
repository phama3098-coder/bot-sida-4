import threading
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QPushButton
from PySide6.QtTest import QTest

from vietphotobooth.desktop.widgets.camera_page import CameraPage


class _FakeFaceService:
    is_available = True

    def __init__(self, *args, **kwargs):
        pass

    def register_callback(self, callback):
        pass

    def unregister_callback(self, callback):
        pass

    def stop(self):
        pass


class _FakeFaceEyeController:
    is_enabled = False

    def __init__(self, *args, **kwargs):
        pass

    def register_state_callback(self, callback):
        pass

    def unregister_state_callback(self, callback):
        pass

    def get_diagnostics(self):
        return {"target_eye": None}

    def disable(self):
        pass


def _make_page(monkeypatch, qapp):
    from vietphotobooth.camera import face_detector, face_eye_af_controller

    monkeypatch.setattr(face_detector, "FaceDetectionService", _FakeFaceService)
    monkeypatch.setattr(face_eye_af_controller, "FaceEyeAFController", _FakeFaceEyeController)
    monkeypatch.setattr(CameraPage, "_init_ui", lambda self: setattr(self, "btn_test_af", QPushButton()))
    monkeypatch.setattr(CameraPage, "_populate_devices", lambda self: None)
    monkeypatch.setattr(CameraPage, "_refresh_camera_info", lambda self: None)
    monkeypatch.setattr(CameraPage, "_apply_af_result", lambda self, success, message: None)

    manager = MagicMock()
    manager.is_connected.return_value = True
    manager.get_frame_data.return_value = None
    page = CameraPage(camera_mgr=manager)
    page._initial_diag_timer.stop()
    return page, manager


def _finish_worker(page, qapp):
    worker = page._af_diagnostic_thread
    assert worker is not None
    worker.join(timeout=2)
    assert not worker.is_alive()
    qapp.processEvents()


def test_af_diagnostic_worker_success_restores_button(monkeypatch, qapp):
    page, manager = _make_page(monkeypatch, qapp)
    manager.diagnose_autofocus.return_value = {
        "success": True, "category": "SUCCESS_IN_FOCUS",
        "message": "ok", "duration_ms": 12.0,
    }
    ui_thread_id = threading.get_ident()
    callback_thread_ids = []
    with patch("vietphotobooth.desktop.widgets.camera_page.QMessageBox.information") as info:
        info.side_effect = lambda *args, **kwargs: callback_thread_ids.append(threading.get_ident())
        page._run_af_diagnostic()
        _finish_worker(page, qapp)
    assert callback_thread_ids == [ui_thread_id]
    assert page.btn_test_af.isEnabled()
    assert page.btn_test_af.text().endswith("Test AF")
    info.assert_called_once()
    page.close()


def test_af_diagnostic_worker_failure_restores_button(monkeypatch, qapp):
    page, manager = _make_page(monkeypatch, qapp)
    manager.diagnose_autofocus.return_value = {
        "success": False, "category": "MAID_REJECTED",
        "message": "lens in MF", "duration_ms": 4.0,
    }
    with patch("vietphotobooth.desktop.widgets.camera_page.QMessageBox.warning") as warning:
        page._run_af_diagnostic()
        _finish_worker(page, qapp)
    assert page.btn_test_af.isEnabled()
    assert page.btn_test_af.text().endswith("Test AF")
    warning.assert_called_once()
    page.close()


def test_af_diagnostic_worker_exception_restores_button(monkeypatch, qapp):
    page, manager = _make_page(monkeypatch, qapp)
    manager.diagnose_autofocus.side_effect = RuntimeError("sdk failure")
    with patch("vietphotobooth.desktop.widgets.camera_page.QMessageBox.warning") as warning:
        page._run_af_diagnostic()
        _finish_worker(page, qapp)
    assert page.btn_test_af.isEnabled()
    assert page.btn_test_af.text().endswith("Test AF")
    warning.assert_called_once()
    page.close()


def test_af_diagnostic_watchdog_warns_without_stopping_worker(monkeypatch, qapp):
    page, manager = _make_page(monkeypatch, qapp)
    entered = threading.Event()
    release = threading.Event()

    def blocking_diagnostic(**kwargs):
        entered.set()
        assert release.wait(timeout=2)
        return {
            "success": False, "category": "MAID_NOT_COMPLETED",
            "message": "timeout", "duration_ms": 4.0,
        }

    manager.diagnose_autofocus.side_effect = blocking_diagnostic
    page._AF_DIAGNOSTIC_WATCHDOG_MS = 20
    with patch("vietphotobooth.desktop.widgets.camera_page.logger.warning") as warning, patch("vietphotobooth.desktop.widgets.camera_page.QMessageBox.warning"):
        page._run_af_diagnostic()
        assert entered.wait(timeout=1)
        QTest.qWait(120)
        assert not page.btn_test_af.isEnabled()
        assert page._af_diagnostic_thread.is_alive()
        warning.assert_called()
        try:
            release.set()
            _finish_worker(page, qapp)
        finally:
            release.set()
    assert page.btn_test_af.isEnabled()
    page.close()
