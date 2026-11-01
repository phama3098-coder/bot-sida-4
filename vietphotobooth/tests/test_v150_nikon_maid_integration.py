"""
1998 TEAM — Photobooth v1.5.0 Nikon MAID Native USB Integration Tests
Verifies UI controls, backend switching, diagnostics formatting, and kiosk recovery.
"""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from vietphotobooth.camera.connection_manager import CameraConnectionManager
from vietphotobooth.camera.backends.nikon_maid.nikon_d780_backend import NikonD780Backend
from vietphotobooth.camera.diagnostics import check_nikon_maid_status, format_diagnostic_report_text
from vietphotobooth.camera.models import ConnectionState


def test_nikon_maid_backend_instantiation_and_properties():
    backend = NikonD780Backend()
    assert backend.backend_type == "nikon_maid"
    assert "Nikon D780" in backend.display_name
    assert backend.get_status() == ConnectionState.DISCONNECTED
    caps = backend.get_capabilities()
    assert caps.can_capture is True
    assert caps.can_liveview is True
    assert (6048, 4024) in caps.supported_resolutions


def test_connection_manager_switch_to_nikon_maid():
    mgr = CameraConnectionManager(default_backend="simulator")
    assert mgr.current_backend_name == "simulator"

    # Switch to nikon_maid
    with patch.object(NikonD780Backend, "connect", return_value=True), \
         patch.object(NikonD780Backend, "start_live_view", return_value=True):
        ok = mgr.switch_backend("nikon_maid")
        assert ok is True
        assert mgr.current_backend_name == "nikon_maid"
        assert isinstance(mgr._backend, NikonD780Backend)

    mgr.disconnect()


def test_camera_diagnostics_nikon_maid():
    status = check_nikon_maid_status()
    assert isinstance(status, dict)
    assert status["backend"] == "Nikon MAID Native USB"
    assert "sdk_installed" in status
    assert "camera_detected" in status
    assert "status_summary" in status

    # Format text verification
    mock_report = {
        "platform": "win32",
        "python_version": "3.12.10",
        "opencv_version": "4.10.0",
        "directshow_devices": [],
        "nikon_maid_status": {
            "backend": "Nikon MAID Native USB",
            "sdk_installed": True,
            "sdk_path": "C:\\fake\\sdk",
            "camera_detected": True,
            "detected_camera_name": "Nikon D780",
            "status_summary": "Sẵn sàng"
        },
        "digicam_status": {},
        "summary": {}
    }
    text = format_diagnostic_report_text(mock_report)
    assert "HỆ THỐNG GIAO TIẾP NATIVE USB NIKON" in text
    assert "Nikon D780" in text
    assert "ĐÃ SẴN SÀNG" in text


def test_camera_page_backend_combo_includes_nikon_maid(qapp):
    from vietphotobooth.desktop.widgets.camera_page import CameraPage
    from vietphotobooth.camera.manager import CameraManager

    cm = CameraManager(default_backend="simulator")
    page = CameraPage(cm)

    # Check combo_backend items
    backend_keys = [page.combo_backend.itemData(i) for i in range(page.combo_backend.count())]
    assert "nikon_maid" in backend_keys
    assert "directshow" in backend_keys
    assert "digicam" in backend_keys
    assert "simulator" in backend_keys

    # Check item text
    maid_idx = page.combo_backend.findData("nikon_maid")
    maid_text = page.combo_backend.itemText(maid_idx)
    assert "Nikon MAID Native USB" in maid_text
    assert "D780" in maid_text

    page.close()
    cm.close()
