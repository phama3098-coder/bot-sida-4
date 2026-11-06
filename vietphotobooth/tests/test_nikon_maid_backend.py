"""
1998 TEAM — Photobooth Unit Tests for Nikon MAID3 Backend
Tests struct layouts, loader discovery, backend contract and state machine.
"""

import ctypes
import pytest
from unittest.mock import MagicMock, patch

from vietphotobooth.camera.backends.nikon_maid.maid_types import (
    NkMAIDObject, NkMAIDCapInfo, NkMAIDArray, NkMAIDEnum, NkMAIDRange,
    NkMAIDFileInfo, NkMAIDObjectType, NkMAIDCommand, NkMAIDCapability,
    NkMAIDLiveViewStatus
)
from vietphotobooth.camera.backends.nikon_maid.maid_loader import NikonSDKLoader
from vietphotobooth.camera.backends.nikon_maid.nikon_d780_backend import NikonD780Backend
from vietphotobooth.camera.models import ConnectionState


def test_maid_struct_packing_and_sizes():
    """Kiểm tra kích thước chuẩn của các struct MAID3 với pack=2 trên kiến trúc 64-bit."""
    assert ctypes.sizeof(ctypes.c_void_p) == 8, "Yêu cầu môi trường 64-bit."

    # NkMAIDObject: 4 (ulType) + 4 (ulID) + 8 (refClient) + 8 (refModule) = 24
    assert ctypes.sizeof(NkMAIDObject) == 24

    # NkMAIDCapInfo: 4 + 4 + 4 + 4 + 256 = 272
    assert ctypes.sizeof(NkMAIDCapInfo) == 272

    # NkMAIDArray: 4 + 4 + 4 + 4 + 4 + 2 + 2 + 8 = 32
    assert ctypes.sizeof(NkMAIDArray) == 32

    # NkMAIDEnum: 4 + 4 + 4 + 4 + 2 + 8 (với pack=2, pData nằm tại offset 18) = 26
    assert ctypes.sizeof(NkMAIDEnum) == 26

    # NkMAIDFileInfo: 4 + 4 + 4 + 4 + 4 + 4 + 4 = 28
    assert ctypes.sizeof(NkMAIDFileInfo) == 28


def test_nikon_sdk_loader_discovery():
    """Kiểm tra cơ chế dò tìm thư mục DLL của NikonSDKLoader."""
    loader = NikonSDKLoader()
    candidates = loader.get_candidate_directories()
    assert len(candidates) > 0, "Phải có ít nhất 1 đường dẫn ứng viên cho Nikon SDK."

    sdk_dir = loader.find_sdk_directory()
    assert sdk_dir is not None, "Phải tìm thấy thư mục Nikon SDK (tích hợp trong bin/x64)."


def test_nikon_d780_backend_contract():
    """Kiểm tra tuân thủ giao diện chuẩn CameraBackendBase của NikonD780Backend."""
    backend = NikonD780Backend()
    assert backend.backend_type == "nikon_maid"
    assert "Nikon D780" in backend.display_name
    assert backend.get_status() == ConnectionState.DISCONNECTED
    assert backend.get_error() is None

    caps = backend.get_capabilities()
    assert caps.can_capture is True
    assert caps.can_liveview is True
    assert caps.can_download is True
    assert (6048, 4024) in caps.supported_resolutions


def test_nikon_d780_backend_mocked_lifecycle():
    """Kiểm tra toàn bộ vòng đời trạng thái của backend khi kết nối, live view và ngắt kết nối."""
    backend = NikonD780Backend()

    with patch.object(backend._session, "open_camera", return_value=(True, "OK")), \
         patch.object(backend._session, "close_camera") as mock_close_cam, \
         patch.object(backend._session, "close_module") as mock_close_mod, \
         patch.object(backend._session, "get_string_capability", return_value="Nikon D780"):

        # 1. Connect
        connected = backend.connect("nikon_d780_usb")
        assert connected is True
        assert backend.get_status() == ConnectionState.CONNECTED

        # 2. Live View
        with patch.object(backend._session, "start_live_view", return_value=True), \
             patch.object(backend._session, "stop_live_view") as mock_stop_lv:

            lv_started = backend.start_live_view()
            assert lv_started is True
            assert backend.get_status() == ConnectionState.LIVE_VIEW_ACTIVE

            backend.stop_live_view()
            assert backend.get_status() == ConnectionState.CONNECTED
            mock_stop_lv.assert_called()

        # 3. Disconnect
        backend.disconnect()
        assert backend.get_status() == ConnectionState.DISCONNECTED
        mock_close_cam.assert_called()
        mock_close_mod.assert_called()


def test_maid_result_success_and_capture_callback():
    """Kiểm tra NkMAIDResult.SUCCESS == NkMAIDResult.NO_ERROR == 0 và callback on_capture_start."""
    from vietphotobooth.camera.backends.nikon_maid.maid_types import NkMAIDResult
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession

    assert NkMAIDResult.NO_ERROR == 0
    assert NkMAIDResult.SUCCESS == 0
    assert NkMAIDResult.WAITING_2ND_RELEASE == 168

    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    callback_called = [False]
    def on_start():
        callback_called[0] = True

    # Giả lập lệnh CAP_START trả về NO_ERROR (0)
    with patch.object(session, "_entry", return_value=NkMAIDResult.NO_ERROR), \
         patch.object(session, "set_unsigned_capability", return_value=True), \
         patch.object(session, "pump_async"):
        # Timeout 0.05s để kết thúc nhanh vì new_items rỗng
        res = session.capture_photo(timeout_sec=0.05, on_capture_start=on_start)
        assert callback_called[0] is True
        assert res is None  # Do giả lập không có item mới trong SDRAM
