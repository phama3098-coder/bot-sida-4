"""
1998 TEAM — Studio Audio & Frame Gallery Final Verification
Automated test suite covering all architecture overhaul specifications:
1. Exactly once per capture transaction
2. Capture rejected (no shutter sound)
3. Capture started (shutter sound exactly once)
4. Duplicate callback suppression
5. Retry with new transaction
6. Countdown voice prompt once (no double trigger at mark 3)
7. Cancel countdown stops audio
8. Audio disabled handling
9. Audio error handling (QSoundEffect status error tolerance)
10. Settings live synchronization
11. Lifecycle cleanup
12. Non-blocking GUI execution
13. Frame gallery header styling and cluster structure
"""

import os
import time
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QWidget, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtMultimedia import QSoundEffect
from PIL import Image

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.audio.constants import SOUND_SHUTTER, SOUND_VOICE, SOUND_TICK
from vietphotobooth.audio.sound_controller import SoundController
from vietphotobooth.desktop.widgets.kiosk_page import KioskPage
from vietphotobooth.desktop.widgets.settings_page import SettingsPage
from vietphotobooth.desktop.widgets.frame_gallery_page import FrameGalleryPage
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.camera.backends.simulator import SimulatorBackend
from vietphotobooth.filters.filter_engine import FilterEngine
from vietphotobooth.core.events import EventManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.printing.manager import PrintManager


@pytest.fixture
def temp_config(tmp_path):
    cfg_file = str(tmp_path / "test_audio_final_config.json")
    return ConfigManager(cfg_file)


