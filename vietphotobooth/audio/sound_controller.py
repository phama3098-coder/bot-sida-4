"""
1998 TEAM — Photobooth Studio Sound Controller
Handles studio voice cues, countdown beeps, and mechanical shutter sound effects
via PySide6 QSoundEffect.
Guarantees non-blocking GUI execution and zero-crash fault tolerance if audio hardware is absent.
"""

import os
import time
from typing import Optional, Dict, List, Set, Any, Tuple
from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect

from vietphotobooth.core.logger import get_logger
from vietphotobooth.audio.constants import (
    SOUND_TICK, SOUND_VOICE, SOUND_SHUTTER,
    get_sound_file_path, get_countdown_voice_file_path
)

logger = get_logger()


class SoundController(QObject):
    """
    Bộ điều khiển âm thanh phòng Studio Photobooth:
    - Quản lý hiệu ứng âm thanh đếm ngược động (Dynamic Voice Countdown).
    - Hỗ trợ mapping động theo giá trị số thực tế (N -> voice_N.wav).
    - Quản lý Countdown Transaction ID và Shutter Transaction ID, đảm bảo phát
      chính xác duy nhất một lần (Exactly Once) và triệt tiêu callback trùng lặp/chồng âm.
    - Chạy hoàn toàn bất đồng bộ trên Qt Multimedia loop, không gây block GUI.
    - Phòng ngừa lỗi: không crash nếu thiếu file, hỏng codec hoặc không có loa.
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

        # Theo dõi trạng thái từng effect (READY, LOADING, ERROR, NULL, MISSING)
        self._sound_status: Dict[str, str] = {}

        # Quản lý giao dịch màn trập (Capture Transaction ID -> timestamp đã phát)
        self._shutter_transactions: Dict[str, float] = {}
        self._current_active_transaction: Optional[str] = None

        # Quản lý giao dịch đếm ngược động (Countdown Transaction ID -> Set[mốc số đã phát])
        self._countdown_tx_played: Dict[str, Set[int]] = {}
        self._current_active_countdown_tx: Optional[str] = None

        # Lịch sử ghi nhận các lần phát âm thanh phục vụ kiểm toán và đo lường timeline
        self._playback_history: List[Dict[str, Any]] = []

        if self.config_mgr:
            self.load_settings()

        # Cache các đối tượng QSoundEffect theo sound_key (Tái sử dụng, nạp khi cần)
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

    def sync_with_config(self, config_mgr=None) -> None:
        """Đồng bộ thời gian thực (Live Sync) cấu hình từ ConfigManager."""
        if config_mgr:
            self.config_mgr = config_mgr
        self.load_settings()
        for effect in self._effects.values():
            try:
                effect.setVolume(self.volume)
            except Exception:
                pass

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
        """Nạp trước các tệp âm thanh cơ sở vào bộ đệm QSoundEffect."""
        for key in (SOUND_TICK, SOUND_VOICE, SOUND_SHUTTER):
            self._load_effect(key)

    def _on_effect_status_changed(self, key: str, effect: QSoundEffect) -> None:
        """Xử lý sự kiện thay đổi trạng thái của QSoundEffect (Ready, Loading, Error)."""
        try:
            status = effect.status()
            if status == QSoundEffect.Status.Ready:
                self._sound_status[key] = "READY"
                logger.debug(f"[SoundController] Hiệu ứng âm thanh '{key}' đã sẵn sàng (READY).")
            elif status == QSoundEffect.Status.Loading:
                self._sound_status[key] = "LOADING"
            elif status == QSoundEffect.Status.Error:
                self._sound_status[key] = "ERROR"
                logger.warning(f"[SoundController] Lỗi phần cứng hoặc codec âm thanh khi nạp '{key}' (ERROR).")
            elif status == QSoundEffect.Status.Null:
                self._sound_status[key] = "NULL"
        except Exception as e:
            logger.debug(f"[SoundController] Lỗi kiểm tra trạng thái effect '{key}': {e}")

    def _load_effect(self, key: str) -> Optional[QSoundEffect]:
        """Khởi tạo và nạp một tệp âm thanh cụ thể với cơ chế phòng ngừa lỗi và theo dõi trạng thái."""
        try:
            path = get_sound_file_path(key)
            if not os.path.exists(path):
                self._sound_status[key] = "MISSING"
                return None

            effect = QSoundEffect(self)
            effect.statusChanged.connect(lambda k=key, eff=effect: self._on_effect_status_changed(k, eff))
            effect.setSource(QUrl.fromLocalFile(path))
            effect.setVolume(self.volume)
            self._effects[key] = effect
            self._on_effect_status_changed(key, effect)
            return effect
        except Exception as e:
            logger.debug(f"[SoundController] Không thể khởi tạo QSoundEffect cho '{key}': {e}")
            self._sound_status[key] = "ERROR"
            return None

    def get_effect_status(self, key: str) -> str:
        """Lấy trạng thái hiện tại của hiệu ứng âm thanh (READY, LOADING, ERROR, NULL, MISSING)."""
        if key not in self._effects:
            return self._sound_status.get(key, "MISSING")
        effect = self._effects[key]
        try:
            st = effect.status()
            if st == QSoundEffect.Status.Ready:
                return "READY"
            elif st == QSoundEffect.Status.Loading:
                return "LOADING"
            elif st == QSoundEffect.Status.Error:
                return "ERROR"
            else:
                return "NULL"
        except Exception:
            return self._sound_status.get(key, "ERROR")

    def is_effect_ready(self, key: str) -> bool:
        """Kiểm tra hiệu ứng âm thanh đã sẵn sàng phát hay chưa."""
        return self.get_effect_status(key) == "READY"

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
        if (sound_key == SOUND_VOICE or sound_key.startswith("voice_")) and not self.voice_enabled:
            return False
        if sound_key == SOUND_SHUTTER and not self.shutter_enabled:
            return False

        try:
            effect = self._effects.get(sound_key)
            if effect is None:
                effect = self._load_effect(sound_key)

            if effect is not None:
                try:
                    if effect.status() == QSoundEffect.Status.Error:
                        logger.warning(f"[SoundController] Bỏ qua phát '{sound_key}' do driver báo lỗi (ERROR).")
                        return False
                except Exception:
                    pass

                # Dừng nếu đang phát và phát lại từ đầu
                if effect.isPlaying():
                    effect.stop()
                effect.setVolume(self.volume)
                effect.play()

                # Ghi nhận lịch sử phát âm thanh chính xác
                fpath = get_sound_file_path(sound_key)
                fname = os.path.basename(fpath) if fpath else f"{sound_key}.wav"
                self._playback_history.append({
                    "key": sound_key,
                    "filename": fname,
                    "timestamp": time.monotonic(),
                    "time_str": time.strftime("%H:%M:%S") + f".{int(time.time()*1000)%1000:03d}",
                    "volume": self.volume
                })
                return True
        except Exception as e:
            logger.debug(f"[SoundController] Ngoại lệ khi phát âm thanh '{sound_key}': {e}")

        return False

    def play_tick(self) -> bool:
        """Phát âm thanh đếm nhịp (Tick)."""
        return self.play_sound(SOUND_TICK)

    def has_voice_asset(self, number: int) -> bool:
        """
        Kiểm tra xem file âm thanh giọng nói tiếng Việt cho mốc số number (N) có tồn tại trên đĩa không.
        Hỗ trợ:
        - voice_{number}.wav hoặc countdown_voice_{number}.wav
        - Riêng mốc 3: hỗ trợ fallback tương thích với countdown_voice_vi.wav nếu có.
        """
        dyn_path = get_countdown_voice_file_path(number)
        if dyn_path and os.path.exists(dyn_path):
            return True
        if number == 3:
            legacy_path = get_sound_file_path(SOUND_VOICE)
            if legacy_path and os.path.exists(legacy_path):
                return True
        return False

    def play_voice_prompt(self, number: Optional[int] = None) -> bool:
        """
        Phát giọng nói studio tiếng Việt chỉ dẫn tạo dáng hoặc đếm số theo mốc động number (N).
        Nếu number được cung cấp:
        - Kiểm tra file giọng nói 'voice_{number}' tương ứng.
        - Nếu có, phát đúng file đó và trả về True.
        - Nếu không có (thiếu tài nguyên), trả về False để kích hoạt fallback sang tick.
        Nếu number là None:
        - Phát SOUND_VOICE (countdown_voice_vi.wav) mặc định.
        """
        if not self.enabled or not self.voice_enabled:
            return False

        if number is not None:
            dyn_path = get_countdown_voice_file_path(number)
            if dyn_path and os.path.exists(dyn_path):
                return self.play_sound(f"voice_{number}")
            if number == 3 and os.path.exists(get_sound_file_path(SOUND_VOICE)):
                return self.play_sound(SOUND_VOICE)
            return False

        return self.play_sound(SOUND_VOICE)

    # -------------------------------------------------------------------------
    # Quản lý giao dịch đếm ngược động (Dynamic Countdown Transaction)
    # -------------------------------------------------------------------------
    def start_countdown_transaction(self, tx_id: str) -> None:
        """Bắt đầu một transaction đếm ngược mới: dừng âm thanh cũ và reset tracking."""
        self.stop_countdown_audio()
        self._current_active_countdown_tx = tx_id
        self._countdown_tx_played[tx_id] = set()

    def cancel_countdown_transaction(self, tx_id: Optional[str] = None) -> None:
        """Hủy transaction đếm ngược hiện tại và lập tức dừng toàn bộ âm thanh đếm ngược."""
        if tx_id is None or tx_id == self._current_active_countdown_tx:
            self._current_active_countdown_tx = None
        self.stop_countdown_audio()

    def stop_countdown_audio(self) -> None:
        """Dừng các hiệu ứng âm thanh đếm ngược (voice và tick) đang phát để tránh chồng âm."""
        for key, effect in self._effects.items():
            if key == SOUND_TICK or key == SOUND_VOICE or key.startswith("voice_"):
                try:
                    if effect is not None and effect.isPlaying():
                        effect.stop()
                except Exception:
                    pass

    def play_countdown_step(self, number: int, tx_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Phát âm thanh tương ứng duy nhất một lần cho mốc số countdown (number = N, ví dụ: 10, 5, 4, 3, 2, 1)
        gắn liền với Countdown Transaction ID:
        - Tra cứu động file âm thanh theo giá trị thực tế N: 'voice_{N}.wav' hoặc 'countdown_voice_{N}.wav'.
        - Nếu voice_enabled:
            + Dừng âm thanh đếm trước đó (tránh chồng âm).
            + Thử phát giọng nói tương ứng với number bằng play_voice_prompt(number).
            + Nếu có file giọng nói (hoặc play_voice_prompt trả về True): hoàn tất.
            + Nếu không có file giọng nói (thiếu tài nguyên): Tự động fallback sang play_tick().
        - Nếu voice_enabled bị tắt:
            + Dừng âm thanh đếm trước đó.
            + Phát play_tick() nếu tick_enabled.
        - Đảm bảo mỗi mốc number trong transaction tx_id chỉ phát ĐÚNG MỘT LẦN duy nhất.
        - Trả về (success: bool, asset_played: str).
        """
        active_tx = tx_id or self._current_active_countdown_tx
        if active_tx:
            played = self._countdown_tx_played.setdefault(active_tx, set())
            if number in played:
                logger.debug(f"[SoundController] Bỏ qua mốc số {number} đã phát trong transaction '{active_tx}'.")
                return False, "ALREADY_PLAYED"

        if not self.enabled:
            return False, "DISABLED"

        # 1. Chế độ Giọng nói: Ưu tiên phát giọng nói tiếng Việt nếu có tài nguyên
        if self.voice_enabled and self.has_voice_asset(number):
            self.stop_countdown_audio()
            success = self.play_voice_prompt(number)
            if success:
                if active_tx:
                    self._countdown_tx_played.setdefault(active_tx, set()).add(number)
                dyn_path = get_countdown_voice_file_path(number)
                fname = os.path.basename(dyn_path) if dyn_path else f"voice_{number}.wav"
                if not dyn_path and number == 3:
                    fname = os.path.basename(get_sound_file_path(SOUND_VOICE))
                return True, fname

        # 2. Chế độ Đếm nhịp hoặc Fallback khi thiếu file giọng nói
        if self.tick_enabled:
            self.stop_countdown_audio()
            success = self.play_tick()
            if success:
                if active_tx:
                    self._countdown_tx_played.setdefault(active_tx, set()).add(number)
                return True, "countdown_tick.wav"

        return False, "NO_AUDIO"

    def clear_playback_history(self) -> None:
        """Xóa lịch sử phát âm thanh."""
        self._playback_history.clear()

    def get_playback_history(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các sự kiện âm thanh đã phát kèm timestamp monotonic."""
        return list(self._playback_history)

    def play_shutter(self) -> bool:
        """Phát âm thanh màn trập cơ học khi máy ảnh chụp."""
        return self.play_sound(SOUND_SHUTTER)

    # -------------------------------------------------------------------------
    # Quản lý âm thanh màn trập theo Capture Transaction ID (Exactly Once)
    # -------------------------------------------------------------------------
    def start_transaction(self, tx_id: str) -> None:
        """Đăng ký bắt đầu một transaction chụp ảnh mới."""
        self._current_active_transaction = tx_id

    def is_transaction_played(self, tx_id: str) -> bool:
        """Kiểm tra transaction đã phát âm thanh màn trập hay chưa."""
        return bool(tx_id and tx_id in self._shutter_transactions)

    def play_shutter_for_transaction(self, tx_id: str) -> bool:
        """
        Phát âm thanh màn trập gắn chặt với Capture Transaction ID:
        - Đảm bảo phát DUY NHẤT một lần cho mỗi transaction ID (Exactly Once).
        - Triệt tiêu các tín hiệu callback trễ hoặc trùng lặp.
        - Trả về True nếu âm thanh được kích hoạt thành công, False nếu bị bỏ qua hoặc lỗi.
        """
        if not tx_id or not isinstance(tx_id, str):
            logger.warning("[SoundController] Giao dịch chụp không hợp lệ (tx_id rỗng).")
            return False

        if tx_id in self._shutter_transactions:
            logger.debug(f"[SoundController] Bỏ qua âm thanh màn trập trùng lặp cho transaction '{tx_id}'.")
            return False

        # Đánh dấu transaction đã được xử lý âm thanh màn trập
        self._shutter_transactions[tx_id] = time.time()

        if not self.enabled or not self.shutter_enabled:
            return False

        return self.play_shutter()

    def reset_transaction(self, tx_id: str) -> None:
        """Xóa trạng thái đã phát của một transaction để cho phép retry (nếu cần)."""
        if tx_id:
            self._shutter_transactions.pop(tx_id, None)

    def cancel_transaction(self, tx_id: str) -> None:
        """Hủy transaction hiện tại và lập tức dừng toàn bộ âm thanh."""
        if self._current_active_transaction == tx_id:
            self._current_active_transaction = None
        self.stop_all()

    def cleanup_transactions(self, max_age_seconds: float = 3600.0) -> None:
        """Dọn dẹp các transaction cũ trong bộ nhớ đệm để tránh rò rỉ RAM."""
        now = time.time()
        expired_shutter = [k for k, v in self._shutter_transactions.items() if now - v > max_age_seconds]
        for k in expired_shutter:
            self._shutter_transactions.pop(k, None)

        if len(self._countdown_tx_played) > 500:
            self._countdown_tx_played.clear()

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
        self._sound_status.clear()
        self._shutter_transactions.clear()
        self._countdown_tx_played.clear()
        self._playback_history.clear()
        self._current_active_transaction = None
        self._current_active_countdown_tx = None
