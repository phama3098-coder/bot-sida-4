"""
Google Drive REST API v3 Client.
Supports folder creation, photo uploads, public permission sharing, and web view links.
"""

import os
import json
import mimetypes
from typing import Optional, Dict, Any, List, Tuple
import requests

from .gdrive_auth import GDriveAuth
from vietphotobooth.core.logger import get_logger

logger = get_logger()

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
UPLOAD_API_BASE = "https://www.googleapis.com/upload/drive/v3"


class GDriveClient:
    """Client tương tác với Google Drive API v3 phục vụ lưu trữ và chia sẻ ảnh Photobooth."""

    def __init__(self, auth: GDriveAuth):
        self.auth = auth

    def _get_headers(self) -> Optional[Dict[str, str]]:
        token = self.auth.get_valid_access_token()
        if not token:
            return None
        return {
            "Authorization": f"Bearer {token}"
        }

    def get_user_profile(self) -> Dict[str, str]:
        """Lấy thông tin tài khoản Google đã kết nối."""
        if self.auth.simulation_mode:
            return {
                "name": "1998 Studio Demo",
                "email": "studio1998.demo@gmail.com",
                "is_simulation": True
            }

        headers = self._get_headers()
        if not headers:
            return {}

        try:
            resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "name": data.get("name", ""),
                    "email": data.get("email", ""),
                    "picture": data.get("picture", "")
                }
        except Exception as e:
            logger.error(f"Lỗi truy vấn hồ sơ Google: {e}")
        return {}

    def get_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Tìm hoặc tạo mới thư mục trên Google Drive."""
        if self.auth.simulation_mode:
            sim_id = f"sim_folder_{folder_name.replace(' ', '_').lower()}"
            logger.info(f"[SIMULATOR] Tạo/Tìm thư mục Google Drive: {folder_name} -> ID: {sim_id}")
            return sim_id

        headers = self._get_headers()
        if not headers:
            logger.error("Chưa có token hợp lệ để tạo thư mục.")
            return None

        # Tìm thư mục đã tồn tại chưa
        query = f"mimeType = 'application/vnd.google-apps.folder' and name = '{folder_name}' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        try:
            search_resp = requests.get(
                f"{DRIVE_API_BASE}/files",
                headers=headers,
                params={"q": query, "spaces": "drive", "fields": "files(id, name)"},
                timeout=15
            )
            if search_resp.status_code == 200:
                files = search_resp.json().get("files", [])
                if files:
                    folder_id = files[0]["id"]
                    logger.info(f"Đã tìm thấy thư mục Google Drive có sẵn: '{folder_name}' (ID: {folder_id})")
                    return folder_id

            # Nếu chưa có thì tạo mới
            body: Dict[str, Any] = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder"
            }
            if parent_id:
                body["parents"] = [parent_id]

            create_resp = requests.post(
                f"{DRIVE_API_BASE}/files",
                headers={**headers, "Content-Type": "application/json"},
                data=json.dumps(body),
                timeout=15
            )
            if create_resp.status_code in (200, 201):
                folder_id = create_resp.json().get("id")
                logger.info(f"Đã tạo mới thư mục Google Drive: '{folder_name}' (ID: {folder_id})")
                return folder_id
            else:
                logger.error(f"Lỗi tạo thư mục Google Drive: {create_resp.status_code} {create_resp.text}")
                return None
        except Exception as e:
            logger.error(f"Ngoại lệ khi tạo thư mục Google Drive: {e}")
            return None

    def set_public_permission(self, file_or_folder_id: str, role: str = "reader") -> bool:
        """Cấp quyền truy cập công khai qua liên kết (Anyone with the link can view)."""
        if self.auth.simulation_mode:
            logger.info(f"[SIMULATOR] Đã cấp quyền công khai cho ID: {file_or_folder_id}")
            return True

        headers = self._get_headers()
        if not headers:
            return False

        try:
            perm_body = {
                "role": role,
                "type": "anyone"
            }
            resp = requests.post(
                f"{DRIVE_API_BASE}/files/{file_or_folder_id}/permissions",
                headers={**headers, "Content-Type": "application/json"},
                data=json.dumps(perm_body),
                timeout=15
            )
            if resp.status_code in (200, 201):
                logger.info(f"Đã kích hoạt quyền công khai thành công cho file/thư mục {file_or_folder_id}")
                return True
            else:
                logger.error(f"Không thể cấp quyền chia sẻ: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Ngoại lệ khi cấp quyền chia sẻ công khai: {e}")
            return False

    def upload_photo(
        self,
        file_path: str,
        folder_id: Optional[str] = None,
        description: str = "1998 TEAM Photobooth Photo",
        make_public: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Tải ảnh lên Google Drive bằng phương thức Multipart Upload."""
        if not os.path.exists(file_path):
            logger.error(f"File ảnh không tồn tại: {file_path}")
            return None

        filename = os.path.basename(file_path)

        # Chế độ giả lập
        if self.auth.simulation_mode:
            sim_id = f"sim_file_{abs(hash(file_path))}"
            web_link = f"https://drive.google.com/file/d/{sim_id}/view?usp=sharing"
            logger.info(f"[SIMULATOR] Đã tải lên ảnh mẫu: {filename} -> {web_link}")
            return {
                "id": sim_id,
                "name": filename,
                "webViewLink": web_link,
                "webContentLink": web_link,
                "is_simulation": True
            }

        headers = self._get_headers()
        if not headers:
            logger.error("Không có token hợp lệ để tải file lên Google Drive.")
            return None

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "image/jpeg"

        metadata: Dict[str, Any] = {
            "name": filename,
            "description": description
        }
        if folder_id:
            metadata["parents"] = [folder_id]

        try:
            with open(file_path, "rb") as f:
                file_content = f.read()

            boundary = "-------1998TeamPhotoboothBoundary"
            body = (
                f"--{boundary}\r\n"
                f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{json.dumps(metadata)}\r\n"
                f"--{boundary}\r\n"
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode("utf-8") + file_content + f"\r\n--{boundary}--\r\n".encode("utf-8")

            upload_headers = {
                **headers,
                "Content-Type": f"multipart/related; boundary={boundary}",
                "Content-Length": str(len(body))
            }

            resp = requests.post(
                f"{UPLOAD_API_BASE}/files?uploadType=multipart&fields=id,name,webViewLink,webContentLink",
                headers=upload_headers,
                data=body,
                timeout=60
            )

            if resp.status_code in (200, 201):
                res_data = resp.json()
                file_id = res_data.get("id")
                logger.info(f"Đã tải thành công ảnh '{filename}' lên Google Drive (ID: {file_id})")

                if make_public and file_id:
                    self.set_public_permission(file_id, role="reader")

                return res_data
            else:
                logger.error(f"Lỗi tải ảnh lên Google Drive: {resp.status_code} {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Ngoại lệ khi tải file ảnh lên Google Drive: {e}")
            return None

    def get_folder_share_link(self, folder_id: str) -> str:
        """Sinh đường dẫn công khai xem thư mục sự kiện trên Google Drive."""
        return f"https://drive.google.com/drive/folders/{folder_id}?usp=sharing"
