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
from vietphotobooth.printing.presets import PrintPreset, PrintPresetRegistry

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
        job_title: str = "VietPhotoBooth Print",
        offset_x: int = 0,
        offset_y: int = 0,
        zoom: float = 1.0,
        orientation: str = "portrait",
        preset: Optional[PrintPreset] = None,
        safety_margin_enabled: bool = True,
        safety_margin_zoom: float = 0.98,
        auto_orientation_enabled: bool = True,
        thermal_pacing_sec: float = 0.0
    ) -> Dict[str, Any]:
        """
        Gửi file ảnh trực tiếp tới Windows Print Spooler sử dụng GDI Device Context (DC).
        Áp dụng căn chỉnh lề (offset X/Y), độ phóng (zoom), Safety Margin chống cắt phạm,
        tự động khớp hướng giấy (auto-orientation) và giãn cách nhiệt (thermal pacing).
        """
        if not os.path.exists(image_path):
            return {"success": False, "error": f"File ảnh không tồn tại: {image_path}"}

        # 1. Xác định Print Preset theo model máy in
        if preset is None and printer_name:
            preset = PrintPresetRegistry.get_preset_for_printer(printer_name)

        # 2. Tính toán Safety Margin zoom
        effective_safety_zoom = 1.0
        if preset and preset.supports_safety_margin and safety_margin_enabled:
            effective_safety_zoom = safety_margin_zoom if safety_margin_zoom > 0 else preset.default_safety_margin_zoom
            logger.debug(f"[Spooler] Áp dụng Safety Margin {effective_safety_zoom:.2f} cho máy in '{printer_name}'")

        combined_zoom = zoom * effective_safety_zoom

        # 3. Tính toán thời gian giãn cách nhiệt (thermal pacing)
        effective_pacing = thermal_pacing_sec
        if effective_pacing <= 0 and preset:
            effective_pacing = preset.default_thermal_pacing_sec

        is_simulation = (
            not WIN32_AVAILABLE
            or "giả lập" in printer_name.lower()
            or "virtual" in printer_name.lower()
            or "mock" in printer_name.lower()
        )
        if is_simulation:
            time.sleep(0.05)
            if effective_pacing > 0 and copies > 1:
                time.sleep(min(0.2, effective_pacing))  # Giả lập thời gian giãn cách nhỏ cho test nhanh
            logger.info(
                f"[Giả lập in] Đã gửi {copies} bản in của {image_path} tới {printer_name} "
                f"(Lệch X:{offset_x}, Y:{offset_y}, Zoom:{combined_zoom:.3f}, Hướng:{orientation}, Pacing:{effective_pacing}s)"
            )
            return {
                "success": True,
                "message": f"[Giả lập] Đã in thành công {copies} bản.",
                "spooler_job_id": 9999,
                "combined_zoom": combined_zoom,
                "effective_safety_zoom": effective_safety_zoom,
                "effective_pacing": effective_pacing,
                "preset_id": preset.preset_id if preset else "none"
            }

        if not printer_name:
            printer_name = WindowsPrintSpooler.get_default_printer()

        try:
            img = Image.open(image_path)

            # Khởi tạo Windows Print DC để đọc Device Capabilities chuẩn xác
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(printer_name)

            horz_res = hdc.GetDeviceCaps(win32con.HORZRES)
            vert_res = hdc.GetDeviceCaps(win32con.VERTRES)

            logger.info(f"Bắt đầu gửi lệnh in tới '{printer_name}' (Khổ trang Driver: {horz_res}x{vert_res})")

            # 4. Tự động so khớp hướng trang in (Auto Orientation Match)
            should_auto_match = auto_orientation_enabled and (preset.supports_auto_orientation if preset else False)
            if should_auto_match and horz_res > 0 and vert_res > 0 and img.width != img.height:
                page_is_landscape = horz_res > vert_res
                img_is_landscape = img.width > img.height
                if page_is_landscape != img_is_landscape:
                    logger.info(
                        f"[Spooler] Phát hiện lệch hướng trang (Driver Landscape={page_is_landscape} vs Image Landscape={img_is_landscape}). "
                        f"Tự động xoay ảnh 90 độ."
                    )
                    img = img.rotate(90, expand=True)
            else:
                # Giữ nguyên hành vi v1.6.5 cho máy in thông thường hoặc khi tắt auto_orientation
                if orientation.lower() in ("landscape", "ngang") and img.height > img.width:
                    img = img.rotate(90, expand=True)
                elif orientation.lower() in ("portrait", "dọc") and img.width > img.height:
                    img = img.rotate(90, expand=True)

            # 5. Áp dụng Zoom (User Zoom * Safety Margin) và Offset lề
            if combined_zoom != 1.0 or offset_x != 0 or offset_y != 0:
                orig_w, orig_h = img.size
                clamped_zoom = max(0.5, min(2.0, combined_zoom))
                new_w = max(10, int(orig_w * clamped_zoom))
                new_h = max(10, int(orig_h * clamped_zoom))
                scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (orig_w, orig_h), (255, 255, 255))
                paste_x = (orig_w - new_w) // 2 + offset_x
                paste_y = (orig_h - new_h) // 2 + offset_y
                canvas.paste(scaled, (paste_x, paste_y))
                img = canvas

            # 6. Gửi các trang in kèm Thermal Pacing Delay an toàn giữa các bản in
            for copy_idx in range(copies):
                hdc.StartDoc(f"{job_title} - Bản {copy_idx + 1}/{copies}")
                hdc.StartPage()

                dib = ImageWin.Dib(img)
                dib.draw(hdc.GetHandleOutput(), (0, 0, horz_res, vert_res))

                hdc.EndPage()
                hdc.EndDoc()

                # Thermal Pacing giữa các trang in đa bản
                if effective_pacing > 0 and copy_idx < (copies - 1):
                    logger.debug(f"[Spooler] Thermal Pacing delay {effective_pacing:.1f}s trước khi gửi bản {copy_idx + 2}/{copies}...")
                    time.sleep(effective_pacing)

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
