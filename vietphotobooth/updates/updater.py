"""
1998 TEAM — Photobooth Update Engine
Handles asynchronous update checking, manifest verification, chunked secure downloading,
SHA-256 integrity checks, Windows Authenticode signature verification, and safe installer launching.
"""

import os
import sys
import re
import time
import shutil
import socket
import hashlib
import subprocess
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse
import json

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

def verify_digital_signature(file_path: str) -> Dict[str, Any]:
    """
    Xác minh chữ ký số Windows Authenticode của tệp thực thi.
    Kiểm tra trạng thái chữ ký số qua PowerShell Authenticode Provider trên Windows.
    """
    if not sys.platform.startswith("win"):
        return {"signed": False, "valid": False, "status": "Not Windows", "signer": ""}

    try:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"(Get-AuthenticodeSignature -LiteralPath '{file_path}').Status.ToString()"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        status = res.stdout.strip()
        is_valid = (status == "Valid")
        is_signed = status in ("Valid", "NotTrusted", "HashMismatch")
        return {
            "signed": is_signed,
            "valid": is_valid,
            "status": status,
            "signer": ""
        }
    except Exception as e:
        logger.warning(f"Không thể kiểm tra chữ ký số: {e}")
        return {"signed": False, "valid": False, "status": f"Error: {e}", "signer": ""}


DEFAULT_GITHUB_REPO = "phama3098-coder/bot-sida-4"
DEFAULT_UPDATE_URL = "https://api.github.com/repos/phama3098-coder/bot-sida-4/releases/latest"

def normalize_update_url(url: str) -> str:
    """
    Chuẩn hóa URL cập nhật: nếu người dùng nhập URL trang web GitHub Release
    (như https://github.com/phama3098-coder/bot-sida-4/releases/latest),
    tự động chuyển thành endpoint GitHub Releases API chính thức.
    """
    clean_url = str(url or "").strip()
    if not clean_url:
        return DEFAULT_UPDATE_URL
    gh_match = re.match(
        r"^https?://github\.com/([^/]+)/([^/]+)(?:/releases(?:/(?:latest|tag/[^/]+))?)?/?$",
        clean_url,
        re.IGNORECASE
    )
    if gh_match:
        owner, repo = gh_match.group(1), gh_match.group(2)
        return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    return clean_url


