"""
VietPhotoBooth Windows Print Spooler Integration
Direct communication with Windows Print Spooler via Win32 API (win32print, win32ui, win32con).
"""

import os
import sys
import time
from typing import List, Dict, Any, Optional
from PIL import Image, ImageWin
from vietphotobooth.core.logger import get_logger

logger = get_logger()

# Kiểm tra sự sẵn sàng của thư viện Win32 trên Windows
WIN32_AVAILABLE = False
try:
    import win32print
    import win32ui
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    logger.warning("Thư viện pywin32 chưa sẵn sàng, hệ thống in sẽ chuyển sang chế độ giả lập.")

# Mã lỗi và trạng thái máy in theo Windows Win32 API
PRINTER_STATUS_MAP = {
    0x00000001: "Máy in bị tạm dừng (Paused)",
    0x00000002: "Máy in báo lỗi (Error)",
    0x00000004: "Đang xóa lệnh in (Pending Deletion)",
    0x00000008: "Kẹt giấy (Paper Jam)",
    0x00000010: "Hết giấy (Paper Out)",
    0x00000020: "Cần nạp giấy thủ công (Manual Feed)",
    0x00000040: "Lỗi khay giấy (Paper Problem)",
    0x00000080: "Máy in ngoại tuyến / Mất kết nối (Offline)",
    0x00000100: "Đang nạp dữ liệu (IO Active)",
    0x00000200: "Bận (Busy)",
    0x00000400: "Đang in (Printing)",
    0x00000800: "Đầu ra đầy (Output Bin Full)",
    0x00001000: "Hết mực / Ruy-băng (No Toner/Ribbon)",
    0x00002000: "Mở nắp máy in (Door Open)",
}

class WindowsPrintSpooler:
    @staticmethod
    def is_available() -> bool:
        return WIN32_AVAILABLE

    @staticmethod
    def get_installed_printers() -> List[Dict[str, Any]]:
        """Liệt kê danh sách tất cả máy in đã cài đặt trên hệ thống Windows."""
        printers = []
        if not WIN32_AVAILABLE:
            return [{
                "name": "Giả Lập Máy In Windows (Virtual Printer)",
                "is_default": True,
                "status": "Sẵn sàng (Giả lập)",
                "port": "VIRTUAL:",
                "driver": "Virtual Driver"
            }]

        try:
            default_printer = win32print.GetDefaultPrinter()
        except Exception:
            default_printer = ""

        try:
            # Lấy máy in cục bộ và máy in kết nối mạng
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            raw_printers = win32print.EnumPrinters(flags)
            for p in raw_printers:
                p_name = p[2]
                status_info = WindowsPrintSpooler.get_printer_status(p_name)
                printers.append({
                    "name": p_name,
                    "is_default": p_name == default_printer,
                    "status": status_info["status_text"],
                    "is_online": status_info["is_online"],
                    "port": p[1],
                    "driver": p[3] if len(p) > 3 else ""
                })
        except Exception as e:
            logger.error(f"Lỗi khi liệt kê máy in Windows: {e}")

        return printers

    @staticmethod
    def get_default_printer() -> str:
        """Lấy tên máy in mặc định hiện tại của Windows."""
        if not WIN32_AVAILABLE:
            return "Giả Lập Máy In Windows"
        try:
            return win32print.GetDefaultPrinter()
        except Exception as e:
            logger.warning(f"Không thể lấy máy in mặc định: {e}")
            return ""

    @staticmethod
    def get_printer_status(printer_name: str) -> Dict[str, Any]:
        """Truy xuất trạng thái chi tiết của máy in từ Windows Spooler."""
        if not WIN32_AVAILABLE:
            return {"status_code": 0, "status_text": "Sẵn sàng (Giả lập)", "is_online": True}

        hprinter = None
        try:
            hprinter = win32print.OpenPrinter(printer_name)
            p_info = win32print.GetPrinter(hprinter, 2)
            raw_status = p_info.get("Status", 0)

            status_messages = []
            for code, msg in PRINTER_STATUS_MAP.items():
                if raw_status & code:
                    status_messages.append(msg)

            status_text = ", ".join(status_messages) if status_messages else "Sẵn sàng (Ready)"
            is_online = not bool(raw_status & (0x00000002 | 0x00000008 | 0x00000010 | 0x00000080 | 0x00001000))

            return {
                "status_code": raw_status,
                "status_text": status_text,
                "is_online": is_online,
                "cjobs": p_info.get("cJobs", 0)
            }
        except Exception as e:
            return {
                "status_code": -1,
                "status_text": f"Không truy xuất được trạng thái ({e})",
                "is_online": False,
                "cjobs": 0
            }
        finally:
            if hprinter:
                try:
                    win32print.ClosePrinter(hprinter)
                except Exception:
                    pass

    @staticmethod
    def send_image_to_printer(
        printer_name: str,
        image_path: str,
        copies: int = 1,
        job_title: str = "VietPhotoBooth Print"
    ) -> Dict[str, Any]:
        """
        Gửi file ảnh trực tiếp tới Windows Print Spooler sử dụng GDI Device Context (DC).
        Đảm bảo tỷ lệ 1:1, khớp kích thước vật lý không bị méo và hỗ trợ số bản in.
        """
        if not os.path.exists(image_path):
            return {"success": False, "error": f"File ảnh không tồn tại: {image_path}"}

        if not WIN32_AVAILABLE:
            time.sleep(0.5)
            logger.info(f"[Giả lập in] Đã gửi {copies} bản in của {image_path} tới {printer_name}")
            return {"success": True, "message": f"[Giả lập] Đã in thành công {copies} bản.", "spooler_job_id": 9999}

        if not printer_name:
            printer_name = WindowsPrintSpooler.get_default_printer()

        try:
            img = Image.open(image_path)
            # Khởi tạo Windows Print DC
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(printer_name)

            # Lấy thông số độ phân giải của máy in (DPI và kích thước trang)
            horz_res = hdc.GetDeviceCaps(win32con.HORZRES)
            vert_res = hdc.GetDeviceCaps(win32con.VERTRES)

            logger.info(f"Bắt đầu gửi lệnh in tới '{printer_name}' (Khổ trang: {horz_res}x{vert_res})")

            for copy_idx in range(copies):
                hdc.StartDoc(f"{job_title} - Bản {copy_idx + 1}/{copies}")
                hdc.StartPage()

                # Vẽ ảnh phóng đầy khổ in với tỷ lệ gốc
                dib = ImageWin.Dib(img)
                dib.draw(hdc.GetHandleOutput(), (0, 0, horz_res, vert_res))

                hdc.EndPage()
                hdc.EndDoc()

            hdc.DeleteDC()
            logger.info(f"Lệnh in ({copies} bản) đã được gửi thành công vào Windows Print Spooler.")
            return {
                "success": True,
                "message": f"Đã gửi {copies} bản in tới Spooler máy in {printer_name}.",
                "printer_name": printer_name
            }
        except Exception as e:
            err_msg = f"Lỗi khi gửi lệnh in tới {printer_name}: {e}"
            logger.error(err_msg)
            return {"success": False, "error": err_msg}
