"""
1998 TEAM — Photobooth Print Preset System
Models, paper profiles, safety margins, auto-orientation matching, and thermal pacing.
Strictly preserves backward compatibility for generic printers.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from vietphotobooth.core.logger import get_logger

logger = get_logger()

# Danh sách nhận diện các dòng máy in ảnh nhiệt thăng hoa Photobooth chuyên nghiệp
DYE_SUB_SIGNATURES = [
    "rx1", "ds-rx1", "ds-rx1hs", "ds620", "ds820", "ds40", "qw410",  # DNP
    "cy-02", "op900", "cx-02", "cy", "cx",                            # Citizen
    "p525l", "p520l", "p720l", "p530d",                              # HiTi
    "cs2", "s6145", "chc-s6145", "s2145",                            # Sinfonia
    "cp-d70dw", "cp-d80dw", "cp-d90dw", "cp-m1a",                    # Mitsubishi
    "kodak 305", "kodak 6850", "kodak 6900"                          # Kodak
]


@dataclass
class PrintPreset:
    """Cấu hình chi tiết theo model máy in và khổ giấy."""
    preset_id: str
    model_name: str
    manufacturer: str
    signatures: List[str] = field(default_factory=list)
    paper_size: str = "4x6"
    is_dye_sub: bool = False
    supports_safety_margin: bool = False
    default_safety_margin_zoom: float = 0.98
    supports_auto_orientation: bool = False
    default_thermal_pacing_sec: float = 0.0
    native_dpi: int = 300
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "model_name": self.model_name,
            "manufacturer": self.manufacturer,
            "paper_size": self.paper_size,
            "is_dye_sub": self.is_dye_sub,
            "supports_safety_margin": self.supports_safety_margin,
            "default_safety_margin_zoom": self.default_safety_margin_zoom,
            "supports_auto_orientation": self.supports_auto_orientation,
            "default_thermal_pacing_sec": self.default_thermal_pacing_sec,
            "native_dpi": self.native_dpi,
            "description": self.description,
        }


# =========================================================================
# DANH MỤC CÁC PRESET ĐÃ ĐƯỢC CHUẨN HÓA VÀ KIỂM CHỨNG
# =========================================================================

PRESET_DNP_RX1HS_4X6 = PrintPreset(
    preset_id="dnp_rx1hs_4x6",
    model_name="DNP DS-RX1 / DS-RX1HS",
    manufacturer="Dai Nippon Printing (DNP)",
    signatures=["rx1", "ds-rx1", "ds-rx1hs"],
    paper_size="4x6",
    is_dye_sub=True,
    supports_safety_margin=True,
    default_safety_margin_zoom=0.98,
    supports_auto_orientation=True,
    default_thermal_pacing_sec=2.0,
    native_dpi=300,
    description="Máy in nhiệt thăng hoa tiêu chuẩn sự kiện DNP DS-RX1HS khổ 4x6 inch (cắt đôi 2 dải 2x6)."
)

PRESET_DNP_QW410_4X6 = PrintPreset(
    preset_id="dnp_qw410_4x6",
    model_name="DNP QW410 Compact",
    manufacturer="Dai Nippon Printing (DNP)",
    signatures=["qw410", "qw-410"],
    paper_size="4x6",
    is_dye_sub=True,
    supports_safety_margin=True,
    default_safety_margin_zoom=0.98,
    supports_auto_orientation=True,
    default_thermal_pacing_sec=2.5,
    native_dpi=300,
    description="Máy in mini siêu nhẹ DNP QW410 cho booth di động."
)

PRESET_CITIZEN_CY02_4X6 = PrintPreset(
    preset_id="citizen_cy02_4x6",
    model_name="Citizen CY-02 / OP900",
    manufacturer="Citizen Systems",
    signatures=["cy-02", "op900", "cx-02", "cy", "cx"],
    paper_size="4x6",
    is_dye_sub=True,
    supports_safety_margin=True,
    default_safety_margin_zoom=0.98,
    supports_auto_orientation=True,
    default_thermal_pacing_sec=1.8,
    native_dpi=300,
    description="Máy in nhiệt thăng hoa công suất lớn Citizen CY-02 (700 bản/cuộn)."
)

PRESET_SINFONIA_CS2_4X6 = PrintPreset(
    preset_id="sinfonia_cs2_4x6",
    model_name="Sinfonia CS2 (CHC-S6145)",
    manufacturer="Sinfonia Technology",
    signatures=["cs2", "s6145", "chc-s6145"],
    paper_size="4x6",
    is_dye_sub=True,
    supports_safety_margin=True,
    default_safety_margin_zoom=0.98,
    supports_auto_orientation=True,
    default_thermal_pacing_sec=2.0,
    native_dpi=300,
    description="Máy in nhiệt nhỏ gọn chuyên dụng cho photobooth cưới Sinfonia CS2."
)

PRESET_GENERIC_PHOTO = PrintPreset(
    preset_id="generic_photo",
    model_name="Máy in ảnh tiêu chuẩn (Generic Photo Printer)",
    manufacturer="Generic",
    signatures=[],
    paper_size="4x6",
    is_dye_sub=False,
    supports_safety_margin=False,
    default_safety_margin_zoom=1.0,
    supports_auto_orientation=False,
    default_thermal_pacing_sec=0.0,
    native_dpi=300,
    description="Máy in thông thường hoặc máy in ảo (giữ nguyên hành vi mặc định v1.6.5)."
)


class PrintPresetRegistry:
    """Quản lý tra cứu và áp dụng preset in ấn theo model máy in và khổ giấy."""

    _PRESETS: List[PrintPreset] = [
        PRESET_DNP_RX1HS_4X6,
        PRESET_DNP_QW410_4X6,
        PRESET_CITIZEN_CY02_4X6,
        PRESET_SINFONIA_CS2_4X6,
    ]

    @classmethod
    def is_dye_sub_printer(cls, printer_name: str) -> bool:
        """Kiểm tra máy in có thuộc danh mục máy in nhiệt thăng hoa không."""
        if not printer_name:
            return False
        name_lower = printer_name.lower()
        return any(sig in name_lower for sig in DYE_SUB_SIGNATURES)

    @classmethod
    def get_preset_for_printer(
        cls,
        printer_name: str,
        paper_size: str = "4x6"
    ) -> PrintPreset:
        """
        Tra cứu preset phù hợp nhất dựa trên tên máy in và khổ giấy.
        Nếu không khớp bất kỳ profile chuyên dụng nào, trả về PRESET_GENERIC_PHOTO
        để bảo toàn 100% hành vi mặc định của phiên bản v1.6.5.
        """
        if not printer_name:
            return PRESET_GENERIC_PHOTO

        name_lower = printer_name.lower()

        # 1. Tìm kiếm theo danh sách preset đã định nghĩa
        for preset in cls._PRESETS:
            for sig in preset.signatures:
                if sig in name_lower:
                    logger.debug(f"[PrintPreset] Khớp máy in '{printer_name}' với preset '{preset.model_name}' (ID: {preset.preset_id})")
                    return preset

        # 2. Nếu tên có signature dye-sub chung nhưng không khớp model cụ thể
        if cls.is_dye_sub_printer(printer_name):
            logger.debug(f"[PrintPreset] Nhận diện máy in nhiệt dye-sub chung cho '{printer_name}'")
            return PrintPreset(
                preset_id="generic_dye_sub",
                model_name=f"Dye-Sub Printer ({printer_name})",
                manufacturer="Dye-Sub",
                signatures=[],
                paper_size=paper_size,
                is_dye_sub=True,
                supports_safety_margin=True,
                default_safety_margin_zoom=0.98,
                supports_auto_orientation=True,
                default_thermal_pacing_sec=2.0,
                native_dpi=300,
                description="Profile nhiệt thăng hoa tổng quát với tính năng an toàn dao cắt 98%."
            )

        # 3. Mặc định: Giữ nguyên hành vi v1.6.5
        return PRESET_GENERIC_PHOTO
