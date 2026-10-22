"""
1998 TEAM — Photobooth Camera Diagnostics & Video Sources Test Suite
Covers:
1. DirectShow device enumeration (friendly names, device paths, indices).
2. Video source probe (openability, actual resolution, FPS, brightness, status).
3. Search device by name or keyword (e.g. 'Nikon', 'Logi').
4. DirectShow adapter connect by name vs index, error reporting.
5. DigiCamControl adapter tethered capture separation, live view error handling.
6. CameraManager backend switching with device_name, diagnostic report generation.
7. Diagnostics engine: full diagnostics run, formatted report, file export (.txt/.json).
8. Camera Page UI: device dropdown, diagnostic table, re-run and export buttons.
9. Camera Diagnostic Dialog: display, copy, and save features.
10. Kiosk Page: panel_no_feed alert when liveview stream is absent.
"""

import os
import json
import tempfile
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from vietphotobooth.camera.enumerator import (
    enumerate_directshow_devices,
    probe_video_source,
    find_device_by_name_or_keyword
)
from vietphotobooth.camera.diagnostics import (
    run_full_camera_diagnostics,
    format_diagnostic_report_text,
    export_diagnostic_report_file
)
from vietphotobooth.camera.directshow import DirectShowCameraAdapter
from vietphotobooth.camera.digicam import DigiCamControlAdapter
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.desktop.widgets.camera_page import CameraDiagnosticDialog
from vietphotobooth.desktop.main_window import MainWindow


# =========================================================================
# 1. DIRECTSHOW ENUMERATION & PROBING
# =========================================================================

def test_enumerate_directshow_devices():
    """Kiểm tra hàm enumerate_directshow_devices trả về danh sách hợp lệ."""
    devices = enumerate_directshow_devices()
    assert isinstance(devices, list)
    for dev in devices:
        assert "index" in dev
        assert "name" in dev
        assert "path" in dev
        assert isinstance(dev["index"], int)
        assert isinstance(dev["name"], str)
        assert len(dev["name"]) > 0


def test_find_device_by_name_or_keyword():
    """Kiểm tra tìm kiếm thiết bị theo tên hoặc từ khóa."""
    mock_devices = [
        {"index": 0, "name": "Logi C270 HD WebCam", "path": "path0"},
        {"index": 1, "name": "Nikon Webcam Utility", "path": "path1"}
    ]
    with patch("vietphotobooth.camera.enumerator.enumerate_directshow_devices", return_value=mock_devices):
        # Tìm thấy Nikon
        nikon_match = find_device_by_name_or_keyword("nikon")
        assert nikon_match is not None
        assert nikon_match["index"] == 1
        assert "Nikon" in nikon_match["name"]

        # Tìm thấy Logi
        logi_match = find_device_by_name_or_keyword("C270")
        assert logi_match is not None
        assert logi_match["index"] == 0

        # Không tìm thấy
        none_match = find_device_by_name_or_keyword("Canon EOS R50")
        assert none_match is None


def test_probe_video_source_mock():
    """Kiểm tra hàm probe_video_source với mock cv2.VideoCapture."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_cap.get.side_effect = lambda prop: 30.0 if prop == 5 else (640.0 if prop == 3 else 480.0)

    with patch("cv2.VideoCapture", return_value=mock_cap):
        result = probe_video_source(0)
        assert result["openable"] is True
        assert result["frame_readable"] is True
        assert result["actual_width"] == 640
        assert result["actual_height"] == 480
        assert result["reported_fps"] == 30.0
        assert result["mean_brightness"] == 128.0
        assert "Hoạt động hoàn hảo" in result["status"]
        assert result["error_message"] == ""
        mock_cap.release.assert_called_once()


def test_probe_video_source_cannot_open():
    """Kiểm tra probe_video_source khi nguồn không thể mở."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False

    with patch("cv2.VideoCapture", return_value=mock_cap):
        result = probe_video_source(99)
        assert result["openable"] is False
        assert result["frame_readable"] is False
        assert result["actual_width"] == 0
        assert result["error_message"] != ""
        assert "Không mở được" in result["status"]


