"""
1998 TEAM — Photobooth v1.6.6 Studio Audio System Verification
Unit, Integration, and Hardware-Fault-Tolerance Tests for Studio Audio:
- SoundController initialization, configuration persistence, volume clamping.
- Audio assets resolution and validity (tick, voice, shutter).
- Safe asynchronous execution and fault tolerance when audio hardware/files are missing.
- Kiosk countdown and capture flow synchronization.
- Settings page audio controls and persistence.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.audio.constants import (
    SOUND_TICK, SOUND_VOICE, SOUND_SHUTTER, get_sound_file_path, get_asset_base_path
)
from vietphotobooth.audio.sound_controller import SoundController


@pytest.fixture(autouse=True)
def clean_qt_audio(qapp):
    yield
    qapp.processEvents()


@pytest.fixture
def temp_config(tmp_path):
    cfg_file = str(tmp_path / "test_audio_config.json")
    cm = ConfigManager(cfg_file)
    return cm


class TestStudioAudioSystem:

    def test_audio_assets_exist_and_valid(self):
        """Kiểm tra các tệp âm thanh phòng studio tồn tại trên đĩa và có dung lượng hợp lệ."""
        for key in (SOUND_TICK, SOUND_VOICE, SOUND_SHUTTER):
            p = get_sound_file_path(key)
            assert os.path.exists(p), f"Tệp âm thanh '{key}' không tồn tại tại: {p}"
            sz = os.path.getsize(p)
            assert sz > 1000, f"Tệp âm thanh '{key}' có dung lượng quá nhỏ ({sz} bytes)"

    def test_sound_controller_initialization_defaults(self, qapp):
        """Khởi tạo SoundController mặc định khi chưa có config."""
        sc = SoundController(config_mgr=None)
        try:
            assert sc.enabled is True
            assert sc.volume == 0.8
            assert sc.tick_enabled is True
            assert sc.voice_enabled is True
            assert sc.shutter_enabled is True
            assert SOUND_TICK in sc._effects
            assert SOUND_VOICE in sc._effects
            assert SOUND_SHUTTER in sc._effects
        finally:
            sc.cleanup()

    def test_sound_controller_config_persistence(self, qapp, temp_config):
        """Đọc và ghi cấu hình âm thanh với ConfigManager."""
        temp_config.set("audio.enabled", False)
        temp_config.set("audio.volume", 0.65)
        temp_config.set("audio.tick_enabled", False)
        temp_config.set("audio.voice_enabled", True)
        temp_config.set("audio.shutter_enabled", False)

        sc = SoundController(config_mgr=temp_config)
        try:
            assert sc.enabled is False
            assert abs(sc.volume - 0.65) < 1e-4
            assert sc.tick_enabled is False
            assert sc.voice_enabled is True
            assert sc.shutter_enabled is False

            # Thay đổi giá trị và lưu lại
            sc.set_enabled(True)
            sc.set_volume(0.9)
            sc.tick_enabled = True
            sc.save_settings()

            assert temp_config.get("audio.enabled") is True
            assert abs(temp_config.get("audio.volume") - 0.9) < 1e-4
            assert temp_config.get("audio.tick_enabled") is True
        finally:
            sc.cleanup()

    def test_volume_clamping(self, qapp):
        """Âm lượng luôn được khống chế an toàn trong khoảng [0.0, 1.0]."""
        sc = SoundController()
        try:
            sc.set_volume(-0.5)
            assert sc.volume == 0.0

            sc.set_volume(1.8)
            assert sc.volume == 1.0

            sc.set_volume(0.55)
            assert abs(sc.volume - 0.55) < 1e-4
        finally:
            sc.cleanup()

    def test_playback_non_blocking_and_flags(self, qapp):
        """Kiểm tra cờ bật/tắt khi gọi các hàm phát âm thanh."""
        sc = SoundController()
        try:
            # Khi tắt toàn bộ âm thanh
            sc.enabled = False
            assert sc.play_tick() is False
            assert sc.play_voice_prompt() is False
            assert sc.play_shutter() is False

            # Khi bật toàn bộ
            sc.enabled = True
            assert sc.play_tick() is True
            assert sc.play_voice_prompt() is True
            assert sc.play_shutter() is True

            # Khi tắt riêng từng hiệu ứng
            sc.tick_enabled = False
            assert sc.play_tick() is False
            assert sc.play_voice_prompt() is True

            sc.voice_enabled = False
            assert sc.play_voice_prompt() is False

            sc.shutter_enabled = False
            assert sc.play_shutter() is False
        finally:
            sc.cleanup()

    def test_defensive_fault_tolerance(self, qapp):
        """Kiểm tra khả năng chịu lỗi phòng vệ tuyệt đối khi tệp âm thanh thiếu hoặc hỏng."""
        sc = SoundController()
        try:
            # Khóa không hợp lệ
            res = sc.play_sound("unknown_key_xyz")
            assert res is False

            # Giả lập nạp tệp không tồn tại
            with patch("vietphotobooth.audio.sound_controller.get_sound_file_path", return_value="C:/non_existent_path.wav"):
                loaded = sc._load_effect("fake_sound")
                assert loaded is None
        finally:
            sc.cleanup()

    def test_kiosk_audio_integration(self, qapp, temp_config):
        """Kiểm tra tích hợp âm thanh trong luồng đếm ngược và chụp của KioskPage."""
        from vietphotobooth.desktop.widgets.kiosk_page import KioskPage
        from vietphotobooth.camera.manager import CameraManager
        from vietphotobooth.filters.filter_engine import FilterEngine
        from vietphotobooth.frames.frame_manager import FrameManager
        from vietphotobooth.core.events import EventManager
        from vietphotobooth.sharing.token_manager import TokenManager
        from vietphotobooth.printing.manager import PrintManager

        cam_mgr = CameraManager()
        flt_eng = FilterEngine()
        frm_mgr = FrameManager()
        evt_mgr = EventManager()
        tok_mgr = TokenManager()
        prn_mgr = PrintManager()
        mock_face = MagicMock()
        mock_af = MagicMock()
        kiosk = None

        try:
            kiosk = KioskPage(
                camera_mgr=cam_mgr,
                filter_engine=flt_eng,
                frame_mgr=frm_mgr,
                print_mgr=prn_mgr,
                event_mgr=evt_mgr,
                token_mgr=tok_mgr,
                config_mgr=temp_config,
                face_service=mock_face,
                face_eye_af_controller=mock_af
            )
            if hasattr(kiosk, "live_view_worker") and kiosk.live_view_worker:
                kiosk.live_view_worker.stop()
            kiosk.stop_live_view()

            assert hasattr(kiosk, "sound_controller")
            assert kiosk.sound_controller is not None

            # Mock sound controller methods to monitor call sequence
            kiosk.sound_controller.play_voice_prompt = MagicMock(return_value=True)
            kiosk.sound_controller.play_tick = MagicMock(return_value=True)
            kiosk.sound_controller.play_shutter = MagicMock(return_value=True)

            # 1. Bắt đầu đếm ngược 3 giây -> gọi play_voice_prompt
            kiosk.countdown_duration = 3
            kiosk._start_single_shot_countdown()
            kiosk.countdown_timer.stop()
            kiosk.sound_controller.play_voice_prompt.assert_called()

            # 2. Bắt đầu đếm ngược 5 giây -> gọi play_tick
            kiosk.sound_controller.play_tick.reset_mock()
            kiosk.countdown_duration = 5
            kiosk._start_single_shot_countdown()
            kiosk.countdown_timer.stop()
            kiosk.sound_controller.play_tick.assert_called()

            # 3. Khi countdown tick giảm về 3 -> gọi play_voice_prompt
            kiosk.sound_controller.play_voice_prompt.reset_mock()
            kiosk.countdown_remaining = 4
            kiosk._on_countdown_tick()  # giảm xuống 3
            assert kiosk.countdown_remaining == 3
            kiosk.sound_controller.play_voice_prompt.assert_called()

            # 4. Khi capture bị từ chối / lỗi -> KHÔNG phát âm thanh màn trập (Bảo vệ âm thanh theo kiến trúc mới)
            kiosk.sound_controller.play_shutter = MagicMock(return_value=True)
            kiosk.sound_controller.play_shutter_for_transaction = MagicMock(return_value=True)
            with patch.object(cam_mgr, "capture_photo", return_value=(False, None)), \
                 patch("PySide6.QtWidgets.QMessageBox.warning"):
                kiosk._execute_photo_capture("dummy_path.jpg")
                kiosk.sound_controller.play_shutter.assert_not_called()
                kiosk.sound_controller.play_shutter_for_transaction.assert_not_called()

            # 5. Khi camera chấp nhận lệnh chụp (on_capture_start) -> gọi play_shutter_for_transaction duy nhất 1 lần
            def mock_capture_photo(save_path, on_capture_start=None, **kwargs):
                if on_capture_start:
                    on_capture_start()
                from PIL import Image
                return True, Image.new("RGB", (100, 100), (255, 255, 255))

            kiosk.sound_controller.play_shutter_for_transaction.reset_mock()
            with patch.object(cam_mgr, "capture_photo", side_effect=mock_capture_photo), \
                 patch("PIL.Image.Image.save"), \
                 patch("os.path.exists", return_value=True), \
                 patch("os.path.getsize", return_value=5000), \
                 patch("PIL.Image.open") as mock_open:
                mock_im = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_im
                kiosk._execute_photo_capture("dummy_path.jpg", tx_id="test_tx_001")
                kiosk.sound_controller.play_shutter_for_transaction.assert_called_once_with("test_tx_001")
        finally:
            if kiosk is not None:
                kiosk.cleanup()
                kiosk.close()
            cam_mgr.close()
            if hasattr(prn_mgr, "stop"):
                prn_mgr.stop()

    def test_settings_page_audio_controls(self, qapp, temp_config):
        """Kiểm tra giao diện cấu hình âm thanh trong SettingsPage."""
        from vietphotobooth.desktop.widgets.settings_page import SettingsPage
        from vietphotobooth.sharing.token_manager import TokenManager

        tok_mgr = TokenManager()
        sp = SettingsPage(config_mgr=temp_config, token_mgr=tok_mgr)

        try:
            assert hasattr(sp, "chk_audio_enabled")
            assert hasattr(sp, "spin_audio_volume")
            assert hasattr(sp, "chk_audio_voice")
            assert hasattr(sp, "chk_audio_tick")
            assert hasattr(sp, "chk_audio_shutter")

            # Thay đổi giá trị trên UI và lưu
            sp.chk_audio_enabled.setChecked(True)
            sp.spin_audio_volume.setValue(75)
            sp.chk_audio_voice.setChecked(False)
            sp.chk_audio_tick.setChecked(True)
            sp.chk_audio_shutter.setChecked(True)

            sp._save_config()

            assert temp_config.get("audio.enabled") is True
            assert abs(temp_config.get("audio.volume") - 0.75) < 1e-4
            assert temp_config.get("audio.voice_enabled") is False
            assert temp_config.get("audio.tick_enabled") is True

            # Test nút thử âm thanh
            sp._test_audio_playback()  # Chạy an toàn không ném ngoại lệ
        finally:
            sp.close()
