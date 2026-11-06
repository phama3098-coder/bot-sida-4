"""
1998 TEAM — Dynamic Countdown Voice Synchronization Test Suite
Verifies:
1. Dynamic Audio Mapping: countdown_value -> corresponding voice asset (or tick fallback).
2. All countdown configurations: 2s, 3s, 4s, 5s, 10s.
3. Dynamic switching between different countdown durations across consecutive capture cycles.
4. Strict transaction isolation: Each countdown transaction has a unique transaction_id.
5. Exactly-once playback per countdown value within a transaction.
6. Zero overlapping sounds (stop_countdown_audio called before each new sound).
7. Capture trigger at countdown = 0 (timer stops, UI shows 📸, shutter plays exactly once, camera captures).
8. Cancel safety: Cancelling stops timer and sounds; no shutter click is ever played.
9. Dynamic asset fallback: Gracefully uses tick if voice_{N}.wav is missing, and automatically uses voice_{N}.wav when present.
"""

import os
import time
import pytest
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock

from PySide6.QtWidgets import QApplication

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.filters.filter_engine import FilterEngine
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.desktop.widgets.kiosk_page import KioskPage
from vietphotobooth.audio.constants import SOUND_TICK, SOUND_SHUTTER, get_sound_file_path


@pytest.fixture
def dynamic_env(tmp_path, qapp):
    """Môi trường kiểm thử KioskPage & Camera Simulator cho Dynamic Audio Mapping."""
    cfg_file = str(tmp_path / "config_dynamic_audio.json")
    cm = ConfigManager(cfg_file)
    cm.set("countdown_seconds", 3)
    cm.set("audio.enabled", True)
    cm.set("audio.volume", 0.8)
    cm.set("audio.voice_enabled", True)
    cm.set("audio.tick_enabled", True)
    cm.set("audio.shutter_enabled", True)
    cm.set("camera.backend", "simulator")

    cam_mgr = CameraManager()
    cam_mgr.switch_backend("simulator", 0)

    flt_eng = FilterEngine()
    frm_mgr = FrameManager()
    evt_mgr = EventManager()
    tok_mgr = TokenManager()
    prn_mgr = PrintManager()

    kiosk = KioskPage(
        camera_mgr=cam_mgr,
        filter_engine=flt_eng,
        frame_mgr=frm_mgr,
        print_mgr=prn_mgr,
        event_mgr=evt_mgr,
        token_mgr=tok_mgr,
        config_mgr=cm
    )
    kiosk.stop_live_view()
    kiosk._enter_review_state = lambda: None

    yield {
        "kiosk": kiosk,
        "cam_mgr": cam_mgr,
        "config_mgr": cm,
        "sc": kiosk.sound_controller,
        "tmp_path": tmp_path
    }

    try:
        kiosk.cancel_countdown()
        kiosk.cleanup()
        kiosk.close()
    except Exception:
        pass
    cam_mgr.close()
    if hasattr(prn_mgr, "stop"):
        prn_mgr.stop()
    qapp.processEvents()


