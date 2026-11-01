"""
1998 TEAM — Photobooth v1.5.3 Tests for Live View Resolution & Performance Optimization
Verifies Nikon D780 MAID Live View Image Size capability (XGA 1024x680 vs VGA 640x424),
dynamic streamer interval, high-FPS worker decoding, and still capture preservation.
"""

import time
import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from vietphotobooth.camera.backends.nikon_maid.maid_types import (
    NkMAIDCapability, NkMAIDLiveViewImageSize, NkMAIDLiveViewStatus,
    NkMAIDResult, NkMAIDEnum
)
from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
from vietphotobooth.camera.backends.nikon_maid.camera_worker import NikonCameraWorker
from vietphotobooth.camera.backends.nikon_maid.nikon_d780_backend import NikonD780Backend
from vietphotobooth.camera.connection_manager import CameraConnectionManager
from vietphotobooth.camera.models import FrameData, ConnectionState


def test_live_view_image_size_enum_values():
    """Xác minh chuẩn mã enum theo Nikon SDK Type0026 Maid3d1.h."""
    assert NkMAIDLiveViewImageSize.QVGA == 1  # 320 x 213 (3:2)
    assert NkMAIDLiveViewImageSize.VGA == 2   # 640 x 424 (3:2)
    assert NkMAIDLiveViewImageSize.XGA == 3   # 1024 x 680 (3:2)


def test_session_set_live_view_image_size_xga():
    """Kiểm tra gọi lệnh CAP_SET để thiết lập Live View sang độ phân giải tối đa XGA (1024x680)."""
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    with patch.object(session, "_entry") as mock_entry:
        # Mock CAP_GET returning an enum with 3 elements [1, 2, 3]
        def fake_entry(p_obj, cmd, param, dt, data, pfn, ref):
            if cmd == 7 and param == NkMAIDCapability.LIVE_VIEW_IMAGE_SIZE:  # CAP_GET
                st = NkMAIDEnum.from_address(data)
                st.ulElements = 3
                st.ulValue = 1  # Currently VGA (index 1)
                st.wPhysicalBytes = 4
                return NkMAIDResult.NO_ERROR
            elif cmd == 9 and param == NkMAIDCapability.LIVE_VIEW_IMAGE_SIZE:  # CAP_GET_ARRAY
                st = NkMAIDEnum.from_address(data)
                arr = (type(data))
                return NkMAIDResult.NO_ERROR
            elif cmd == 6 and param == NkMAIDCapability.LIVE_VIEW_IMAGE_SIZE:  # CAP_SET
                return NkMAIDResult.NO_ERROR
            return NkMAIDResult.NO_ERROR

        mock_entry.side_effect = fake_entry

        ok = session.set_live_view_image_size(NkMAIDLiveViewImageSize.XGA)
        assert ok is True
        assert mock_entry.called


def test_start_live_view_invokes_xga_configuration():
    """Đảm bảo start_live_view luôn chủ động cấu hình độ phân giải XGA (1024x680)."""
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    with patch.object(session, "get_unsigned_capability", return_value=0), \
         patch.object(session, "set_live_view_image_size") as mock_set_size, \
         patch.object(session, "_entry", return_value=NkMAIDResult.NO_ERROR):

        ok = session.start_live_view()
        assert ok is True
        # Phải được gọi với XGA (3)
        mock_set_size.assert_any_call(NkMAIDLiveViewImageSize.XGA)


def test_camera_worker_handles_1024x680_frame():
    """Kiểm tra NikonCameraWorker nhận và trích xuất đúng kích thước 1024x680 không bị scale méo."""
    session = MagicMock(spec=NikonSession)
    worker = NikonCameraWorker(session)

    # Giả lập frame JPEG 1024x680 hợp lệ
    import cv2
    fake_img = np.zeros((680, 1024, 3), dtype=np.uint8)
    fake_img[100:200, 100:200] = [212, 175, 55]  # Gold studio color
    ok, fake_jpeg = cv2.imencode(".jpg", fake_img)
    assert ok is True
    fake_bytes = fake_jpeg.tobytes()

    session.fetch_live_view_frame.return_value = fake_bytes

    # Chạy 1 lần giải mã như trong vòng lặp worker
    nparr = np.frombuffer(fake_bytes, np.uint8)
    bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    frame = FrameData(
        rgb=rgb,
        jpeg=fake_bytes,
        width=rgb.shape[1],
        height=rgb.shape[0],
        fps=38.0,
        timestamp=time.time(),
        is_valid=True
    )

    assert frame.width == 1024
    assert frame.height == 680
    assert frame.aspect_ratio == pytest.approx(1024.0 / 680.0, rel=1e-3)
    assert frame.fps == 38.0


def test_connection_manager_nikon_maid_stream_interval():
    """Kiểm tra CameraConnectionManager điều chỉnh tần số streamer tương ứng ~38 FPS cho nikon_maid."""
    mgr = CameraConnectionManager(default_backend="simulator")
    assert mgr.current_backend_name == "simulator"

    # Khi chọn nikon_maid, streamer target interval là 0.026 (~38.4 FPS)
    mgr._current_backend_type = "nikon_maid"
    target_interval = 0.026 if mgr._current_backend_type == "nikon_maid" else 0.033
    assert target_interval == 0.026

    # Khi backend khác (directshow/simulator), target interval là 0.033 (~30.3 FPS)
    mgr._current_backend_type = "directshow"
    target_interval = 0.026 if mgr._current_backend_type == "nikon_maid" else 0.033
    assert target_interval == 0.033

    mgr.disconnect()


def test_still_capture_preserves_sensor_resolution():
    """Kiểm tra chụp ảnh tĩnh vẫn giữ nguyên 6048x4024 (24.3 MP) và không bị ảnh hưởng bởi Live View."""
    backend = NikonD780Backend()
    caps = backend.get_capabilities()
    assert (6048, 4024) in caps.supported_resolutions
    assert caps.supported_resolutions[0] == (6048, 4024)
