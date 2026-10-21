"""
Offline-First Background Sync Manager for Google Drive.
Features persistent registry, non-blocking network probe, retry logic, and Qt event signals.
"""

import os
import json
import time
import socket
import threading
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

from PySide6.QtCore import QObject, Signal, QThread

from .gdrive_auth import GDriveAuth
from .gdrive_client import GDriveClient
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.logger import get_logger

logger = get_logger()

DEFAULT_REGISTRY_FILE = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "1998TeamPhotobooth",
    "sync_registry.json"
)


class SyncStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    SYNCED = "synced"
    FAILED = "failed"
    OFFLINE = "offline"


@dataclass
class SyncTask:
    file_path: str
    event_name: str
    is_final: bool = True
    attempts: int = 0
    added_at: float = 0.0

    def __post_init__(self):
        if self.added_at == 0.0:
            self.added_at = time.time()


class SyncWorker(QThread):
    """Worker ngầm xử lý hàng đợi đồng bộ lên Google Drive không gây giật lag giao diện."""

    sync_started = Signal(str)
    sync_completed = Signal(str, str)  # file_path, web_link
    sync_failed = Signal(str, str)     # file_path, error_msg
    status_changed = Signal(bool, int) # is_online, queue_len
    event_folder_ready = Signal(str, str) # event_name, folder_link

    def __init__(self, sync_manager: "SyncManager"):
        super().__init__()
        self.mgr = sync_manager
        self._running = True

    def stop(self):
        self._running = False
        self.wait(2000)

    def run(self):
        logger.info("Khởi chạy tiến trình nền Đồng bộ Google Drive (SyncWorker).")
        while self._running:
            try:
                # 1. Kiểm tra mạng Internet
                is_online = self.mgr.check_internet_connection()
                q_len = len(self.mgr._queue)
                self.status_changed.emit(is_online, q_len)

                # 2. Nếu có mạng và có file trong hàng đợi và đã xác thực Google Drive
                if is_online and q_len > 0 and self.mgr.is_ready():
                    task = self.mgr._pop_task()
                    if task:
                        self._process_task(task)
                else:
                    # Chờ 2 giây nếu rảnh hoặc mất mạng
                    for _ in range(20):
                        if not self._running:
                            break
                        time.sleep(0.1)
            except Exception as e:
                logger.error(f"Ngoại lệ trong vòng lặp SyncWorker: {e}")
                time.sleep(2)

    def _process_task(self, task: SyncTask):
        file_path = task.file_path
        if not os.path.exists(file_path):
            logger.warning(f"File cần đồng bộ không còn tồn tại trên ổ đĩa: {file_path}")
            return

        # Kiểm tra registry xem đã đồng bộ chưa
        cached = self.mgr.get_file_info(file_path)
        if cached and cached.get("status") == SyncStatus.SYNCED and cached.get("web_link"):
            logger.info(f"File {os.path.basename(file_path)} đã có sẵn trên Google Drive, bỏ qua tải lại.")
            self.sync_completed.emit(file_path, cached["web_link"])
            return

        self.sync_started.emit(file_path)
        logger.info(f"Bắt đầu đồng bộ lên Google Drive: {os.path.basename(file_path)}")

        try:
            # 1. Tìm hoặc tạo thư mục gốc "1998 TEAM Photobooth"
            root_folder_id = self.mgr.get_root_folder_id()
            if not root_folder_id:
                raise RuntimeError("Không thể tạo hoặc truy cập thư mục gốc trên Google Drive.")

            # 2. Tìm hoặc tạo thư mục cho sự kiện này
            event_name = task.event_name or "Sự Kiện Chung"
            event_folder_name = f"1998 TEAM — {event_name}"
            event_folder_id = self.mgr.get_or_create_event_folder(event_name, event_folder_name, root_folder_id)

            if not event_folder_id:
                raise RuntimeError(f"Không thể tạo thư mục sự kiện '{event_folder_name}'.")

            # 3. Tải ảnh lên
            res = self.mgr.client.upload_photo(
                file_path=file_path,
                folder_id=event_folder_id,
                description=f"Ảnh Photobooth - Sự kiện: {event_name}",
                make_public=self.mgr.is_public_sharing_enabled()
            )

            if res and "webViewLink" in res:
                web_link = res["webViewLink"]
                file_id = res.get("id", "")
                self.mgr._record_success(file_path, task.event_name, file_id, web_link)
                self.sync_completed.emit(file_path, web_link)
                logger.info(f"Đã đồng bộ thành công {os.path.basename(file_path)} -> {web_link}")
            else:
                raise RuntimeError("Google Drive không phản hồi đường dẫn webViewLink hợp lệ.")

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Đồng bộ thất bại cho {os.path.basename(file_path)}: {err_msg}")
            task.attempts += 1
            if task.attempts < 3:
                # Đưa lại vào hàng đợi để thử lại sau
                self.mgr._requeue_task(task)
            else:
                self.mgr._record_failure(file_path, task.event_name, err_msg)
            self.sync_failed.emit(file_path, err_msg)


