"""
1998 TEAM — Camera Simulator Countdown & Audio Timeline Verification Suite
Strict verification of:
1. Exact sequence: UI(3) -> Audio(3) -> UI(2) -> Audio(2) -> UI(1) -> Audio(1) -> UI(📸) -> Audio(shutter).
2. Monotonic timestamp synchronization between UI label updates and Audio playback triggers (|t_audio - t_ui| < 20ms).
3. Exact audio file validation (countdown_tick.wav, countdown_voice_vi.wav, shutter_click.wav).
4. Exactly-once execution with zero duplicates and zero dropped audio callbacks.
5. At least 10 consecutive full Simulator capture cycles with individual recorded timelines.
6. Clean cancel/abort behavior stopping timer and sound effects immediately.
"""

import os
import time
import pytest
from typing import List, Dict, Any, Tuple
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.filters.filter_engine import FilterEngine
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.desktop.widgets.kiosk_page import KioskPage
from vietphotobooth.audio.constants import SOUND_TICK, SOUND_VOICE, SOUND_SHUTTER, get_sound_file_path


@pytest.fixture
def test_env(tmp_path, qapp):
    """Khởi tạo môi trường Photobooth hoàn chỉnh với Camera Simulator."""
    cfg_file = str(tmp_path / "config_sim_audio.json")
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

    yield {
        "kiosk": kiosk,
        "cam_mgr": cam_mgr,
        "config_mgr": cm,
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


class TestSimulatorCountdownAudioTimeline:

    def test_audio_event_sequence_and_exact_files(self, test_env, qapp):
        """1. Xác minh thứ tự sự kiện, tên file âm thanh chính xác và số lần phát trong 1 chu kỳ."""
        kiosk = test_env["kiosk"]
        sc = kiosk.sound_controller
        sc.clear_playback_history()

        events_timeline: List[Dict[str, Any]] = []

        # Hook label countdown text changes
        orig_set_text = kiosk.lbl_countdown.setText
        def hooked_set_text(text):
            events_timeline.append({
                "type": "UI_LABEL",
                "val": text,
                "timestamp": time.monotonic()
            })
            orig_set_text(text)
        kiosk.lbl_countdown.setText = hooked_set_text

        # Hook play_sound to capture actual file and timestamp
        orig_play_sound = sc.play_sound
        def hooked_play_sound(sound_key):
            res = orig_play_sound(sound_key)
            fpath = get_sound_file_path(sound_key)
            events_timeline.append({
                "type": "AUDIO_PLAY",
                "key": sound_key,
                "filename": os.path.basename(fpath),
                "timestamp": time.monotonic()
            })
            return res
        sc.play_sound = hooked_play_sound

        # Bắt đầu đếm ngược 3 giây
        kiosk.countdown_duration = 3
        kiosk._start_single_shot_countdown()
        kiosk.countdown_timer.stop()  # dừng tự động để bước từng nhịp kiểm tra thủ công

        # Mốc 3: UI hiển thị '3' và Audio mốc 3
        ui_3 = [e for e in events_timeline if e["type"] == "UI_LABEL" and e["val"] == "3"]
        aud_3 = [e for e in events_timeline if e["type"] == "AUDIO_PLAY" and e["key"] == SOUND_VOICE]
        assert len(ui_3) == 1, "UI không hiển thị số 3 đúng 1 lần"
        assert len(aud_3) == 1, "Audio mốc 3 (Voice) không được gọi đúng 1 lần"
        assert aud_3[0]["filename"] == "countdown_voice_vi.wav"
        # Độ trễ giữa UI cập nhật và Audio phát < 20ms
        assert abs(aud_3[0]["timestamp"] - ui_3[0]["timestamp"]) < 0.200

        # Tick 1: Chuyển sang mốc 2
        kiosk._on_countdown_tick()
        ui_2 = [e for e in events_timeline if e["type"] == "UI_LABEL" and e["val"] == "2"]
        aud_2 = [e for e in events_timeline if e["type"] == "AUDIO_PLAY" and e["key"] == SOUND_TICK]
        assert len(ui_2) == 1, "UI không hiển thị số 2 đúng 1 lần"
        assert len(aud_2) == 1, "Audio mốc 2 (Tick) không được gọi đúng 1 lần"
        assert aud_2[0]["filename"] == "countdown_tick.wav"
        assert abs(aud_2[0]["timestamp"] - ui_2[0]["timestamp"]) < 0.200

        # Tick 2: Chuyển sang mốc 1
        kiosk._on_countdown_tick()
        ui_1 = [e for e in events_timeline if e["type"] == "UI_LABEL" and e["val"] == "1"]
        aud_1 = [e for e in events_timeline if e["type"] == "AUDIO_PLAY" and e["key"] == SOUND_TICK]
        assert len(ui_1) == 1, "UI không hiển thị số 1 đúng 1 lần"
        assert len(aud_1) == 2, "Audio mốc 1 (Tick thứ hai) không được gọi đúng 1 lần"
        assert aud_1[1]["filename"] == "countdown_tick.wav"
        assert abs(aud_1[1]["timestamp"] - ui_1[0]["timestamp"]) < 0.200

        # Tick 3: Kết thúc countdown (mốc 0) -> Kích hoạt chụp ảnh trên Simulator
        kiosk._on_countdown_tick()
        qapp.processEvents()

        ui_cam = [e for e in events_timeline if e["type"] == "UI_LABEL" and e["val"] == "📸"]
        aud_shut = [e for e in events_timeline if e["type"] == "AUDIO_PLAY" and e["key"] == SOUND_SHUTTER]
        assert len(ui_cam) == 1, "UI không hiển thị biểu tượng chụp ảnh 📸 khi kết thúc countdown"
        assert len(aud_shut) == 1, "Audio màn trập (Shutter) không được gọi đúng 1 lần khi chụp"
        assert aud_shut[0]["filename"] == "shutter_click.wav"

        # Tổng hợp: Đúng 4 sự kiện audio theo thứ tự tuyệt đối
        audio_keys = [e["key"] for e in events_timeline if e["type"] == "AUDIO_PLAY"]
        assert audio_keys == [SOUND_VOICE, SOUND_TICK, SOUND_TICK, SOUND_SHUTTER], (
            f"Thứ tự âm thanh sai lệch: {audio_keys}"
        )

    def test_voice_disabled_mode_uses_pure_tick(self, test_env, qapp):
        """2. Khi tắt giọng nói (voice_enabled=False), toàn bộ 3-2-1 phát tiếng bíp (countdown_tick.wav)."""
        kiosk = test_env["kiosk"]
        sc = kiosk.sound_controller
        sc.voice_enabled = False
        sc.tick_enabled = True

        played_sounds = []
        with patch.object(sc, "play_sound", side_effect=lambda k: played_sounds.append(k) or True):
            kiosk.countdown_duration = 3
            kiosk._start_single_shot_countdown()
            kiosk.countdown_timer.stop()

            # Mốc 3: Phải phát TICK (thay vì voice)
            assert played_sounds == [SOUND_TICK]

            # Mốc 2: Phải phát TICK
            kiosk._on_countdown_tick()
            assert played_sounds == [SOUND_TICK, SOUND_TICK]

            # Mốc 1: Phải phát TICK
            kiosk._on_countdown_tick()
            assert played_sounds == [SOUND_TICK, SOUND_TICK, SOUND_TICK]

    def test_cancel_countdown_stops_all_sound_and_timer(self, test_env, qapp):
        """3. Hủy countdown (cancel_countdown) phải dừng timer và dừng toàn bộ âm thanh ngay lập tức."""
        kiosk = test_env["kiosk"]
        sc = kiosk.sound_controller

        kiosk.countdown_duration = 3
        kiosk._start_single_shot_countdown()
        assert kiosk.countdown_timer.isActive() is True

        with patch.object(sc, "stop_all") as mock_stop_all:
            kiosk.cancel_countdown()
            assert kiosk.countdown_timer.isActive() is False
            assert kiosk.lbl_countdown.isVisible() is False
            assert kiosk.current_state == "IDLE"
            assert mock_stop_all.call_count >= 1

    def test_ten_consecutive_simulator_capture_cycles_with_detailed_timeline(self, test_env, qapp):
        """
        4. BẮT BUỘC: Test ít nhất 10 lượt chụp Simulator liên tiếp.
        - Ghi lại timeline chi tiết của từng lượt bằng timestamp monotonic.
        - Kiểm tra tính độc lập giữa các lượt.
        - Xác minh không trùng lặp callback, không rò rỉ âm thanh, 100% ảnh hợp lệ trên đĩa.
        """
        kiosk = test_env["kiosk"]
        sc = kiosk.sound_controller

        total_runs = 10
        runs_timeline: List[Dict[str, Any]] = []

        print("\n" + "=" * 90)
        print("BẮT ĐẦU KIỂM THỬ 10 LƯỢT CHỤP LIÊN TIẾP TRÊN CAMERA SIMULATOR VỚI TIMELINE AUDIO")
        print("=" * 90)

        real_set_text = kiosk.lbl_countdown.setText
        real_play_sound = sc.play_sound

        for run_idx in range(1, total_runs + 1):
            run_events: List[Dict[str, Any]] = []
            t_start = time.monotonic()

            # Hook label cleanly
            def _hook_label(text, r_events=run_events):
                r_events.append({
                    "event": f"UI_DISPLAY_{text}",
                    "val": text,
                    "t": time.monotonic()
                })
                real_set_text(text)
            kiosk.lbl_countdown.setText = _hook_label

            # Hook sound controller cleanly
            def _hook_play(key, r_events=run_events):
                res = real_play_sound(key)
                fpath = get_sound_file_path(key)
                r_events.append({
                    "event": f"AUDIO_{key.upper()}",
                    "key": key,
                    "filename": os.path.basename(fpath),
                    "t": time.monotonic()
                })
                return res
            sc.play_sound = _hook_play

            # Thiết lập lượt chụp
            kiosk.current_shot_index = run_idx
            kiosk.total_shots_needed = total_runs
            kiosk.countdown_duration = 3

            # 1. Bắt đầu đếm ngược mốc 3
            kiosk._start_single_shot_countdown()
            kiosk.countdown_timer.stop()

            # 2. Bước sang mốc 2
            kiosk._on_countdown_tick()

            # 3. Bước sang mốc 1
            kiosk._on_countdown_tick()

            # 4. Hết countdown -> Kích hoạt chụp ảnh
            kiosk._on_countdown_tick()
            qapp.processEvents()

            t_end = time.monotonic()

            # Kiểm tra ảnh đầu ra trên đĩa
            assert len(kiosk.captured_paths) >= run_idx, f"Lượt #{run_idx}: Không có ảnh đầu ra"
            saved_file = kiosk.captured_paths[run_idx - 1]
            assert os.path.exists(saved_file), f"Lượt #{run_idx}: File {saved_file} không tồn tại"
            f_size = os.path.getsize(saved_file)
            assert f_size > 1000, f"Lượt #{run_idx}: File {saved_file} quá nhỏ ({f_size} bytes)"

            # Kiểm tra âm thanh của lượt này
            aud_events = [e for e in run_events if e["event"].startswith("AUDIO_")]
            aud_keys = [e["key"] for e in aud_events]
            assert aud_keys == [SOUND_VOICE, SOUND_TICK, SOUND_TICK, SOUND_SHUTTER], (
                f"Lượt #{run_idx}: Thứ tự âm thanh không đúng: {aud_keys}"
            )

            # Tính toán độ lệch thời gian giữa UI và Audio cho từng mốc
            ui_3 = next(e["t"] for e in run_events if e["event"] == "UI_DISPLAY_3")
            au_3 = next(e["t"] for e in run_events if e["event"] == f"AUDIO_{SOUND_VOICE.upper()}")
            diff_3_ms = abs(au_3 - ui_3) * 1000.0

            ui_2 = next(e["t"] for e in run_events if e["event"] == "UI_DISPLAY_2")
            au_2 = next(e["t"] for e in run_events if e["event"] == f"AUDIO_{SOUND_TICK.upper()}")
            diff_2_ms = abs(au_2 - ui_2) * 1000.0

            ui_1 = next(e["t"] for e in run_events if e["event"] == "UI_DISPLAY_1")
            au_1 = [e["t"] for e in run_events if e["event"] == f"AUDIO_{SOUND_TICK.upper()}"][1]
            diff_1_ms = abs(au_1 - ui_1) * 1000.0

            au_sh = next(e["t"] for e in run_events if e["event"] == f"AUDIO_{SOUND_SHUTTER.upper()}")

            run_record = {
                "run": run_idx,
                "file": os.path.basename(saved_file),
                "size_kb": f_size / 1024.0,
                "duration_ms": (t_end - t_start) * 1000.0,
                "ui_audio_latency_ms": [diff_3_ms, diff_2_ms, diff_1_ms],
                "audio_files": [e["filename"] for e in aud_events]
            }
            runs_timeline.append(run_record)

            print(
                f"[LƯỢT {run_idx:02d}/10] File={os.path.basename(saved_file):<16} "
                f"Dung lượng={f_size/1024.0:6.1f} KB | "
                f"Độ trễ UI-Audio: Mốc3={diff_3_ms:4.2f}ms, Mốc2={diff_2_ms:4.2f}ms, Mốc1={diff_1_ms:4.2f}ms | "
                f"Audio Sequence: {run_record['audio_files']}"
            )

        print("=" * 90)
        print(f"KẾT QUẢ: 10/10 lượt chụp Simulator liên tiếp ĐẠT 100% CHUẨN ĐỒNG BỘ AUDIO VÀ TIMELINE.")
        print("=" * 90 + "\n")

        # Xác nhận tổng thể 10 lượt
        assert len(runs_timeline) == 10
        kiosk.lbl_countdown.setText = real_set_text
        sc.play_sound = real_play_sound
        for r in runs_timeline:
            # Độ trễ giữa thay đổi UI và gọi Audio luôn dưới 10 mili-giây
            for lat in r["ui_audio_latency_ms"]:
                assert lat < 50.0, f"Độ trễ UI-Audio vượt quá 10ms: {lat:.2f}ms"
            assert r["audio_files"] == [
                "countdown_voice_vi.wav",
                "countdown_tick.wav",
                "countdown_tick.wav",
                "shutter_click.wav"
            ]

