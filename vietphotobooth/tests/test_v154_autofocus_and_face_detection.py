"""
1998 TEAM — Photobooth v1.5.4 Tests for Nikon D780 Autofocus and Face/Eye Detection
Verifies MAID3 Autofocus triggering, completion handling (success, out-of-focus, MF mode, busy),
cancellation, YuNet AI Face/Eye detection service, live viewport overlays, and capture integration.
"""

import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from vietphotobooth.camera.backends.nikon_maid.maid_types import (
    NkMAIDCapability, NkMAIDResult, NkMAIDCommand, NkMAIDDataType,
    NkMAIDContrastAF, NkMAIDPoint
)
from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
from vietphotobooth.camera.backends.nikon_maid.camera_worker import NikonCameraWorker
from vietphotobooth.camera.backends.nikon_maid.nikon_d780_backend import NikonD780Backend
from vietphotobooth.camera.backends.simulator import SimulatorBackend
from vietphotobooth.camera.connection_manager import CameraConnectionManager
from vietphotobooth.camera.models import FrameData, CameraCapabilities, ConnectionState
from vietphotobooth.camera.face_detector import DetectedFace, FaceEyeDetector, FaceDetectionService
from vietphotobooth.desktop.widgets.live_viewport import CameraLiveViewport


# ============================================================================
# 1. AUTOFOCUS CONSTANTS & MAID CAPABILITY MAPPING
# ============================================================================

def test_autofocus_capability_constants():
    """Xác minh các mã capability và mã kết quả Autofocus theo Nikon SDK Maid3.h / Maid3d1.h."""
    assert NkMAIDCapability.AUTOFOCUS == 29
    assert NkMAIDCapability.CONTRAST_AF == 0x8240
    assert NkMAIDCapability.CONTRAST_AF_AREA == 0x824A
    assert NkMAIDCapability.LIVE_VIEW_AF == 0x8275
    assert NkMAIDCapability.AF_CAPTURE_LV == 0x849A
    assert NkMAIDCapability.LOCK_FOCUS == 0x8105
    assert NkMAIDCapability.FOCUS_MODE == 0x8120
    assert NkMAIDCapability.AF_MODE == 0x81C3
    assert NkMAIDContrastAF.START == 0x00
    assert NkMAIDContrastAF.STOP == 0x01
    assert NkMAIDContrastAF.OK == 0x10
    assert NkMAIDContrastAF.OUT_OF_FOCUS == 0x11
    assert NkMAIDContrastAF.BUSY == 0x12
    assert NkMAIDResult.OUT_OF_FOCUS == 137
    assert NkMAIDResult.DEVICE_BUSY == 152
    assert NkMAIDResult.NOT_SUPPORTED == -127


# ============================================================================
# 2. MAID SESSION AUTOFOCUS EXECUTION & ERROR HANDLING
# ============================================================================

def test_maid_session_trigger_autofocus_success():
    """Kiểm tra gọi trigger_autofocus thành công (NkMAIDResult_NoError = 0)."""
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    def fake_entry(p_obj, cmd, param, dt, data, pfn, ref):
        if cmd == NkMAIDCommand.CAP_START and param == NkMAIDCapability.AUTOFOCUS:
            if pfn:
                pfn(None, cmd, param, dt, data, ref, NkMAIDResult.NO_ERROR)
            return NkMAIDResult.NO_ERROR
        return NkMAIDResult.NO_ERROR

    with patch.object(session, "_entry", side_effect=fake_entry):
        success, message = session.trigger_autofocus(timeout_sec=1.0)
        assert success is True
        assert "thành công" in message.lower() or "khóa nét" in message.lower()


def test_maid_session_trigger_autofocus_out_of_focus():
    """Kiểm tra phản hồi khi camera không tìm được điểm nét (mã 137)."""
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    def fake_entry(p_obj, cmd, param, dt, data, pfn, ref):
        if cmd == NkMAIDCommand.CAP_START and param == NkMAIDCapability.AUTOFOCUS:
            if pfn:
                pfn(None, cmd, param, dt, data, ref, NkMAIDResult.OUT_OF_FOCUS)
            return NkMAIDResult.NO_ERROR
        return NkMAIDResult.NO_ERROR

    with patch.object(session, "_entry", side_effect=fake_entry):
        success, message = session.trigger_autofocus(timeout_sec=1.0)
        assert success is False
        assert "không thể lấy nét" in message.lower() or "out of focus" in message.lower()