class UpdateCheckWorker(QThread):
    """Worker luồng phụ kiểm tra phiên bản mới ngầm không làm gián đoạn chụp ảnh."""
    check_finished = Signal(bool, object, str)  # has_update: bool, manifest: Optional[UpdateManifest], message: str

    def __init__(self, manifest_url: str, current_version: str, current_build: int, parent=None):
        super().__init__(parent)
        self.manifest_url = normalize_update_url(manifest_url) if manifest_url else ""
        self.current_version = current_version
        self.current_build = current_build

    def run(self):
        # 1. Kiểm tra cấu hình URL
        if not self.manifest_url:
            self.check_finished.emit(
                False, None,
                "Chưa cấu hình máy chủ cập nhật (Manifest URL). Vui lòng cấu hình nguồn phát hành trong Cài Đặt."
            )
            return

        placeholder_domains = ["example.com", "example.org", "placeholder", "your-domain.com"]
        if any(p in self.manifest_url.lower() for p in placeholder_domains):
            self.check_finished.emit(
                False, None,
                "Chưa cấu hình máy chủ cập nhật (đang để URL mẫu example.com). Vui lòng cấu hình URL thật trong Cài đặt."
            )
            return

        is_local_file = os.path.exists(self.manifest_url) or self.manifest_url.startswith("file://")

        # 2. Nếu là URL từ xa, kiểm tra kết nối mạng trước
        if not is_local_file:
            if not check_network_connectivity():
                self.check_finished.emit(False, None, "Không có kết nối Internet để kiểm tra cập nhật.")
                return

        # 3. Lấy nội dung manifest
        try:
            content = ""
            if is_local_file:
                clean_path = self.manifest_url.replace("file:///", "").replace("file://", "")
                if not os.path.exists(clean_path):
                    self.check_finished.emit(False, None, f"Tệp manifest cập nhật không tồn tại: {clean_path}")
                    return
                with open(clean_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                try:
                    resp = requests.get(
                        self.manifest_url,
                        timeout=8.0,
                        allow_redirects=True,
                        headers={
                            "User-Agent": "1998TeamPhotobooth-Updater/1.0",
                            "Accept": "application/vnd.github.v3+json, application/json, text/plain, */*"
                        }
                    )
                except requests.exceptions.Timeout:
                    self.check_finished.emit(False, None, "Quá thời gian kết nối đến máy chủ cập nhật (Timeout).")
                    return
                except requests.exceptions.ConnectionError:
                    self.check_finished.emit(False, None, "Không thể kết nối đến máy chủ cập nhật. Vui lòng kiểm tra lại kết nối mạng hoặc địa chỉ URL.")
                    return
                except requests.exceptions.RequestException as req_err:
                    self.check_finished.emit(False, None, f"Lỗi kết nối máy chủ cập nhật: {req_err}")
                    return

                if resp.status_code == 404:
                    if "api.github.com" in self.manifest_url or "github.com" in self.manifest_url:
                        self.check_finished.emit(
                            False, None,
                            f"Không tìm thấy kho lưu trữ hoặc bản phát hành trên GitHub (Lỗi HTTP 404 Not Found tại {self.manifest_url}). Vui lòng kiểm tra lại repository."
                        )
                    else:
                        self.check_finished.emit(
                            False, None,
                            f"Máy chủ phản hồi: Tệp manifest cập nhật không tồn tại (Lỗi HTTP 404 Not Found tại {self.manifest_url})."
                        )
                    return
                elif resp.status_code == 403:
                    if resp.headers.get("x-ratelimit-remaining") == "0":
                        self.check_finished.emit(
                            False, None,
                            "Đã vượt quá giới hạn truy vấn tạm thời của GitHub API (Rate Limit 60 lượt/giờ đối với IP công cộng). Vui lòng thử lại sau vài phút."
                        )
                    else:
                        self.check_finished.emit(
                            False, None,
                            f"Máy chủ cập nhật từ chối truy cập (Lỗi HTTP 403 Forbidden tại {self.manifest_url})."
                        )
                    return
                elif resp.status_code >= 500:
                    self.check_finished.emit(
                        False, None,
                        f"Máy chủ cập nhật đang gặp sự cố nội bộ (Lỗi HTTP {resp.status_code} tại {self.manifest_url})."
                    )
                    return
                elif resp.status_code != 200:
                    self.check_finished.emit(
                        False, None,
                        f"Máy chủ cập nhật phản hồi mã lỗi HTTP {resp.status_code} tại {self.manifest_url}."
                    )
                    return

                content = resp.text

            # 4. Phân tích cú pháp JSON
            try:
                data = json.loads(content)
            except Exception as json_err:
                self.check_finished.emit(False, None, f"Tệp phản hồi từ máy chủ cập nhật không đúng định dạng JSON: {json_err}")
                return

            if not isinstance(data, dict):
                self.check_finished.emit(False, None, "Dữ liệu cập nhật từ máy chủ phải là một JSON Object.")
                return

            try:
                is_github_endpoint = (
                    "api.github.com" in self.manifest_url or
                    "github.com" in self.manifest_url or
                    UpdateManifest.is_github_release(data)
                )
                if is_github_endpoint:
                    logger.info(f"Phân tích dữ liệu theo chuẩn GitHub Releases API: {self.manifest_url}")
                    manifest = UpdateManifest.from_github_release(data)
                else:
                    logger.info(f"Phân tích dữ liệu theo chuẩn Manifest JSON nội bộ: {self.manifest_url}")
                    manifest = UpdateManifest.from_dict(data)
            except Exception as parse_err:
                self.check_finished.emit(False, None, f"Lỗi phân tích bản cập nhật: {parse_err}")
                return

            # 5. Xác thực tính toàn vẹn của metadata manifest
            errors = manifest.validate_integrity()
            if errors:
                err_str = "; ".join(errors)
                self.check_finished.emit(False, None, f"Dữ liệu bản cập nhật không hợp lệ: {err_str}")
                return

            # 6. So sánh phiên bản
            has_update = is_newer_version(
                current_ver=self.current_version,
                candidate_ver=manifest.version,
                current_build=self.current_build,
                candidate_build=manifest.build
            )

            if not has_update:
                msg = f"Phiên bản hiện tại (v{self.current_version}) đã là mới nhất."
                self.check_finished.emit(False, manifest, msg)
                return

            # 7. Kiểm tra trước nguồn tải bộ cài (Pre-check Download URL)
            # Ngăn chặn tình trạng thông báo có bản mới nhưng link tải trả về 404
            dl_url = manifest.download_url
            if os.path.exists(dl_url) or dl_url.startswith("file://"):
                local_installer = dl_url.replace("file:///", "").replace("file://", "")
                if not os.path.exists(local_installer):
                    err_msg = f"Nguồn tải gói cài đặt không hợp lệ hoặc không tồn tại (Tệp không tìm thấy: {local_installer}). Vui lòng kiểm tra lại cấu hình phát hành."
                    logger.error(err_msg)
                    self.check_finished.emit(False, None, err_msg)
                    return
                if manifest.file_size_bytes <= 0:
                    manifest.file_size_bytes = os.path.getsize(local_installer)
            else:
                try:
                    # Gửi yêu cầu kiểm tra sự tồn tại của tệp cài đặt trên máy chủ
                    check_resp = requests.head(
                        dl_url,
                        timeout=5.0,
                        allow_redirects=True,
                        headers={"User-Agent": "1998TeamPhotobooth-Updater/1.0"}
                    )
                    if check_resp.status_code == 405:
                        check_resp = requests.get(
                            dl_url,
                            stream=True,
                            timeout=5.0,
                            allow_redirects=True,
                            headers={"User-Agent": "1998TeamPhotobooth-Updater/1.0"}
                        )

                    if check_resp.status_code == 404:
                        err_msg = f"Nguồn tải gói cài đặt không tồn tại trên máy chủ (Lỗi HTTP 404 Not Found - URL: {dl_url}). Vui lòng kiểm tra lại cấu hình phát hành."
                        logger.error(err_msg)
                        self.check_finished.emit(False, None, err_msg)
                        return
                    elif check_resp.status_code >= 500:
                        err_msg = f"Máy chủ lưu trữ gói cài đặt đang gặp sự cố nội bộ (Lỗi HTTP {check_resp.status_code} - URL: {dl_url})."
                        logger.error(err_msg)
                        self.check_finished.emit(False, None, err_msg)
                        return
                    elif check_resp.status_code != 200:
                        err_msg = f"Không thể truy cập tệp cài đặt (Mã lỗi HTTP {check_resp.status_code} - URL: {dl_url})."
                        logger.error(err_msg)
                        self.check_finished.emit(False, None, err_msg)
                        return

                    # Nếu máy chủ trả Content-Length và manifest chưa có size, tự động bổ sung
                    cl_header = check_resp.headers.get("content-length")
                    if cl_header and cl_header.isdigit():
                        server_size = int(cl_header)
                        if manifest.file_size_bytes <= 0:
                            manifest.file_size_bytes = server_size
                        elif manifest.file_size_bytes != server_size:
                            logger.warning(
                                f"Dung lượng công bố ({manifest.file_size_bytes}) khác Content-Length máy chủ ({server_size}). Sử dụng kích thước thực tế máy chủ."
                            )
                            manifest.file_size_bytes = server_size
                except requests.exceptions.RequestException as dl_err:
                    err_msg = f"Lỗi kết nối khi kiểm tra nguồn tải bộ cài ({dl_url}): {dl_err}"
                    logger.error(err_msg)
                    self.check_finished.emit(False, None, err_msg)
                    return

            msg = f"Đã tìm thấy phiên bản mới: v{manifest.version} (Build {manifest.build})"
            self.check_finished.emit(True, manifest, msg)

        except Exception as e:
            logger.warning(f"Lỗi khi kiểm tra cập nhật từ {self.manifest_url}: {e}")
            self.check_finished.emit(False, None, f"Lỗi không xác định khi kiểm tra cập nhật: {e}")


class UpdateDownloadWorker(QThread):
    """Worker tải gói cài đặt an toàn, hỗ trợ redirect, streaming chunk, và xác thực SHA-256."""
    progress_changed = Signal(int, int, int)  # percent (-1 nếu không rõ tổng kích thước), downloaded_bytes, total_bytes
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
        placeholder_domains = ["example.com", "example.org", "placeholder", "your-domain.com"]
        if any(p in url.lower() for p in placeholder_domains):
            self.download_finished.emit(
                False, "",
                "Đường dẫn tải gói cài đặt là URL mẫu (example.com), chưa được cấu hình máy chủ phát hành thực tế."
            )
            return

        os.makedirs(self.dest_dir, exist_ok=True)
        raw_name = os.path.basename(urlparse(url).path) or f"1998-TEAM-Setup-v{self.manifest.version}.exe"
        if not raw_name.endswith(".exe"):
            raw_name += ".exe"

        dest_file = os.path.join(self.dest_dir, raw_name)
        temp_file = dest_file + ".part"

        # Nếu tệp tạm cũ còn sót lại từ lần trước, xóa dọn dẹp
        self._cleanup_temp(temp_file)

        try:
            # 1. Hỗ trợ tệp cục bộ (Local Testing / LAN Share)
            if os.path.exists(url) or url.startswith("file://"):
                src_path = url.replace("file:///", "").replace("file://", "")
                if not os.path.exists(src_path):
                    self.download_finished.emit(False, "", f"Không tìm thấy tệp cài đặt tại: {src_path}")
                    return

                total_bytes = os.path.getsize(src_path)
                downloaded = 0
                with open(src_path, "rb") as f_in, open(temp_file, "wb") as f_out:
                    while self._running:
                        chunk = f_in.read(65536)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        downloaded += len(chunk)
                        percent = min(100, int((downloaded / total_bytes) * 100)) if total_bytes > 0 else -1
                        self.progress_changed.emit(percent, downloaded, total_bytes)

                if not self._running:
                    self._cleanup_temp(temp_file)
                    self.download_finished.emit(False, "", "Tiến trình tải xuống đã bị hủy bởi người dùng.")
                    return
            else:
                # 2. Tải qua HTTP/HTTPS hỗ trợ đầy đủ redirects (301, 302, 307, 308)
                try:
                    resp = requests.get(
                        url,
                        stream=True,
                        timeout=12.0,
                        allow_redirects=True,
                        headers={"User-Agent": "1998TeamPhotobooth-Updater/1.0"}
                    )
                except requests.exceptions.Timeout:
                    self._cleanup_temp(temp_file)
                    self.download_finished.emit(False, "", "Quá thời gian chờ máy chủ phản hồi khi tải gói cài đặt (Timeout).")
                    return
                except requests.exceptions.ConnectionError:
                    self._cleanup_temp(temp_file)
                    self.download_finished.emit(False, "", "Không thể kết nối đến máy chủ tải bộ cài. Vui lòng kiểm tra lại mạng Internet.")
                    return
                except requests.exceptions.RequestException as req_err:
                    self._cleanup_temp(temp_file)
                    self.download_finished.emit(False, "", f"Lỗi kết nối tải gói cài đặt: {req_err}")
                    return

                with resp:
                    if resp.status_code == 404:
                        self._cleanup_temp(temp_file)
                        self.download_finished.emit(
                            False, "",
                            f"Tệp cài đặt không tồn tại trên máy chủ (Lỗi HTTP 404 Not Found - URL: {url}). Vui lòng kiểm tra lại cấu hình phát hành."
                        )
                        return
                    elif resp.status_code >= 500:
                        self._cleanup_temp(temp_file)
                        self.download_finished.emit(
                            False, "",
                            f"Máy chủ lưu trữ bộ cài gặp sự cố nội bộ (Mã lỗi HTTP {resp.status_code} - URL: {url})."
                        )
                        return
                    elif resp.status_code != 200:
                        self._cleanup_temp(temp_file)
                        self.download_finished.emit(
                            False, "",
                            f"Không thể tải bộ cài đặt (Mã lỗi HTTP {resp.status_code} - URL: {url})."
                        )
                        return

                    # Xác định kích thước: Content-Length từ header hoặc manifest
                    cl_header = resp.headers.get("content-length")
                    content_length = int(cl_header) if (cl_header and cl_header.isdigit()) else 0
                    total_bytes = content_length or self.manifest.file_size_bytes
                    downloaded = 0

                    with open(temp_file, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if not self._running:
                                self._cleanup_temp(temp_file)
                                self.download_finished.emit(False, "", "Tiến trình tải xuống đã bị hủy bởi người dùng.")
                                return
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_bytes > 0:
                                    percent = min(100, int((downloaded / total_bytes) * 100))
                                else:
                                    percent = -1  # Không có Content-Length: indeterminate
                                self.progress_changed.emit(percent, downloaded, total_bytes)

            # Kiểm tra trạng thái hủy
            if not self._running:
                self._cleanup_temp(temp_file)
                self.download_finished.emit(False, "", "Tiến trình tải xuống đã bị hủy bởi người dùng.")
                return

            # Kiểm tra tệp tạm có dữ liệu không
            if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                self._cleanup_temp(temp_file)
                self.download_finished.emit(False, "", "Tệp tải về rỗng (0 bytes).")
                return

            # 3. Tính toán và xác minh mã băm SHA-256
            hasher = hashlib.sha256()
            with open(temp_file, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            actual_sha256 = hasher.hexdigest().lower()

            expected_sha256 = self.manifest.sha256.lower().strip()
            if not expected_sha256:
                self._cleanup_temp(temp_file)
                err = "Gói cài đặt chưa có mã băm SHA-256 đáng tin cậy được công bố. Cài đặt tự động bị từ chối để đảm bảo an toàn."
                logger.error(err)
                self.download_finished.emit(False, "", err)
                return
            elif actual_sha256 != expected_sha256:
                self._cleanup_temp(temp_file)
                err = f"Xác thực tính toàn vẹn thất bại: Mã SHA-256 thực tế ({actual_sha256[:12]}...) không khớp với chữ ký ({expected_sha256[:12]}...). Tệp tạm đã bị hủy bỏ."
                logger.error(err)
                self.download_finished.emit(False, "", err)
                return

            # 4. Kiểm tra dung lượng tệp nếu manifest có định nghĩa
            actual_size = os.path.getsize(temp_file)
            if self.manifest.file_size_bytes > 0 and actual_size != self.manifest.file_size_bytes:
                self._cleanup_temp(temp_file)
                err = f"Dung lượng tệp tải về ({actual_size} bytes) không khớp với dung lượng công bố ({self.manifest.file_size_bytes} bytes)."
                logger.error(err)
                self.download_finished.emit(False, "", err)
                return

            # 5. Kiểm tra chữ ký số nếu có
            sig_info = verify_digital_signature(temp_file)
            if sig_info.get("status") == "HashMismatch":
                self._cleanup_temp(temp_file)
                err = "Chữ ký số Authenticode của tệp cài đặt bị hỏng hoặc không hợp lệ (HashMismatch)."
                logger.error(err)
                self.download_finished.emit(False, "", err)
                return
            elif sig_info.get("valid"):
                logger.info(f"Đã xác minh chữ ký số Authenticode hợp lệ cho: {dest_file}")

            # 6. Đổi tên tệp tạm hoàn chỉnh sang tệp đích
            if os.path.exists(dest_file):
                try:
                    os.remove(dest_file)
                except Exception:
                    pass
            os.rename(temp_file, dest_file)

            logger.info(f"Đã tải và xác thực thành công bộ cài mới: {dest_file} ({actual_size} bytes)")
            self.download_finished.emit(True, dest_file, "")

        except Exception as e:
            self._cleanup_temp(temp_file)
            logger.error(f"Lỗi khi tải bộ cài: {e}")
            self.download_finished.emit(False, "", f"Lỗi khi tải bộ cài: {e}")

    def _cleanup_temp(self, temp_file: str):
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass


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
        url = self.config_mgr.get("updates.manifest_url", "")
        if not url:
            return DEFAULT_UPDATE_URL
        return normalize_update_url(str(url))

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
        """Khởi chạy luồng kiểm tra cập nhật (ngăn chặn chạy đồng thời)."""
        if (self._check_worker and self._check_worker.isRunning()) or (self._download_worker and self._download_worker.isRunning()):
            logger.info("Tiến trình cập nhật đang chạy, bỏ qua yêu cầu kiểm tra mới.")
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

    @property
    def latest_manifest(self) -> Optional[UpdateManifest]:
        return self._latest_manifest

    def cancel_download(self):
        """Hủy tiến trình tải bộ cài đặt hiện tại và dọn dẹp an toàn."""
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.stop()

    def start_download(self, manifest: UpdateManifest):
        """Khởi chạy luồng tải bộ cài (ngăn chặn chạy đồng thời)."""
        if self._download_worker and self._download_worker.isRunning():
            logger.info("Tiến trình tải xuống đang chạy.")
            return

        app_dir = get_user_data_dir()
        download_dir = os.path.join(app_dir, "Downloads")

        self._download_worker = UpdateDownloadWorker(manifest, download_dir, parent=self)
        self._download_worker.progress_changed.connect(self.download_progress.emit)
        self._download_worker.download_finished.connect(self.download_completed.emit)
        self._download_worker.start()

    def apply_update_and_restart(self, installer_path: str, user_data_dir: Optional[str] = None) -> bool:
        """
        Sao lưu cấu hình hiện tại, chạy bộ cài đặt Windows, và đóng ứng dụng an toàn.
        """
        if not os.path.exists(installer_path):
            logger.error(f"Tệp bộ cài đặt không tồn tại: {installer_path}")
            return False

        try:
            # 1. Tạo bản sao lưu an toàn toàn bộ cấu hình trước khi nâng cấp
            backup_dir = user_data_dir
            if not backup_dir and hasattr(self.config_mgr, "config_path") and self.config_mgr.config_path:
                backup_dir = os.path.dirname(self.config_mgr.config_path)

            create_pre_update_backup(user_data_dir=backup_dir)

            # 2. Khởi chạy bộ cài đặt Inno Setup
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
