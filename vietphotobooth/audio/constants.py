"""
1998 TEAM — Studio Audio Constants & Asset Resolver
Provides resource paths and event keys for QSoundEffect audio playback.
Supports both development environment and PyInstaller packaged binaries.
"""

import os
import sys

# Khóa định danh sự kiện âm thanh
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


def get_sound_file_path(sound_key: str) -> str:
    """Trả về đường dẫn file âm thanh tương ứng với khóa sự kiện."""
    base = get_asset_base_path()
    audio_dir = os.path.join(base, "Audio")

    mapping = {
        SOUND_TICK: "countdown_tick.wav",
        SOUND_VOICE: "countdown_voice_vi.wav",
        SOUND_SHUTTER: "shutter_click.wav",
    }

    fname = mapping.get(sound_key, f"{sound_key}.wav")
    return os.path.join(audio_dir, fname)
