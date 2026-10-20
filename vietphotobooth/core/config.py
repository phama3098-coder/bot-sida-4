"""
VietPhotoBooth Configuration Module
Manages application configuration, persistent JSON storage, and security.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any
from vietphotobooth.core.logger import get_logger

logger = get_logger()

DEFAULT_CONFIG: Dict[str, Any] = {
    "app_name": "VietPhotoBooth",
    "version": "1.0.0",
    "admin_pin_hash": hashlib.sha256("1234".encode()).hexdigest(),
    "current_event": "SuKien_MacDinh",
    "storage_dir": os.path.join(os.path.expanduser("~"), "Documents", "VietPhotoBooth"),
    "countdown_seconds": 5,
    "delay_between_shots": 2,
    "photos_per_session": 3,
    "template_type": "2x6",
    "template_id": "strip_2x6_3photos",
    "camera_backend": "simulator",
    "camera_device_index": 0,
    "printer_name": "",
    "printer_paper_size": "4x6",
    "printer_cut_2x6": True,
    "printer_max_copies": 4,
    "auto_print": False,
    "lan_server_port": 8080,
    "share_token_expire_hours": 24,
    "disk_warning_gb": 2.0,
    "dark_mode": True,
    "show_guide_on_start": True,
    "event_title": "Kỷ Niệm Ngày Cưới",
    "event_subtitle": "Chúc Mừng Hạnh Phúc",
    "event_date": "2026-10-20"
}

class ConfigManager:
    def __init__(self, config_path: str = None):
        if not config_path:
            base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            app_dir = os.path.join(base_dir, "VietPhotoBooth")
            os.makedirs(app_dir, exist_ok=True)
            config_path = os.path.join(app_dir, "config.json")
        
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Đọc cấu hình từ file JSON. Nếu chưa có, tạo cấu hình mặc định."""
        self._config = DEFAULT_CONFIG.copy()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._config.update(data)
                logger.info(f"Đã tải cấu hình từ {self.config_path}")
            except Exception as e:
                logger.error(f"Lỗi khi đọc file cấu hình {self.config_path}: {e}")
        else:
            self.save()

    def save(self) -> bool:
        """Lưu cấu hình hiện tại vào file JSON an toàn."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            temp_path = self.config_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            if os.path.exists(self.config_path):
                os.replace(temp_path, self.config_path)
            else:
                os.rename(temp_path, self.config_path)
            logger.info("Đã lưu cấu hình thành công.")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi lưu cấu hình: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value

    def update(self, new_data: Dict[str, Any]) -> bool:
        for k, v in new_data.items():
            if k == "admin_pin" and v:
                self._config["admin_pin_hash"] = hashlib.sha256(str(v).strip().encode()).hexdigest()
            else:
                self._config[k] = v
        return self.save()

    def verify_pin(self, pin: str) -> bool:
        """Xác thực mã PIN quản trị."""
        if not pin:
            return False
        hashed = hashlib.sha256(str(pin).strip().encode()).hexdigest()
        return hashed == self._config.get("admin_pin_hash")

    def set_pin(self, new_pin: str) -> bool:
        """Đổi mã PIN quản trị."""
        if not new_pin or len(str(new_pin).strip()) < 4:
            return False
        self._config["admin_pin_hash"] = hashlib.sha256(str(new_pin).strip().encode()).hexdigest()
        return self.save()

    @property
    def all(self) -> Dict[str, Any]:
        result = self._config.copy()
        result.pop("admin_pin_hash", None)
        return result
