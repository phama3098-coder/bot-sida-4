"""
1998 TEAM — Unit & Integration Tests for Software-Triggered Face/Eye AF
Tests all 5 states (SEARCHING, FOCUSING, FOCUSED, LOST, ERROR), stability tracking,
cooldown, hysteresis movement refocus, single in-flight guard, and Live View preservation.
"""

import time
import pytest
from unittest.mock import MagicMock, call

from vietphotobooth.camera.face_detector import DetectedFace
from vietphotobooth.camera.face_eye_af_controller import FaceEyeAFController, FaceEyeAFState


@pytest.fixture
def dummy_face():
    """Tạo đối tượng khuôn mặt mẫu với mắt và độ tự tin cao."""
    return DetectedFace(
        x=200.0, y=150.0, w=160.0, h=200.0,
        confidence=0.92,
        right_eye=(240.0, 200.0),
        left_eye=(310.0, 200.0),
        nose=(275.0, 240.0),
        mouth_right=(250.0, 280.0),
        mouth_left=(300.0, 280.0)
    )


class TestFaceEyeAFController:
    """Kiểm thử toàn diện bộ điều khiển Face/Eye AF."""

    def test_initial_state_and_lifecycle(self):
        controller = FaceEyeAFController(stability_frames=3, cooldown_sec=1.0)
        assert not controller.is_enabled
        assert controller.state == FaceEyeAFState.SEARCHING

        state_events = []
        controller.register_state_callback(lambda s, msg, f, e: state_events.append((s, msg)))

        assert controller.enable()
        assert controller.is_enabled
        assert controller.state == FaceEyeAFState.SEARCHING
        assert len(state_events) == 1
        assert state_events[-1][0] == FaceEyeAFState.SEARCHING

        controller.disable()
        assert not controller.is_enabled
        assert state_events[-1][0] == FaceEyeAFState.SEARCHING

    def test_stability_detection_triggers_af(self, dummy_face):
        mock_af_trigger = MagicMock()
        controller = FaceEyeAFController(
            af_trigger_fn=mock_af_trigger,
            stability_frames=3,
            stability_px_threshold=15.0,
            cooldown_sec=1.0
        )
        controller.enable()

        # Frame 1: mới nhận diện, chưa đủ 3 frames ổn định -> chuyển sang FACE_DETECTED
        controller.process_faces([dummy_face])
        assert mock_af_trigger.call_count == 0
        assert controller.state == FaceEyeAFState.FACE_DETECTED

        # Frame 2: mắt lệch nhẹ 2px (trong ngưỡng 15px) -> stable_frames = 2
        f2 = DetectedFace(
            x=201.0, y=150.0, w=160.0, h=200.0, confidence=0.93,
            right_eye=(241.0, 201.0), left_eye=(311.0, 201.0)
        )
        controller.process_faces([f2])
        assert mock_af_trigger.call_count == 0

        # Frame 3: mắt ổn định -> kích hoạt AF!
        f3 = DetectedFace(
            x=200.0, y=150.0, w=160.0, h=200.0, confidence=0.94,
            right_eye=(240.5, 200.5), left_eye=(310.5, 200.5)
        )
        controller.process_faces([f3])
        assert mock_af_trigger.call_count == 1
        assert controller.state == FaceEyeAFState.FOCUSING
        assert controller.is_af_in_progress

    def test_af_successful_completion_transitions_to_focused(self, dummy_face):
        saved_cb = []

        def fake_af(callback):
            saved_cb.append(callback)

        controller = FaceEyeAFController(
            af_trigger_fn=fake_af,
            stability_frames=2,
            cooldown_sec=0.5
        )
        controller.enable()

        # Đạt ngưỡng ổn định (2 frames)
        controller.process_faces([dummy_face])
        controller.process_faces([dummy_face])

        assert controller.state == FaceEyeAFState.FOCUSING
        assert len(saved_cb) == 1

        # Camera phản hồi lấy nét thành công
        saved_cb[0](True, "In Focus")
        assert controller.state == FaceEyeAFState.FOCUSED
        assert not controller.is_af_in_progress
        assert controller.get_diagnostics()["total_af_successes"] == 1
        assert controller.get_diagnostics()["locked_eye_pos"] == dummy_face.right_eye

    def test_af_failure_transitions_to_error(self, dummy_face):
        saved_cb = []

        def fake_af(callback):
            saved_cb.append(callback)

        controller = FaceEyeAFController(
            af_trigger_fn=fake_af,
            stability_frames=2,
            cooldown_sec=0.5
        )
        controller.enable()

        controller.process_faces([dummy_face])
        controller.process_faces([dummy_face])
        assert controller.state == FaceEyeAFState.FOCUSING

        # Camera phản hồi Out of Focus
        saved_cb[0](False, "Out of Focus (mã 137)")
        assert controller.state == FaceEyeAFState.ERROR
        assert not controller.is_af_in_progress
        assert controller.get_diagnostics()["total_af_failures"] == 1

    def test_single_in_flight_guard_prevents_duplicate_af(self, dummy_face):
        mock_af_trigger = MagicMock()
        controller = FaceEyeAFController(
            af_trigger_fn=mock_af_trigger,
            stability_frames=1,
            cooldown_sec=0.0
        )
        controller.enable()

        # Trigger AF lần 1
        controller.process_faces([dummy_face])
        assert mock_af_trigger.call_count == 1
        assert controller.is_af_in_progress

        # Trong lúc AF in progress, các frames mới đến tiếp tục không được spam AF
        controller.process_faces([dummy_face])
        controller.process_faces([dummy_face])
        assert mock_af_trigger.call_count == 1

    def test_cooldown_guard_prevents_af_spam(self, dummy_face):
        trigger_count = [0]

        def instant_af(callback):
            trigger_count[0] += 1
            callback(True, "In Focus")

        controller = FaceEyeAFController(
            af_trigger_fn=instant_af,
            stability_frames=1,
            cooldown_sec=1.5
        )
        controller.enable()

        # Lần 1: trigger ngay
        controller.process_faces([dummy_face])
        assert trigger_count[0] == 1
        assert controller.state == FaceEyeAFState.FOCUSED

        # Ngay sau đó (trong 1.5s cooldown): dù chủ thể di chuyển cũng không được spam
        moved_face = DetectedFace(
            x=350.0, y=150.0, w=160.0, h=200.0, confidence=0.92,
            right_eye=(390.0, 200.0), left_eye=(460.0, 200.0)
        )
        controller.process_faces([moved_face])
        controller.process_faces([moved_face])
        assert trigger_count[0] == 1  # Không tăng vì đang trong cooldown

    def test_movement_triggers_refocus_after_cooldown(self, dummy_face):
        trigger_count = [0]

        def instant_af(callback):
            trigger_count[0] += 1
            callback(True, "In Focus")

        controller = FaceEyeAFController(
            af_trigger_fn=instant_af,
            stability_frames=1,
            movement_px_threshold=30.0,
            cooldown_sec=0.05
        )
        controller.enable()

        # Lần 1: Khóa nét
        controller.process_faces([dummy_face])
        assert trigger_count[0] == 1
        assert controller.state == FaceEyeAFState.FOCUSED

        time.sleep(0.06)  # Vượt qua cooldown

        # Chủ thể di chuyển mắt 60px (> threshold 30px) qua 2 frames
        moved_face = DetectedFace(
            x=260.0, y=150.0, w=160.0, h=200.0, confidence=0.92,
            right_eye=(300.0, 200.0), left_eye=(370.0, 200.0)
        )
        controller.process_faces([moved_face])
        assert trigger_count[0] == 1  # Cần frame thứ 2 để chống nhiễu rung giật

        controller.process_faces([moved_face])
        assert trigger_count[0] == 2  # Đã kích hoạt chu kỳ lấy nét lại!
        assert controller.state == FaceEyeAFState.FOCUSED

    def test_box_scale_delta_triggers_refocus(self, dummy_face):
        trigger_count = [0]

        def instant_af(callback):
            trigger_count[0] += 1
            callback(True, "In Focus")

        controller = FaceEyeAFController(
            af_trigger_fn=instant_af,
            stability_frames=1,
            box_scale_threshold=0.15,
            cooldown_sec=0.05
        )
        controller.enable()

        # Khóa nét ban đầu (w = 160)
        controller.process_faces([dummy_face])
        assert trigger_count[0] == 1

        time.sleep(0.06)

        # Đối tượng tiến lại gần: w tăng từ 160 lên 210 (+31% > 15%)
        closer_face = DetectedFace(
            x=180.0, y=130.0, w=210.0, h=260.0, confidence=0.95,
            right_eye=(240.0, 200.0), left_eye=(310.0, 200.0)
        )
        controller.process_faces([closer_face])
        controller.process_faces([closer_face])
        assert trigger_count[0] == 2

    def test_target_lost_and_recovery(self, dummy_face):
        trigger_count = [0]

        def instant_af(callback):
            trigger_count[0] += 1
            callback(True, "In Focus")

        controller = FaceEyeAFController(
            af_trigger_fn=instant_af,
            stability_frames=1,
            lost_frames_threshold=3,
            cooldown_sec=0.05
        )
        controller.enable()

        controller.process_faces([dummy_face])
        assert controller.state == FaceEyeAFState.FOCUSED

        # Mất dấu trong 3 frames liên tiếp
        controller.process_faces([])
        controller.process_faces([])
        assert controller.state == FaceEyeAFState.FOCUSED

        controller.process_faces([])
        assert controller.state == FaceEyeAFState.LOST
        assert controller.target_face is None
        assert controller.target_eye is None

        time.sleep(0.06)

        # Khuôn mặt xuất hiện trở lại -> Kích hoạt AF lại
        controller.process_faces([dummy_face])
        assert controller.state == FaceEyeAFState.FOCUSED
        assert trigger_count[0] == 2

    def test_diagnostics_telemetry(self, dummy_face):
        controller = FaceEyeAFController(stability_frames=2, cooldown_sec=1.5)
        controller.enable()

        diag = controller.get_diagnostics()
        assert diag["enabled"] is True
        assert diag["state"] == "SEARCHING"
        assert diag["config"]["stability_frames"] == 2
        assert diag["config"]["cooldown_sec"] == 1.5
        assert "total_af_triggers" in diag

        # Khi đưa khuôn mặt vào -> cập nhật target_eye và state FACE_DETECTED
        controller.process_faces([dummy_face])
        diag_after = controller.get_diagnostics()
        assert diag_after["state"] == "FACE_DETECTED"
        assert diag_after["target_eye"] == dummy_face.right_eye

    def test_viewport_rendering_all_face_eye_af_states(self, dummy_face):
        """Kiểm tra widget CameraLiveViewport hiển thị đầy đủ 5 trạng thái Face/Eye AF."""
        from PySide6.QtGui import QImage, QPixmap
        from vietphotobooth.desktop.widgets.live_viewport import CameraLiveViewport

        vp = CameraLiveViewport()
        vp.resize(640, 426)

        # Tạo một ảnh giả lập 1024x680
        img = QImage(1024, 680, QImage.Format_RGB888)
        img.fill(0x102030)
        vp.setPixmap(QPixmap.fromImage(img))
        vp.set_detected_faces([dummy_face])

        # Test lần lượt 5 trạng thái
        for state in [
            FaceEyeAFState.SEARCHING,
            FaceEyeAFState.FOCUSING,
            FaceEyeAFState.FOCUSED,
            FaceEyeAFState.LOST,
            FaceEyeAFState.ERROR
        ]:
            vp.set_face_eye_af_state(True, state.value, dummy_face.right_eye)
            assert vp._face_eye_af_enabled is True
            assert vp._face_eye_af_state == state.value
            assert vp._target_eye_pos == dummy_face.right_eye

            # Kích hoạt paintEvent thực tế để đảm bảo không có lỗi vẽ đồ họa
            vp.repaint()

        # Tắt Face/Eye AF
        vp.set_face_eye_af_state(False, None, None)
        assert vp._face_eye_af_enabled is False
        vp.repaint()

    def test_maid_session_trigger_autofocus_releases_lock_during_wait(self):
        """
        Kiểm tra cơ chế bảo toàn luồng Live View trong maid_session.py:
        Khóa self._lock không bị chiếm giữ trong chu kỳ đợi completion,
        cho phép fetch_live_view_frame() tiếp tục đọc khung hình song song.
        """
        import ctypes
        from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
        from vietphotobooth.camera.backends.nikon_maid.maid_types import NkMAIDResult, NkMAIDObject
        import threading

        session = NikonSession()
        session._is_src_open = True
        session._src_obj = NkMAIDObject()

        # Giả lập _entry thành công khi gọi CAP_START
        def mock_entry(p_obj, cmd, param, dt, data, comp_fn, ref_comp):
            if comp_fn:
                # Giả lập hoàn thành sau 60ms
                def delayed_complete():
                    time.sleep(0.06)
                    obj_addr = ctypes.addressof(p_obj) if p_obj else 0
                    comp_fn(obj_addr, cmd, param, dt, data, ref_comp, NkMAIDResult.NO_ERROR)
                threading.Thread(target=delayed_complete, daemon=True).start()
            return NkMAIDResult.NO_ERROR

        session._entry = mock_entry

        # Trong lúc trigger_autofocus đang chạy trong background thread:
        lock_accessible = [False]
        def check_lock_task():
            time.sleep(0.02)
            # Thử acquire lock trong vòng 10ms
            acquired = session._lock.acquire(timeout=0.03)
            if acquired:
                lock_accessible[0] = True
                session._lock.release()

        checker = threading.Thread(target=check_lock_task, daemon=True)
        checker.start()

        ok, msg = session.trigger_autofocus(timeout_sec=1.0)
        checker.join(timeout=0.5)

        assert ok is True
        assert "Lấy nét thành công" in msg
        assert lock_accessible[0] is True, "Khóa self._lock phải giải phóng trong chu kỳ đợi để Live View không bị treo!"

    def test_camera_page_face_eye_af_toggle_and_state_updates(self, monkeypatch, dummy_face):
        """Kiểm tra giao diện CameraPage bật/tắt Face/Eye AF và cập nhật UI chính xác."""
        from vietphotobooth.camera.manager import CameraManager
        from vietphotobooth.desktop.widgets.camera_page import CameraPage
        from vietphotobooth.camera.face_eye_af_controller import FaceEyeAFState

        # Dùng simulator để không cần camera thật trong test
        cam_mgr = CameraManager()
        cam_mgr.set_face_eye_af_enabled(False)
        page = CameraPage(cam_mgr)
        page.resize(800, 600)

        # Ban đầu Face/Eye AF tắt
        assert page._face_eye_af_enabled is False
        assert page.btn_face_eye_af.text() == "🎯 Face/Eye AF: Tắt"
        assert "TẮT" in page.lbl_face_eye_af_status.text()

        # Mock FaceDetectionService enable thành công
        monkeypatch.setattr(page._face_service, "enable", lambda: True)

        # 1. Bật Face/Eye AF
        page._toggle_face_eye_af()
        assert page._face_eye_af_enabled is True
        assert page.btn_face_eye_af.text() == "🎯 Face/Eye AF: BẬT"
        assert "ĐANG TÌM KHUÔN MẶT" in page.lbl_face_eye_af_status.text()
        assert page.lbl_viewport._face_eye_af_enabled is True

        # 2. Giả lập controller chuyển trạng thái sang FOCUSING
        page._apply_face_eye_af_state(FaceEyeAFState.FOCUSING, "Đang lấy nét...", dummy_face, dummy_face.right_eye)
        assert "ĐANG LẤY NÉT" in page.lbl_face_eye_af_status.text()
        assert page.lbl_viewport._face_eye_af_state == "FOCUSING"
        assert page.lbl_viewport._target_eye_pos == dummy_face.right_eye

        # 3. Giả lập controller chuyển trạng thái sang FOCUSED
        page._apply_face_eye_af_state(FaceEyeAFState.FOCUSED, "Khóa nét ✓", dummy_face, dummy_face.right_eye)
        assert "ĐÃ LẤY NÉT" in page.lbl_face_eye_af_status.text()
        assert page.lbl_viewport._face_eye_af_state == "FOCUSED"

        # 4. Giả lập controller chuyển trạng thái sang LOST
        page._apply_face_eye_af_state(FaceEyeAFState.LOST, "Mất dấu", None, None)
        assert "KHÔNG TÌM THẤY MẶT" in page.lbl_face_eye_af_status.text()
        assert page.lbl_viewport._face_eye_af_state == "LOST"

        # 5. Giả lập controller chuyển trạng thái sang ERROR
        page._apply_face_eye_af_state(FaceEyeAFState.ERROR, "Lỗi MF", None, None)
        assert "AF THẤT BẠI" in page.lbl_face_eye_af_status.text()
        assert page.lbl_viewport._face_eye_af_state == "ERROR"

        # 6. Tắt Face/Eye AF
        page._toggle_face_eye_af()
        assert page._face_eye_af_enabled is False
        assert page.btn_face_eye_af.text() == "🎯 Face/Eye AF: Tắt"
        assert "TẮT" in page.lbl_face_eye_af_status.text()
        assert page.lbl_viewport._face_eye_af_enabled is False

        page.close()
        cam_mgr.set_face_eye_af_enabled(True)
        cam_mgr.close()
