"""
VietPhotoBooth Frame & Template Models
Defines data structures for Photo Slots, Text Layers, Logo Overlays, and 300 DPI Frame Templates.
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Any

# Kích thước pixel chuẩn tại độ phân giải in 300 DPI
DPI_300_SIZES = {
    "2x6": (600, 1800),             # 2 inch x 6 inch (Dải dọc)
    "4x6_portrait": (1200, 1800),   # 4 inch x 6 inch (Khổ đứng)
    "4x6_landscape": (1800, 1200),  # 6 inch x 4 inch (Khổ ngang)
    "4x6_dual": (1200, 1800),       # Ghép đôi 2 dải 2x6 trên khổ 4x6 (DNP cắt tự động)
}

@dataclass
class PhotoSlot:
    """Tọa độ và thuộc tính của một ô chứa ảnh trên khung hình."""
    id: int
    x: int
    y: int
    w: int
    h: int
    rotation: int = 0             # 0, 90, 180, 270 độ
    corner_radius: int = 0        # Bo góc (pixel)
    border_width: int = 0         # Độ dày viền ảnh
    border_color: str = "#FFFFFF" # Màu viền
    photo_index: int = 0          # Chỉ số ảnh chụp được gán (0, 1, 2, 3...)
    z_order: int = 0              # Thứ tự lớp (lớp cao hơn vẽ đè lên lớp thấp hơn)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhotoSlot":
        valid = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in valid})


@dataclass
class TextLayer:
    """Lớp chữ văn bản (Tên cô dâu chú rể, tên sự kiện, ngày tháng, lời chúc)."""
    id: str
    text: str
    x: int
    y: int
    font_size: int = 36
    font_color: str = "#222222"
    font_name: str = "arial.ttf"
    alignment: str = "center"     # "left", "center", "right"
    is_variable: bool = False     # Cho phép thay thế tự động bằng tên Event / ngày giờ

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextLayer":
        valid = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in valid})


@dataclass
class LogoLayer:
    """Lớp hình ảnh logo nhà tài trợ / icon trang trí."""
    id: str
    image_path: str
    x: int
    y: int
    w: int
    h: int
    opacity: float = 1.0          # 0.0 đến 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogoLayer":
        valid = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in valid})


@dataclass
class FrameTemplate:
    """Mẫu khung ảnh Photobooth chuẩn 300 DPI."""
    id: str
    name: str
    category: str = "Custom"      # "Wedding", "Birthday", "Corporate", "Custom"
    type: str = "2x6"             # "2x6", "4x6_portrait", "4x6_landscape", "4x6_dual"
    canvas_size: List[int] = field(default_factory=lambda: [600, 1800])
    bg_color: str = "#FFFFFF"
    bg_image_path: Optional[str] = None
    overlay_png_path: Optional[str] = None  # File PNG suốt viền khung nổi lên trên
    slots: List[PhotoSlot] = field(default_factory=list)
    text_layers: List[TextLayer] = field(default_factory=list)
    logo_layers: List[LogoLayer] = field(default_factory=list)

    # Căn lề an toàn & In ấn chuyên dụng
    bleed_px: int = 15            # Vùng xén lề máy in (15px ~ 1.27mm tại 300 DPI)
    safe_zone_px: int = 40        # Vùng an toàn không đặt chữ/mặt người
    is_dual_strip: bool = False   # Nhân đôi dải 2x6 sang bên phải (chuẩn máy in DNP DS-RX1HS)
    has_cut_line: bool = False    # Vẽ đường đứt nét căn cắt giữa 2 dải
    notes: str = ""               # Ghi chú hướng dẫn sử dụng khung
    version: str = "1.0"
    author: str = "1998 TEAM"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FrameTemplate":
        slots_data = data.get("slots", [])
        text_data = data.get("text_layers", [])
        logo_data = data.get("logo_layers", [])

        slots = [PhotoSlot.from_dict(s) for s in slots_data]
        text_layers = [TextLayer.from_dict(t) for t in text_data]
        logo_layers = [LogoLayer.from_dict(l) for l in logo_data]

        valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__.keys() and k not in ("slots", "text_layers", "logo_layers")}
        return cls(
            slots=slots,
            text_layers=text_layers,
            logo_layers=logo_layers,
            **valid_fields
        )

    def save_to_json(self, filepath: str) -> bool:
        """Lưu cấu hình template ra file JSON."""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    @classmethod
    def load_from_json(cls, filepath: str) -> Optional["FrameTemplate"]:
        """Nạp template từ file JSON."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception:
            return None
