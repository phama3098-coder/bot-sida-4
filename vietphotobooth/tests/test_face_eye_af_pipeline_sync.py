"""
1998 TEAM — Photobooth Tests for Face/Eye AF Pipeline Synchronization & Edge Cases
Covers:
1. Missing AI model handling (graceful failure, no crash).
2. No-face hysteresis & transition (SEARCHING -> LOST -> FACE_DETECTED).
3. Dynamic frame dimension adaptation in YuNet detector.
4. Out-of-order / delayed frame dropping via monotonic sequence IDs.
5. Obsolete AF completion callback rejection (command ID mismatch).
6. AF completion callback after disable() rejection.
7. Zero-Jitter Live Viewport overlay rendering with target eye reticle.
"""

import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from vietphotobooth.camera.models import FrameData
from vietphotobooth.camera.face_detector import DetectedFace, FaceEyeDetector, FaceDetectionService
from vietphotobooth.camera.face_eye_af_controller import FaceEyeAFController, FaceEyeAFState
from vietphotobooth.desktop.widgets.live_viewport import CameraLiveViewport


# ============================================================================
# 1. MISSING AI MODEL HANDLING
# ============================================================================

def test_missing_ai_model_graceful_handling():
    """Kiểm tra khi không tìm thấy mô hình ONNX: detector báo không khả dụng, không văng exception."""
    detector = FaceEyeDetector(model_path="Assets/Models/non_existent_model_xyz.onnx")
    assert not detector.is_available
    
    # detect_faces trên ảnh bất kỳ phải trả về [] an toàn
    dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
    faces = detector.detect_faces(dummy_img)
    assert faces == []

    # FaceDetectionService không thể enable nếu detector không khả dụng
    service = FaceDetectionService()
    service._detector = detector
    assert not service.enable()
    assert not service.is_enabled


# ============================================================================
# 2. NO-FACE HYSTERESIS: SEARCHING -> LOST -> FACE_DETECTED
# ============================================================================

def test_no_face_hysteresis_and_recovery():
    """Kiểm tra máy trạng thái khi không có khuôn mặt và khi khuôn mặt xuất hiện lại."""
    controller = FaceEyeAFController(
        stability_frames=3,
        lost_frames_threshold=4,
        cooldown_sec=1.0
    )
    controller.enable()
    assert controller.state == FaceEyeAFState.SEARCHING

    # Gửi 3 frames không có mặt (< lost_frames_threshold=4) -> vẫn giữ SEARCHING
    for _ in range(3):
        controller.process_faces([])
        assert controller.state == FaceEyeAFState.SEARCHING

    # Frame thứ 4 không có mặt -> chuyển sang LOST
    controller.process_faces([])
    assert controller.state == FaceEyeAFState.LOST

    # Khuôn mặt xuất hiện lại -> chuyển ngay sang FACE_DETECTED
    dummy_face = DetectedFace(
        x=150.0, y=100.0, w=120.0, h=160.0,
        confidence=0.91,
        right_eye=(180.0, 140.0),
        left_eye=(230.0, 140.0)
    )
    controller.process_faces([dummy_face])
    assert controller.state == FaceEyeAFState.FACE_DETECTED


# ============================================================================
# 3. DYNAMIC FRAME SIZE ADAPTATION IN DETECTOR
# ============================================================================

def test_detector_dynamic_frame_shape_adaptation():
    """Kiểm tra detector tự thích ứng khi kích thước khung hình thay đổi đột ngột."""
    detector = FaceEyeDetector()
    if not detector.is_available:
        pytest.skip("YuNet model không có sẵn trong môi trường test")

    # Kích thước 1: 680x1024
    frame_1 = np.zeros((680, 1024, 3), dtype=np.uint8)
    res1 = detector.detect_faces(frame_1)
    assert isinstance(res1, list)

    # Kích thước 2: 720x1280 (thay đổi độ phân giải đột ngột)
    frame_2 = np.zeros((720, 1280, 3), dtype=np.uint8)
    res2 = detector.detect_faces(frame_2)
    assert isinstance(res2, list)

    # Kích thước 3: 480x640
    frame_3 = np.zeros((480, 640, 3), dtype=np.uint8)
    res3 = detector.detect_faces(frame_3)
    assert isinstance(res3, list)


# ============================================================================
# 4. OUT-OF-ORDER / DELAYED FRAME DROPPING
# ============================================================================