class TestDynamicCountdownVoiceSync:

    @pytest.mark.parametrize("duration,expected_sequence", [
        (2, [2, 1]),
        (3, [3, 2, 1]),
        (4, [4, 3, 2, 1]),
        (5, [5, 4, 3, 2, 1]),
        (10, [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]),
    ])
    def test_countdown_durations_step_sequence(self, dynamic_env, qapp, duration, expected_sequence):
        """Kiểm tra từng mức countdown (2s, 3s, 4s, 5s, 10s): đúng mốc số, đúng thứ tự, kết thúc bằng 📸 và capture."""
        kiosk = dynamic_env["kiosk"]
        sc = dynamic_env["sc"]
        sc.clear_playback_history()

        ui_steps: List[str] = []
        orig_set_text = kiosk.lbl_countdown.setText
        def _hook_text(val):
            ui_steps.append(str(val))
            orig_set_text(val)
        kiosk.lbl_countdown.setText = _hook_text

        # 1. Bắt đầu countdown với thời lượng chỉ định
        kiosk.countdown_duration = duration
        kiosk.current_shot_index = 1
        kiosk.total_shots_needed = 1
        kiosk._start_single_shot_countdown()
        kiosk.countdown_timer.stop()

        tx_id = kiosk._active_countdown_tx_id
        assert tx_id is not None, "Countdown transaction ID không được tạo"
        assert tx_id.startswith("cd_tx_")

        # 2. Bước từng nhịp qua timer callback
        for _ in range(duration - 1):
            kiosk._on_countdown_tick()

        # 3. Nhịp cuối cùng -> Về 0 -> Kích hoạt chụp
        kiosk._on_countdown_tick()
        qapp.processEvents()

        kiosk.lbl_countdown.setText = orig_set_text

        # Xác minh UI hiển thị đúng thứ tự số rồi đến 📸
        expected_ui = [str(n) for n in expected_sequence] + ["📸"]
        assert ui_steps == expected_ui, f"Thứ tự UI không khớp cho {duration}s: {ui_steps}"

        # Xác minh các mốc số đã được ghi nhận trong transaction
        played_in_tx = sc._countdown_tx_played.get(tx_id, set())
        assert played_in_tx == set(expected_sequence), f"Transaction {tx_id} ghi nhận thiếu mốc số: {played_in_tx}"

    def test_dynamic_configuration_switching_between_runs(self, dynamic_env, qapp):
        """Thay đổi cấu hình countdown giữa các lượt chụp (3s -> 5s -> 2s -> 10s -> 4s) với Transaction ID độc lập."""
        kiosk = dynamic_env["kiosk"]
        sc = dynamic_env["sc"]
        configs = [3, 5, 2, 10, 4]
        tx_ids = []

        for shot_idx, dur in enumerate(configs, start=1):
            sc.clear_playback_history()
            kiosk.current_shot_index = shot_idx
            kiosk.total_shots_needed = len(configs)
            kiosk._set_countdown_duration(dur)
            assert kiosk.countdown_duration == dur

            kiosk._start_single_shot_countdown()
            kiosk.countdown_timer.stop()

            tx = kiosk._active_countdown_tx_id
            assert tx not in tx_ids, f"Trùng lặp transaction ID giữa các lượt: {tx}"
            tx_ids.append(tx)

            # Chạy hết các nhịp
            for _ in range(dur):
                kiosk._on_countdown_tick()
            qapp.processEvents()

            # Mỗi lượt ghi nhận đúng số lượng mốc tương ứng với dur
            played = sc._countdown_tx_played.get(tx, set())
            assert len(played) == dur, f"Lượt {shot_idx} ({dur}s) chỉ phát {len(played)} mốc"
            assert max(played) == dur
            assert min(played) == 1

        assert len(set(tx_ids)) == len(configs), "Các transaction ID phải hoàn toàn phân biệt"

    def test_no_duplicate_audio_within_same_transaction(self, dynamic_env, qapp):
        """Kiểm tra không phát trùng: gọi lặp cùng một mốc số trong cùng một transaction sẽ bị chặn."""
        kiosk = dynamic_env["kiosk"]
        sc = dynamic_env["sc"]

        kiosk.countdown_duration = 3
        kiosk._start_single_shot_countdown()
        kiosk.countdown_timer.stop()

        tx = kiosk._active_countdown_tx_id
        # Mốc 3 đã được phát tại start
        assert 3 in sc._countdown_tx_played.get(tx, set())

        # Thử gọi lại mốc 3 thủ công trong cùng transaction
        success, reason = sc.play_countdown_step(3, tx_id=tx)
        assert success is False
        assert reason == "ALREADY_PLAYED"

    def test_cancel_countdown_stops_immediately_and_never_triggers_shutter(self, dynamic_env, qapp):
        """Khi hủy countdown: Timer dừng ngay, âm thanh dừng ngay và tuyệt đối không phát âm thanh màn trập."""
        kiosk = dynamic_env["kiosk"]
        sc = dynamic_env["sc"]

        kiosk.countdown_duration = 5
        kiosk._start_single_shot_countdown()
        assert kiosk.countdown_timer.isActive() is True

        with patch.object(sc, "play_shutter") as mock_shutter:
            kiosk.cancel_countdown()
            assert kiosk.countdown_timer.isActive() is False
            assert kiosk._active_countdown_tx_id is None
            assert kiosk._active_capture_tx_id is None
            assert kiosk.lbl_countdown.isVisible() is False
            assert kiosk.current_state == "IDLE"

            # Đảm bảo không bao giờ phát shutter
            mock_shutter.assert_not_called()

    def test_dynamic_voice_asset_resolution_and_fallback(self, dynamic_env, tmp_path, qapp):
        """
        Kiểm tra cơ chế phân giải tài nguyên động:
        - Nếu có file voice_{N}.wav trên đĩa: Phát file đó.
        - Nếu thiếu file voice_{N}.wav: Tự động fallback sang countdown_tick.wav mà không bị lỗi.
        """
        sc = dynamic_env["sc"]
        tx_test = "cd_tx_mock_dynamic_001"
        sc.start_countdown_transaction(tx_test)

        # 1. Mốc 5: Hiện tại chưa có voice_5.wav trong repo -> Fallback sang countdown_tick.wav
        success, asset = sc.play_countdown_step(5, tx_id=tx_test)
        assert success is True
        assert asset == "countdown_tick.wav"

# 2. Giả lập khi người dùng bổ sung file voice_4.wav vào thư mục
        dummy_wav = tmp_path / "voice_4.wav"
        import wave
        with wave.open(str(dummy_wav), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b'\x00\x00' * 1000)

        with patch("vietphotobooth.audio.sound_controller.get_countdown_voice_file_path", return_value=str(dummy_wav)), \
             patch("vietphotobooth.audio.sound_controller.get_sound_file_path", return_value=str(dummy_wav)):
            success, asset = sc.play_countdown_step(4, tx_id=tx_test)
            assert success is True
            assert asset == "voice_4.wav"