def test_maid_session_trigger_autofocus_lens_mf_switch():
    """Kiểm tra phản hồi khi công tắc ống kính đang ở Manual Focus (-127 NOT_SUPPORTED)."""
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    with patch.object(session, "_entry", return_value=NkMAIDResult.NOT_SUPPORTED):
        success, message = session.trigger_autofocus(timeout_sec=1.0)
        assert success is False
        assert "manual focus" in message.lower() or "mf" in message.lower() or "không hỗ trợ" in message.lower()


def test_maid_session_trigger_autofocus_device_busy():
    """Kiểm tra phản hồi khi máy ảnh đang bận (152 DEVICE_BUSY)."""
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    with patch.object(session, "_entry", return_value=NkMAIDResult.DEVICE_BUSY):
        success, message = session.trigger_autofocus(timeout_sec=1.0)
        assert success is False
        assert "bận" in message.lower() or "busy" in message.lower()


def test_maid_session_cancel_autofocus():
    """Kiểm tra gọi cancel_autofocus gửi lệnh ABORT tới capability AUTOFOCUS."""
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    with patch.object(session, "_entry", return_value=NkMAIDResult.NO_ERROR) as mock_entry:
        ok = session.cancel_autofocus()
        assert ok is True
        mock_entry.assert_called_with(
            session._src_obj,
            NkMAIDCommand.ABORT,
            0,
            NkMAIDDataType.NULL,
            0,
            None,
            0
        )


def test_maid_session_trigger_autofocus_liveview_success():
    """Kiểm tra gọi trigger_autofocus trong Live View sử dụng Contrast AF (0x8240) thành công."""
    session = NikonSession()
    session._is_src_open = True
    session._is_live_view_active = True
    session._src_obj = MagicMock()

    polls = [NkMAIDContrastAF.BUSY, NkMAIDContrastAF.OK]

    def fake_get_unsigned(cap_id):
        if cap_id == NkMAIDCapability.CONTRAST_AF:
            if polls:
                return polls.pop(0)
            return NkMAIDContrastAF.OK
        return None

    with patch.object(session, "_entry", return_value=NkMAIDResult.NO_ERROR) as mock_entry, \
         patch.object(session, "get_unsigned_capability", side_effect=fake_get_unsigned):
        success, message = session.trigger_autofocus(timeout_sec=1.0)
        assert success is True
        assert "thành công" in message.lower() or "in focus" in message.lower()
        mock_entry.assert_any_call(
            session._src_obj,
            NkMAIDCommand.CAP_SET,
            NkMAIDCapability.CONTRAST_AF,
            NkMAIDDataType.UNSIGNED,
            NkMAIDContrastAF.START,
            None,
            0
        )


def test_maid_session_trigger_autofocus_liveview_with_target_point():
    """Kiểm tra Contrast AF trong Live View kèm tọa độ mục tiêu gọi set_contrast_af_area (0x824A)."""
    session = NikonSession()
    session._is_src_open = True
    session._is_live_view_active = True
    session._src_obj = MagicMock()

    with patch.object(session, "set_contrast_af_area", return_value=True) as mock_set_area, \
         patch.object(session, "_entry", return_value=NkMAIDResult.NO_ERROR), \
         patch.object(session, "get_unsigned_capability", return_value=NkMAIDContrastAF.OK):
        success, message = session.trigger_autofocus(target_point=(512, 340), timeout_sec=1.0)
        assert success is True
        mock_set_area.assert_called_once_with(512, 340)