class TestAudioArchitectureFinal:

    def test_01_exactly_once_per_transaction(self, qapp, temp_config):
        """1. Chỉ phát duy nhất 1 lần âm thanh màn trập cho mỗi Transaction ID."""
        sc = SoundController(config_mgr=temp_config)
        try:
            with patch.object(sc, "play_shutter", return_value=True) as mock_play:
                tx_id = "tx_test_001"
                # Lần gọi thứ nhất -> Thành công
                assert sc.play_shutter_for_transaction(tx_id) is True
                assert mock_play.call_count == 1
                assert sc.is_transaction_played(tx_id) is True

                # Lần gọi thứ hai cho cùng tx_id -> Bị chặn (False), không gọi play_shutter thêm lần nào
                assert sc.play_shutter_for_transaction(tx_id) is False
                assert mock_play.call_count == 1
        finally:
            sc.cleanup()

    def test_02_capture_rejected_no_shutter(self, qapp, temp_config):
        """2. Khi camera từ chối lệnh chụp hoặc bị ngắt kết nối -> KHÔNG phát âm thanh."""
        cam_mgr = CameraManager()
        flt_eng = FilterEngine()
        frm_mgr = FrameManager()
        evt_mgr = EventManager()
        tok_mgr = TokenManager()
        prn_mgr = PrintManager()
        kiosk = None

        try:
            kiosk = KioskPage(
                camera_mgr=cam_mgr,
                filter_engine=flt_eng,
                frame_mgr=frm_mgr,
                print_mgr=prn_mgr,
                event_mgr=evt_mgr,
                token_mgr=tok_mgr,
                config_mgr=temp_config
            )
            kiosk.stop_live_view()

            with patch.object(cam_mgr, "capture_photo", return_value=(False, None)), \
                 patch.object(kiosk.sound_controller, "play_shutter_for_transaction") as mock_play_tx, \
                 patch.object(kiosk.sound_controller, "play_shutter") as mock_play, \
                 patch("PySide6.QtWidgets.QMessageBox.warning"):
                kiosk._execute_photo_capture("dummy.jpg", tx_id="tx_rejected_01")
                mock_play_tx.assert_not_called()
                mock_play.assert_not_called()
        finally:
            if kiosk:
                kiosk.cleanup()
                kiosk.close()
            cam_mgr.close()

    def test_03_capture_started_exactly_once(self, qapp, temp_config):
        """3. Khi camera xác nhận bắt đầu chụp (on_capture_start) -> Phát đúng 1 lần."""
        cam_mgr = CameraManager()
        flt_eng = FilterEngine()
        frm_mgr = FrameManager()
        evt_mgr = EventManager()
        tok_mgr = TokenManager()
        prn_mgr = PrintManager()
        kiosk = None

        try:
            kiosk = KioskPage(
                camera_mgr=cam_mgr,
                filter_engine=flt_eng,
                frame_mgr=frm_mgr,
                print_mgr=prn_mgr,
                event_mgr=evt_mgr,
                token_mgr=tok_mgr,
                config_mgr=temp_config
            )
            kiosk.stop_live_view()

            def mock_capture(save_path, on_capture_start=None, **kwargs):
                if on_capture_start:
                    on_capture_start()
                return True, Image.new("RGB", (100, 100), (255, 255, 255))

            with patch.object(cam_mgr, "capture_photo", side_effect=mock_capture), \
                 patch.object(kiosk.sound_controller, "play_shutter", return_value=True) as mock_play, \
                 patch("PIL.Image.Image.save"), \
                 patch("os.path.exists", return_value=True), \
                 patch("os.path.getsize", return_value=5000), \
                 patch("PIL.Image.open") as mock_open:
                mock_open.return_value.__enter__.return_value = MagicMock()
                kiosk._execute_photo_capture("dummy.jpg", tx_id="tx_started_01")
                assert mock_play.call_count == 1
        finally:
            if kiosk:
                kiosk.cleanup()
                kiosk.close()
            cam_mgr.close()

    def test_04_duplicate_callback_suppression(self, qapp, temp_config):
        """4. Triệt tiêu toàn bộ callback trùng lặp từ phần cứng cho cùng một transaction."""
        sc = SoundController(config_mgr=temp_config)
        try:
            with patch.object(sc, "play_shutter", return_value=True) as mock_play:
                tx_id = "tx_dup_callback"
                # Giả lập 5 callback dồn dập từ driver/threads
                r1 = sc.play_shutter_for_transaction(tx_id)
                r2 = sc.play_shutter_for_transaction(tx_id)
                r3 = sc.play_shutter_for_transaction(tx_id)
                r4 = sc.play_shutter_for_transaction(tx_id)
                r5 = sc.play_shutter_for_transaction(tx_id)

                assert r1 is True
                assert r2 is False and r3 is False and r4 is False and r5 is False
                assert mock_play.call_count == 1
        finally:
            sc.cleanup()

    def test_05_retry_with_new_transaction(self, qapp, temp_config):
        """5. Khi chụp lại (Retry), transaction mới được cấp phép phát âm thanh bình thường."""
        sc = SoundController(config_mgr=temp_config)
        try:
            with patch.object(sc, "play_shutter", return_value=True) as mock_play:
                tx_initial = "tx_shot_1_attempt_1"
                tx_retry = "tx_shot_1_attempt_2"

                assert sc.play_shutter_for_transaction(tx_initial) is True
                assert sc.play_shutter_for_transaction(tx_retry) is True
                assert mock_play.call_count == 2
        finally:
            sc.cleanup()

    def test_06_countdown_voice_once(self, qapp, temp_config):
        """6. Giọng nói hướng dẫn 'Ba, hai, một. Cười lên nào!' chỉ phát đúng 1 lần tại mốc 3."""
        cam_mgr = CameraManager()
        flt_eng = FilterEngine()
        frm_mgr = FrameManager()
        evt_mgr = EventManager()
        tok_mgr = TokenManager()
        prn_mgr = PrintManager()
        kiosk = None

        try:
            kiosk = KioskPage(
                camera_mgr=cam_mgr,
                filter_engine=flt_eng,
                frame_mgr=frm_mgr,
                print_mgr=prn_mgr,
                event_mgr=evt_mgr,
                token_mgr=tok_mgr,
                config_mgr=temp_config
            )
            kiosk.stop_live_view()
            kiosk.sound_controller.play_voice_prompt = MagicMock(return_value=True)
            kiosk.sound_controller.play_tick = MagicMock(return_value=True)

            # Trường hợp 1: Countdown bắt đầu từ 3
            kiosk.countdown_duration = 3
            kiosk._start_single_shot_countdown()
            kiosk.countdown_timer.stop()
            assert kiosk.sound_controller.play_voice_prompt.call_count == 1

            # Tick 1 (giảm từ 3 xuống 2) -> KHÔNG phát lại voice prompt
            kiosk.sound_controller.play_voice_prompt.reset_mock()
            kiosk._on_countdown_tick()
            assert kiosk.countdown_remaining == 2
            kiosk.sound_controller.play_voice_prompt.assert_not_called()

            # Trường hợp 2: Countdown bắt đầu từ 5
            kiosk.sound_controller.play_voice_prompt.reset_mock()
            kiosk.countdown_duration = 5
            kiosk._start_single_shot_countdown()
            kiosk.countdown_timer.stop()
            kiosk.sound_controller.play_voice_prompt.assert_not_called()

            # Tick giảm về 4
            kiosk._on_countdown_tick()
            assert kiosk.countdown_remaining == 4
            kiosk.sound_controller.play_voice_prompt.assert_not_called()

            # Tick giảm về 3 -> Phát voice prompt đúng 1 lần
            kiosk._on_countdown_tick()
            assert kiosk.countdown_remaining == 3
            assert kiosk.sound_controller.play_voice_prompt.call_count == 1

            # Tick giảm tiếp về 2 -> KHÔNG phát thêm lần nào nữa
            kiosk._on_countdown_tick()
            assert kiosk.countdown_remaining == 2
            assert kiosk.sound_controller.play_voice_prompt.call_count == 1
        finally:
            if kiosk:
                kiosk.cleanup()
                kiosk.close()
            cam_mgr.close()

    def test_07_cancel_stops_audio(self, qapp, temp_config):
        """7. Hủy countdown hoặc ngắt kết nối lập tức dừng mọi âm thanh đang phát."""
        cam_mgr = CameraManager()
        flt_eng = FilterEngine()
        frm_mgr = FrameManager()
        evt_mgr = EventManager()
        tok_mgr = TokenManager()
        prn_mgr = PrintManager()
        kiosk = None

        try:
            kiosk = KioskPage(
                camera_mgr=cam_mgr,
                filter_engine=flt_eng,
                frame_mgr=frm_mgr,
                print_mgr=prn_mgr,
                event_mgr=evt_mgr,
                token_mgr=tok_mgr,
                config_mgr=temp_config
            )
            kiosk.stop_live_view()
            with patch.object(kiosk.sound_controller, "stop_all") as mock_stop:
                kiosk.countdown_duration = 5
                kiosk._start_single_shot_countdown()
                assert kiosk.countdown_timer.isActive()

                # Gọi cancel_countdown
                kiosk.cancel_countdown()
                assert not kiosk.countdown_timer.isActive()
                mock_stop.assert_called_once()
                assert getattr(kiosk, "_active_capture_tx", None) is None
                assert getattr(kiosk, "_active_capture_tx_id", None) is None
        finally:
            if kiosk:
                kiosk.cleanup()
                kiosk.close()
            cam_mgr.close()

    def test_08_audio_disabled_handling(self, qapp, temp_config):
        """8. Khi tắt âm thanh hoặc tắt riêng shutter, play_shutter_for_transaction trả về False an toàn."""
        sc = SoundController(config_mgr=temp_config)
        try:
            with patch.object(sc, "play_shutter", return_value=True) as mock_play:
                # Toàn bộ âm thanh bị tắt
                sc.enabled = False
                assert sc.play_shutter_for_transaction("tx_dis_01") is False
                mock_play.assert_not_called()

                # Shutter bị tắt riêng
                sc.enabled = True
                sc.shutter_enabled = False
                assert sc.play_shutter_for_transaction("tx_dis_02") is False
                mock_play.assert_not_called()
        finally:
            sc.cleanup()

    def test_09_audio_error_handling(self, qapp, temp_config):
        """9. Khi driver hoặc codec báo lỗi QSoundEffect.Status.Error, hệ thống không crash và bỏ qua an toàn."""
        sc = SoundController(config_mgr=temp_config)
        try:
            effect = sc._effects.get(SOUND_SHUTTER)
            if effect:
                with patch.object(effect, "status", return_value=QSoundEffect.Status.Error):
                    assert sc.get_effect_status(SOUND_SHUTTER) == "ERROR"
                    assert sc.is_effect_ready(SOUND_SHUTTER) is False
                    assert sc.play_sound(SOUND_SHUTTER) is False
        finally:
            sc.cleanup()

    def test_10_settings_live_sync(self, qapp, temp_config):
        """10. Thay đổi cài đặt âm thanh trong SettingsPage tự động đồng bộ Live Sync sang SoundController."""
        tok_mgr = TokenManager()
        sp = SettingsPage(config_mgr=temp_config, token_mgr=tok_mgr)
        sc = SoundController(config_mgr=temp_config)

        try:
            signals_received = []
            sp.audio_settings_changed.connect(lambda: signals_received.append(True))

            # Điều chỉnh âm lượng từ 80% về 45%
            sp.spin_audio_volume.setValue(45)
            assert len(signals_received) >= 1
            assert abs(temp_config.get("audio.volume") - 0.45) < 1e-4

            # Đồng bộ sang SoundController
            sc.sync_with_config(temp_config)
            assert abs(sc.volume - 0.45) < 1e-4

            # Tắt âm thanh màn trập
            sp.chk_audio_shutter.setChecked(False)
            sc.sync_with_config(temp_config)
            assert sc.shutter_enabled is False
        finally:
            sp.close()
            sc.cleanup()

    def test_11_lifecycle_cleanup(self, qapp, temp_config):
        """11. Cleanup giải phóng hoàn toàn bộ đệm âm thanh và transaction đệm mà không rò rỉ bộ nhớ."""
        sc = SoundController(config_mgr=temp_config)
        sc.play_shutter_for_transaction("tx_cleanup_01")
        assert len(sc._shutter_transactions) == 1
        assert len(sc._effects) > 0

        sc.cleanup()
        assert len(sc._effects) == 0
        assert len(sc._shutter_transactions) == 0
        assert sc._current_active_transaction is None

    def test_12_non_blocking_gui(self, qapp, temp_config):
        """12. Thực thi âm thanh hoàn toàn không khóa GUI thread (đo thời gian thực thi < 25ms)."""
        sc = SoundController(config_mgr=temp_config)
        try:
            t0 = time.perf_counter()
            sc.play_tick()
            sc.play_voice_prompt()
            sc.play_shutter_for_transaction("tx_perf_01")
            dt = (time.perf_counter() - t0) * 1000.0
            # Gọi API âm thanh phải là async, dưới 25ms trên luồng chính
            assert dt < 25.0, f"Thao tác âm thanh tốn quá nhiều thời gian: {dt:.2f}ms"
        finally:
            sc.cleanup()

    def test_13_frame_gallery_header_cluster(self, qapp, temp_config):
        """13. Header Frame Gallery: cụm thống nhất, không có border/nền thừa ở tiêu đề, mô tả và icon."""
        fm = FrameManager()
        page = FrameGalleryPage(frame_mgr=fm, config_mgr=temp_config)
        try:
            assert hasattr(page, "header_cluster")
            assert page.header_cluster is not None

            # Kiểm tra cluster có style trong suốt và không border
            cluster_ss = page.header_cluster.styleSheet()
            assert "border: none" in cluster_ss
            assert "background: transparent" in cluster_ss

            # Kiểm tra icon, title, subtitle bên trong
            icon_lbl = page.findChild(QLabel, "frame_gallery_header_icon")
            title_lbl = page.findChild(QLabel, "frame_gallery_title")
            sub_lbl = page.findChild(QLabel, "frame_gallery_subtitle")

            assert icon_lbl is not None
            assert title_lbl is not None
            assert sub_lbl is not None

            assert "border: none" in icon_lbl.styleSheet()
            assert "border: none" in title_lbl.styleSheet()
            assert "border: none" in sub_lbl.styleSheet()
            assert "background: transparent" in title_lbl.styleSheet()
            assert "background: transparent" in sub_lbl.styleSheet()
        finally:
            page.close()