# =========================================================================
# 2. ADAPTER TESTS: DIRECTSHOW & DIGICAMCONTROL
# =========================================================================

def test_directshow_adapter_connect_by_name():
    """Kiểm tra DirectShowCameraAdapter kết nối bằng device_id dạng tên."""
    mock_devices = [
        {"index": 0, "name": "Logi C270 HD WebCam", "path": "path0"},
        {"index": 1, "name": "Nikon Webcam Utility", "path": "path1"}
    ]
    with patch("vietphotobooth.camera.enumerator.enumerate_directshow_devices", return_value=mock_devices):
        adapter = DirectShowCameraAdapter(device_index=0)
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        fake_frame = np.full((768, 1024, 3), 100, dtype=np.uint8)
        mock_cap.read.return_value = (True, fake_frame)
        mock_cap.get.side_effect = lambda prop: 30.0 if prop == 5 else (1024.0 if prop == 3 else 768.0)

        with patch("cv2.VideoCapture", return_value=mock_cap):
            ok = adapter.connect(device_id="Nikon Webcam Utility")
            assert ok is True
            assert adapter.is_connected() is True
            assert adapter.device_index == 1
            assert adapter.device_name == "Nikon Webcam Utility"
            assert adapter.actual_resolution == (1024, 768)
            assert adapter.last_error is None or adapter.last_error == ""

            info = adapter.get_info()
            assert info.name == "Nikon Webcam Utility"
            assert info.capabilities["can_liveview"] is True

            adapter.disconnect()
            assert adapter.is_connected() is False


def test_directshow_adapter_failed_read_records_error():
    """Kiểm tra DirectShowCameraAdapter khi không đọc được frame sẽ ghi log error cụ thể."""
    adapter = DirectShowCameraAdapter(device_index=5)
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (False, None)

    with patch("cv2.VideoCapture", return_value=mock_cap):
        ok = adapter.connect(device_id=5)
        assert ok is False
        assert adapter.is_connected() is False
        assert adapter.last_error is not None
        assert "không nhận được khung hình" in adapter.last_error or "không đọc được khung hình" in adapter.last_error


def test_digicam_adapter_separation_and_liveview_error():
    """
    Kiểm tra DigiCamControlAdapter:
    - Vẫn giữ nguyên kết nối tethered capture PTP/USB.
    - get_liveview_frame ghi nhận rõ error khi web server port 5513 không bật.
    """
    adapter = DigiCamControlAdapter()
    info = adapter.get_info()
    assert "DSLR" in info.name or "digiCamControl" in info.name or "Chưa kết nối" in info.name
    assert info.capabilities["can_capture"] is True

    # Khi get_liveview_frame gọi mà server không phản hồi -> trả về None và set last_error
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        frame = adapter.get_liveview_frame()
        assert frame is None
        assert adapter.last_error is not None
        assert "5513" in adapter.last_error or "digiCamControl" in adapter.last_error


# =========================================================================
# 3. CAMERA MANAGER & SWITCHING
# =========================================================================

def test_camera_manager_switch_with_device_name():
    """Kiểm tra CameraManager switch_backend hỗ trợ device_name."""
    mgr = CameraManager(default_backend="simulator")
    assert mgr.backend_name == "simulator"

    # Switch to directshow with device_name
    mock_devices = [{"index": 1, "name": "Nikon Webcam Utility", "path": "p1"}]
    with patch("vietphotobooth.camera.enumerator.enumerate_directshow_devices", return_value=mock_devices):
        with patch.object(DirectShowCameraAdapter, "connect", return_value=True):
            ok = mgr.switch_backend("directshow", device_name="Nikon Webcam Utility")
            assert ok is True
            assert mgr.backend_name == "directshow"

    # Switch back to simulator
    mgr.switch_backend("simulator")
    assert mgr.backend_name == "simulator"
    assert mgr.is_connected() is True


def test_camera_manager_get_diagnostic_report():
    """Kiểm tra CameraManager sinh báo cáo chẩn đoán dạng dict."""
    mgr = CameraManager(default_backend="simulator")
    report = mgr.get_diagnostic_report()
    assert isinstance(report, dict)
    assert "summary" in report
    assert "directshow_devices" in report


