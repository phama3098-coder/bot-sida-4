"""
1998 TEAM — Photobooth Face/Eye AF Pre-Capture Integration Tests
Kiểm thử tích hợp lấy nét tự động nhận diện khuôn mặt và mắt vào quy trình chụp ảnh (Kiosk Page):
1. Ưu tiên mắt được nhận diện (eye target point).
2. Fallback tâm khuôn mặt khi không có mắt (face center).
3. Fallback an toàn khi không có khuôn mặt (no-face fallback).
4. Watchdog timeout & fallback an toàn khi AF bị treo/quá thời gian.
5. Fallback an toàn khi AF báo lỗi (out of focus, MF mode).
6. Đảm bảo giao diện chụp không hiển thị bất kỳ overlay nhận diện nào (Zero UI overlay).
7. Kiểm thử các trường hợp biên của thuật toán select_af_target.
"""

import time
import os
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication

from vietphotobooth.desktop.main_window import MainWindow
from vietphotobooth.desktop.widgets.kiosk_page import KioskPage
from vietphotobooth.camera.face_detector import DetectedFace
from vietphotobooth.camera.face_eye_af_controller import select_af_target


@pytest.fixture
def kiosk_page(qapp):
    window = MainWindow(start_in_kiosk=False)
    window.resize(1280, 800)
    window.show()
    page = window.kiosk_page
    qapp.processEvents()
    yield page
    if hasattr(page, "_face_service"):
        page._face_service.stop()
    if hasattr(page, "_af_watchdog_timer"):
        page._af_watchdog_timer.stop()
    page.cleanup()
    window.close()
    qapp.processEvents()


def test_select_af_target_algorithm():
    """Kiểm tra thuật toán select_af_target độc lập."""
    # 1. Danh sách rỗng
    target, ttype, face = select_af_target([])
    assert target is None
    assert ttype == "none"
    assert face is None

    # 2. Khuôn mặt có mắt hợp lệ -> Ưu tiên mắt
    f1 = DetectedFace(
        x=200.0, y=150.0, w=160.0, h=180.0,
        confidence=0.95,
        right_eye=(240.0, 210.0),
        left_eye=(310.0, 210.0)
    )
    target, ttype, face = select_af_target([f1], frame_shape=(680, 1024))
    assert target == (240.0, 210.0)
    assert ttype == "eye"
    assert face is f1

    # 3. Khuôn mặt không có tọa độ mắt -> Fallback tâm khuôn mặt (vùng mắt/mũi)
    f2 = DetectedFace(
        x=200.0, y=150.0, w=160.0, h=180.0,
        confidence=0.92,
        right_eye=None,
        left_eye=None
    )
    target, ttype, face = select_af_target([f2], frame_shape=(680, 1024))
    assert ttype == "face"
    assert target == (280.0, 150.0 + 180.0 * 0.4)
    assert face is f2

    # 4. Khuôn mặt có mắt nằm ngoài bounding box (tọa độ rác) -> Fallback tâm khuôn mặt
    f3 = DetectedFace(
        x=200.0, y=150.0, w=160.0, h=180.0,
        confidence=0.88,
        right_eye=(999.0, 999.0),
        left_eye=(-10.0, -10.0)
    )
    target, ttype, face = select_af_target([f3], frame_shape=(680, 1024))
    assert ttype == "face"
    assert target == (280.0, 150.0 + 180.0 * 0.4)

    # 5. Nhiều khuôn mặt -> Chọn khuôn mặt chính lớn nhất & gần tâm nhất
    f_small = DetectedFace(x=20.0, y=20.0, w=60.0, h=60.0, confidence=0.8)
    f_center_large = DetectedFace(x=450.0, y=250.0, w=200.0, h=200.0, confidence=0.95, right_eye=(500.0, 320.0))
    target, ttype, face = select_af_target([f_small, f_center_large], frame_shape=(680, 1024))
    assert face is f_center_large
    assert ttype == "eye"
    assert target == (500.0, 320.0)


