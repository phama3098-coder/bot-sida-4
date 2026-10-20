"""
VietPhotoBooth Main Entrypoint
Starts the backend server and launches the kiosk web interface on Windows.
"""

import os
import sys
import time
import socket
import webbrowser
import threading
import uvicorn

# Thêm thư mục gốc vào sys.path để import các module
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from vietphotobooth.core.logger import get_logger
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.server import create_app

logger = get_logger()

def wait_for_server(host: str, port: int, timeout: float = 8.0) -> bool:
    """Chờ cho đến khi server mở cổng TCP thành công."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.15)
    return False

def open_browser(url: str) -> None:
    """Mở trình duyệt sau khi máy chủ đã sẵn sàng."""
    if wait_for_server("127.0.0.1", 8080):
        logger.info(f"Đang mở giao diện Kiosk tại: {url}")
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.warning(f"Không thể mở trình duyệt tự động: {e}")

def main():
    print("=" * 60)
    print("      VIETPHOTOBOOTH - HỆ THỐNG PHOTOBOOTH CHUYÊN NGHIỆP")
    print("                 DÀNH CHO WINDOWS 10 / 11")
    print("=" * 60)

    config = ConfigManager()
    port = int(config.get("lan_server_port", 8080))
    host = "0.0.0.0"

    logger.info(f"Khởi động VietPhotoBooth trên {host}:{port}...")

    # Chạy luồng mở trình duyệt
    kiosk_url = f"http://localhost:{port}/"
    threading.Thread(target=open_browser, args=(kiosk_url,), daemon=True).start()

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")

if __name__ == "__main__":
    main()
