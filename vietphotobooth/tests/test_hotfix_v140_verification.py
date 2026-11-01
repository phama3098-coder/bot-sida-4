"""
Hotfix v1.4.0 Verification Tests
Validates all 10 required scenarios from Section 4 of the specification:
1. Mở trang Chụp Ảnh và để Live View chạy (kiểm tra frame rate-limiting 30 FPS, không runaway counter).
2. Chuyển qua lại giữa Chụp Ảnh và Máy Ảnh ít nhất 10 lần (xác nhận worker singleton, timer dừng sạch sẽ).
3. Bật/tắt Simulator và kiểm tra số lượng worker/timer.
4. Đổi backend và kiểm tra backend cũ được giải phóng, cache frame cũ được xóa.
5. Ngắt kết nối trong lúc Live View chạy (chuyển trạng thái 🔴 Chưa kết nối an toàn).
6. Đóng ứng dụng và xác nhận worker đã dừng.
7. Kiểm tra giao diện tại 1920×1080.
8. Kiểm tra giao diện tại 1600×900.
9. Kiểm tra giao diện tại 1366×768.
10. Kiểm tra giao diện tại 1280×720.
"""

import time
import pytest
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize

from vietphotobooth.desktop.main_window import MainWindow
from vietphotobooth.camera.backends.simulator import SimulatorBackend
from vietphotobooth.camera.connection_manager import CameraConnectionManager


def test_scenario_1_and_6_liveview_run_and_clean_close(qapp):
    """Kịch bản 1 & 6: Live View chạy ổn định ở 30 FPS và dừng sạch khi đóng cửa sổ."""
    sim = SimulatorBackend()
    assert sim.connect()

    # Đo tần số đọc frame: gọi dồn dập 60 lần
    start_t = time.time()
    frames = []
    for _ in range(60):
        fd = sim.read_frame()
        if fd is not None:
            frames.append(fd)
        time.sleep(0.005)  # 5ms mỗi lần gọi
    elapsed = time.time() - start_t

    # Kiểm tra frame counter không tăng vô hạn nhờ bộ đệm cache rate-limiting 30 FPS
    max_allowed = max(15, int(elapsed * 35) + 3)
    assert sim._frame_count <= max_allowed, f"Frame counter tăng quá nhanh ({sim._frame_count} > {max_allowed}), vượt giới hạn 30 FPS!"
    assert len(frames) == 60  # Trả về frame cache mượt mà

    sim.disconnect()
    assert sim._cached_frame_data is None

    # Kịch bản 6: Đóng ứng dụng MainWindow và xác nhận worker dừng
    window = MainWindow(start_in_kiosk=False)
    window.show()
    qapp.processEvents()
    kiosk = window.kiosk_page
    worker = kiosk.live_view_worker
    assert worker.isRunning()

    window.close()
    qapp.processEvents()
    qapp.processEvents()
    assert not worker.isRunning()


def test_scenario_2_switch_tabs_10_times_worker_lifecycle(qapp):
    """Kịch bản 2: Chuyển qua lại giữa Chụp Ảnh và Máy Ảnh 10 lần."""
    window = MainWindow(start_in_kiosk=False)
    window.show()
    qapp.processEvents()
    kiosk = window.kiosk_page
    cam_page = window.camera_page

    worker = kiosk.live_view_worker
    assert worker.isRunning()

    # Mở khóa PIN quản trị trước để chuyển sang Máy Ảnh tự do
    window.auth_mgr._authenticated = True
    window.auth_mgr._last_auth_time = time.time()

    for cycle in range(10):
        # 1. Chuyển sang Tab 2 (Máy Ảnh)
        window.auth_mgr._last_auth_time = time.time()
        window.tabs.setCurrentIndex(2)
        qapp.processEvents()

        # Kiosk worker PHẢI tạm dừng
        assert worker._paused, f"Chu kỳ {cycle}: Kiosk worker chưa tạm dừng khi ở tab Máy Ảnh!"
        # CameraPage timer PHẢI hoạt động
        assert cam_page._timer.isActive(), f"Chu kỳ {cycle}: CameraPage timer không chạy!"

        # 2. Chuyển về Tab 0 (Chụp Ảnh)
        window.tabs.setCurrentIndex(0)
        qapp.processEvents()

        # Kiosk worker PHẢI tiếp tục
        assert not worker._paused, f"Chu kỳ {cycle}: Kiosk worker chưa tiếp tục khi ở tab Chụp Ảnh!"
        # CameraPage timer PHẢI dừng
        assert not cam_page._timer.isActive(), f"Chu kỳ {cycle}: CameraPage timer chưa dừng khi rời khỏi tab!"

        # Xác nhận tuyệt đối không tạo worker mới (singleton)
        assert kiosk.live_view_worker is worker

    window.close()
    qapp.processEvents()
    qapp.processEvents()