def test_kiosk_zero_ui_overlay_during_face_tracking(kiosk_page, qapp):
    """
    Yêu cầu 5: Không hiển thị bất kỳ dấu hiệu nhận diện nào trên giao diện chụp
    (không bounding box, không reticle, không khung đánh dấu, không tọa độ).
    """
    vp = kiosk_page.lbl_viewport
    # Viewport overlay flags phải luôn là False trên trang Kiosk
    assert vp._face_detection_enabled is False
    assert vp._face_eye_af_enabled is False
    assert len(vp._detected_faces) == 0

    # Tạm dừng worker nền để kiểm tra trực tiếp callback mà không bị frame trống từ simulator ghi đè
    if hasattr(kiosk_page, "_face_service"):
        kiosk_page._face_service.disable()
    if hasattr(kiosk_page, "live_view_worker"):
        kiosk_page.live_view_worker.pause()

    # Giả lập worker gửi callback phát hiện khuôn mặt vào KioskPage
    f = DetectedFace(x=100.0, y=100.0, w=150.0, h=150.0, confidence=0.92, right_eye=(130.0, 140.0))
    kiosk_page._on_faces_detected([f], frame_shape=(680, 1024), seq_id=1, ts=time.time())
    qapp.processEvents()

    # KioskPage lưu lại tọa độ cho AF nhưng KHÔNG truyền vào viewport
    assert len(kiosk_page._latest_detected_faces) == 1
    assert len(vp._detected_faces) == 0
    assert vp._face_detection_enabled is False
    assert vp._face_eye_af_enabled is False


def test_kiosk_trigger_shot_with_eye_target(kiosk_page, qapp):
    """
    Khi có mắt được nhận diện, quy trình chụp gọi trigger_autofocus với điểm ngắm mắt
    trước khi thực hiện chụp ảnh.
    """
    if hasattr(kiosk_page, "_face_service"):
        kiosk_page._face_service.disable()
    if hasattr(kiosk_page, "live_view_worker"):
        kiosk_page.live_view_worker.pause()

    f = DetectedFace(x=200.0, y=200.0, w=150.0, h=150.0, confidence=0.95, right_eye=(245.0, 255.0))
    kiosk_page._latest_detected_faces = [f]
    kiosk_page._latest_frame_shape = (680, 1024)
    kiosk_page._latest_detection_time = time.time()
    kiosk_page._enable_af_on_simulator = True

    af_called_args = []
    capture_called = []

    def mock_trigger_af(callback=None, target_point=None, frame_size=None):
        af_called_args.append({
            "target_point": target_point,
            "frame_size": frame_size,
            "callback": callback
        })
        if callback:
            callback(True, "SUCCESS_IN_FOCUS")

    orig_capture = kiosk_page._execute_photo_capture
    def mock_execute_capture(target_path):
        capture_called.append(target_path)

    kiosk_page.camera_mgr.trigger_autofocus = mock_trigger_af
    kiosk_page._execute_photo_capture = mock_execute_capture

    # Kích hoạt chụp ảnh
    kiosk_page.current_shot_index = 1
    kiosk_page.total_shots_needed = 3
    kiosk_page._trigger_shot()
    qapp.processEvents()

    assert len(af_called_args) == 1
    assert af_called_args[0]["target_point"] == (245.0, 255.0)
    assert af_called_args[0]["frame_size"] == (680, 1024)
    assert len(capture_called) == 1


def test_kiosk_trigger_shot_with_face_center_fallback(kiosk_page, qapp):
    """
    Khi khuôn mặt không có mốc mắt (nhắm mắt / che mắt), quy trình chụp
    lấy nét vào tâm khuôn mặt (face center fallback).
    """
    if hasattr(kiosk_page, "_face_service"):
        kiosk_page._face_service.disable()
    if hasattr(kiosk_page, "live_view_worker"):
        kiosk_page.live_view_worker.pause()

    f = DetectedFace(x=200.0, y=200.0, w=150.0, h=150.0, confidence=0.95, right_eye=None, left_eye=None)
    kiosk_page._latest_detected_faces = [f]
    kiosk_page._latest_frame_shape = (680, 1024)
    kiosk_page._latest_detection_time = time.time()
    kiosk_page._enable_af_on_simulator = True

    af_called_args = []
    def mock_trigger_af(callback=None, target_point=None, frame_size=None):
        af_called_args.append({"target_point": target_point, "frame_size": frame_size})
        if callback:
            callback(True, "SUCCESS_IN_FOCUS")

    capture_called = []
    kiosk_page.camera_mgr.trigger_autofocus = mock_trigger_af
    kiosk_page._execute_photo_capture = lambda p: capture_called.append(p)

    kiosk_page.current_shot_index = 1
    kiosk_page._trigger_shot()
    qapp.processEvents()

    assert len(af_called_args) == 1
    expected_center = (200.0 + 150.0 / 2.0, 200.0 + 150.0 * 0.4)
    assert af_called_args[0]["target_point"] == expected_center
    assert len(capture_called) == 1


