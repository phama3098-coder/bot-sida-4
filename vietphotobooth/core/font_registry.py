"""
VietPhotoBooth Font Registry & Management System
Discovers, categorizes, and provides high-quality Vietnamese wedding and event fonts.
All fonts are packaged locally for 100% offline operation.
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Optional
from PySide6.QtGui import QFontDatabase

from vietphotobooth.core.logger import get_logger

logger = get_logger()

@dataclass
class FontItem:
    id: str                  # e.g., "GreatVibes-Regular.ttf" or "Arial"
    display_name: str        # e.g., "Great Vibes"
    category: str            # "handwriting", "luxury", "modern"
    category_label: str      # "Viết Tay", "Sang Trọng", "Hiện Đại"
    file_path: Optional[str] # Absolute path to file or None if system font
    family_name: str         # Family name for QFont / PIL
    description: str         # Short descriptive style note

class FontRegistry:
    """Hệ thống đăng ký và tra cứu phông chữ tiếng Việt cho Photobooth."""

    CATEGORIES = {
        "all": "Tất Cả",
        "handwriting": "Viết Tay / Ký Tên",
        "luxury": "Sang Trọng (Serif)",
        "modern": "Hiện Đại (Sans-serif)"
    }

    _initialized = False
    _qt_fonts_registered = False
    _fonts: List[FontItem] = []

    @classmethod
    def get_assets_font_dir(cls) -> str:
        """Trả về đường dẫn tuyệt đối tới thư mục Assets/Fonts."""
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Fonts"))

    @classmethod
    def _register_qt_fonts(cls):
        """Nạp các phông chữ đóng gói vào QFontDatabase khi QGuiApplication đã khả dụng."""
        from PySide6.QtGui import QGuiApplication, QFontDatabase
        if QGuiApplication.instance() is None:
            return
        for f_item in cls._fonts:
            if f_item.file_path and os.path.exists(f_item.file_path):
                try:
                    font_id = QFontDatabase.addApplicationFont(f_item.file_path)
                    if font_id >= 0:
                        loaded_families = QFontDatabase.applicationFontFamilies(font_id)
                        if loaded_families:
                            f_item.family_name = loaded_families[0]
                except Exception as e:
                    logger.warning(f"Không thể nạp font {f_item.id} vào QFontDatabase: {e}")

        # Thiết lập cơ chế Qt Font Fallback chuẩn xác cấp engine (không chỉ phụ thuộc vào CSS)
        from PySide6.QtGui import QFont
        QFont.insertSubstitutions("Be Vietnam Pro", ["Segoe UI", "Arial", "Segoe UI Emoji", "Segoe UI Symbol"])
        QFont.insertSubstitutions("Segoe UI", ["Segoe UI Emoji", "Segoe UI Symbol", "Arial"])
        cls._qt_fonts_registered = True

    @classmethod
    def initialize(cls):
        """Khởi tạo danh mục phông chữ và nạp vào QFontDatabase của hệ thống (idempotent & thread-safe)."""
        from PySide6.QtGui import QGuiApplication

        # 1. Nếu đã nạp hoàn chỉnh cả danh mục lẫn Qt fonts -> an toàn thoát ngay lập tức
        if cls._initialized and cls._qt_fonts_registered:
            return

        # 2. Nếu danh mục đã tạo nhưng trước đó QApplication chưa khởi tạo -> chỉ cần đăng ký Qt fonts
        if cls._initialized and not cls._qt_fonts_registered:
            if QGuiApplication.instance() is not None:
                cls._register_qt_fonts()
            return

        cls._fonts = []
        fonts_dir = cls.get_assets_font_dir()

        # 1. Định nghĩa danh sách các phông chữ chuẩn studio cưới được đóng gói offline
        packaged_definitions = [
            # Viết tay / Ký tên lãng mạn
            {
                "file": "GreatVibes-Regular.ttf",
                "display": "Great Vibes",
                "family": "Great Vibes",
                "cat": "handwriting",
                "cat_label": "Viết Tay",
                "desc": "Thư pháp cưới lãng mạn, thanh thoát"
            },
            {
                "file": "DancingScript-Regular.ttf",
                "display": "Dancing Script",
                "family": "Dancing Script",
                "cat": "handwriting",
                "cat_label": "Viết Tay",
                "desc": "Chữ viết tay tự nhiên, phóng khoáng"
            },
            # Sang trọng / Serif đẳng cấp
            {
                "file": "PlayfairDisplay-Regular.ttf",
                "display": "Playfair Display",
                "family": "Playfair Display",
                "cat": "luxury",
                "cat_label": "Sang Trọng",
                "desc": "Serif cổ điển sang trọng chuẩn Châu Âu"
            },
            {
                "file": "Lora-Regular.ttf",
                "display": "Lora",
                "family": "Lora",
                "cat": "luxury",
                "cat_label": "Sang Trọng",
                "desc": "Serif ấm áp, tinh tế, trang nhã"
            },
            # Hiện đại / Sans-serif dễ đọc
            {
                "file": "BeVietnamPro-Bold.ttf",
                "display": "Be Vietnam Pro Bold",
                "family": "Be Vietnam Pro",
                "cat": "modern",
                "cat_label": "Hiện Đại",
                "desc": "Nét đậm hiện đại, chuẩn dấu tiếng Việt"
            },
            {
                "file": "BeVietnamPro-Regular.ttf",
                "display": "Be Vietnam Pro",
                "family": "Be Vietnam Pro",
                "cat": "modern",
                "cat_label": "Hiện Đại",
                "desc": "Thiết kế hiện đại, dễ đọc, thanh lịch"
            },
        ]

        from PySide6.QtGui import QGuiApplication

        for p_font in packaged_definitions:
            fpath = os.path.join(fonts_dir, p_font["file"])
            if os.path.exists(fpath):
                actual_family = p_font["family"]
                # Nạp vào hệ thống Qt GUI nếu ứng dụng Qt đã khởi tạo
                if QGuiApplication.instance() is not None:
                    try:
                        font_id = QFontDatabase.addApplicationFont(fpath)
                        if font_id >= 0:
                            loaded_families = QFontDatabase.applicationFontFamilies(font_id)
                            if loaded_families:
                                actual_family = loaded_families[0]
                    except Exception as e:
                        logger.warning(f"Không thể nạp font {p_font['file']} vào QFontDatabase: {e}")

                cls._fonts.append(FontItem(
                    id=p_font["file"],
                    display_name=p_font["display"],
                    category=p_font["cat"],
                    category_label=p_font["cat_label"],
                    file_path=fpath,
                    family_name=actual_family,
                    description=p_font["desc"]
                ))
            else:
                logger.warning(f"Không tìm thấy tệp phông chữ đóng gói: {fpath}")

        # 2. Bổ sung các phông chữ chuẩn hệ thống Windows hỗ trợ tiếng Việt
        system_definitions = [
            {"id": "arial.ttf", "display": "Arial", "family": "Arial", "cat": "modern", "cat_label": "Hiện Đại", "desc": "Phông tiêu chuẩn rõ ràng"},
            {"id": "segoeui.ttf", "display": "Segoe UI", "family": "Segoe UI", "cat": "modern", "cat_label": "Hiện Đại", "desc": "Giao diện Windows hiện đại"},
            {"id": "times.ttf", "display": "Times New Roman", "family": "Times New Roman", "cat": "luxury", "cat_label": "Sang Trọng", "desc": "Serif truyền thống"},
            {"id": "calibri.ttf", "display": "Calibri", "family": "Calibri", "cat": "modern", "cat_label": "Hiện Đại", "desc": "Thanh mảnh, trang nhã"},
            {"id": "tahoma.ttf", "display": "Tahoma", "family": "Tahoma", "cat": "modern", "cat_label": "Hiện Đại", "desc": "Rõ nét trên mọi độ phân giải"},
        ]

        windir = os.environ.get("WINDIR", "C:\\Windows")
        win_fonts_dir = os.path.join(windir, "Fonts")

        for s_font in system_definitions:
            fpath = os.path.join(win_fonts_dir, s_font["id"])
            cls._fonts.append(FontItem(
                id=s_font["id"],
                display_name=s_font["display"],
                category=s_font["cat"],
                category_label=s_font["cat_label"],
                file_path=fpath if os.path.exists(fpath) else None,
                family_name=s_font["family"],
                description=s_font["desc"]
            ))

        cls._initialized = True
        logger.info(f"Đã khởi tạo FontRegistry với {len(cls._fonts)} phông chữ tiếng Việt.")
        if QGuiApplication.instance() is not None:
            cls._register_qt_fonts()

    @classmethod
    def list_fonts(cls, category: str = "all") -> List[FontItem]:
        """Lấy danh sách phông chữ theo danh mục lọc."""
        cls.initialize()
        if category == "all":
            return list(cls._fonts)
        return [f for f in cls._fonts if f.category == category]

    @classmethod
    def get_font_names_by_category(cls, category: str = "all") -> List[str]:
        """Lấy danh sách tên hiển thị của các phông chữ theo danh mục lọc."""
        return [f.display_name for f in cls.list_fonts(category)]

    @classmethod
    def find_font(cls, font_identifier: str) -> Optional[FontItem]:
        """Tìm phông chữ theo id, file hoặc family name."""
        cls.initialize()
        ident_lower = font_identifier.strip().lower()
        # Khớp chính xác id hoặc display_name
        for f in cls._fonts:
            if f.id.lower() == ident_lower or f.display_name.lower() == ident_lower or f.family_name.lower() == ident_lower:
                return f
        # Khớp mềm
        for f in cls._fonts:
            if ident_lower in f.id.lower() or ident_lower in f.family_name.lower() or ident_lower in f.display_name.lower():
                return f
        return None

    @classmethod
    def resolve_font_path(cls, font_name: str) -> Optional[str]:
        """Trả về đường dẫn tệp phông chữ thực tế, ưu tiên Assets/Fonts rồi đến Windows/Fonts."""
        cls.initialize()
        item = cls.find_font(font_name)
        if item and item.file_path and os.path.exists(item.file_path):
            return item.file_path

        # Tìm trực tiếp trong Assets/Fonts
        assets_dir = cls.get_assets_font_dir()
        direct_asset = os.path.join(assets_dir, os.path.basename(font_name))
        if os.path.exists(direct_asset):
            return direct_asset

        # Tìm trong Windows/Fonts
        windir = os.environ.get("WINDIR", "C:\\Windows")
        win_path = os.path.join(windir, "Fonts", os.path.basename(font_name))
        if os.path.exists(win_path):
            return win_path

        # Fallback an toàn: BeVietnamPro-Regular.ttf hoặc arial.ttf
        fallback_asset = os.path.join(assets_dir, "BeVietnamPro-Regular.ttf")
        if os.path.exists(fallback_asset):
            return fallback_asset

        fallback_arial = os.path.join(windir, "Fonts", "arial.ttf")
        if os.path.exists(fallback_arial):
            return fallback_arial

        return None

    @classmethod
    def get_default_font_family(cls) -> str:
        """Trả về family phông chữ mặc định của hệ thống, ưu tiên Be Vietnam Pro nếu khả dụng."""
        cls.initialize()
        try:
            from PySide6.QtGui import QFontDatabase
            available = QFontDatabase.families()
            if "Be Vietnam Pro" in available:
                return "Be Vietnam Pro"
            if "Segoe UI" in available:
                return "Segoe UI"
            if "Arial" in available:
                return "Arial"
        except Exception:
            pass
        return "sans-serif"

    @classmethod
    def get_default_application_font(cls, point_size: int = 10, bold: bool = False):
        """Trả về đối tượng QFont mặc định cho toàn ứng dụng với cơ chế fallback tin cậy."""
        cls.initialize()
        from PySide6.QtGui import QFont
        family = cls.get_default_font_family()
        font = QFont(family, point_size)
        font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        font.setStyleHint(QFont.SansSerif)
        return font