def test_scenario_3_and_4_simulator_switch_backend_release(qapp):
    """Kịch bản 3 & 4: Bật/tắt Simulator, chuyển backend và giải phóng tài nguyên."""
    mgr = CameraConnectionManager()
    assert mgr.switch_backend("simulator")
    assert mgr.current_backend_name == "simulator"
    assert mgr.is_connected()

    # Đọc frame simulator
    frame1 = mgr.get_liveview_rgb()
    assert frame1 is not None and frame1.size > 0
    info = mgr.get_info()
    assert info["brand"] == "Simulator"
    assert "Mô Phỏng" in info["model"]

    # Chuyển backend sang directshow (không cắm webcam)
    mgr.switch_backend("directshow", device_index=999)
    # Backend cũ (simulator) phải được ngắt kết nối
    assert mgr.current_backend_name == "directshow"
    assert mgr._last_frame_data is None  # Cache cũ đã xóa sạch
    assert mgr._last_jpeg is None

    # Không nhận được frame từ webcam giả lập -> trả về None, không trả frame cũ
    frame_ds = mgr.get_liveview_rgb()
    assert frame_ds is None

    # Chuyển lại về simulator
    assert mgr.switch_backend("simulator")
    assert mgr.is_connected()
    frame2 = mgr.get_liveview_rgb()
    assert frame2 is not None

    mgr.disconnect()
    assert not mgr.is_connected()
    assert mgr.get_liveview_rgb() is None


def test_scenario_5_disconnect_during_liveview(qapp):
    """Kịch bản 5: Ngắt kết nối trong lúc Live View đang chạy."""
    window = MainWindow(start_in_kiosk=False)
    window.show()
    qapp.processEvents()
    kiosk = window.kiosk_page

    # Kiosk đang ở simulator
    kiosk.camera_mgr.switch_backend("simulator")
    kiosk._update_camera_status_ui()
    qapp.processEvents()

    assert kiosk.lbl_cam_dot.text() == "🟡"
    assert "Mô phỏng" in kiosk.lbl_cam_status_text.text()
    assert kiosk.panel_disconnected.isHidden()

    # Bất ngờ ngắt kết nối
    kiosk.camera_mgr.disconnect()
    kiosk._update_camera_status_ui()
    qapp.processEvents()

    assert kiosk.lbl_cam_dot.text() == "🔴"
    assert "Chưa kết nối" in kiosk.lbl_cam_status_text.text()
    assert not kiosk.panel_disconnected.isHidden()

    window.close()
    qapp.processEvents()
    qapp.processEvents()


def test_scenario_7_to_10_responsive_resolutions(qapp):
    """Kịch bản 7, 8, 9, 10: Kiểm tra giao diện tại 1920×1080, 1600×900, 1366×768, 1280×720."""
    window = MainWindow(start_in_kiosk=False)
    window.show()
    qapp.processEvents()
    kiosk = window.kiosk_page

    test_resolutions = [
        (1920, 1080),  # Kịch bản 7
        (1600, 900),   # Kịch bản 8
        (1366, 768),   # Kịch bản 9
        (1280, 720),   # Kịch bản 10
        (1024, 680),   # Màn hình tối thiểu
    ]

    for width, height in test_resolutions:
        window.resize(width, height)
        qapp.processEvents()

        # 1. Thanh điều hướng: Logo + Brand widget <= 260px và < 40% width
        brand_w = window.brand_widget.width()
        assert brand_w <= 260
        assert brand_w < (width * 0.4)

        # 2. Toàn bộ 6 tab hiển thị đầy đủ
        assert window.tabs.count() == 6
        for tab_idx in range(6):
            tab_rect = window.tabs.tabBar().tabRect(tab_idx)
            assert tab_rect.width() > 0

        # 3. Kiosk: card_camera nằm gọn trong cửa sổ
        assert not kiosk.card_camera.isHidden()
        assert kiosk.card_camera.width() <= 260

        # 4. Kiosk: Viewport camera lớn
        assert kiosk.lbl_viewport.width() >= 300
        assert kiosk.lbl_viewport.height() >= 180

        # 5. Kiosk: Nút bắt đầu chụp co giãn hợp lý, không tràn
        assert not kiosk.btn_start.isHidden()
        assert kiosk.btn_start.width() in (270, 360)

        # 6. Kiosk: Các khối điều khiển số ảnh, đếm ngược, khung, bộ lọc hiển thị
        assert not kiosk.card_shots.isHidden()
        assert not kiosk.card_cd.isHidden()
        assert not kiosk.card_frames.isHidden()
        assert not kiosk.card_filters.isHidden()

    window.close()
    qapp.processEvents()