def test_out_of_order_frame_dropping():
    """Kiểm tra controller bỏ qua các khung hình cũ (sequence_id < last_processed)."""
    controller = FaceEyeAFController(stability_frames=3, cooldown_sec=1.0)
    controller.enable()

    face_seq10 = DetectedFace(
        x=200.0, y=150.0, w=160.0, h=200.0, confidence=0.90,
        right_eye=(240.0, 200.0), left_eye=(310.0, 200.0)
    )

    # Xử lý frame seq=10
    state1 = controller.process_faces([face_seq10], sequence_id=10)
    assert state1 == FaceEyeAFState.FACE_DETECTED
    assert controller._last_processed_seq_id == 10

    # Frame trễ seq=8 đến muộn -> phải bị drop, không làm thay đổi trạng thái
    face_seq8 = DetectedFace(
        x=50.0, y=50.0, w=100.0, h=100.0, confidence=0.80,
        right_eye=(70.0, 70.0), left_eye=(110.0, 70.0)
    )
    state2 = controller.process_faces([face_seq8], sequence_id=8)
    assert state2 == FaceEyeAFState.FACE_DETECTED
    assert controller._last_processed_seq_id == 10
    assert controller.target_face == face_seq10  # Target không bị thay đổi bởi frame cũ

    # Frame seq=11 hợp lệ -> được xử lý bình thường
    face_seq11 = DetectedFace(
        x=201.0, y=150.0, w=160.0, h=200.0, confidence=0.91,
        right_eye=(241.0, 200.0), left_eye=(311.0, 200.0)
    )
    state3 = controller.process_faces([face_seq11], sequence_id=11)
    assert controller._last_processed_seq_id == 11
    assert controller.target_face == face_seq11


# ============================================================================
# 5. OBSOLETE AF COMPLETION CALLBACK REJECTION (COMMAND ID)
# ============================================================================

def test_obsolete_af_completion_callback_rejected():
    """Kiểm tra callback hoàn thành của lệnh AF cũ không được ghi đè trạng thái của chu kỳ mới."""
    saved_callbacks = []

    def fake_af_trigger(cb):
        saved_callbacks.append(cb)

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

    # 2 frames ổn định -> kích hoạt AF lệnh 1
    controller.process_faces([face], sequence_id=1)
    controller.process_faces([face], sequence_id=2)
    assert controller.state == FaceEyeAFState.FOCUSING
    assert len(saved_callbacks) == 1
    first_cb = saved_callbacks[0]

    # Giả lập lệnh 1 bị timeout hoặc controller reset chu kỳ AF mới (cmd_id tăng)
    controller._is_af_in_progress = False
    controller._trigger_af(face.right_eye, face, reason="Chu kỳ mới")
    assert len(saved_callbacks) == 2
    second_cb = saved_callbacks[1]

    # Bây giờ callback của lệnh cũ (first_cb) mới trả về kết quả FAILED
    first_cb(False, "Old command timeout")

    # Controller KHÔNG bị chuyển thành ERROR vì first_cb là lệnh cũ!
    assert controller.state == FaceEyeAFState.FOCUSING

    # Khi second_cb trả về SUCCESS -> chuyển thành FOCUSED
    second_cb(True, "In Focus")
    assert controller.state == FaceEyeAFState.FOCUSED


# ============================================================================
# 6. AF COMPLETION CALLBACK AFTER DISABLE() REJECTED
# ============================================================================

def test_af_completion_after_disable_rejected():
    """Kiểm tra nếu người dùng đã tắt Face/Eye AF, callback hoàn thành sau đó không ghi đè."""
    saved_cb = []

    def fake_af(cb):
        saved_cb.append(cb)

    controller = FaceEyeAFController(
        af_trigger_fn=fake_af,
        stability_frames=2,
        cooldown_sec=0.1
    )
    controller.enable()

    face = DetectedFace(
        x=200.0, y=150.0, w=160.0, h=200.0, confidence=0.95,
        right_eye=(240.0, 200.0), left_eye=(310.0, 200.0)
    )

    controller.process_faces([face], sequence_id=1)
    controller.process_faces([face], sequence_id=2)
    assert controller.state == FaceEyeAFState.FOCUSING
    assert len(saved_cb) == 1

    # Người dùng bấm Tắt Face/Eye AF
    controller.disable()
    assert not controller.is_enabled
    assert controller.state == FaceEyeAFState.SEARCHING

    # Sau đó phần cứng camera mới phản hồi AF xong
    saved_cb[0](True, "In Focus")

    # Controller vẫn phải ở trạng thái tắt (không bị chuyển sang FOCUSED)
    assert not controller.is_enabled
    assert controller.state == FaceEyeAFState.SEARCHING


# ============================================================================
# 7. LIVE VIEWPORT OVERLAY WITH TARGET EYE (REGRESSION VERIFICATION)
# ============================================================================