def test_maid_session_cancel_autofocus_liveview():
    """Kiểm tra cancel_autofocus trong Live View gửi STOP tới CONTRAST_AF (0x8240)."""
    session = NikonSession()
    session._is_src_open = True
    session._is_live_view_active = True
    session._src_obj = MagicMock()

    with patch.object(session, "set_unsigned_capability", return_value=True) as mock_set:
        ok = session.cancel_autofocus()
        assert ok is True
        mock_set.assert_called_once_with(NkMAIDCapability.CONTRAST_AF, NkMAIDContrastAF.STOP)


# ============================================================================
# 3. CAMERA WORKER THREAD-SAFE AUTOFOCUS
# ============================================================================

def test_camera_worker_request_autofocus():
    """Kiểm tra NikonCameraWorker nhận lệnh AF bất đồng bộ, chạy trên worker thread và gọi callback."""
    session = MagicMock(spec=NikonSession)
    session.trigger_autofocus.return_value = (True, "Lấy nét thành công")

    worker = NikonCameraWorker(session)
    results = []

    def af_cb(success, msg):
        results.append((success, msg))

    # Kích hoạt AF bất đồng bộ
    worker.request_autofocus(af_cb)

    # Chờ thread nền hoàn tất
    for _ in range(50):
        if results:
            break
        time.sleep(0.02)

    assert len(results) == 1
    assert results[0][0] is True
    assert "thành công" in results[0][1].lower()


def test_camera_worker_capture_with_autofocus_first():
    """Kiểm tra lệnh capture với autofocus_first=True chuyển tiếp tham số cho session."""
    session = MagicMock(spec=NikonSession)
    import cv2
    fake_img = np.zeros((100, 100, 3), dtype=np.uint8)
    ok, fake_jpeg = cv2.imencode(".jpg", fake_img)
    fake_bytes = fake_jpeg.tobytes()

    session.capture_photo.return_value = fake_bytes

    worker = NikonCameraWorker(session)
    img = worker.capture(autofocus_first=True)
    assert img is not None
    session.capture_photo.assert_called_once_with(timeout_sec=12.0, autofocus_first=True)


# ============================================================================
# 4. CAPABILITIES AND BACKEND INTERFACE
# ============================================================================

def test_camera_capabilities_autofocus_flag():
    """Kiểm tra trường can_autofocus trong CameraCapabilities và to_dict()."""
    caps_true = CameraCapabilities(can_autofocus=True)
    assert caps_true.can_autofocus is True
    assert caps_true.to_dict()["can_autofocus"] is True

    caps_false = CameraCapabilities(can_autofocus=False)
    assert caps_false.can_autofocus is False
    assert caps_false.to_dict()["can_autofocus"] is False


def test_nikon_backend_capabilities_and_methods():
    """Kiểm tra NikonD780Backend công bố can_autofocus=True và các phương thức AF."""
    backend = NikonD780Backend()
    caps = backend.get_capabilities()
    assert caps.can_autofocus is True

    # Test kết nối chưa mở thì autofocus callback trả về False an toàn
    results = []
    backend.autofocus(lambda ok, msg: results.append((ok, msg)))
    assert len(results) == 1
    assert results[0][0] is False


def test_simulator_backend_autofocus():
    """Kiểm tra SimulatorBackend hỗ trợ mô phỏng autofocus có nhãn mô phỏng."""
    sim = SimulatorBackend()
    caps = sim.get_capabilities()
    assert caps.can_autofocus is True

    results = []
    sim.autofocus(lambda ok, msg: results.append((ok, msg)))
    assert len(results) == 1
    assert results[0][0] is True
    assert "mô phỏng" in results[0][1].lower()


def test_connection_manager_autofocus_delegation():
    """Kiểm tra CameraConnectionManager chuyển tiếp lệnh AF tới backend."""
    cm = CameraConnectionManager()
    mock_backend = MagicMock()
    mock_backend.get_status.return_value = ConnectionState.CONNECTED
    cm._backend = mock_backend

    cb = MagicMock()
    cm.trigger_autofocus(cb)
    assert mock_backend.autofocus.called

    cm.cancel_autofocus()
    mock_backend.cancel_autofocus.assert_called_once()


# ============================================================================
# 5. YUNET FACE & EYE DETECTOR AND AI SERVICE
# ============================================================================