def test_kiosk_trigger_shot_no_face_fallback(kiosk_page, qapp):
    """
    Khi không phát hiện khuôn mặt nào (hoặc kết quả cũ quá 2.0s),
    lệnh AF được gửi với target_point=None (lấy nét trung tâm) và chụp bình thường.
    """
    kiosk_page._latest_detected_faces = []
    kiosk_page._latest_detection_time = 0.0
    kiosk_page._enable_af_on_simulator = True

    af_called_args = []
    def mock_trigger_af(callback=None, target_point=None, frame_size=None):
        af_called_args.append({"target_point": target_point})
        if callback:
            callback(True, "SUCCESS_IN_FOCUS")

    capture_called = []
    kiosk_page.camera_mgr.trigger_autofocus = mock_trigger_af
    kiosk_page._execute_photo_capture = lambda p: capture_called.append(p)

    kiosk_page.current_shot_index = 1
    kiosk_page._trigger_shot()
    qapp.processEvents()

    assert len(af_called_args) == 1
    assert af_called_args[0]["target_point"] is None
    assert len(capture_called) == 1


def test_kiosk_trigger_shot_af_failure_fallback(kiosk_page, qapp):
    """
    Khi autofocus thất bại (out of focus, máy ảnh gạt MF), quy trình vẫn tiếp tục
    chụp ảnh bình thường mà không bị ngắt quãng hoặc dừng phiên chụp.
    """
    f = DetectedFace(x=100.0, y=100.0, w=100.0, h=100.0, confidence=0.9, right_eye=(140.0, 140.0))
    kiosk_page._latest_detected_faces = [f]
    kiosk_page._latest_frame_shape = (680, 1024)
    kiosk_page._latest_detection_time = time.time()
    kiosk_page._enable_af_on_simulator = True

    def mock_trigger_af(callback=None, target_point=None, frame_size=None):
        if callback:
            # Giả lập thất bại (ví dụ: máy ảnh gạt MF hoặc không thể khóa nét)
            callback(False, "OUT_OF_FOCUS: Đối tượng quá mờ")

    capture_called = []
    kiosk_page.camera_mgr.trigger_autofocus = mock_trigger_af
    kiosk_page._execute_photo_capture = lambda p: capture_called.append(p)

    kiosk_page.current_shot_index = 1
    kiosk_page._trigger_shot()
    qapp.processEvents()

    assert len(capture_called) == 1


def test_kiosk_trigger_shot_watchdog_timeout_fallback(kiosk_page, qapp):
    """
    Khi lệnh autofocus bị treo (không bao giờ gọi callback), watchdog timer
    sẽ tự kích hoạt timeout và fallback chụp ảnh ngay lập tức.
    """
    f = DetectedFace(x=100.0, y=100.0, w=100.0, h=100.0, confidence=0.9, right_eye=(140.0, 140.0))
    kiosk_page._latest_detected_faces = [f]
    kiosk_page._latest_frame_shape = (680, 1024)
    kiosk_page._latest_detection_time = time.time()
    kiosk_page._enable_af_on_simulator = True

    def mock_hanging_af(callback=None, target_point=None, frame_size=None):
        # Không bao giờ gọi callback để mô phỏng camera bị treo
        pass

    capture_called = []
    cancel_called = []
    kiosk_page.camera_mgr.trigger_autofocus = mock_hanging_af
    kiosk_page.camera_mgr.cancel_autofocus = lambda: cancel_called.append(True)
    kiosk_page._execute_photo_capture = lambda p: capture_called.append(p)

    kiosk_page.current_shot_index = 1
    kiosk_page._trigger_shot()

    assert kiosk_page._is_af_in_flight is True
    assert len(capture_called) == 0

    # Kích hoạt timeout sớm
    kiosk_page._on_af_timeout()
    qapp.processEvents()

    assert kiosk_page._is_af_in_flight is False
    assert len(capture_called) == 1
    assert len(cancel_called) == 1