def test_live_viewport_target_eye_reticle_rendering(qapp):
    """Kiểm tra Live Viewport vẽ reticle mắt mục tiêu mượt mà, không gặp lỗi NameError math."""
    viewport = CameraLiveViewport()
    viewport.set_face_eye_af_state(True, "FACE_DETECTED", target_eye=(240.0, 200.0))

    face = DetectedFace(
        x=200.0, y=150.0, w=160.0, h=200.0, confidence=0.92,
        right_eye=(240.0, 200.0), left_eye=(310.0, 200.0)
    )
    viewport.set_detected_faces([face])

    # Tạo một dummy frame để paintEvent được gọi trọn vẹn
    dummy_rgb = np.full((680, 1024, 3), 40, dtype=np.uint8)
    viewport.set_frame_rgb(dummy_rgb)

    # Trigger repaint
    viewport.repaint()
    assert viewport._face_eye_af_enabled is True
    assert viewport._face_eye_af_state == "FACE_DETECTED"
    assert viewport._target_eye_pos == (240.0, 200.0)


# ============================================================================
# 8. CROSS-THREAD DISPATCH: BACKGROUND THREAD CALLBACKS TO UI VIEWPORT
# ============================================================================

def test_camerapage_background_thread_callback_safe_dispatch(qapp):
    """
    Kiểm tra callback từ luồng ngầm FaceDetection-Worker hoặc AF Controller
    được chuyển tiếp an toàn sang UI thread mà không bị nuốt/bỏ qua (QTimer.singleShot với context QObject).
    """
    import threading
    from vietphotobooth.camera.manager import CameraManager
    from vietphotobooth.desktop.widgets.camera_page import CameraPage

    mgr = CameraManager()
    page = CameraPage(mgr)
    page._face_eye_af_enabled = True

    face = DetectedFace(
        x=120.0, y=100.0, w=150.0, h=160.0, confidence=0.91,
        right_eye=(150.0, 140.0), left_eye=(210.0, 140.0)
    )

    def worker_thread():
        page._on_faces_detected([face], frame_shape=(680, 1024), seq_id=10, ts=time.time())
        page._on_face_eye_af_state_changed(FaceEyeAFState.FACE_DETECTED, "Target locked", face, face.right_eye)

    t = threading.Thread(target=worker_thread)
    t.start()
    t.join()

    # Bơm sự kiện Qt để xử lý singleShot posted events
    qapp.processEvents()

    assert len(page.lbl_viewport._detected_faces) == 1
    assert page.lbl_viewport._detected_faces[0].confidence == 0.91
    assert "ĐÃ PHÁT HIỆN MẶT" in page.lbl_face_eye_af_status.text()

    page.deleteLater()
    qapp.processEvents()


# ============================================================================
# 9. VIEWPORT SEQUENCE PROTECTION & OUT-OF-ORDER REJECTION
# ============================================================================

def test_viewport_sequence_protection_outdated_frame_rejected(qapp):
    """
    Kiểm tra Viewport sequence protection:
    Khi callback của frame cũ (seq_id=15) đến sau frame mới (seq_id=20),
    kết quả của frame cũ phải bị từ chối, bảo toàn kết quả của frame mới.
    """
    viewport = CameraLiveViewport()
    viewport.set_face_detection_enabled(True)

    face_new = DetectedFace(x=200.0, y=100.0, w=150.0, h=150.0, confidence=0.95)
    face_old = DetectedFace(x=50.0, y=50.0, w=80.0, h=80.0, confidence=0.70)

    # Frame mới seq_id=20 đến trước
    viewport.set_detected_faces([face_new], sequence_id=20)
    assert len(viewport._detected_faces) == 1
    assert viewport._detected_faces[0].confidence == 0.95
    assert viewport._last_detected_seq_id == 20

    # Frame cũ seq_id=15 đến muộn (out-of-order)
    viewport.set_detected_faces([face_old], sequence_id=15)
    # Phải giữ nguyên face_new, không bị face_old đè lên
    assert len(viewport._detected_faces) == 1
    assert viewport._detected_faces[0].confidence == 0.95
    assert viewport._last_detected_seq_id == 20

    # Frame kế tiếp seq_id=21 hợp lệ
    face_next = DetectedFace(x=210.0, y=105.0, w=150.0, h=150.0, confidence=0.96)
    viewport.set_detected_faces([face_next], sequence_id=21)
    assert len(viewport._detected_faces) == 1
    assert viewport._detected_faces[0].confidence == 0.96
    assert viewport._last_detected_seq_id == 21


# ============================================================================
# 10. LIVE VIEW RESTART & SEQUENCE RESYNCHRONIZATION
# ============================================================================