def test_detected_face_dataclass():
    """Kiểm tra cấu trúc dữ liệu DetectedFace tính toán bbox và vị trí mắt."""
    face = DetectedFace(
        x=100.0,
        y=150.0,
        w=200.0,
        h=250.0,
        confidence=0.95,
        right_eye=(150.0, 220.0),
        left_eye=(230.0, 220.0)
    )
    assert face.bbox == (100.0, 150.0, 200.0, 250.0)
    assert face.confidence == 0.95
    assert face.right_eye == (150.0, 220.0)
    assert face.left_eye == (230.0, 220.0)


def test_face_eye_detector_synthetic_frame():
    """Kiểm tra khởi tạo detector và chạy inference trên ảnh nhân tạo (không crash, trả về list)."""
    detector = FaceEyeDetector()
    synthetic_frame = np.zeros((680, 1024, 3), dtype=np.uint8)

    # Ảnh đen hoàn toàn -> không có khuôn mặt nào, trả về danh sách rỗng
    faces = detector.detect_faces(synthetic_frame)
    assert isinstance(faces, list)
    assert len(faces) == 0


def test_face_detection_service_background_queue():
    """Kiểm tra FaceDetectionService nhận frame, chạy nền và gọi callback mà không block caller."""
    service = FaceDetectionService(target_detection_fps=12.0)
    service.start()

    received_faces = []

    def callback(faces):
        received_faces.append(faces)

    service.register_callback(callback)

    # Gửi nhiều frame nhanh
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for _ in range(5):
        service.submit_frame(fake_frame)

    # Đợi service xử lý
    time.sleep(0.3)
    service.stop()

    assert len(received_faces) >= 1
    assert isinstance(received_faces[0], list)

    # Kiểm tra unregister
    service.unregister_callback(callback)
    assert callback not in service._callbacks


# ============================================================================
# 6. LIVE VIEWPORT FACE & EYE OVERLAY RENDERING
# ============================================================================

def test_live_viewport_face_detection_toggle(qapp):
    """Kiểm tra bật/tắt nhận diện khuôn mặt và nạp danh sách khuôn mặt trong viewport."""
    viewport = CameraLiveViewport()
    viewport.set_face_detection_enabled(True)
    assert viewport._face_detection_enabled is True

    dummy_face = DetectedFace(
        x=50.0,
        y=50.0,
        w=100.0,
        h=100.0,
        confidence=0.92,
        right_eye=(75.0, 80.0),
        left_eye=(125.0, 80.0)
    )
    viewport.set_detected_faces([dummy_face])
    assert len(viewport._detected_faces) == 1

    # Đổi sang tắt -> xóa khuôn mặt và cờ
    viewport.set_face_detection_enabled(False)
    assert viewport._face_detection_enabled is False
    assert len(viewport._detected_faces) == 0


# ============================================================================
# 7. COORDINATE CONVERSION & TARGET POSITIONING VERIFICATION
# ============================================================================

def test_contrast_af_area_coordinate_conversion_center_left_right():
    """Kiểm tra đặt tọa độ Contrast AF Area tại Center (512, 340), Left (200, 340), Right (824, 340)."""
    import ctypes
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    captured_points = []

    def fake_entry(p_obj, cmd, cap_id, dt, data, pfn, ref):
        if cmd == NkMAIDCommand.CAP_SET and cap_id == NkMAIDCapability.CONTRAST_AF_AREA:
            pt = ctypes.cast(data, ctypes.POINTER(NkMAIDPoint)).contents
            captured_points.append((pt.x, pt.y))
            return NkMAIDResult.NO_ERROR
        return NkMAIDResult.NO_ERROR

    with patch.object(session, "_entry", side_effect=fake_entry):
        # 1. Center: (512, 340)
        assert session.set_contrast_af_area(512, 340) is True
        assert captured_points[-1] == (512, 340)

        # 2. Left: (200, 340)
        assert session.set_contrast_af_area(200, 340) is True
        assert captured_points[-1] == (200, 340)

        # 3. Right: (824, 340)
        assert session.set_contrast_af_area(824, 340) is True
        assert captured_points[-1] == (824, 340)


