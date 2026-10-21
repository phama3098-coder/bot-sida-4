"""
1998 TEAM — Photobooth Update Engine
Handles asynchronous update checking, manifest verification, chunked secure downloading,
SHA-256 integrity checks, and safe Windows installer launching.
"""

import os
import sys
import time
import shutil
import socket
import hashlib
import subprocess
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

import requests
from PySide6.QtCore import QObject, Signal, QThread

from vietphotobooth.version import (
    __version__, __build__, __app_name__, is_newer_version, get_version_string
)
from vietphotobooth.updates.manifest import UpdateManifest
from vietphotobooth.updates.migration import create_pre_update_backup
from vietphotobooth.core.config import ConfigManager, get_user_data_dir
from vietphotobooth.core.logger import get_logger

logger = get_logger()

def check_network_connectivity(host: str = "8.8.8.8", port: int = 53, timeout: float = 1.5) -> bool:
    """Kiểm tra kết nối Internet nhanh không làm nghẽn ứng dụng."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
        return True
    except Exception:
        return False


class UpdateCheckWorker(QThread):
    """Worker luồng phụ kiểm tra phiên bản mới ngầm không làm gián đoạn chụp ảnh."""
    check_finished = Signal(bool, object, str)  # has_update: bool, manifest: Optional[UpdateManifest], message: str

    def __init__(self, manifest_url: str, current_version: str, current_build: int, parent=None):
        super().__init__(parent)
        self.manifest_url = (manifest_url or "").strip()
        self.current_version = current_version
        self.current_build = current_build

    def run(self):
        if not self.manifest_url:
            self.check_finished.emit(False, None, "Chưa cấu hình địa chỉ máy chủ cập nhật.")
            return

        is_local_file = os.path.exists(self.manifest_url) or self.manifest_url.startswith("file://")

        # Nếu là URL từ xa, kiểm tra kết nối mạng trước
        if not is_local_file:
            if not check_network_connectivity():
                self.check_finished.emit(False, None, "Không có kết nối Internet để kiểm tra cập nhật.")
                return

        try:
            content = ""
            if is_local_file:
                clean_path = self.manifest_url.replace("file:///", "").replace("file://", "")
                with open(clean_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                resp = requests.get(self.manifest_url, timeout=4.0, headers={"User-Agent": "1998TeamPhotobooth-Updater/1.0"})
                if resp.status_code != 200:
                    self.check_finished.emit(False, None, f"Máy chủ cập nhật phản hồi mã lỗi HTTP {resp.status_code}.")
                    return
                content = resp.text

            manifest = UpdateManifest.from_json(content)
            errors = manifest.validate_integrity()
            if errors:
                err_str = "; ".join(errors)
                self.check_finished.emit(False, None, f"Dữ liệu manifest không hợp lệ: {err_str}")
                return

            # So sánh phiên bản
            has_update = is_newer_version(
                current_ver=self.current_version,
                candidate_ver=manifest.version,
                current_build=self.current_build,
                candidate_build=manifest.build
            )

            if has_update:
                msg = f"Đã tìm thấy phiên bản mới: v{manifest.version} (Build {manifest.build})"
            else:
                msg = f"Bạn đang sử dụng phiên bản mới nhất: v{self.current_version}."

            self.check_finished.emit(has_update, manifest, msg)

        except Exception as e:
            logger.warning(f"Lỗi khi kiểm tra cập nhật từ {self.manifest_url}: {e}")
            self.check_finished.emit(False, None, f"Lỗi kết nối máy chủ cập nhật: {e}")


class UpdateDownloadWorker(QThread):
    """Worker tải gói cài đặt và kiểm tra tính toàn vẹn SHA-256."""
    progress_changed = Signal(int, int, int)  # percent, downloaded_bytes, total_bytes
    download_finished = Signal(bool, str, str)  # success, installer_path, error_msg

    def __init__(self, manifest: UpdateManifest, dest_dir: str, parent=None):
        super().__init__(parent)
        self.manifest = manifest
        self.dest_dir = dest_dir
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        url = self.manifest.download_url
        os.makedirs(self.dest_dir, exist_ok=True)
        filename = os.path.basename(urlparse(url).path) or f"1998-TEAM-Setup-v{self.manifest.version}.exe"
        if not filename.endswith(".exe"):
            filename += ".exe"

        dest_file = os.path.join(self.dest_dir, filename)
        temp_file = dest_file + ".part"

        try:
            # 1. Hỗ trợ tệp cục bộ (Local Testing / LAN Share)
            if os.path.exists(url) or url.startswith("file://"):
                src_path = url.replace("file:///", "").replace("file://", "")
                with open(src_path, "rb") as f_in, open(temp_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            else:
                # 2. Tải qua HTTP/HTTPS
                with requests.get(url, stream=True, timeout=10.0, headers={"User-Agent": "1998TeamPhotobooth-Updater/1.0"}) as resp:
                    resp.raise_for_status()
                    total_bytes = int(resp.headers.get("content-length", 0)) or self.manifest.file_size_bytes
                    downloaded = 0

                    hasher = hashlib.sha256()
                    with open(temp_file, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if not self._running:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                self.download_finished.emit(False, "", "Tiến trình tải xuống đã bị hủy.")
                                return
                            if chunk:
                                f.write(chunk)
                                hasher.update(chunk)
                                downloaded += len(chunk)
                                if total_bytes > 0:
                                    percent = min(100, int((downloaded / total_bytes) * 100))
                                    self.progress_changed.emit(percent, downloaded, total_bytes)

            # 3. Tính toán và xác minh mã băm SHA-256
            hasher = hashlib.sha256()
            with open(temp_file, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            actual_sha256 = hasher.hexdigest().lower()

            expected_sha256 = self.manifest.sha256.lower().strip()
            if expected_sha256 and actual_sha256 != expected_sha256:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                err = f"Xác thực tính toàn vẹn thất bại: Mã SHA-256 ({actual_sha256[:12]}...) không khớp ({expected_sha256[:12]}...)."
                logger.error(err)
                self.download_finished.emit(False, "", err)
                return

            # Đổi tên tệp hoàn chỉnh
            if os.path.exists(dest_file):
                try:
                    os.remove(dest_file)
                except Exception:
                    pass
            os.rename(temp_file, dest_file)

            logger.info(f"Đã tải và xác thực thành công bộ cài mới: {dest_file}")
            self.download_finished.emit(True, dest_file, "")

        except Exception as e:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            logger.error(f"Lỗi khi tải bộ cài: {e}")
            self.download_finished.emit(False, "", f"Lỗi khi tải bộ cài: {e}")


class UpdateManager(QObject):
    """Bộ quản lý kiểm tra, thông báo, tải xuống và áp dụng bản cập nhật cho 1998 TEAM Photobooth."""
    check_started = Signal()
    check_completed = Signal(bool, object, str)  # has_update, manifest, msg
    download_progress = Signal(int, int, int)
    download_completed = Signal(bool, str, str)

    def __init__(self, config_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_mgr = config_mgr
        self._check_worker: Optional[UpdateCheckWorker] = None
        self._download_worker: Optional[UpdateDownloadWorker] = None
        self._latest_manifest: Optional[UpdateManifest] = None
        self._dismissed_versions_in_session = set()

    @property
    def manifest_url(self) -> str:
        return self.config_mgr.get("updates.manifest_url", "")

    @manifest_url.setter
    def manifest_url(self, url: str):
        self.config_mgr.set("updates.manifest_url", str(url).strip())
        self.config_mgr.save()

    @property
    def is_auto_check_enabled(self) -> bool:
        return bool(self.config_mgr.get("updates.auto_check_on_startup", True))

    @is_auto_check_enabled.setter
    def is_auto_check_enabled(self, enabled: bool):
        self.config_mgr.set("updates.auto_check_on_startup", bool(enabled))
        self.config_mgr.save()

    def check_for_updates(self, manual: bool = False):
        """Khởi chạy luồng kiểm tra cập nhật."""
        if self._check_worker and self._check_worker.isRunning():
            return

        self.check_started.emit()
        url = self.manifest_url

        self._check_worker = UpdateCheckWorker(
            manifest_url=url,
            current_version=__version__,
            current_build=__build__,
            parent=self
        )
        self._check_worker.check_finished.connect(
            lambda has_up, m, msg: self._on_check_finished(has_up, m, msg, manual=manual)
        )
        self._check_worker.start()

    def _on_check_finished(self, has_update: bool, manifest: Optional[UpdateManifest], msg: str, manual: bool = False):
        if manifest:
            self._latest_manifest = manifest

        # Nếu kiểm tra tự động mà người dùng đã chọn "Để sau" trong phiên này thì không nhắc lại
        if has_update and not manual and manifest:
            if manifest.version in self._dismissed_versions_in_session:
                has_update = False

        self.check_completed.emit(has_update, manifest, msg)

    def dismiss_version_for_session(self, version: str):
        """Ghi nhớ người dùng đã chọn 'Để sau' cho phiên làm việc này."""
        self._dismissed_versions_in_session.add(version)

    def start_download(self, manifest: UpdateManifest):
        """Khởi chạy luồng tải bộ cài."""
        if self._download_worker and self._download_worker.isRunning():
            return

        app_dir = get_user_data_dir()
        download_dir = os.path.join(app_dir, "Downloads")

        self._download_worker = UpdateDownloadWorker(manifest, download_dir, parent=self)
        self._download_worker.progress_changed.connect(self.download_progress.emit)
        self._download_worker.download_finished.connect(self.download_completed.emit)
        self._download_worker.start()

    def apply_update_and_restart(self, installer_path: str) -> bool:
        """
        Sao lưu cấu hình hiện tại, chạy bộ cài đặt Windows, và đóng ứng dụng an toàn.
        """
        if not os.path.exists(installer_path):
            logger.error(f"Tệp bộ cài đặt không tồn tại: {installer_path}")
            return False

        try:
            # 1. Tạo bản sao lưu an toàn toàn bộ cấu hình trước khi nâng cấp
            create_pre_update_backup()

            # 2. Khởi chạy bộ cài đặt Inno Setup
            # Inno Setup hỗ trợ tham số chạy im lặng nếu cần, ở đây chạy trực tiếp để người dùng nhìn thấy wizard cài đặt
            subprocess.Popen([installer_path], shell=True)
            logger.info(f"Đã khởi chạy bộ cài đặt: {installer_path}")

            # 3. Yêu cầu ứng dụng thoát
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.quit()
            return True
        except Exception as e:
            logger.error(f"Không thể khởi chạy bộ cài đặt {installer_path}: {e}")
            return False