def test_viewport_and_controller_liveview_restart_resync(qapp):
    """
    Kiểm tra cơ chế tái đồng bộ khi Live View khởi động lại:
    Bộ đếm sequence_id bị nhảy lùi (>10 frame) hoặc gọi reset_sequence(),
    cả Viewport và Controller đều tái đồng bộ và chấp nhận frame mới.
    """
    viewport = CameraLiveViewport()
    viewport.set_face_detection_enabled(True)

    face1 = DetectedFace(x=100.0, y=100.0, w=100.0, h=100.0, confidence=0.9)
    viewport.set_detected_faces([face1], sequence_id=100)
    assert viewport._last_detected_seq_id == 100

    # Live View restart: sequence_id nhảy về 1 (lùi 99 frame > 10)
    face_restarted = DetectedFace(x=120.0, y=120.0, w=110.0, h=110.0, confidence=0.92)
    viewport.set_detected_faces([face_restarted], sequence_id=1)
    assert viewport._last_detected_seq_id == 1
    assert len(viewport._detected_faces) == 1
    assert viewport._detected_faces[0].confidence == 0.92

    # Gọi reset_face_sequence thủ công
    viewport.reset_face_sequence()
    assert viewport._last_detected_seq_id == 0

    # Controller reset_sequence
    controller = FaceEyeAFController()
    controller.enable()
    controller.process_faces([face1], sequence_id=50)
    assert controller._last_processed_seq_id == 50

    controller.reset_sequence()
    assert controller._last_processed_seq_id == 0

    # Chấp nhận frame mới sau reset
    controller.process_faces([face_restarted], sequence_id=1)
    assert controller._last_processed_seq_id == 1


# ============================================================================
# 11. QOBJECT LIFECYCLE: DIALOG CLOSED WHILE WORKER DISPATCHES
# ============================================================================

def test_dialog_closed_while_worker_dispatches_callback(qapp):
    """
    Kiểm tra vòng đời QObject: Khi Dialog bị đóng và giải phóng C++ object
    trong lúc worker thread đang phát callback hoặc callback đang đợi trong
    Qt event queue, bảo vệ shiboken6.isValid ngăn ngừa crash và exception.
    """
    import threading
    import shiboken6
    from vietphotobooth.camera.manager import CameraManager
    from vietphotobooth.desktop.widgets.camera_page import CameraFullscreenDialog

    mgr = CameraManager()
    dlg = CameraFullscreenDialog(mgr, grid_enabled=False, face_detect_enabled=True)

    face = DetectedFace(x=150.0, y=120.0, w=140.0, h=140.0, confidence=0.88)

    # Worker phát callback
    dlg._on_faces_detected([face], frame_shape=(680, 1024), seq_id=1)
    dlg._on_af_state_changed(FaceEyeAFState.FACE_DETECTED, "Locking", face, (200.0, 180.0))

    # Đóng dialog
    dlg.accept()

    # Xóa C++ object để mô phỏng đóng và hủy dialog
    shiboken6.delete(dlg)

    # Giờ dlg không còn hợp lệ trong C++
    assert not shiboken6.isValid(dlg)

    # Bơm sự kiện Qt để thực thi bất kỳ singleShot callback nào đang nằm trong hàng đợi
    # Nếu không có bảo vệ shiboken6.isValid, dòng này sẽ gây RuntimeError hoặc crash!
    qapp.processEvents()


# ============================================================================
# 12. CAMERA DISCONNECT AND RECONNECT OVERLAY CLEARING
# ============================================================================

def test_camera_disconnect_and_reconnect_clears_overlays(qapp):
    """
    Kiểm tra khi camera ngắt kết nối hoặc chuyển nguồn:
    Bounding box, Eye Reticle và target point được xóa sạch sẽ (clear_overlays),
    không để lại tàn dư (ghost overlay) trên màn hình.
    """
    viewport = CameraLiveViewport()
    viewport.set_face_eye_af_state(True, "FOCUSED", target_eye=(250.0, 200.0))
    face = DetectedFace(x=200.0, y=150.0, w=120.0, h=120.0, confidence=0.94)
    viewport.set_detected_faces([face], sequence_id=5)

    assert len(viewport._detected_faces) == 1
    assert viewport._face_eye_af_state == "FOCUSED"
    assert viewport._target_eye_pos == (250.0, 200.0)

    # Khi ngắt kết nối hoặc mất tín hiệu
    viewport.clear_overlays()

    assert len(viewport._detected_faces) == 0
    assert viewport._face_eye_af_state is None
    assert viewport._target_eye_pos is None
    assert viewport._last_detected_seq_id == 0

    # Khi set_message được gọi (hiển thị thông báo mất kết nối)
    viewport.set_face_eye_af_state(True, "SEARCHING", None)
    viewport.set_detected_faces([face], sequence_id=6)
    viewport.set_message("NIKON D780 NATIVE USB (CHƯA KẾT NỐI)")

    assert len(viewport._detected_faces) == 0
    assert viewport._face_eye_af_state is None
    assert viewport._target_eye_pos is None


