"""
Test suite for Minimal Luxury Operator Dashboard (Stage 2.2 Integration)
Verifies:
1. Widget hierarchy and Reusable Cards integration.
2. LIVE / DEMO / N/A state accuracy.
3. Camera disconnected detection and recovery.
4. Printer unavailable and low paper alert handling.
5. Storage low disk space warning banner behavior.
6. Responsive rendering at 1920x1080 and 1366x768.
7. Non-blocking resilience when hardware managers throw exceptions.
"""

from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.desktop.widgets.dashboard_page import DashboardPage
from vietphotobooth.desktop.widgets.minimal_luxury_cards import (
    SurfaceCard, SecondaryCard, StatCardMetric, AlertBannerWidget
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dashboard_widget_hierarchy_and_cards(qapp):
    """Verify DashboardPage initializes all Minimal Luxury cards, banners, and buttons."""
    page = DashboardPage(config_mgr=ConfigManager())
    assert page.scroll_area is not None
    assert page.btn_start_kiosk is not None
    assert page.disclaimer_banner is not None
    assert page.viewport is not None

    # Stat cards
    assert isinstance(page.card_event, StatCardMetric)
    assert isinstance(page.card_sessions, StatCardMetric)
    assert isinstance(page.card_prints, StatCardMetric)
    assert isinstance(page.card_paper, StatCardMetric)

    # Alert banners
    assert isinstance(page.alert_cam_disconnect, AlertBannerWidget)
    assert isinstance(page.alert_printer_error, AlertBannerWidget)
    assert isinstance(page.alert_storage_warning, AlertBannerWidget)

    page.close()


def test_dashboard_live_demo_na_state_handling(qapp):
    """Verify data transparency: LIVE when connected, N/A when offline, DEMO only when enabled."""
    # 1. Without managers -> N/A mode
    page_offline = DashboardPage(camera_mgr=None, print_mgr=None, event_mgr=None)
    page_offline.update_telemetry()

    assert page_offline.card_paper.badge_mode == "N/A"
    assert page_offline.card_paper.lbl_val.text() == "--"
    assert "Offline" in page_offline.card_paper.lbl_sub.text()

    # 2. Demo mode enabled in config
    cfg_demo = ConfigManager()
    cfg_demo.set("developer_mock_mode", True)
    page_demo = DashboardPage(config_mgr=cfg_demo)
    page_demo.update_telemetry()

    assert page_demo.card_event.badge_mode == "DEMO"
    assert page_demo.card_sessions.badge_mode == "DEMO"

    # 3. Live event manager connected
    mock_event = MagicMock()
    mock_event.get_active_event_name.return_value = "Wedding_Rose_2026"
    mock_event.get_event_stats.return_value = {
        "total_final_photos": 48,
        "total_prints": 96
    }
    mock_event.check_disk_space.return_value = {
        "free_gb": 45.0,
        "total_gb": 512.0,
        "percent_used": 15.0,
        "is_warning": False
    }

    cfg_live = ConfigManager()
    cfg_live.set("developer_mock_mode", False)
    page_live = DashboardPage(event_mgr=mock_event, config_mgr=cfg_live)
    page_live.update_telemetry()

    assert page_live.card_event.badge_mode == "LIVE"
    assert page_live.card_event.lbl_val.text() == "Wedding_Rose_2026"
    assert page_live.card_sessions.lbl_val.text() == "48"
    assert page_live.card_prints.lbl_val.text() == "96"

    page_offline.close()
    page_demo.close()
    page_live.close()


def test_dashboard_camera_disconnected_and_recovery(qapp):
    """Verify camera disconnection shows alert banner, updates pill, and hides when reconnected."""
    mock_cam = MagicMock()
    mock_cam.is_connected.return_value = False
    mock_cam.get_info.return_value = {}

    page = DashboardPage(camera_mgr=mock_cam)
    page.update_telemetry()

    # Disconnected state
    assert page.alert_cam_disconnect.isHidden() is False
    assert "DISCONNECTED" in page.pill_cam.lbl_badge.text()
    assert "ngắt kết nối" in page.lbl_ct_val.text()

    # Recovery
    mock_cam.is_connected.return_value = True
    mock_cam.get_info.return_value = {
        "model": "Nikon D780",
        "battery_level": 92,
        "shutter_speed": "1/160s",
        "aperture": "f/2.8",
        "iso": "ISO 200"
    }
    page.update_telemetry()

    assert page.alert_cam_disconnect.isHidden() is True
    assert "CONNECTED" in page.pill_cam.lbl_badge.text()
    assert "92% Pin" in page.pill_cam.lbl_subtitle.text()
    assert "1/160s" in page.lbl_ct_val.text()

    page.close()


def test_dashboard_printer_unavailable_and_paper_alert(qapp):
    """Verify printer offline shows N/A, and paper < 25 triggers alert banner."""
    mock_prn = MagicMock()
    cfg = ConfigManager()

    # 1. Offline printer
    mock_prn.get_selected_printer.return_value = ""
    page = DashboardPage(print_mgr=mock_prn, config_mgr=cfg)
    page.update_telemetry()

    assert page.card_paper.badge_mode == "N/A"
    assert page.alert_printer_error.isHidden() is True
    assert "OFFLINE" in page.pill_prn.lbl_badge.text()

    # 2. Online printer with low paper (e.g. 15 remaining) - No hardware sensor -> MANUAL mode
    mock_prn.get_selected_printer.return_value = "DNP DS-RX1HS"
    mock_prn.has_hardware_paper_sensor.return_value = False
    cfg.set("printer_paper_remaining", 15)
    page.update_telemetry()

    assert page.card_paper.badge_mode == "MANUAL"
    assert "Nhập thủ công" in page.card_paper.lbl_sub.text()
    assert "15 / 700" in page.card_paper.lbl_val.text()
    assert page.alert_printer_error.isHidden() is False
    assert "15 bản in" in page.alert_printer_error.lbl_message.text()

    # 3. Hardware sensor supported -> LIVE mode
    mock_prn.has_hardware_paper_sensor.return_value = True
    page.update_telemetry()
    assert page.card_paper.badge_mode == "LIVE"
    assert "Cảm biến HW" in page.card_paper.lbl_sub.text()

    # 4. Paper refilled to 700
    cfg.set("printer_paper_remaining", 700)
    page.update_telemetry()

    assert page.alert_printer_error.isHidden() is True
    assert "700 / 700" in page.card_paper.lbl_val.text()

    page.close()


def test_dashboard_storage_warning_behavior(qapp):
    """Verify disk space < 2.0 GB shows warning banner, and normal space hides it."""
    mock_event = MagicMock()
    mock_event.get_active_event_name.return_value = "SuKien_Test"
    mock_event.get_event_stats.return_value = {"total_final_photos": 10, "total_prints": 20}

    # Low storage
    mock_event.check_disk_space.return_value = {
        "free_gb": 1.4,
        "total_gb": 500.0,
        "percent_used": 99.7,
        "is_warning": True
    }
    page = DashboardPage(event_mgr=mock_event)
    page.update_telemetry()

    assert page.alert_storage_warning.isHidden() is False
    assert "1.4 GB" in page.alert_storage_warning.lbl_message.text()

    # Normal storage
    mock_event.check_disk_space.return_value = {
        "free_gb": 85.0,
        "total_gb": 500.0,
        "percent_used": 83.0,
        "is_warning": False
    }
    page.update_telemetry()

    assert page.alert_storage_warning.isHidden() is True

    page.close()


def test_dashboard_responsive_rendering(qapp):
    """Verify DashboardPage renders cleanly without clipping at 1920x1080 and 1366x768."""
    page = DashboardPage(config_mgr=ConfigManager())

    for w, h in [(1920, 1080), (1366, 768)]:
        page.resize(w, h)
        page.show()
        qapp.processEvents()

        assert page.width() == w
        assert page.height() == h
        assert page.scroll_area.width() == w

        pixmap = page.grab()
        assert not pixmap.isNull()
        assert pixmap.width() == w
        assert pixmap.height() == h

    page.close()


def test_dashboard_non_blocking_on_hardware_failure(qapp):
    """Verify update_telemetry and tick do not freeze UI or throw when managers fail."""
    faulty_cam = MagicMock()
    faulty_cam.is_connected.side_effect = RuntimeError("USB Connection Timeout")
    faulty_cam.get_liveview_rgb.side_effect = Exception("Driver Worker Crash")

    faulty_prn = MagicMock()
    faulty_prn.get_selected_printer.side_effect = OSError("Spooler RPC Failure")

    faulty_evt = MagicMock()
    faulty_evt.get_active_event_name.side_effect = ValueError("Corrupted Event DB")
    faulty_evt.check_disk_space.side_effect = PermissionError("Disk Access Denied")

    page = DashboardPage(
        camera_mgr=faulty_cam,
        print_mgr=faulty_prn,
        event_mgr=faulty_evt
    )

    # Calling update_telemetry and _on_telemetry_tick should be completely safe
    page.update_telemetry()
    page._on_telemetry_tick()

    # UI remains responsive and functional
    assert page.btn_start_kiosk.isEnabled() is True
    assert page.card_paper.badge_mode == "N/A"
    assert page.card_event.lbl_val.text() == "Lỗi đọc đĩa"
    assert page.card_event.badge_mode == "ERROR"
    assert page.card_sessions.lbl_val.text() == "ERROR"
    assert page.card_sessions.badge_mode == "ERROR"
    assert page.card_prints.lbl_val.text() == "ERROR"
    assert page.card_prints.badge_mode == "ERROR"

    page.close()


def test_dashboard_event_zero_photos_vs_error(qapp):
    """Verify distinct semantics between genuine 0 photos vs disk read failure."""
    # 1. Event genuinely has 0 photos
    mock_event = MagicMock()
    mock_event.get_active_event_name.return_value = "Event_Brand_New"
    mock_event.get_event_stats.return_value = {
        "total_final_photos": 0,
        "total_prints": 0
    }
    mock_event.check_disk_space.return_value = {"free_gb": 50.0, "percent_used": 10.0, "is_warning": False}

    cfg = ConfigManager()
    cfg.set("developer_mock_mode", False)
    page = DashboardPage(event_mgr=mock_event, config_mgr=cfg)
    page.update_telemetry()

    assert page.card_event.badge_mode == "LIVE"
    assert page.card_sessions.lbl_val.text() == "0"
    assert page.card_sessions.badge_mode == "LIVE"
    assert "Chưa có ảnh (sẵn sàng đón khách)" in page.card_sessions.lbl_sub.text()
    assert page.card_prints.lbl_val.text() == "0"

    # 2. Disk read failure occurs on get_event_stats
    mock_event.get_event_stats.side_effect = PermissionError("EACCES: Permission denied accessing storage")
    page.update_telemetry()

    assert page.card_event.lbl_val.text() == "Lỗi đọc đĩa"
    assert page.card_event.badge_mode == "ERROR"
    assert page.card_sessions.lbl_val.text() == "ERROR"
    assert page.card_sessions.badge_mode == "ERROR"
    assert "Lỗi truy xuất dữ liệu đĩa" in page.card_sessions.lbl_sub.text()
    assert page.card_prints.lbl_val.text() == "ERROR"
    assert page.card_prints.badge_mode == "ERROR"

    page.close()