def test_kiosk_next_shot_af_not_blocked_after_previous_af_timeout(kiosk_page, qapp):
    """
    Yêu cầu 2: Xác minh sau khi Shot 1 bị Watchdog timeout và hủy AF,
    lượt chụp tiếp theo (Shot 2) vẫn có thể kích hoạt AF và chụp bình thường
    mà không bị xung đột hay cờ treo từ Shot 1.
    """
    kiosk_page._latest_detected_faces = []
    kiosk_page._latest_detection_time = 0.0
    kiosk_page._enable_af_on_simulator = True

    shot_af_calls = []
    capture_calls = []

    def mock_af_sequential(callback=None, target_point=None, frame_size=None):
        shot_num = len(shot_af_calls) + 1
        shot_af_calls.append(shot_num)
        if shot_num == 1:
            # Shot 1: Bị treo (không gọi callback ngay để kích hoạt timeout)
            pass
        else:
            # Shot 2: Hoạt động bình thường
            if callback:
                callback(True, "SUCCESS_IN_FOCUS_SHOT_2")

    kiosk_page.camera_mgr.trigger_autofocus = mock_af_sequential
    kiosk_page._execute_photo_capture = lambda p: capture_calls.append(p)

    # 1. Thực hiện Shot 1 -> Bị timeout
    kiosk_page.current_shot_index = 1
    kiosk_page._trigger_shot()
    assert kiosk_page._is_af_in_flight is True

    kiosk_page._on_af_timeout()
    qapp.processEvents()

    assert len(capture_calls) == 1
    assert kiosk_page._is_af_in_flight is False
    assert kiosk_page._active_capture_tx is None

    # 2. Thực hiện Shot 2 -> Phải chạy AF thành công và chụp tiếp
    kiosk_page.current_shot_index = 2
    kiosk_page._trigger_shot()
    qapp.processEvents()

    assert len(shot_af_calls) == 2
    assert len(capture_calls) == 2
    assert kiosk_page._is_af_in_flight is False
    assert kiosk_page._active_capture_tx is None


def test_kiosk_late_af_callback_after_watchdog_timeout_ignored(kiosk_page, qapp):
    """
    Yêu cầu 1, 2, 3: Nếu Watchdog đã fallback chụp ảnh, callback AF đến muộn
    sau đó phải bị hủy bỏ hoàn toàn và KHÔNG được gọi _execute_photo_capture lần 2.
    """
    f = DetectedFace(x=100.0, y=100.0, w=100.0, h=100.0, confidence=0.9, right_eye=(140.0, 140.0))
    kiosk_page._latest_detected_faces = [f]
    kiosk_page._latest_frame_shape = (680, 1024)
    kiosk_page._latest_detection_time = time.time()
    kiosk_page._enable_af_on_simulator = True

    saved_callback = []

    def mock_af_delayed(callback=None, target_point=None, frame_size=None):
        # Lưu callback lại để kích hoạt sau khi watchdog đã timeout
        saved_callback.append(callback)

    capture_called = []
    kiosk_page.camera_mgr.trigger_autofocus = mock_af_delayed
    kiosk_page._execute_photo_capture = lambda p: capture_called.append(p)

    kiosk_page.current_shot_index = 1
    kiosk_page._trigger_shot()
    assert len(saved_callback) == 1
    assert len(capture_called) == 0

    # 1. Watchdog timeout kích hoạt trước
    kiosk_page._on_af_timeout()
    qapp.processEvents()

    # Phải có đúng 1 lần chụp từ nhánh watchdog
    assert len(capture_called) == 1
    assert kiosk_page._active_capture_tx is None
    assert kiosk_page._is_af_in_flight is False

    # 2. Callback AF từ worker đến sau
    late_cb = saved_callback[0]
    late_cb(True, "SUCCESS_IN_FOCUS_LATE")
    qapp.processEvents()

    # Vẫn chỉ có đúng 1 lần chụp, nhánh callback trễ bị bỏ qua hoàn toàn
    assert len(capture_called) == 1


