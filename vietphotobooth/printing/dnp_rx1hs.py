"""
VietPhotoBooth DNP DS-RX1HS & Dye-Sublimation Printer Profile
Specialized driver settings, 2x6 auto-cut configurations, and verification for Photobooth photo printers.
"""

from typing import Dict, Any, Tuple
from PIL import Image
from vietphotobooth.core.logger import get_logger

logger = get_logger()

# Danh sách nhận diện các dòng máy in ảnh nhiệt thăng hoa phổ biến
DYE_SUB_SIGNATURES = [
    "rx1", "ds-rx1", "ds-rx1hs", "ds620", "ds820", "ds40",  # DNP
    "cy-02", "op900", "cx-02",                              # Citizen
    "p525l", "p520l", "p720l",                              # HiTi
    "cs2", "s6145", "chc-s6145",                            # Sinfonia
    "cp-d70dw", "cp-d80dw", "cp-d90dw",                     # Mitsubishi
    "kodak 305", "kodak 6850", "kodak 6900"                 # Kodak
]

class DNPRX1HSProfile:
    """Cấu hình tối ưu cho dòng máy in chuyên dụng DNP DS-RX1HS trong Photobooth."""

    MODEL_NAME = "DNP DS-RX1 / DS-RX1HS"
    MANUFACTURER = "Dai Nippon Printing (DNP)"
    NATIVE_DPI = 300
    PRINT_SPEED_4X6_SEC = 12.4  # Chế độ High Speed 300x300 DPI

    @staticmethod
    def is_dye_sub_printer(printer_name: str) -> bool:
        """Kiểm tra xem máy in được chọn có phải máy in nhiệt Photobooth chuyên nghiệp không."""
        name_lower = printer_name.lower()
        return any(sig in name_lower for sig in DYE_SUB_SIGNATURES)

    @staticmethod
    def get_hardware_guidelines() -> Dict[str, Any]:
        """Hướng dẫn cấu hình driver máy in DNP trên Windows để cắt 2 dải 2x6 tự động."""
        return {
            "model": "DNP DS-RX1HS",
            "recommended_paper_size": "4x6 inch (102 x 152 mm)",
            "cut_feature_name": "2-inch Cut (Cắt thành 2 dải 2x6)",
            "driver_instructions": [
                "1. Vào Windows Settings -> Printers & Scanners -> Chọn máy in DNP DS-RX1.",
                "2. Chọn Printing Preferences (Tùy chọn in) -> Tab Paper / Layout.",
                "3. Tại mục Paper Size: Chọn '4x6 inch' (102x152mm).",
                "4. Tại mục Options / Cut Settings: Bật '2-inch cut' (hoặc '2x6 Cut').",
                "5. Khi bật tính năng này, máy sẽ in ảnh khổ 1200x1800 px và dao cắt tích hợp sẽ tự động chém đôi thành hai dải 600x1800 px (2x6 inch) sắc nét.",
                "6. Chọn 'High Speed' để thời gian in mỗi ảnh chỉ mất khoảng 12.4 giây."
            ],
            "ribbon_info": "Bộ mực/giấy chuẩn DNP RX1HS-4x6 (Hộp 2 cuộn, 700 kiểu/cuộn = 1.400 bản in)."
        }

    @staticmethod
    def validate_image_for_print(
        image_path: str,
        target_mode: str = "4x6"
    ) -> Tuple[bool, str]:
        """
        Kiểm tra độ phân giải và tỷ lệ của file ảnh trước khi in để tránh bị cắt lẹm hoặc sai màu.
        """
        try:
            with Image.open(image_path) as img:
                w, h = img.size
                ratio = w / h if h != 0 else 0

                if target_mode in ("2x6", "strip"):
                    # Tỷ lệ 1:3 hoặc 3:1 (xấp xỉ 0.333 hoặc 3.0)
                    expected_ratio = 600 / 1800
                    if abs(ratio - expected_ratio) > 0.05 and abs(ratio - (1 / expected_ratio)) > 0.05:
                        return False, f"Ảnh {w}x{h} không đúng tỷ lệ 2x6 (chuẩn 600x1800 px)."
                elif target_mode in ("4x6", "4x6_dual"):
                    # Tỷ lệ 2:3 hoặc 3:2 (xấp xỉ 0.667 hoặc 1.5)
                    expected_ratio = 1200 / 1800
                    if abs(ratio - expected_ratio) > 0.05 and abs(ratio - (1 / expected_ratio)) > 0.05:
                        return False, f"Ảnh {w}x{h} không đúng tỷ lệ 4x6 (chuẩn 1200x1800 px hoặc 1800x1200 px)."

                if w < 600 or h < 600:
                    return False, f"Độ phân giải {w}x{h} quá thấp so với chuẩn 300 DPI in ấn chất lượng cao."

                return True, "Kích thước và tỷ lệ hoàn toàn chuẩn xác cho máy in ảnh."
        except Exception as e:
            return False, f"Không thể đọc file ảnh: {e}"
