"""
1998 TEAM — Photobooth Studio Sound Controller
Handles studio voice cues, countdown beeps, and mechanical shutter sound effects
via PySide6 QSoundEffect.
Guarantees non-blocking GUI execution and zero-crash fault tolerance if audio hardware is absent.
"""

import os
from typing import Optional, Dict
from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect

from vietphotobooth.core.logger import get_logger
from vietphotobooth.audio.constants import (
    SOUND_TICK, SOUND_VOICE, SOUND_SHUTTER, get_sound_file_path
)

logger = get_logger()


class SoundController(QObject):
    """
    Bộ điều khiển âm thanh phòng Studio Photobooth:
    - Quản lý hiệu ứng âm thanh đếm ngược, giọng nói tiếng Việt và âm thanh chụp.
    - Chạy hoàn toàn bất đồng bộ trên Qt Multimedia loop, không làm giật hay chặn GUI.
    - Bảo vệ an toàn tuyệt đối: không bao giờ gây crash ứng dụng nếu máy tính không có loa,
      driver âm thanh bị lỗi hoặc file âm thanh bị thiếu.
    """

    def __init__(self, config_mgr=None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config_mgr = config_mgr

        # Trạng thái cấu hình âm thanh
        self.enabled: bool = True
        self.volume: float = 0.8
        self.tick_enabled: bool = True
        self.voice_enabled: bool = True
        self.shutter_enabled: bool = True

        if self.config_mgr:
            self.load_settings()

        # Cache các đối tượng QSoundEffect theo sound_key
        self._effects: Dict[str, QSoundEffect] = {}
        self._load_all_effects()

    def load_settings(self) -> None:
        """Đọc cấu hình âm thanh từ ConfigManager."""
        if not self.config_mgr:
            return
        try:
            self.enabled = bool(self.config_mgr.get("audio.enabled", True))
            self.volume = max(0.0, min(1.0, float(self.config_mgr.get("audio.volume", 0.8))))
            self.tick_enabled = bool(self.config_mgr.get("audio.tick_enabled", True))
            self.voice_enabled = bool(self.config_mgr.get("audio.voice_enabled", True))
            self.shutter_enabled = bool(self.config_mgr.get("audio.shutter_enabled", True))
        except Exception as e:
            logger.debug(f"[SoundController] Lỗi khi đọc cấu hình âm thanh: {e}")

    def save_settings(self) -> None:
        """Lưu cấu hình âm thanh vào ConfigManager."""
        if not self.config_mgr:
            return
        try:
            self.config_mgr.set("audio.enabled", self.enabled)
            self.config_mgr.set("audio.volume", self.volume)
            self.config_mgr.set("audio.tick_enabled", self.tick_enabled)
            self.config_mgr.set("audio.voice_enabled", self.voice_enabled)
            self.config_mgr.set("audio.shutter_enabled", self.shutter_enabled)
            self.config_mgr.save()
        except Exception as e:
            logger.debug(f"[SoundController] Lỗi khi lưu cấu hình âm thanh: {e}")

    def _load_all_effects(self) -> None:
        """Nạp trước các tệp âm thanh vào bộ đệm QSoundEffect."""
        for key in (SOUND_TICK, SOUND_VOICE, SOUND_SHUTTER):
            self._load_effect(key)

    def _load_effect(self, key: str) -> Optional[QSoundEffect]:
        """Khởi tạo và nạp một tệp âm thanh cụ thể với cơ chế phòng ngừa lỗi."""
        try:
            path = get_sound_file_path(key)
            if not os.path.exists(path):
                logger.debug(f"[SoundController] File âm thanh '{key}' không tồn tại tại: {path}")
                return None

            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(path))
            effect.setVolume(self.volume)
            self._effects[key] = effect
            return effect
        except Exception as e:
            logger.debug(f"[SoundController] Không thể khởi tạo QSoundEffect cho '{key}': {e}")
            return None

    def set_volume(self, volume: float) -> None:
        """Thiết lập mức âm lượng (0.0 đến 1.0)."""
        self.volume = max(0.0, min(1.0, float(volume)))
        for effect in self._effects.values():
            try:
                effect.setVolume(self.volume)
            except Exception:
                pass
        self.save_settings()

    def set_enabled(self, enabled: bool) -> None:
        """Bật hoặc tắt toàn bộ âm thanh."""
        self.enabled = bool(enabled)
        self.save_settings()

    def play_sound(self, sound_key: str) -> bool:
        """
        Phát hiệu ứng âm thanh theo khóa bất đồng bộ.
        Tuyệt đối không gây block luồng giao diện hoặc gây ngoại lệ.
        """
        if not self.enabled:
            return False

        if sound_key == SOUND_TICK and not self.tick_enabled:
            return False
        if sound_key == SOUND_VOICE and not self.voice_enabled:
            return False
        if sound_key == SOUND_SHUTTER and not self.shutter_enabled:
            return False

        try:
            effect = self._effects.get(sound_key)
            if effect is None:
                effect = self._load_effect(sound_key)

            if effect is not None:
                # Nếu đang phát dở thì dừng và phát lại từ đầu
                if effect.isPlaying():
                    effect.stop()
                effect.setVolume(self.volume)
                effect.play()
                return True
        except Exception as e:
            logger.debug(f"[SoundController] Ngoại lệ khi phát âm thanh '{sound_key}': {e}")

        return False

    def play_tick(self) -> bool:
        """Phát âm thanh đếm nhịp (Tick)."""
        return self.play_sound(SOUND_TICK)

    def play_voice_prompt(self) -> bool:
        """Phát giọng nói studio tiếng Việt chỉ dẫn tạo dáng."""
        return self.play_sound(SOUND_VOICE)

    def play_shutter(self) -> bool:
        """Phát âm thanh màn trập cơ học khi máy ảnh chụp."""
        return self.play_sound(SOUND_SHUTTER)

    def stop_all(self) -> None:
        """Dừng toàn bộ hiệu ứng âm thanh đang phát."""
        for effect in list(self._effects.values()):
            try:
                if effect is not None and effect.isPlaying():
                    effect.stop()
            except Exception:
                pass

    def cleanup(self) -> None:
        """Giải phóng toàn bộ tài nguyên âm thanh và ngắt kết nối an toàn."""
        self.stop_all()
        for effect in list(self._effects.values()):
            try:
                effect.deleteLater()
            except Exception:
                pass
        self._effects.clear()