def test_kiosk_duplicate_af_callbacks_ignored(kiosk_page, qapp):
    """
    Yêu cầu 2: Nếu callback AF bị gọi trùng lặp (nhiều lần cho 1 lần chụp),
    chỉ lần đầu tiên được xử lý, các lần sau phải bị bỏ qua.
    """
    f = DetectedFace(x=100.0, y=100.0, w=100.0, h=100.0, confidence=0.9, right_eye=(140.0, 140.0))
    kiosk_page._latest_detected_faces = [f]
    kiosk_page._latest_frame_shape = (680, 1024)
    kiosk_page._latest_detection_time = time.time()
    kiosk_page._enable_af_on_simulator = True

    capture_called = []

    def mock_af_duplicate_calls(callback=None, target_point=None, frame_size=None):
        if callback:
            # Gọi callback 2 lần liên tiếp
            callback(True, "SUCCESS_1")
            callback(True, "SUCCESS_2_DUPLICATE")

    kiosk_page.camera_mgr.trigger_autofocus = mock_af_duplicate_calls
    kiosk_page._execute_photo_capture = lambda p: capture_called.append(p)

    kiosk_page.current_shot_index = 1
    kiosk_page._trigger_shot()
    qapp.processEvents()

    # Chỉ được chụp đúng 1 lần duy nhất
    assert len(capture_called) == 1
    assert kiosk_page._active_capture_tx is None
    assert kiosk_page._is_af_in_flight is False


def test_kiosk_close_event_cancels_af_transaction(kiosk_page, qapp):
    """
    Yêu cầu 5, 6: Hủy transaction an toàn khi Kiosk đóng; callback AF đến sau
    khi đóng cửa sổ không được gây lỗi hoặc gọi chụp ảnh.
    """
    f = DetectedFace(x=100.0, y=100.0, w=100.0, h=100.0, confidence=0.9, right_eye=(140.0, 140.0))
    kiosk_page._latest_detected_faces = [f]
    kiosk_page._latest_frame_shape = (680, 1024)
    kiosk_page._latest_detection_time = time.time()
    kiosk_page._enable_af_on_simulator = True

    saved_callback = []
    cancel_called = []

    def mock_af_in_flight(callback=None, target_point=None, frame_size=None):
        saved_callback.append(callback)

    kiosk_page.camera_mgr.trigger_autofocus = mock_af_in_flight
    kiosk_page.camera_mgr.cancel_autofocus = lambda: cancel_called.append(True)

    capture_called = []
    kiosk_page._execute_photo_capture = lambda p: capture_called.append(p)

    kiosk_page.current_shot_index = 1
    kiosk_page._trigger_shot()
    assert kiosk_page._is_af_in_flight is True
    assert kiosk_page._active_capture_tx is not None

    # Đóng Kiosk trong khi AF đang chạy
    kiosk_page.close()
    qapp.processEvents()

    assert len(cancel_called) == 1
    assert kiosk_page._active_capture_tx is None
    assert kiosk_page._is_af_in_flight is False

    # Giả lập callback AF trả về sau khi đóng cửa sổ
    if saved_callback:
        saved_callback[0](True, "LATE_AFTER_CLOSE")
        qapp.processEvents()

    assert len(capture_called) == 0


