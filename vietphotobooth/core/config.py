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
from vietphotobooth.version import __version__, __app_name__

logger = get_logger()

DEFAULT_CONFIG: Dict[str, Any] = {
    "app_name": __app_name__,
    "version": __version__,
    "admin_pin_hash": hashlib.sha256("1234".encode()).hexdigest(),
    "current_event": "SuKien_MacDinh",
    "storage_dir": os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "1998TeamPhotobooth"),
    "countdown_seconds": 5,
    "delay_between_shots": 2,
    "photos_per_session": 3,
    "template_type": "2x6",
    "template_id": "wedding_2x6_strip3",
    "camera_backend": "directshow",
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
    "event_title": "1998 Studio Phóng Sự Cưới",
    "event_subtitle": "Lưu Giữ Khoảnh Khắc Hạnh Phúc",
    "event_date": "2026-10-20",
    "updates": {
        "manifest_url": "",
        "auto_check_on_startup": True,
        "channel": "stable"
    }
}

def get_user_data_dir() -> str:
    """Trả về thư mục lưu trữ tài nguyên người dùng ngoài thư mục cài đặt để bảo toàn dữ liệu khi cập nhật."""
    base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    user_dir = os.path.join(base_dir, "1998TeamPhotobooth")
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

class ConfigManager:
    def __init__(self, config_path: str = None):
        if not config_path:
            app_dir = get_user_data_dir()
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
                # Loại bỏ URL mẫu placeholder nếu người dùng từng lưu trước đó
                manifest_url = self.get("updates.manifest_url", "")
                if isinstance(manifest_url, str) and ("example.com" in manifest_url.lower() or "example.org" in manifest_url.lower()):
                    self.set("updates.manifest_url", "")
                    self.save()
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
        if "." in key:
            parts = key.split(".")
            curr = self._config
            found = True
            for part in parts:
                if isinstance(curr, dict) and part in curr:
                    curr = curr[part]
                else:
                    found = False
                    break
            if found:
                return curr
            return self._config.get(key, default)
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if "." in key:
            parts = key.split(".")
            curr = self._config
            for part in parts[:-1]:
                if part not in curr or not isinstance(curr[part], dict):
                    curr[part] = {}
                curr = curr[part]
            curr[parts[-1]] = value
            if key in self._config:
                del self._config[key]
        else:
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

    def backup(self) -> str:
        """Tạo bản sao lưu snapshot của tệp config.json trước khi nâng cấp."""
        import time, shutil
        if not os.path.exists(self.config_path):
            return ""
        backup_dir = os.path.join(os.path.dirname(self.config_path), "Backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target = os.path.join(backup_dir, f"config_backup_{timestamp}.json")
        shutil.copy2(self.config_path, target)
        logger.info(f"Đã tạo bản sao lưu cấu hình tại: {target}")
        return target
