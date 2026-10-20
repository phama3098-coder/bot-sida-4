"""
VietPhotoBooth LAN Sharing Token Manager & QR Generator
Generates secure non-guessable tokens, QR codes, and enforces access control and expiration.
"""

import os
import io
import time
import socket
import secrets
from datetime import datetime
from typing import Dict, Any, Optional
import qrcode
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class ShareToken:
    def __init__(
        self,
        token: str,
        file_path: str,
        event_name: str,
        expire_hours: int = 24
    ):
        self.token = token
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.event_name = event_name
        self.created_at = time.time()
        self.expires_at = self.created_at + (expire_hours * 3600)
        self.is_revoked = False
        self.download_count = 0

    @property
    def is_valid(self) -> bool:
        if self.is_revoked:
            return False
        if time.time() > self.expires_at:
            return False
        return os.path.exists(self.file_path)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "filename": self.filename,
            "event_name": self.event_name,
            "is_valid": self.is_valid,
            "is_revoked": self.is_revoked,
            "download_count": self.download_count,
            "created_at": datetime.fromtimestamp(self.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": datetime.fromtimestamp(self.expires_at).strftime("%Y-%m-%d %H:%M:%S")
        }

class TokenManager:
    def __init__(self, port: int = 8080):
        self.port = port
        self._tokens: Dict[str, ShareToken] = {}

    @staticmethod
    def get_local_ip() -> str:
        """Tự động phát hiện địa chỉ IP mạng nội bộ (LAN) của máy tính Photobooth."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Không gửi gói tin ra ngoài, chỉ mượn cơ chế routing để lấy local IP
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def create_share_token(self, file_path: str, event_name: str, expire_hours: int = 24) -> ShareToken:
        """Sinh mã token ngẫu nhiên độ an toàn cao 128-bit."""
        token = secrets.token_urlsafe(16)
        share_obj = ShareToken(
            token=token,
            file_path=os.path.abspath(file_path),
            event_name=event_name,
            expire_hours=expire_hours
        )
        self._tokens[token] = share_obj
        logger.info(f"Đã tạo token chia sẻ ảnh {share_obj.filename} (Hết hạn sau {expire_hours}h)")
        return share_obj

    def get_token(self, token: str) -> Optional[ShareToken]:
        share_obj = self._tokens.get(token)
        if share_obj and share_obj.is_valid:
            return share_obj
        return None

    def revoke_token(self, token: str) -> bool:
        """Thu hồi quyền truy cập đường dẫn chia sẻ ngay lập tức."""
        if token in self._tokens:
            self._tokens[token].is_revoked = True
            logger.info(f"Đã thu hồi token chia sẻ {token}")
            return True
        return False

    def list_tokens(self) -> Dict[str, Any]:
        return {
            "local_ip": self.get_local_ip(),
            "port": self.port,
            "tokens": [t.to_dict() for t in self._tokens.values()]
        }

    def get_share_url(self, token: str) -> str:
        ip = self.get_local_ip()
        return f"http://{ip}:{self.port}/s/{token}"

    def generate_qr_bytes(self, url: str) -> bytes:
        """Tạo ảnh mã QR định dạng PNG bytes chất lượng cao."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#000000", back_color="#FFFFFF")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
