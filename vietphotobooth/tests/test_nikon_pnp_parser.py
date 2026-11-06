"""
1998 TEAM — Photobooth Unit Tests for Nikon D780 PnP Parser & Hardware Discovery
Tests whitespace-tolerant regex parsing, multi-device isolation, Disconnected state rejection,
PowerShell fallback behavior, subprocess timeout handling, and discover_devices() SDK enumeration gating.
"""

import subprocess
import pytest
from unittest.mock import patch, MagicMock

from vietphotobooth.camera.backends.nikon_maid.nikon_d780_backend import (
    parse_pnputil_device_status,
    check_nikon_d780_pnp,
    NikonD780Backend
)
from vietphotobooth.camera.models import ConnectionState


# ==============================================================================
# SAMPLE PNPUTIL OUTPUTS
# ==============================================================================

REAL_WINDOWS_PNPUTIL_D780_STARTED = """Microsoft PnP Utility

Instance ID:                USB\\VID_04B0&PID_0446\\0000002008880
Device Description:         D780
Class Name:                 WPD
Class GUID:                 {eec5ad98-8080-425f-922a-dabf3de3f69a}
Manufacturer Name:          Nikon Corporation
Status:                     Started
Driver Name:                wpdmtp.inf
"""

PNPUTIL_D780_SINGLE_SPACE = """Instance ID: USB\\VID_04B0&PID_0446\\0000002008880
Device Description: D780
Class Name: WPD
Manufacturer Name: Nikon Corporation
Status: Started
Driver Name: wpdmtp.inf"""

PNPUTIL_D780_TABS_AND_WHITESPACE = (
    "Instance ID:\tUSB\\VID_04B0&PID_0446\\0000002008880\r\n"
    "Device Description:\tD780\r\n"
    "Class Name:\tWPD\r\n"
    "Manufacturer Name:\tNikon Corporation\r\n"
    "Status:\t\tStarted\r\n"
    "Driver Name:\twpdmtp.inf\r\n"
)

PNPUTIL_D780_DISCONNECTED = """Microsoft PnP Utility

Instance ID:                USB\\VID_04B0&PID_0446\\0000002008880
Device Description:         D780
Class Name:                 WPD
Class GUID:                 {eec5ad98-8080-425f-922a-dabf3de3f69a}
Manufacturer Name:          Nikon Corporation
Status:                     Disconnected
Driver Name:                wpdmtp.inf
"""

PNPUTIL_MULTI_DEVICE_OTHER_STARTED_D780_DISCONNECTED = """Microsoft PnP Utility

Instance ID:                USB\\VID_04E8&PID_6860\\6&2f62a6c1&0&0000
Device Description:         Galaxy S21 5G
Class Name:                 WPD
Manufacturer Name:          samsung
Status:                     Started
Driver Name:                wpdmtp.inf

Instance ID:                USB\\VID_04B0&PID_0446\\0000002008880
Device Description:         D780
Class Name:                 WPD
Manufacturer Name:          Nikon Corporation
Status:                     Disconnected
Driver Name:                wpdmtp.inf
"""

PNPUTIL_MULTI_DEVICE_OTHER_DISCONNECTED_D780_STARTED = """Microsoft PnP Utility

Instance ID:                USB\\VID_04E8&PID_6860\\6&2f62a6c1&0&0000
Device Description:         Galaxy S21 5G
Class Name:                 WPD
Manufacturer Name:          samsung
Status:                     Disconnected
Driver Name:                wpdmtp.inf

Instance ID:                USB\\VID_04B0&PID_0446\\0000002008880
Device Description:         D780
Class Name:                 WPD
Manufacturer Name:          Nikon Corporation
Status:                     Started
Driver Name:                wpdmtp.inf
"""

PNPUTIL_CLONE_NON_NIKON = """Microsoft PnP Utility

Instance ID:                USB\\VID_9999&PID_8888\\00001
Device Description:         Fake D780 Clone
Class Name:                 WPD
Manufacturer Name:          Generic Manufacturer
Status:                     Started
Driver Name:                generic.inf
"""


# ==============================================================================
# TESTS FOR parse_pnputil_device_status
# ==============================================================================

def test_parse_pnputil_real_windows_21_spaces():
    """Kiểm tra nhận diện thành công định dạng thực tế của Windows với 21 khoảng trắng."""
    assert parse_pnputil_device_status(REAL_WINDOWS_PNPUTIL_D780_STARTED) is True


def test_parse_pnputil_single_space():
    """Kiểm tra nhận diện định dạng chuẩn 1 khoảng trắng (Status: Started)."""
    assert parse_pnputil_device_status(PNPUTIL_D780_SINGLE_SPACE) is True


def test_parse_pnputil_tabs_and_variable_whitespace():
    """Kiểm tra nhận diện với các ký tự tab và whitespace bất kỳ."""
    assert parse_pnputil_device_status(PNPUTIL_D780_TABS_AND_WHITESPACE) is True


def test_parse_pnputil_casing_variations():
    """Kiểm tra không phân biệt chữ hoa/thường (Started, started, STARTED)."""
    lower_out = PNPUTIL_D780_SINGLE_SPACE.replace("Status: Started", "status: started")
    assert parse_pnputil_device_status(lower_out) is True

    upper_out = PNPUTIL_D780_SINGLE_SPACE.replace("Status: Started", "STATUS: STARTED")
    assert parse_pnputil_device_status(upper_out) is True


def test_parse_pnputil_disconnected_state():
    """Không nhận nhầm máy ảnh Nikon D780 ở trạng thái Disconnected."""
    assert parse_pnputil_device_status(PNPUTIL_D780_DISCONNECTED) is False


