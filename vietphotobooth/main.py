"""
VietPhotoBooth Main Desktop Entrypoint
Launches the native Windows PySide6 Desktop GUI as the primary interface,
with an auxiliary FastAPI background service for LAN QR mobile downloads.
"""

import os
import sys
import argparse
import threading
import uvicorn

# Thêm thư mục gốc vào sys.path để import các module
if getattr(sys, 'frozen', False):
    root_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from vietphotobooth.core.logger import get_logger
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.server import create_app
from vietphotobooth.desktop.main_window import MainWindow

logger = get_logger()

def run_sharing_server(host: str, port: int):
    """Chạy máy chủ chia sẻ ảnh nội bộ qua QR dưới dạng tiến trình nền daemon."""
    try:
        app = create_app()
        logger.info(f"Khởi động máy chủ chia sẻ ảnh LAN tại http://{host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
    except Exception as e:
        logger.warning(f"Không thể khởi động máy chủ chia sẻ LAN: {e}")

def main():
    parser = argparse.ArgumentParser(description="1998 TEAM — Photobooth | Ứng Dụng Photobooth Chuyên Nghiệp Windows")
    parser.add_argument("--kiosk", action="store_true", help="Khởi động trực tiếp ở chế độ toàn màn hình Kiosk")
    parser.add_argument("--no-server", action="store_true", help="Không khởi động máy chủ chia sẻ LAN")
    parser.add_argument("--port", type=int, default=None, help="Cổng máy chủ chia sẻ LAN (mặc định: 8080)")
    parser.add_argument("--updated-from", type=str, default=None, help="Thông báo nâng cấp từ phiên bản cũ")
    parser.add_argument("--updated-to", type=str, default=None, help="Phiên bản mới vừa nâng cấp lên")
    parser.add_argument("--updated-build", type=int, default=0, help="Số build vừa nâng cấp lên")
    parser.add_argument("--update-failed", type=str, default=None, help="Mã lỗi cập nhật thất bại")
    args = parser.parse_args()

    # Đăng ký AppUserModelID cho Windows Taskbar hiển thị đúng icon
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("1998team.photobooth.studio.1")
        except Exception:
            pass

    print("=" * 65)
    print("      1998 TEAM — PHOTOBOOTH CHUYÊN NGHIỆP")
    print("       1998 STUDIO PHÓNG SỰ CƯỚI & SỰ KIỆN")
    print("             NATIVE DESKTOP GUI DÀNH CHO WINDOWS 10 / 11")
    print("=" * 65)

    config = ConfigManager()
    lan_port = args.port or int(config.get("lan_server_port", 8000))

    # Khởi động máy chủ LAN chia sẻ QR phụ trợ trong luồng nền
    if not args.no_server:
        server_thread = threading.Thread(
            target=run_sharing_server,
            args=("0.0.0.0", lan_port),
            daemon=True
        )
        server_thread.start()

    # Khởi chạy giao diện Desktop Native PySide6
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("1998 TEAM — Photobooth")
    qt_app.setOrganizationName("1998 Studio")

    # Khởi tạo phông chữ tiếng Việt chuẩn hóa và gán cho toàn bộ ứng dụng trước khi dựng giao diện
    from vietphotobooth.core.font_registry import FontRegistry
    FontRegistry.initialize()
    default_app_font = FontRegistry.get_default_application_font(point_size=10)
    qt_app.setFont(default_app_font)

    icon_path = os.path.abspath(os.path.join(root_dir, "Assets", "Branding", "app_icon.ico"))
    if os.path.exists(icon_path):
        from PySide6.QtGui import QIcon
        qt_app.setWindowIcon(QIcon(icon_path))

    update_info = None
    if args.updated_to or args.update_failed:
        update_info = {
            "updated_from": args.updated_from,
            "updated_to": args.updated_to,
            "updated_build": args.updated_build,
            "update_failed": args.update_failed,
        }

    window = MainWindow(start_in_kiosk=args.kiosk, update_info=update_info)
    window.show()

    logger.info("Giao diện Desktop 1998 TEAM — Photobooth đã sẵn sàng.")
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()