# =========================================================================
# 4. FULL DIAGNOSTICS & EXPORT
# =========================================================================

def test_run_full_camera_diagnostics():
    """Kiểm tra chạy chẩn đoán toàn diện trả về cấu trúc dữ liệu đầy đủ."""
    diag = run_full_camera_diagnostics()
    assert "timestamp" in diag
    assert "directshow_devices" in diag
    assert "digicam_status" in diag
    assert "summary" in diag
    assert isinstance(diag["directshow_devices"], list)
    assert "recommendations" in diag["summary"]


def test_format_and_export_diagnostic_report():
    """Kiểm tra định dạng báo cáo text và xuất ra tệp .txt / .json."""
    diag = run_full_camera_diagnostics()
    report_text = format_diagnostic_report_text(diag)
    assert "PHOTOBOOTH" in report_text
    assert "HƯỚNG DẪN XỬ LÝ" in report_text or "KẾT LUẬN" in report_text

    with tempfile.TemporaryDirectory() as tmpdir:
        txt_target = os.path.join(tmpdir, "test_diag.txt")
        res_path = export_diagnostic_report_file(target_path=txt_target)
        json_path = txt_target.replace(".txt", ".json")

        assert res_path == txt_target
        assert os.path.exists(res_path)
        assert os.path.exists(json_path)
        assert os.path.getsize(res_path) > 100
        assert os.path.getsize(json_path) > 100

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "directshow_devices" in data


# =========================================================================
# 5. DESKTOP GUI WIDGET TESTS
# =========================================================================

def test_camera_page_diagnostics_ui(qapp):
    """Kiểm tra CameraPage có dropdown thiết bị, bảng chẩn đoán và nút xuất báo cáo."""
    window = MainWindow(start_in_kiosk=False)
    page = window.camera_page
    assert hasattr(page, "combo_device")
    assert hasattr(page, "table_diag")
    assert hasattr(page, "btn_run_diag")
    assert hasattr(page, "btn_export_diag")

    # Bảng chẩn đoán có 8 cột
    assert page.table_diag.columnCount() == 8

    # Nút bấm hoạt động
    assert page.btn_run_diag.text() == "🔄 Chạy Lại Chẩn Đoán"
    assert "Xuất Báo Cáo" in page.btn_export_diag.text()
    window.close()


def test_camera_diagnostic_dialog(qapp):
    """Kiểm tra CameraDiagnosticDialog khởi tạo, hiển thị text và có nút đóng/sao chép/lưu."""
    sample_text = "1998 TEAM — BÁO CÁO CHẨN ĐOÁN NIKON D780 VÀ WEBCAM\nNikon Webcam Utility: Sẵn sàng 1024x768"
    dlg = CameraDiagnosticDialog(report_text=sample_text)
    assert "NIKON D780" in dlg.txt_report.toPlainText()
    assert dlg.btn_copy is not None
    assert dlg.btn_save is not None
    assert dlg.btn_close is not None
    dlg.close()


def test_kiosk_page_no_feed_panel(qapp):
    """Kiểm tra KioskPage có panel_no_feed cảnh báo khi mất luồng Live View."""
    window = MainWindow(start_in_kiosk=False)
    page = window.kiosk_page
    assert hasattr(page, "panel_no_feed")
    assert hasattr(page, "lbl_no_feed_title")
    assert hasattr(page, "lbl_no_feed_desc")

    # Mặc định ban đầu ẩn
    assert page.panel_no_feed.isHidden()

    # Giả lập chuyển sang directshow và timeout không nhận frame
    page.camera_mgr.is_connected = MagicMock(return_value=True)
    page.camera_mgr.backend_name = "directshow"
    page._last_live_frame_time = 0.0
    page._check_feed_timeout()
    assert not page.panel_no_feed.isHidden()

    # Nhận lại frame hợp lệ -> panel tự ẩn
    valid_frame = np.full((480, 640, 3), 100, dtype=np.uint8)
    page._on_live_view_frame(valid_frame)
    assert page.panel_no_feed.isHidden()
    window.close()
