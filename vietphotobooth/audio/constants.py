"""
1998 TEAM — Studio Audio Constants & Asset Resolver
Provides resource paths and event keys for QSoundEffect audio playback.
Supports both development environment and PyInstaller packaged binaries.
"""

import os
import sys
from typing import Optional

# Khóa định danh sự kiện âm thanh cơ sở
SOUND_TICK = "tick"
SOUND_VOICE = "voice"
SOUND_SHUTTER = "shutter"


def get_asset_base_path() -> str:
    """Trả về đường dẫn tuyệt đối tới thư mục Assets."""
    if hasattr(sys, "_MEIPASS"):
        base = getattr(sys, "_MEIPASS")
        cand = os.path.join(base, "Assets")
        if os.path.exists(cand):
            return cand

    # Thư mục phát triển
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    cand1 = os.path.abspath(os.path.join(curr_dir, "..", "..", "Assets"))
    if os.path.exists(cand1):
        return cand1

    cand2 = os.path.abspath(os.path.join(os.getcwd(), "Assets"))
    if os.path.exists(cand2):
        return cand2

    return cand1


def get_countdown_voice_file_path(number: int) -> Optional[str]:
    """
    Tra cứu động đường dẫn file âm thanh giọng nói tiếng Việt cho mốc số đếm ngược number (N).
    Kiểm tra các quy ước đặt tên file chuẩn:
    1. voice_{number}.wav (ví dụ: voice_5.wav, voice_1.wav)
    2. countdown_voice_{number}.wav (ví dụ: countdown_voice_5.wav)
    Trả về đường dẫn tuyệt đối nếu file tồn tại trên đĩa, ngược lại trả về None.
    """
    base = get_asset_base_path()
    audio_dir = os.path.join(base, "Audio")
    candidates = [
        f"voice_{number}.wav",
        f"countdown_voice_{number}.wav",
    ]
    for cand in candidates:
        p = os.path.join(audio_dir, cand)
        if os.path.exists(p):
            return p
    return None


def get_sound_file_path(sound_key: str) -> str:
    """Trả về đường dẫn file âm thanh tương ứng với khóa sự kiện."""
    base = get_asset_base_path()
    audio_dir = os.path.join(base, "Audio")

    # Kiểm tra nếu là khóa giọng nói động: voice_N hoặc countdown_voice_N
    if sound_key.startswith("voice_"):
        try:
            num = int(sound_key.split("_")[1])
            dyn_path = get_countdown_voice_file_path(num)
            if dyn_path:
                return dyn_path
            # Trả về đường dẫn mặc định nếu file chưa tồn tại
            return os.path.join(audio_dir, f"voice_{num}.wav")
        except Exception:
            pass

    mapping = {
        SOUND_TICK: "countdown_tick.wav",
        SOUND_VOICE: "countdown_voice_vi.wav",
        SOUND_SHUTTER: "shutter_click.wav",
    }

    fname = mapping.get(sound_key, f"{sound_key}.wav")
    return os.path.join(audio_dir, fname)