def test_kiosk_rapid_trigger_shot_prevent_concurrent_transactions(kiosk_page, qapp):
    """
    Yêu cầu 4: Chống kích hoạt chụp liên tục tạo nhiều transaction đồng thời.
    Khi một lệnh chụp/AF đang chạy, lệnh _trigger_shot thứ hai phải bị chặn.
    """
    kiosk_page._latest_detected_faces = []
    kiosk_page._latest_detection_time = 0.0
    kiosk_page._enable_af_on_simulator = True

    af_calls = []

    def mock_af_hanging(callback=None, target_point=None, frame_size=None):
        af_calls.append(callback)

    kiosk_page.camera_mgr.trigger_autofocus = mock_af_hanging
    kiosk_page.current_shot_index = 1

    # Lần 1: Bắt đầu chụp thành công
    kiosk_page._trigger_shot()
    assert len(af_calls) == 1
    first_tx = kiosk_page._active_capture_tx
    assert first_tx is not None

    # Lần 2: Bấm chụp tiếp ngay lập tức khi lần 1 chưa xong
    kiosk_page._trigger_shot()
    assert len(af_calls) == 1  # Không phát thêm lệnh AF nào
    assert kiosk_page._active_capture_tx == first_tx


def test_kiosk_disconnect_aborts_active_af_transaction(kiosk_page, qapp):
    """
    Yêu cầu 5: Khi máy ảnh bị ngắt kết nối (mất tín hiệu / rút cáp),
    active capture transaction phải bị hủy và không kích hoạt chụp.
    """
    kiosk_page._enable_af_on_simulator = True
    saved_callback = []

    kiosk_page.camera_mgr.trigger_autofocus = lambda callback=None, **kw: saved_callback.append(callback)
    capture_called = []
    kiosk_page._execute_photo_capture = lambda p: capture_called.append(p)

    kiosk_page.current_shot_index = 1
    kiosk_page._trigger_shot()
    assert kiosk_page._active_capture_tx is not None

    # Giả lập ngắt kết nối máy ảnh
    with patch("PySide6.QtWidgets.QMessageBox.warning"):
        kiosk_page._abort_capture_due_to_disconnect("Camera disconnected")

    assert kiosk_page._active_capture_tx is None
    assert kiosk_page._is_af_in_flight is False

    # Callback đến sau khi disconnect
    if saved_callback:
        saved_callback[0](True, "LATE_AFTER_DISCONNECT")
        qapp.processEvents()

    assert len(capture_called) == 0


def test_unified_face_eye_af_engine_instance_shared(qapp):
    """
    Yêu cầu B1, B2: Chứng minh FaceDetectionService và FaceEyeAFController
    được dùng chung duy nhất (Single Source of Truth) giữa CameraPage và KioskPage.
    """
    window = MainWindow(start_in_kiosk=False)
    window.resize(1100, 700)
    window.show()
    qapp.processEvents()

    try:
        # Cùng một instance FaceDetectionService
        assert window.kiosk_page._face_service is window.camera_page._face_service
        assert window.kiosk_page._face_service is window.camera_mgr.face_service

        # Cùng một instance FaceEyeAFController
        assert window.kiosk_page._face_eye_af_controller is window.camera_page._face_eye_af_controller
        assert window.kiosk_page._face_eye_af_controller is window.camera_mgr.face_eye_af_controller
    finally:
        window.camera_mgr.close()
        window.close()


def test_sync_af_and_face_detect_toggle_state(qapp):
    """
    Yêu cầu B4, B5: Chứng minh trạng thái bật/tắt Face Detection và Eye AF
    được đồng bộ hoàn toàn giữa CameraPage và KioskPage qua config_mgr và camera_mgr.
    """
    window = MainWindow(start_in_kiosk=False)
    window.resize(1100, 700)
    window.show()
    qapp.processEvents()

    try:
        cam_page = window.camera_page
        kiosk_page = window.kiosk_page
        cam_mgr = window.camera_mgr

        # 1. Bật Face/Eye AF từ CameraPage
        if not cam_page._face_eye_af_enabled:
            cam_page._toggle_face_eye_af()
            qapp.processEvents()

        assert cam_page._face_eye_af_enabled is True
        assert cam_mgr.is_face_eye_af_enabled() is True
        assert cam_page._face_eye_af_controller.is_enabled is True
        assert "BẬT" in cam_page.btn_face_eye_af.text()

        # KioskPage nhận diện trạng thái bật dùng chung
        assert cam_mgr.is_face_eye_af_enabled() is True

        # 2. Tắt Face/Eye AF từ CameraPage
        cam_page._toggle_face_eye_af()
        qapp.processEvents()

        assert cam_page._face_eye_af_enabled is False
        assert cam_mgr.is_face_eye_af_enabled() is False
        assert cam_page._face_eye_af_controller.is_enabled is False
        assert "Tắt" in cam_page.btn_face_eye_af.text()
    finally:
        cam_mgr.set_face_eye_af_enabled(True)
        window.camera_mgr.close()
        window.close()


