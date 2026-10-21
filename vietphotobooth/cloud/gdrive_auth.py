"""
Google Drive OAuth2 Desktop Loopback Authentication with Windows DPAPI Encryption.
Handles user authorization, token exchange, refresh, secure DPAPI persistence, and revocation.
"""

import os
import json
import time
import socket
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any, Tuple
import requests

from vietphotobooth.core.logger import get_logger

logger = get_logger()

# Windows DPAPI
try:
    import win32crypt
    HAS_DPAPI = True
except ImportError:
    HAS_DPAPI = False

# Google OAuth2 Endpoints & Scopes
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email"
]

DEFAULT_TOKEN_FILE = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "1998TeamPhotobooth",
    "gdrive_token.dat"
)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Xử lý redirect callback từ Google OAuth2 trên localhost."""

    def log_message(self, format, *args):
        # Ẩn bớt log access HTTP console
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            self.server.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            success_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>1998 TEAM Photobooth — Kết nối Google Drive thành công</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                        background: #0B132B;
                        color: #E2E8F0;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                    }
                    .card {
                        background: #111E38;
                        border: 2px solid #D4AF37;
                        border-radius: 16px;
                        padding: 32px 48px;
                        text-align: center;
                        box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                        max-width: 460px;
                    }
                    h2 { color: #F5DE88; margin-bottom: 12px; }
                    p { font-size: 15px; color: #94A3B8; line-height: 1.5; }
                    .badge {
                        background: #10B981;
                        color: white;
                        padding: 6px 14px;
                        border-radius: 20px;
                        font-weight: bold;
                        display: inline-block;
                        margin-bottom: 18px;
                    }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="badge">✓ THÀNH CÔNG</div>
                    <h2>1998 TEAM Photobooth</h2>
                    <p>Đã cấp quyền kết nối Google Drive thành công!<br>Bạn có thể đóng tab trình duyệt này và quay lại phần mềm.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode("utf-8"))
        else:
            err = params.get("error", ["Unknown error"])[0]
            self.server.auth_error = err
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            error_html = f"""
            <!DOCTYPE html>
            <html><body style="background:#0B132B;color:#F87171;font-family:sans-serif;padding:40px;text-align:center;">
                <h2>Kết nối thất bại</h2>
                <p>Google trả về lỗi: {err}</p>
            </body></html>
            """
            self.wfile.write(error_html.encode("utf-8"))


class GDriveAuth:
    """Quản lý xác thực OAuth2 Desktop với Google Drive và bảo mật DPAPI."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token_path: str = DEFAULT_TOKEN_FILE,
        simulation_mode: bool = False
    ):
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self.token_path = token_path
        self.simulation_mode = simulation_mode
        self._tokens: Optional[Dict[str, Any]] = None

        # Nạp token đã lưu từ trước nếu có
        self.load_token()

    def _encrypt_data(self, plaintext: str) -> bytes:
        """Mã hóa bằng Windows DPAPI CryptProtectData."""
        raw_bytes = plaintext.encode("utf-8")
        if HAS_DPAPI:
            try:
                return win32crypt.CryptProtectData(raw_bytes, "1998TeamPhotobooth", None, None, None, 0)
            except Exception as e:
                logger.warning(f"Lỗi khi mã hóa DPAPI: {e}. Fallback sang raw bytes.")
        return raw_bytes

    def _decrypt_data(self, cipher_bytes: bytes) -> str:
        """Giải mã bằng Windows DPAPI CryptUnprotectData."""
        if HAS_DPAPI:
            try:
                decrypted = win32crypt.CryptUnprotectData(cipher_bytes, None, None, None, 0)[1]
                return decrypted.decode("utf-8")
            except Exception as e:
                logger.warning(f"Lỗi khi giải mã DPAPI: {e}. Thử parse trực tiếp.")
        return cipher_bytes.decode("utf-8")

    def save_token(self, token_data: Dict[str, Any]):
        """Lưu trữ dữ liệu token vào file sau khi mã hóa DPAPI."""
        self._tokens = token_data
        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        try:
            cipher = self._encrypt_data(json.dumps(token_data))
            with open(self.token_path, "wb") as f:
                f.write(cipher)
            logger.info("Đã lưu trữ token Google Drive an toàn bằng Windows DPAPI.")
        except Exception as e:
            logger.error(f"Không thể lưu file token Google Drive: {e}")

    def load_token(self) -> Optional[Dict[str, Any]]:
        """Đọc và giải mã dữ liệu token từ đĩa."""
        if not os.path.exists(self.token_path):
            return None
        try:
            with open(self.token_path, "rb") as f:
                cipher = f.read()
            plaintext = self._decrypt_data(cipher)
            self._tokens = json.loads(plaintext)
            return self._tokens
        except Exception as e:
            logger.error(f"Lỗi đọc token Google Drive: {e}")
            self._tokens = None
            return None

    def is_authenticated(self) -> bool:
        """Kiểm tra trạng thái đăng nhập hợp lệ (hoặc Simulator)."""
        if self.simulation_mode:
            return True
        if not self._tokens:
            return False
        return bool(self._tokens.get("access_token") or self._tokens.get("refresh_token"))

    def get_valid_access_token(self) -> Optional[str]:
        """Lấy access token hợp lệ, tự động refresh nếu sắp hết hạn."""
        if self.simulation_mode:
            return "simulated_gdrive_access_token"

        if not self._tokens:
            self.load_token()
        if not self._tokens:
            return None

        # Kiểm tra hạn dùng
        expires_at = self._tokens.get("expires_at", 0)
        now = time.time()

        # Nếu còn hơn 2 phút thì dùng tiếp
        if expires_at - now > 120 and "access_token" in self._tokens:
            return self._tokens["access_token"]

        # Nếu có refresh_token thì làm mới
        refresh_token = self._tokens.get("refresh_token")
        if refresh_token and self.client_id and self.client_secret:
            logger.info("Access token sắp hết hạn, đang tự động làm mới từ Google OAuth...")
            refreshed = self.refresh_access_token(refresh_token)
            if refreshed:
                return self._tokens.get("access_token")

        return self._tokens.get("access_token")

    def refresh_access_token(self, refresh_token: str) -> bool:
        """Làm mới access token qua refresh_token."""
        try:
            resp = requests.post(
                TOKEN_ENDPOINT,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                },
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                self._tokens["access_token"] = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self._tokens["expires_at"] = time.time() + expires_in
                if "refresh_token" in data:
                    self._tokens["refresh_token"] = data["refresh_token"]
                self.save_token(self._tokens)
                logger.info("Đã làm mới access token Google Drive thành công.")
                return True
            else:
                logger.error(f"Lỗi làm mới token: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Ngoại lệ khi làm mới access token: {e}")
            return False

    def authorize_interactive(self, timeout_sec: int = 120) -> Tuple[bool, str]:
        """Khởi chạy trình duyệt và web server cục bộ để thực hiện OAuth2 loopback."""
        if self.simulation_mode:
            self._tokens = {
                "access_token": "simulated_access_token",
                "refresh_token": "simulated_refresh_token",
                "expires_at": time.time() + 86400,
                "user_email": "studio1998.demo@gmail.com",
                "user_name": "1998 Studio Demo",
                "is_simulation": True
            }
            self.save_token(self._tokens)
            return True, "Đã kích hoạt chế độ Giả lập Google Drive (Simulator)."

        if not self.client_id or not self.client_secret:
            return False, "Chưa cung cấp Client ID hoặc Client Secret của Google Cloud."

        # Tìm port trống cho loopback
        port = 8088
        for p in range(8088, 8100):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("localhost", p)) != 0:
                    port = p
                    break

        redirect_uri = f"http://localhost:{port}/oauth2callback"

        # Tạo HTTP server
        server = HTTPServer(("localhost", port), OAuthCallbackHandler)
        server.auth_code = None
        server.auth_error = None

        # Build auth URL
        scopes_str = " ".join(SCOPES)
        auth_url = (
            f"{AUTH_ENDPOINT}?client_id={self.client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={scopes_str}"
            f"&access_type=offline"
            f"&prompt=consent"
        )

        logger.info(f"Khởi chạy OAuth2 loopback tại {redirect_uri}")
        webbrowser.open(auth_url)

        # Đợi callback
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            server.handle_request()
            if server.auth_code or server.auth_error:
                break

        server.server_close()

        if server.auth_error:
            return False, f"Lỗi ủy quyền từ Google: {server.auth_error}"
        if not server.auth_code:
            return False, "Quá thời gian chờ phản hồi ủy quyền từ trình duyệt."

        # Trao đổi code lấy access & refresh tokens
        try:
            token_resp = requests.post(
                TOKEN_ENDPOINT,
                data={
                    "code": server.auth_code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                },
                timeout=15
            )
            if token_resp.status_code != 200:
                return False, f"Lỗi trao đổi mã ủy quyền: {token_resp.text}"

            token_data = token_resp.json()
            token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)

            # Lấy thông tin user
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            user_resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers, timeout=10)
            if user_resp.status_code == 200:
                uinfo = user_resp.json()
                token_data["user_email"] = uinfo.get("email", "")
                token_data["user_name"] = uinfo.get("name", "")

            self.save_token(token_data)
            return True, f"Kết nối thành công với tài khoản: {token_data.get('user_email', 'Google User')}"
        except Exception as e:
            return False, f"Ngoại lệ khi xác thực Google Drive: {e}"

    def revoke(self) -> Tuple[bool, str]:
        """Hủy quyền truy cập và xóa file token."""
        if self._tokens:
            token_to_revoke = self._tokens.get("refresh_token") or self._tokens.get("access_token")
            if token_to_revoke and not self._tokens.get("is_simulation"):
                try:
                    requests.post(REVOKE_ENDPOINT, params={"token": token_to_revoke}, timeout=10)
                except Exception as e:
                    logger.warning(f"Không thể gửi yêu cầu revoke lên Google: {e}")

        self._tokens = None
        if os.path.exists(self.token_path):
            try:
                os.remove(self.token_path)
            except Exception as e:
                logger.error(f"Không thể xóa file token: {e}")

        logger.info("Đã hủy kết nối tài khoản Google Drive.")
        return True, "Đã ngắt kết nối Google Drive thành công."