def test_parse_pnputil_disabled_state():
    """Không nhận nhầm máy ảnh Nikon D780 ở trạng thái Disabled."""
    disabled_out = PNPUTIL_D780_SINGLE_SPACE.replace("Status: Started", "Status: Disabled")
    assert parse_pnputil_device_status(disabled_out) is False


def test_parse_pnputil_multi_device_isolation_other_started():
    """
    Khi có nhiều thiết bị, nếu thiết bị khác Started nhưng Nikon D780 Disconnected,
    hệ thống phải trả về False (không bị đánh lừa bởi trạng thái Started của thiết bị khác).
    """
    assert parse_pnputil_device_status(PNPUTIL_MULTI_DEVICE_OTHER_STARTED_D780_DISCONNECTED) is False


def test_parse_pnputil_multi_device_isolation_d780_started():
    """Khi có nhiều thiết bị và Nikon D780 Started, trả về True chính xác."""
    assert parse_pnputil_device_status(PNPUTIL_MULTI_DEVICE_OTHER_DISCONNECTED_D780_STARTED) is True


def test_parse_pnputil_clone_rejected():
    """Từ chối thiết bị clone có chữ D780 nhưng không phải Nikon và sai VID/PID."""
    assert parse_pnputil_device_status(PNPUTIL_CLONE_NON_NIKON) is False


def test_parse_pnputil_empty_none_and_garbage():
    """Xử lý an toàn các dữ liệu rỗng, None hoặc chuỗi không hợp lệ."""
    assert parse_pnputil_device_status("") is False
    assert parse_pnputil_device_status(None) is False
    assert parse_pnputil_device_status("Some random log line without any device") is False


# ==============================================================================
# TESTS FOR check_nikon_d780_pnp (PNPUTIL + POWERSHELL FALLBACK)
# ==============================================================================

def test_check_nikon_d780_pnp_pnputil_success_no_fallback():
    """Khi pnputil thành công và trả về Nikon D780, không kích hoạt PowerShell fallback."""
    with patch("subprocess.check_output", return_value=REAL_WINDOWS_PNPUTIL_D780_STARTED) as mock_pnp, \
         patch("subprocess.run") as mock_ps:
        res = check_nikon_d780_pnp()
        assert res is True
        mock_pnp.assert_called_once()
        mock_ps.assert_not_called()


def test_check_nikon_d780_pnp_fallback_on_subprocess_error():
    """Khi pnputil ném ngoại lệ SubprocessError, PowerShell fallback được gọi."""
    fake_ps_proc = MagicMock()
    fake_ps_proc.returncode = 0
    fake_ps_proc.stdout = "USB\\VID_04B0&PID_0446\\0000002008880\r\n"

    with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "pnputil")), \
         patch("subprocess.run", return_value=fake_ps_proc) as mock_ps:
        res = check_nikon_d780_pnp()
        assert res is True
        mock_ps.assert_called_once()


def test_check_nikon_d780_pnp_fallback_on_timeout():
    """Khi pnputil bị timeout, PowerShell fallback được gọi."""
    fake_ps_proc = MagicMock()
    fake_ps_proc.returncode = 0
    fake_ps_proc.stdout = "USB\\VID_04B0&PID_0446\\0000002008880\r\n"

    with patch("subprocess.check_output", side_effect=subprocess.TimeoutExpired("pnputil", 0.8)), \
         patch("subprocess.run", return_value=fake_ps_proc) as mock_ps:
        res = check_nikon_d780_pnp()
        assert res is True
        mock_ps.assert_called_once()


def test_check_nikon_d780_pnp_both_fail_returns_false():
    """Khi cả pnputil và PowerShell đều lỗi, trả về False an toàn."""
    with patch("subprocess.check_output", side_effect=FileNotFoundError), \
         patch("subprocess.run", side_effect=FileNotFoundError):
        res = check_nikon_d780_pnp()
        assert res is False


# ==============================================================================
# TESTS FOR discover_devices() ENUMERATION GATING
# ==============================================================================

def test_discover_devices_invokes_session_enumeration_when_pnp_found():
    """
    Xác minh khi PnP phát hiện Nikon D780:
    1. discover_devices() gọi self._session.enumerate_cameras().
    2. Cập nhật _last_discovered_sources với Source ID trả về từ MAID SDK.
    3. Trả về CameraDeviceInfo tương ứng.
    """
    backend = NikonD780Backend()

    with patch("vietphotobooth.camera.backends.nikon_maid.nikon_d780_backend.check_nikon_d780_pnp", return_value=True), \
         patch.object(backend._session, "enumerate_cameras", return_value=[1]) as mock_enum:

        devices = backend.discover_devices()
        mock_enum.assert_called_once_with(timeout_sec=0.5)
        assert backend._last_discovered_sources == [1]
        assert len(devices) == 1
        dev = devices[0]
        assert dev.id == "nikon_d780_usb"
        assert dev.name == "Nikon D780 (Native USB)"
        assert dev.path == "USB\\VID_04B0&PID_0446"
        assert dev.is_virtual is False


def test_discover_devices_skips_session_enumeration_when_pnp_not_found():
    """Khi PnP không phát hiện thiết bị và module chưa mở, bỏ qua enumerate_cameras để tránh blocking."""
    backend = NikonD780Backend()

    with patch("vietphotobooth.camera.backends.nikon_maid.nikon_d780_backend.check_nikon_d780_pnp", return_value=False), \
         patch.object(backend._session, "enumerate_cameras") as mock_enum:

        devices = backend.discover_devices()
        mock_enum.assert_not_called()
        assert devices == []
        assert backend._last_discovered_sources == []