def test_kiosk_uses_target_from_shared_controller(kiosk_page, qapp):
    """
    Yêu cầu D: Nhấn chụp lấy mục tiêu mới nhất từ FaceEyeAFController dùng chung.
    Ưu tiên mắt, fallback khuôn mặt.
    """
    if hasattr(kiosk_page, "_face_service") and kiosk_page._face_service:
        kiosk_page._face_service.disable()
    if hasattr(kiosk_page, "live_view_worker") and kiosk_page.live_view_worker:
        kiosk_page.live_view_worker.pause()

    ctrl = kiosk_page._face_eye_af_controller
    ctrl.enable()

    # 1. Khi có mắt
    f_eye = DetectedFace(
        x=200.0, y=150.0, w=160.0, h=180.0,
        confidence=0.96,
        right_eye=(242.0, 212.0),
        left_eye=(308.0, 212.0)
    )
    ctrl.process_faces([f_eye], frame_shape=(680, 1024), sequence_id=1, timestamp=time.time())
    qapp.processEvents()

    target_pt, frame_shape, target_type = kiosk_page._get_af_target_point()
    assert target_type == "eye"
    assert target_pt == (242.0, 212.0)
    assert frame_shape == (680, 1024)

    # 2. Khi không có mắt rõ (nhắm mắt / che mắt) -> Fallback tâm mặt
    ctrl.reset_sequence()
    f_no_eye = DetectedFace(
        x=300.0, y=200.0, w=150.0, h=180.0,
        confidence=0.92,
        right_eye=None,
        left_eye=None
    )
    ctrl.process_faces([f_no_eye], frame_shape=(680, 1024), sequence_id=2, timestamp=time.time())
    qapp.processEvents()

    target_pt, frame_shape, target_type = kiosk_page._get_af_target_point()
    assert target_type == "face"
    assert target_pt == (300.0 + 150.0 / 2.0, 200.0 + 180.0 * 0.4)


def test_camera_page_renders_overlay_while_kiosk_has_zero_overlay(qapp):
    """
    Yêu cầu C & E: Chứng minh CameraPage hiển thị đầy đủ overlay nhận diện
    trong khi KioskPage hoàn toàn KHÔNG render bất kỳ overlay nào (Zero UI Overlay).
    """
    window = MainWindow(start_in_kiosk=False)
    window.resize(1100, 700)
    window.show()
    qapp.processEvents()

    try:
        cam_page = window.camera_page
        kiosk_page = window.kiosk_page

        # Bật nhận diện trên CameraPage
        if not cam_page._face_detect_enabled:
            cam_page._toggle_face_detection()
            qapp.processEvents()

        f = DetectedFace(x=100.0, y=100.0, w=120.0, h=120.0, confidence=0.95, right_eye=(130.0, 140.0))

        # CameraPage xử lý frame
        cam_page._on_faces_detected([f], frame_shape=(680, 1024), seq_id=1, ts=time.time())
        qapp.processEvents()

        # CameraPage viewport: hiển thị overlay
        assert cam_page.lbl_viewport._face_detection_enabled is True
        assert len(cam_page.lbl_viewport._detected_faces) == 1

        # KioskPage xử lý frame
        kiosk_page._on_faces_detected([f], frame_shape=(680, 1024), seq_id=1, ts=time.time())
        qapp.processEvents()

        # KioskPage viewport: TUYỆT ĐỐI KHÔNG hiển thị overlay
        assert kiosk_page.lbl_viewport._face_detection_enabled is False
        assert kiosk_page.lbl_viewport._face_eye_af_enabled is False
        assert len(kiosk_page.lbl_viewport._detected_faces) == 0
    finally:
        window.camera_mgr.close()
        window.close()


