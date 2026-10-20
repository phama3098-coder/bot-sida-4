"""
VietPhotoBooth Event Management Module
Manages events, directories, photo categorization, and disk space monitoring.
"""

import os
import shutil
import zipfile
from datetime import datetime
from typing import List, Dict, Any, Optional
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class EventManager:
    def __init__(self, storage_root: Optional[str] = None, current_event: str = "SuKien_MacDinh"):
        if not storage_root:
            base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            storage_root = os.path.join(base_dir, "VietPhotoBooth")
        self.storage_root = os.path.abspath(storage_root)
        self.events_root = os.path.join(self.storage_root, "Events")
        os.makedirs(self.events_root, exist_ok=True)
        self.current_event = current_event
        self.ensure_event_structure(self.current_event)

    def get_active_event_name(self) -> str:
        """Lấy tên sự kiện đang được chọn để chụp ảnh."""
        return self.current_event

    def get_event_path(self, event_name: str) -> str:
        safe_name = "".join(c for c in event_name if c.isalnum() or c in ("-", "_", " ")).strip()
        if not safe_name:
            safe_name = "SuKien_ChuaDatTen"
        return os.path.join(self.events_root, safe_name)

    def ensure_event_structure(self, event_name: str) -> Dict[str, str]:
        """Tạo cây thư mục chuẩn cho sự kiện: Originals, Final, Thumbnails, Templates, Logs."""
        event_dir = self.get_event_path(event_name)
        subdirs = {
            "root": event_dir,
            "base": event_dir,
            "originals": os.path.join(event_dir, "Originals"),
            "final": os.path.join(event_dir, "Final"),
            "thumbnails": os.path.join(event_dir, "Thumbnails"),
            "templates": os.path.join(event_dir, "Templates"),
            "logs": os.path.join(event_dir, "Logs"),
        }
        for d in subdirs.values():
            os.makedirs(d, exist_ok=True)
        return subdirs

    def get_event_dirs(self, event_name: Optional[str] = None) -> Dict[str, str]:
        """Lấy danh sách các thư mục con của sự kiện chỉ định (hoặc sự kiện hiện tại)."""
        return self.ensure_event_structure(event_name or self.current_event)

    def get_current_dirs(self) -> Dict[str, str]:
        return self.ensure_event_structure(self.current_event)

    def set_active_event(self, event_name: str) -> bool:
        event_dir = self.get_event_path(event_name)
        self.ensure_event_structure(event_name)
        self.current_event = os.path.basename(event_dir)
        logger.info(f"Đã chuyển sự kiện hiện tại sang: {self.current_event}")
        return True

    def list_events(self) -> List[Dict[str, Any]]:
        """Liệt kê tất cả các sự kiện hiện có cùng dung lượng và số lượng ảnh."""
        events = []
        if not os.path.exists(self.events_root):
            return events

        for item in os.listdir(self.events_root):
            item_path = os.path.join(self.events_root, item)
            if os.path.isdir(item_path):
                stats = self.get_event_stats(item)
                events.append({
                    "name": item,
                    "is_active": item == self.current_event,
                    "path": item_path,
                    "created_at": stats["created_at"],
                    "total_final_photos": stats["total_final_photos"],
                    "total_original_photos": stats["total_original_photos"],
                    "disk_used_mb": stats["disk_used_mb"]
                })
        events.sort(key=lambda x: x["created_at"], reverse=True)
        return events

    def create_event(self, event_name: str) -> bool:
        """Tạo sự kiện mới."""
        event_dir = self.get_event_path(event_name)
        if os.path.exists(event_dir):
            logger.warning(f"Sự kiện {event_name} đã tồn tại.")
            return False
        self.ensure_event_structure(event_name)
        logger.info(f"Đã tạo sự kiện mới: {event_name}")
        return True

    def rename_event(self, old_name: str, new_name: str) -> bool:
        """Đổi tên sự kiện an toàn."""
        old_path = self.get_event_path(old_name)
        new_path = self.get_event_path(new_name)
        if not os.path.exists(old_path):
            logger.error(f"Sự kiện {old_name} không tồn tại.")
            return False
        if os.path.exists(new_path) and old_path.lower() != new_path.lower():
            logger.error(f"Sự kiện {new_name} đã tồn tại.")
            return False
        try:
            os.rename(old_path, new_path)
            if self.current_event == old_name:
                self.current_event = os.path.basename(new_path)
            logger.info(f"Đã đổi tên sự kiện {old_name} thành {new_name}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi đổi tên sự kiện: {e}")
            return False

    def get_event_stats(self, event_name: str) -> Dict[str, Any]:
        """Lấy thông số chi tiết của sự kiện."""
        event_dir = self.get_event_path(event_name)
        if not os.path.exists(event_dir):
            return {
                "created_at": "",
                "total_final_photos": 0,
                "total_original_photos": 0,
                "disk_used_mb": 0.0
            }

        ctime = datetime.fromtimestamp(os.path.getctime(event_dir)).strftime("%Y-%m-%d %H:%M:%S")
        final_dir = os.path.join(event_dir, "Final")
        orig_dir = os.path.join(event_dir, "Originals")

        final_count = len([f for f in os.listdir(final_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]) if os.path.exists(final_dir) else 0
        orig_count = len([f for f in os.listdir(orig_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.cr2', '.cr3', '.nef', '.arw'))]) if os.path.exists(orig_dir) else 0

        # Calculate directory size
        total_size = 0
        for dirpath, _, filenames in os.walk(event_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)

        return {
            "created_at": ctime,
            "total_final_photos": final_count,
            "total_original_photos": orig_count,
            "disk_used_mb": round(total_size / (1024 * 1024), 2)
        }

    def check_disk_space(self, warning_threshold_gb: float = 2.0) -> Dict[str, Any]:
        """Kiểm tra dung lượng ổ đĩa chứa thư viện ảnh."""
        try:
            total, used, free = shutil.disk_usage(self.storage_root)
            free_gb = round(free / (1024 ** 3), 2)
            total_gb = round(total / (1024 ** 3), 2)
            used_gb = round(used / (1024 ** 3), 2)
            is_low = free_gb <= warning_threshold_gb
            return {
                "free_gb": free_gb,
                "total_gb": total_gb,
                "used_gb": used_gb,
                "is_low": is_low,
                "warning_message": f"Cảnh báo: Ổ đĩa chỉ còn {free_gb} GB trống! Vui lòng dọn dẹp hoặc chọn ổ đĩa khác." if is_low else "Dung lượng ổn định."
            }
        except Exception as e:
            logger.error(f"Không thể kiểm tra dung lượng ổ đĩa: {e}")
            return {
                "free_gb": 0.0,
                "total_gb": 0.0,
                "used_gb": 0.0,
                "is_low": False,
                "warning_message": f"Không đọc được dung lượng: {e}"
            }

    def export_event_zip(self, event_name: str, output_zip_path: str) -> bool:
        """Xuất toàn bộ ảnh thành phẩm và dữ liệu sự kiện thành file ZIP."""
        event_dir = self.get_event_path(event_name)
        if not os.path.exists(event_dir):
            return False
        try:
            with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(event_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, event_dir)
                        zipf.write(full_path, rel_path)
            logger.info(f"Đã xuất dữ liệu sự kiện {event_name} ra {output_zip_path}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi xuất zip sự kiện: {e}")
            return False