class SyncManager(QObject):
    """Trình quản lý hàng đợi và registry đồng bộ dữ liệu đám mây."""

    def __init__(self, config_mgr: Optional[ConfigManager] = None):
        super().__init__()
        self.config_mgr = config_mgr or ConfigManager()
        self.registry_file = DEFAULT_REGISTRY_FILE
        self._lock = threading.Lock()

        # Cấu hình Google Drive
        client_id = self.config_mgr.get("cloud.gdrive_client_id", "")
        client_secret = self.config_mgr.get("cloud.gdrive_client_secret", "")
        is_sim = self.config_mgr.get("cloud.gdrive_simulation_mode", False)

        self.auth = GDriveAuth(client_id=client_id, client_secret=client_secret, simulation_mode=is_sim)
        self.client = GDriveClient(self.auth)

        # Hàng đợi và registry
        self._queue: List[SyncTask] = []
        self._registry: Dict[str, Any] = self._load_registry()

        # Worker thread
        self.worker = SyncWorker(self)
        self.worker.start()

    def _load_registry(self) -> Dict[str, Any]:
        """Tải registry từ đĩa."""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Lỗi đọc sync_registry.json: {e}")
        return {"files": {}, "events": {}}

    def _save_registry(self):
        """Lưu registry xuống đĩa một cách an toàn."""
        os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
        try:
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(self._registry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Lỗi ghi sync_registry.json: {e}")

    def is_ready(self) -> bool:
        """Kiểm tra xem Google Drive đã sẵn sàng kết nối."""
        return self.auth.is_authenticated()

    def is_public_sharing_enabled(self) -> bool:
        return self.config_mgr.get("cloud.public_sharing", True)

    def check_internet_connection(self, host: str = "8.8.8.8", port: int = 53, timeout: float = 1.0) -> bool:
        """Thử nghiệm kết nối mạng qua socket non-blocking không làm nghẽn UI."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((host, port))
            return True
        except Exception:
            return False

    def get_root_folder_id(self) -> Optional[str]:
        """Lấy hoặc tạo thư mục gốc 1998 TEAM Photobooth."""
        root_name = self.config_mgr.get("cloud.root_folder_name", "1998 TEAM Photobooth")
        cached_id = self._registry.get("root_folder_id")
        if cached_id:
            return cached_id
        folder_id = self.client.get_or_create_folder(root_name)
        if folder_id:
            with self._lock:
                self._registry["root_folder_id"] = folder_id
                self._save_registry()
        return folder_id

    def get_or_create_event_folder(self, event_name: str, folder_display_name: str, root_id: str) -> Optional[str]:
        """Lấy hoặc tạo thư mục cho sự kiện cụ thể."""
        ev_info = self._registry.get("events", {}).get(event_name)
        if ev_info and "folder_id" in ev_info:
            return ev_info["folder_id"]

        folder_id = self.client.get_or_create_folder(folder_display_name, parent_id=root_id)
        if folder_id:
            if self.is_public_sharing_enabled():
                self.client.set_public_permission(folder_id, role="reader")
            share_link = self.client.get_folder_share_link(folder_id)
            with self._lock:
                self._registry["events"][event_name] = {
                    "folder_id": folder_id,
                    "folder_link": share_link,
                    "created_at": time.time()
                }
                self._save_registry()
            self.worker.event_folder_ready.emit(event_name, share_link)
            return folder_id
        return None

    def enqueue(self, file_path: str, event_name: str, is_final: bool = True) -> bool:
        """Thêm file vào hàng đợi đồng bộ ngầm."""
        abs_path = os.path.abspath(file_path)
        with self._lock:
            # Kiểm tra xem đã có trong queue chưa
            for item in self._queue:
                if item.file_path == abs_path:
                    return True
            task = SyncTask(file_path=abs_path, event_name=event_name, is_final=is_final)
            self._queue.append(task)
            logger.info(f"Đã thêm vào hàng đợi đồng bộ: {os.path.basename(abs_path)} (Hàng đợi: {len(self._queue)})")
            return True

    def _pop_task(self) -> Optional[SyncTask]:
        with self._lock:
            if self._queue:
                return self._queue.pop(0)
        return None

    def _requeue_task(self, task: SyncTask):
        with self._lock:
            self._queue.append(task)

    def _record_success(self, file_path: str, event_name: str, file_id: str, web_link: str):
        with self._lock:
            self._registry["files"][file_path] = {
                "status": SyncStatus.SYNCED,
                "file_id": file_id,
                "web_link": web_link,
                "event_name": event_name,
                "synced_at": time.time()
            }
            self._save_registry()

    def _record_failure(self, file_path: str, event_name: str, error_msg: str):
        with self._lock:
            self._registry["files"][file_path] = {
                "status": SyncStatus.FAILED,
                "error": error_msg,
                "event_name": event_name,
                "failed_at": time.time()
            }
            self._save_registry()

    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin đồng bộ của một tệp ảnh."""
        abs_path = os.path.abspath(file_path)
        with self._lock:
            return self._registry.get("files", {}).get(abs_path)

    def get_event_link(self, event_name: str) -> Optional[str]:
        """Lấy link xem toàn bộ album sự kiện trên Google Drive nếu có."""
        with self._lock:
            ev = self._registry.get("events", {}).get(event_name)
            if ev:
                return ev.get("folder_link")
        return None

    def sync_all_event_photos(self, event_name: str, final_folder_path: str) -> int:
        """Đưa toàn bộ ảnh trong thư mục sự kiện vào hàng đợi đồng bộ."""
        if not os.path.exists(final_folder_path):
            return 0

        count = 0
        for f in os.listdir(final_folder_path):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                f_path = os.path.join(final_folder_path, f)
                info = self.get_file_info(f_path)
                if not info or info.get("status") != SyncStatus.SYNCED:
                    self.enqueue(f_path, event_name)
                    count += 1
        return count

    def get_queue_length(self) -> int:
        with self._lock:
            return len(self._queue)

    def close(self):
        """Dừng worker an toàn."""
        if self.worker.isRunning():
            self.worker.stop()