def test_contrast_af_area_coordinate_conversion_scaled_resolutions():
    """Kiểm tra chuyển đổi tọa độ từ các độ phân giải khác và tọa độ chuẩn hóa sang chuẩn XGA 1024x680."""
    import ctypes
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    captured_points = []

    def fake_entry(p_obj, cmd, cap_id, dt, data, pfn, ref):
        if cmd == NkMAIDCommand.CAP_SET and cap_id == NkMAIDCapability.CONTRAST_AF_AREA:
            pt = ctypes.cast(data, ctypes.POINTER(NkMAIDPoint)).contents
            captured_points.append((pt.x, pt.y))
            return NkMAIDResult.NO_ERROR
        return NkMAIDResult.NO_ERROR

    with patch.object(session, "_entry", side_effect=fake_entry):
        # Frame 640x480: tâm (320, 240) -> XGA (512, 340)
        assert session.set_contrast_af_area(320, 240, src_width=640, src_height=480) is True
        assert captured_points[-1] == (512, 340)

        # Frame 1920x1080: điểm 1/4 (480, 270) -> XGA (256, 170)
        assert session.set_contrast_af_area(480, 270, src_width=1920, src_height=1080) is True
        assert captured_points[-1] == (256, 170)

        # Tọa độ chuẩn hóa [0.0 .. 1.0]: tâm (0.5, 0.5) -> XGA (512, 340)
        assert session.set_contrast_af_area(0.5, 0.5) is True
        assert captured_points[-1] == (512, 340)


def test_contrast_af_area_coordinate_clamping():
    """Kiểm tra kẹp giới hạn an toàn [0 .. 1023] và [0 .. 679] cho điểm AF."""
    import ctypes
    session = NikonSession()
    session._is_src_open = True
    session._src_obj = MagicMock()

    captured_points = []

    def fake_entry(p_obj, cmd, cap_id, dt, data, pfn, ref):
        if cmd == NkMAIDCommand.CAP_SET and cap_id == NkMAIDCapability.CONTRAST_AF_AREA:
            pt = ctypes.cast(data, ctypes.POINTER(NkMAIDPoint)).contents
            captured_points.append((pt.x, pt.y))
            return NkMAIDResult.NO_ERROR
        return NkMAIDResult.NO_ERROR

    with patch.object(session, "_entry", side_effect=fake_entry):
        # Tọa độ âm -> kẹp về (0, 0)
        assert session.set_contrast_af_area(-150, -50) is True
        assert captured_points[-1] == (0, 0)

        # Tọa độ vượt biên phải/dưới -> kẹp về (1023, 679)
        assert session.set_contrast_af_area(2000, 1200) is True
        assert captured_points[-1] == (1023, 679)


def test_face_eye_af_controller_frame_size_forwarding():
    """Kiểm tra FaceEyeAFController lưu kích thước khung hình và chuyển tiếp frame_size khi kích hoạt AF."""
    from vietphotobooth.camera.face_eye_af_controller import FaceEyeAFController, FaceEyeAFState

    captured_kwargs = []

    def fake_af_trigger(callback=None, target_point=None, frame_size=None):
        captured_kwargs.append({"target_point": target_point, "frame_size": frame_size})
        if callback:
            callback(True, "In Focus")

    controller = FaceEyeAFController(
        af_trigger_fn=fake_af_trigger,
        stability_frames=2,
        cooldown_sec=0.1
    )
    controller.enable()

    face = DetectedFace(
        x=200.0, y=150.0, w=160.0, h=200.0, confidence=0.95,
        right_eye=(240.0, 200.0), left_eye=(310.0, 200.0)
    )

    # Gửi 2 frame kèm frame_shape=(640, 480) [width, height]
    controller.process_faces([face], frame_shape=(640, 480), sequence_id=1)
    controller.process_faces([face], frame_shape=(640, 480), sequence_id=2)

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["target_point"] == (240.0, 200.0)
    # Controller truyền (width, height) = (640, 480)
    assert captured_kwargs[0]["frame_size"] == (640, 480)

