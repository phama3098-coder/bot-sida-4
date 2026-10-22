"""
VietPhotoBooth Frame Manager
Manages frame templates, categories (Wedding, Birthday, Corporate, Custom),
PNG overlay importing with alpha channel detection, and template persistence.
"""

import os
import shutil
import json
import zipfile
from typing import List, Dict, Optional, Tuple
from PIL import Image

from vietphotobooth.core.logger import get_logger
from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, LogoLayer, DPI_300_SIZES

from vietphotobooth.core.config import get_user_data_dir

logger = get_logger()

DEFAULT_FRAMES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Frames"))
DEFAULT_USER_FRAMES_DIR = os.path.join(get_user_data_dir(), "Frames")

CATEGORIES = [
    "Wedding", "Birthday", "Corporate", "Custom",
    "Sinh nhật", "Đám cưới", "Sự kiện", "Dễ thương", "Vintage", "Minimal", "Khác"
]

class FrameManager:
    """Quản lý danh viện khung in ảnh, nhập khung từ file PNG bên ngoài và sao lưu."""

    def __init__(self, base_dir: str = DEFAULT_FRAMES_DIR, user_dir: str = DEFAULT_USER_FRAMES_DIR):
        self.base_dir = os.path.abspath(base_dir)
        self.user_dir = os.path.abspath(user_dir)
        self.thumb_dir = os.path.join(get_user_data_dir(), "Thumbnails", "frames")
        os.makedirs(self.thumb_dir, exist_ok=True)

        for cat in CATEGORIES:
            os.makedirs(os.path.join(self.base_dir, cat), exist_ok=True)
            os.makedirs(os.path.join(self.user_dir, cat), exist_ok=True)

        self._templates: Dict[str, FrameTemplate] = {}
        self._init_default_templates()
        self.reload_all_frames()

    def _init_default_templates(self):
        """Khởi tạo các khung mẫu sẵn có nếu thư mục chưa có."""
        # 1. Wedding 2x6 - 3 ảnh lãng mạn
        wedding_id = "wedding_2x6_strip3"
        wedding_json = os.path.join(self.base_dir, "Wedding", f"{wedding_id}.json")
        if not os.path.exists(wedding_json):
            # Tạo overlay PNG hoa văn nhẹ
            overlay_path = os.path.join(self.base_dir, "Wedding", f"{wedding_id}_overlay.png")
            if not os.path.exists(overlay_path):
                self._generate_sample_overlay(overlay_path, 600, 1800, [
                    (45, 60, 510, 380),
                    (45, 470, 510, 380),
                    (45, 880, 510, 380)
                ], border_color=(218, 165, 32, 220)) # Gold

            tmpl = FrameTemplate(
                id=wedding_id,
                name="Tiệc Cưới Lãng Mạn (Dải 2x6 - 3 Ảnh)",
                category="Wedding",
                type="2x6",
                canvas_size=[600, 1800],
                bg_color="#FFFDF9",
                overlay_png_path=overlay_path,
                slots=[
                    PhotoSlot(id=1, x=45, y=60, w=510, h=380, corner_radius=12, photo_index=0),
                    PhotoSlot(id=2, x=45, y=470, w=510, h=380, corner_radius=12, photo_index=1),
                    PhotoSlot(id=3, x=45, y=880, w=510, h=380, corner_radius=12, photo_index=2),
                ],
                text_layers=[
                    TextLayer(id="title", text="Happy Wedding", x=300, y=1340, font_size=42, font_color="#8B6508", alignment="center"),
                    TextLayer(id="names", text="Chú Rể & Cô Dâu", x=300, y=1420, font_size=34, font_color="#4A3B32", alignment="center"),
                    TextLayer(id="date", text="{date}", x=300, y=1490, font_size=26, font_color="#7F8C8D", alignment="center"),
                    TextLayer(id="footer", text="Cảm ơn bạn đã đến chung vui!", x=300, y=1680, font_size=22, font_color="#A08060", alignment="center")
                ],
                safe_zone_px=35
            )
            tmpl.save_to_json(wedding_json)

        # 2. Birthday 2x6 - 4 ảnh sinh nhật rực rỡ
        bday_id = "birthday_2x6_strip4"
        bday_json = os.path.join(self.base_dir, "Birthday", f"{bday_id}.json")
        if not os.path.exists(bday_json):
            overlay_path = os.path.join(self.base_dir, "Birthday", f"{bday_id}_overlay.png")
            if not os.path.exists(overlay_path):
                self._generate_sample_overlay(overlay_path, 600, 1800, [
                    (45, 50, 510, 330),
                    (45, 410, 510, 330),
                    (45, 770, 510, 330),
                    (45, 1130, 510, 330)
                ], border_color=(231, 76, 60, 220)) # Red

            tmpl = FrameTemplate(
                id=bday_id,
                name="Sinh Nhật Rực Rỡ (Dải 2x6 - 4 Ảnh)",
                category="Birthday",
                type="2x6",
                canvas_size=[600, 1800],
                bg_color="#FFF8E7",
                overlay_png_path=overlay_path,
                slots=[
                    PhotoSlot(id=1, x=45, y=50, w=510, h=330, corner_radius=16, photo_index=0),
                    PhotoSlot(id=2, x=45, y=410, w=510, h=330, corner_radius=16, photo_index=1),
                    PhotoSlot(id=3, x=45, y=770, w=510, h=330, corner_radius=16, photo_index=2),
                    PhotoSlot(id=4, x=45, y=1130, w=510, h=330, corner_radius=16, photo_index=3),
                ],
                text_layers=[
                    TextLayer(id="title", text="HAPPY BIRTHDAY!", x=300, y=1520, font_size=40, font_color="#E74C3C", alignment="center"),
                    TextLayer(id="subtitle", text="Tuổi Mới Tỏa Sáng", x=300, y=1585, font_size=30, font_color="#F39C12", alignment="center"),
                    TextLayer(id="date", text="{date}", x=300, y=1660, font_size=24, font_color="#7F8C8D", alignment="center")
                ]
            )
            tmpl.save_to_json(bday_json)

        # 3. Dual Strip 4x6 (Ghép đôi 2 dải 2x6 cắt tự động bằng DNP DS-RX1HS)
        dual_id = "dual_strip_4x6_dnp"
        dual_json = os.path.join(self.base_dir, "Custom", f"{dual_id}.json")
        if not os.path.exists(dual_json):
            tmpl = FrameTemplate(
                id=dual_id,
                name="Khổ 4x6 Ghép Đôi 2 Dải 2x6 (Cắt Tự Động DNP RX1HS)",
                category="Custom",
                type="4x6_dual",
                canvas_size=[1200, 1800],
                bg_color="#FFFFFF",
                is_dual_strip=True,
                has_cut_line=True,
                slots=[
                    PhotoSlot(id=1, x=45, y=60, w=510, h=380, corner_radius=10, photo_index=0),
                    PhotoSlot(id=2, x=45, y=470, w=510, h=380, corner_radius=10, photo_index=1),
                    PhotoSlot(id=3, x=45, y=880, w=510, h=380, corner_radius=10, photo_index=2),
                ],
                text_layers=[
                    TextLayer(id="title", text="{event_name}", x=300, y=1340, font_size=42, font_color="#2C3E50", alignment="center"),
                    TextLayer(id="date", text="{date}", x=300, y=1430, font_size=28, font_color="#7F8C8D", alignment="center"),
                    TextLayer(id="footer", text="VietPhotoBooth Kiosk", x=300, y=1650, font_size=24, font_color="#BDC3C7", alignment="center")
                ]
            )
            tmpl.save_to_json(dual_json)

        # 4. Corporate 4x6 Khổ Ngang - 3 Ảnh
        corp_id = "corporate_4x6_landscape"
        corp_json = os.path.join(self.base_dir, "Corporate", f"{corp_id}.json")
        if not os.path.exists(corp_json):
            tmpl = FrameTemplate(
                id=corp_id,
                name="Sự Kiện Doanh Nghiệp (Khổ Ngang 4x6 - 3 Ảnh)",
                category="Corporate",
                type="4x6_landscape",
                canvas_size=[1800, 1200],
                bg_color="#0F172A",
                slots=[
                    PhotoSlot(id=1, x=60, y=60, w=520, h=680, corner_radius=12, photo_index=0),
                    PhotoSlot(id=2, x=640, y=60, w=520, h=680, corner_radius=12, photo_index=1),
                    PhotoSlot(id=3, x=1220, y=60, w=520, h=680, corner_radius=12, photo_index=2),
                ],
                text_layers=[
                    TextLayer(id="title", text="{event_name}", x=900, y=830, font_size=52, font_color="#38BDF8", alignment="center"),
                    TextLayer(id="date", text="Sự Kiện Thường Niên • {date}", x=900, y=930, font_size=32, font_color="#94A3B8", alignment="center"),
                    TextLayer(id="thanks", text="Thank you for joining our team!", x=900, y=1020, font_size=28, font_color="#E2E8F0", alignment="center")
                ]
            )
            tmpl.save_to_json(corp_json)

        # 5. Khởi tạo 16 mẫu khung in ảnh chuẩn 1998 TEAM Photobooth
        templates_specs = [
            ("basic_1", "Basic-1", "Minimal", "2x6", [600, 1800], "#FFFFFF", 3, [
                TextLayer("t1", "1998 TEAM", 300, 1370, 38, "#1E293B", alignment="center", is_bold=True),
                TextLayer("t2", "PHOTOBOOTH", 300, 1430, 24, "#94A3B8", alignment="center"),
                TextLayer("t3", "{date}", 300, 1680, 20, "#CBD5E1", alignment="center")
            ]),
            ("thu", "Thư", "Vintage", "2x6", [600, 1800], "#FBF8F1", 4, [
                TextLayer("t1", "Thư Gửi Thanh Xuân", 300, 1480, 34, "#5C4033", alignment="center", is_bold=True),
                TextLayer("t2", "1998 Studio • Phóng Sự Cưới", 300, 1540, 22, "#8C7355", alignment="center"),
                TextLayer("t3", "{date}", 300, 1680, 18, "#A89F91", alignment="center")
            ]),
            ("basic_2", "Basic-2", "Minimal", "2x6", [600, 1800], "#111827", 4, [
                TextLayer("t1", "CLASSIC NOIR", 300, 1480, 34, "#F9FAFB", alignment="center", is_bold=True),
                TextLayer("t2", "1998 STUDIO EDITION", 300, 1540, 20, "#9CA3AF", alignment="center"),
                TextLayer("t3", "{date}", 300, 1680, 18, "#6B7280", alignment="center")
            ]),
            ("magazine", "Magazine", "Sự kiện", "2x6", [600, 1800], "#FFFDF7", 3, [
                TextLayer("t1", "VOGUE", 300, 1360, 46, "#18181B", alignment="center", is_bold=True),
                TextLayer("t2", "SPECIAL EDITION • NO. 1998", 300, 1430, 22, "#71717A", alignment="center"),
                TextLayer("t3", "PHOTO ARCHIVE {date}", 300, 1680, 18, "#A1A1AA", alignment="center")
            ]),
            ("dau_tay", "Dâu Tây", "Dễ thương", "2x6", [600, 1800], "#E8F5E9", 4, [
                TextLayer("t1", "CUTE STRAWBERRY 🍓", 300, 1480, 32, "#E11D48", alignment="center", is_bold=True),
                TextLayer("t2", "Sweet Summer Day", 300, 1540, 22, "#2E7D32", alignment="center"),
                TextLayer("t3", "1998 Photobooth • {date}", 300, 1680, 18, "#81C784", alignment="center")
            ]),
            ("digital_cartoon", "Digital Cartoon", "Dễ thương", "2x6", [600, 1800], "#E0F2FE", 4, [
                TextLayer("t1", "DIGITAL DREAMS ✦", 300, 1480, 32, "#0284C7", alignment="center", is_bold=True),
                TextLayer("t2", "Sweet Cartoon Vibes", 300, 1540, 22, "#0369A1", alignment="center"),
                TextLayer("t3", "{date}", 300, 1680, 18, "#7DD3FC", alignment="center")
            ]),
            ("matcha", "Matcha", "Dễ thương", "2x6", [600, 1800], "#ECFDF5", 3, [
                TextLayer("t1", "Matcha Moments", 300, 1370, 36, "#047857", alignment="center", is_bold=True),
                TextLayer("t2", "Sweet Green Life", 300, 1430, 22, "#059669", alignment="center"),
                TextLayer("t3", "1998 Studio • {date}", 300, 1680, 18, "#6EE7B7", alignment="center")
            ]),
            ("cutie_pinkie", "Cutie Pinkie", "Sinh nhật", "2x6", [600, 1800], "#FDF2F8", 4, [
                TextLayer("t1", "HAPPY BIRTHDAY CUTIE", 300, 1480, 30, "#DB2777", alignment="center", is_bold=True),
                TextLayer("t2", "Forever Young & Sweet", 300, 1540, 22, "#BE185D", alignment="center"),
                TextLayer("t3", "{date}", 300, 1680, 18, "#F472B6", alignment="center")
            ]),
            ("bear_pink", "BearPink", "Dễ thương", "2x6", [600, 1800], "#FFF1F2", 3, [
                TextLayer("t1", "Teddy & Honey", 300, 1370, 36, "#E11D48", alignment="center", is_bold=True),
                TextLayer("t2", "Love in the Air", 300, 1430, 22, "#BE123C", alignment="center"),
                TextLayer("t3", "1998 Photobooth", 300, 1680, 18, "#FDA4AF", alignment="center")
            ]),
            ("locket", "Locket", "Vintage", "2x6", [600, 1800], "#FAF5EF", 3, [
                TextLayer("t1", "Golden Locket", 300, 1370, 38, "#92400E", alignment="center", is_bold=True),
                TextLayer("t2", "Keep Your Memories Safe", 300, 1430, 22, "#B45309", alignment="center"),
                TextLayer("t3", "{date}", 300, 1680, 18, "#D97706", alignment="center")
            ]),
            ("y2k", "Y2K", "Sinh nhật", "2x6", [600, 1800], "#F5F3FF", 4, [
                TextLayer("t1", "✦ Y2K VIBES ✦", 300, 1480, 34, "#7C3AED", alignment="center", is_bold=True),
                TextLayer("t2", "Millennium Star Party", 300, 1540, 22, "#6D28D9", alignment="center"),
                TextLayer("t3", "{date}", 300, 1680, 18, "#A78BFA", alignment="center")
            ]),
            ("theatre_ticket", "Theatre Ticket", "Vintage", "2x6", [600, 1800], "#FFFBEB", 3, [
                TextLayer("t1", "CINEMA TICKET", 300, 1360, 38, "#78350F", alignment="center", is_bold=True),
                TextLayer("t2", "ADMIT ONE • ROW A SEAT 19", 300, 1420, 22, "#92400E", alignment="center"),
                TextLayer("t3", "Premiere Night • {date}", 300, 1680, 18, "#B45309", alignment="center")
            ]),
            ("wedding_1", "Wedding-1", "Đám cưới", "2x6", [600, 1800], "#FFFDF9", 3, [
                TextLayer("t1", "Happy Wedding", 300, 1360, 42, "#D4AF37", alignment="center", is_bold=True),
                TextLayer("t2", "Trọn Vẹn Yêu Thương", 300, 1430, 24, "#854D0E", alignment="center"),
                TextLayer("t3", "1998 Studio Phóng Sự Cưới • {date}", 300, 1680, 18, "#A16207", alignment="center")
            ]),
            ("vintage_film", "Vintage Film", "Vintage", "2x6", [600, 1800], "#18181B", 4, [
                TextLayer("t1", "35MM NEGATIVE", 300, 1480, 32, "#E4E4E7", alignment="center", is_bold=True),
                TextLayer("t2", "KODAK PORTRA 400", 300, 1540, 20, "#A1A1AA", alignment="center"),
                TextLayer("t3", "FRAME 1998 • {date}", 300, 1680, 18, "#71717A", alignment="center")
            ]),
            ("colorful", "Colorful", "Sự kiện", "2x6", [600, 1800], "#FEF9C3", 4, [
                TextLayer("t1", "FESTIVAL OF COLORS", 300, 1480, 30, "#CA8A04", alignment="center", is_bold=True),
                TextLayer("t2", "Joyful Celebration", 300, 1540, 22, "#A16207", alignment="center"),
                TextLayer("t3", "{date}", 300, 1680, 18, "#EAB308", alignment="center")
            ]),
            ("hello_kitty", "Hello Kitty", "Dễ thương", "2x6", [600, 1800], "#FCE7F3", 4, [
                TextLayer("t1", "Sweet Ribbon & Bows", 300, 1480, 30, "#DB2777", alignment="center", is_bold=True),
                TextLayer("t2", "Lovely Pink Memories", 300, 1540, 22, "#BE185D", alignment="center"),
                TextLayer("t3", "{date}", 300, 1680, 18, "#F472B6", alignment="center")
            ]),
            ("star", "Star", "Sự kiện", "2x6", [600, 1800], "#0B132B", 3, [
                TextLayer("t1", "GOLDEN STARS", 300, 1360, 40, "#D4AF37", alignment="center", is_bold=True),
                TextLayer("t2", "A Night to Remember", 300, 1430, 22, "#E2E8F0", alignment="center"),
                TextLayer("t3", "1998 TEAM Photobooth • {date}", 300, 1680, 18, "#94A3B8", alignment="center")
            ]),
        ]

        for fid, fname, fcat, ftype, fcanvas, fbg, num_slots, flayers in templates_specs:
            cat_dir = os.path.join(self.base_dir, fcat)
            os.makedirs(cat_dir, exist_ok=True)
            fjson = os.path.join(cat_dir, f"{fid}.json")
            if not os.path.exists(fjson):
                if num_slots == 3:
                    slots = [
                        PhotoSlot(id=1, x=45, y=60, w=510, h=380, corner_radius=12, photo_index=0),
                        PhotoSlot(id=2, x=45, y=470, w=510, h=380, corner_radius=12, photo_index=1),
                        PhotoSlot(id=3, x=45, y=880, w=510, h=380, corner_radius=12, photo_index=2),
                    ]
                else:
                    slots = [
                        PhotoSlot(id=1, x=50, y=50, w=500, h=320, corner_radius=14, photo_index=0),
                        PhotoSlot(id=2, x=50, y=395, w=500, h=320, corner_radius=14, photo_index=1),
                        PhotoSlot(id=3, x=50, y=740, w=500, h=320, corner_radius=14, photo_index=2),
                        PhotoSlot(id=4, x=50, y=1085, w=500, h=320, corner_radius=14, photo_index=3),
                    ]

                tmpl = FrameTemplate(
                    id=fid,
                    name=fname,
                    category=fcat,
                    type=ftype,
                    canvas_size=fcanvas,
                    bg_color=fbg,
                    slots=slots,
                    text_layers=flayers,
                    safe_zone_px=35
                )
                tmpl.save_to_json(fjson)

    def _generate_sample_overlay(self, out_path: str, w: int, h: int, cutout_rects: List[Tuple[int, int, int, int]], border_color: Tuple[int, int, int, int]):
        """Tạo một file PNG mẫu có độ trong suốt và viền hoa văn trang trí để kiểm thử."""
        from PIL import ImageDraw
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0)) # Hoàn toàn trong suốt
        draw = ImageDraw.Draw(img)

        # Viền ngoài cùng
        draw.rectangle([10, 10, w - 10, h - 10], outline=border_color, width=4)

        # Các khung viền trang trí quanh từng ô ảnh
        for (rx, ry, rw, rh) in cutout_rects:
            draw.rectangle([rx - 6, ry - 6, rx + rw + 6, ry + rh + 6], outline=border_color, width=3)

        img.save(out_path, "PNG")

    def reload_all_frames(self):
        """Quét và tải lại toàn bộ khung từ tất cả các danh mục (cả thư mục hệ thống và thư mục người dùng)."""
        self._templates.clear()

        # 1. Quét thư mục gốc kèm theo ứng dụng
        if os.path.exists(self.base_dir):
            for cat in os.listdir(self.base_dir):
                cat_dir = os.path.join(self.base_dir, cat)
                if not os.path.isdir(cat_dir):
                    continue
                for fname in os.listdir(cat_dir):
                    if fname.endswith(".json"):
                        tmpl = FrameTemplate.load_from_json(os.path.join(cat_dir, fname))
                        if tmpl:
                            self._templates[tmpl.id] = tmpl

        # 2. Quét thư mục người dùng (ghi đè hoặc bổ sung khung riêng)
        if os.path.exists(self.user_dir):
            for cat in os.listdir(self.user_dir):
                cat_dir = os.path.join(self.user_dir, cat)
                if not os.path.isdir(cat_dir):
                    continue
                for fname in os.listdir(cat_dir):
                    if fname.endswith(".json"):
                        tmpl = FrameTemplate.load_from_json(os.path.join(cat_dir, fname))
                        if tmpl:
                            self._templates[tmpl.id] = tmpl

        logger.info(f"Đã nạp tổng cộng {len(self._templates)} mẫu khung in ảnh.")

    def list_frames(
        self,
        category: Optional[str] = None,
        ratio: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> List[FrameTemplate]:
        """Lọc danh sách các khung theo danh mục, tỷ lệ (2x6 / 4x6) và từ khóa tìm kiếm."""
        result = list(self._templates.values())

        if category and category.lower() not in ("tất cả", "all", ""):
            cat_norm = category.lower().strip()
            synonyms = {
                "đám cưới": ["wedding", "đám cưới"],
                "sinh nhật": ["birthday", "sinh nhật"],
                "sự kiện": ["corporate", "sự kiện", "event"],
                "khác": ["custom", "khác", "other"],
                "wedding": ["wedding", "đám cưới"],
                "birthday": ["birthday", "sinh nhật"],
                "corporate": ["corporate", "sự kiện", "event"],
                "custom": ["custom", "khác", "other"],
            }
            allowed = synonyms.get(cat_norm, [cat_norm])
            result = [t for t in result if any(a in t.category.lower() for a in allowed)]

        if ratio and ratio.lower() not in ("tất cả", "all", ""):
            r_norm = ratio.lower().strip()
            if r_norm == "2x6":
                result = [t for t in result if "2x6" in t.type.lower()]
            elif r_norm == "4x6":
                result = [t for t in result if "4x6" in t.type.lower()]

        if search_query and search_query.strip():
            q = search_query.lower().strip()
            result = [t for t in result if q in t.name.lower() or q in t.id.lower() or q in t.category.lower()]

        return result

    def get_frame(self, frame_id: str) -> Optional[FrameTemplate]:
        """Lấy một khung theo ID."""
        return self._templates.get(frame_id)

    def get_thumbnail_path(self, frame_id: str) -> str:
        """Đường dẫn tệp PNG thumbnail trên đĩa cho khung ảnh."""
        return os.path.join(self.thumb_dir, f"{frame_id}_thumb.png")

    def get_or_create_thumbnail(self, template: FrameTemplate, max_width: int = 110, max_height: int = 140) -> str:
        """Trả về đường dẫn tệp thumbnail PNG của khung (nạp từ cache đĩa nếu có, sinh mới nếu chưa có)."""
        thumb_path = self.get_thumbnail_path(template.id)
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path

        try:
            from vietphotobooth.frames.frame_designer import FrameDesigner
            pil_thumb = FrameDesigner.generate_thumbnail(template, max_width=max_width, max_height=max_height)
            pil_thumb.save(thumb_path, "PNG", optimize=True)
            return thumb_path
        except Exception as e:
            logger.warning(f"Không thể tạo thumbnail lưu đĩa cho khung {template.id}: {e}")
            return ""

    def invalidate_thumbnail(self, frame_id: str) -> None:
        """Xóa thumbnail đệm khi khung bị sửa đổi hoặc xóa."""
        p = self.get_thumbnail_path(frame_id)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    def save_frame(self, template: FrameTemplate) -> bool:
        """Lưu khung ảnh vào thư mục người dùng để bảo toàn khi nâng cấp ứng dụng."""
        self.invalidate_thumbnail(template.id)
        cat_dir = os.path.join(self.user_dir, template.category)
        os.makedirs(cat_dir, exist_ok=True)
        target_json = os.path.join(cat_dir, f"{template.id}.json")
        success = template.save_to_json(target_json)
        if success:
            self._templates[template.id] = template
            logger.info(f"Đã lưu khung in ảnh: {template.name} ({template.id}) tại {target_json}")
        return success

    def delete_frame(self, frame_id: str) -> bool:
        """Xóa một khung ảnh từ thư mục người dùng hoặc thư mục gốc."""
        self.invalidate_thumbnail(frame_id)
        tmpl = self.get_frame(frame_id)
        if not tmpl:
            return False
        
        deleted = False
        for root_dir in (self.user_dir, self.base_dir):
            cat_dir = os.path.join(root_dir, tmpl.category)
            target_json = os.path.join(cat_dir, f"{frame_id}.json")
            if os.path.exists(target_json):
                try:
                    os.remove(target_json)
                    deleted = True
                except Exception as e:
                    logger.error(f"Lỗi khi xóa khung {frame_id}: {e}")

        if deleted:
            self._templates.pop(frame_id, None)
            logger.info(f"Đã xóa khung {frame_id}")
            return True
        return False

    def import_external_frame(
        self,
        file_path: str,
        template_name: str,
        category: str = "Custom",
        strip_type: str = "2x6",
        layer_mode: str = "overlay", # "overlay" (ảnh nằm dưới khung) hoặc "background" (ảnh nằm trên nền)
        notes: str = "",
        num_slots: int = 3
    ) -> Optional[FrameTemplate]:
        """
        Nhập một file ảnh (PNG trong suốt, JPG nền kín hoặc SVG vector) làm khung viền cho Photobooth.
        Tự động chuyển đổi SVG sang ảnh raster 300 DPI độ nét cao.
        Lưu tệp vào thư mục người dùng (USER_DATA_DIR) để bảo toàn vĩnh viễn khi cập nhật ứng dụng.
        """
        if not os.path.exists(file_path):
            logger.error(f"File khung không tồn tại: {file_path}")
            return None

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".svg"):
            logger.error(f"Định dạng tệp không được hỗ trợ: {ext}. Hỗ trợ: PNG, JPG, JPEG, SVG.")
            return None

        cat_dir = os.path.join(self.user_dir, category)
        os.makedirs(cat_dir, exist_ok=True)

        safe_id = "".join(c if c.isalnum() else "_" for c in template_name.lower()).strip("_")
        if not safe_id:
            safe_id = f"frame_{int(os.path.getmtime(file_path))}"

        canvas_size = list(DPI_300_SIZES.get(strip_type, (600, 1800)))
        w, h = canvas_size[0], canvas_size[1]

        dest_image_path = None
        overlay_path = None
        bg_image_path = None

        try:
            if ext == ".svg":
                # Chuyển đổi SVG an toàn sang PNG 300 DPI
                dest_image_path = os.path.join(cat_dir, f"{safe_id}_vector.png")
                success = self.convert_svg_to_png(file_path, dest_image_path, w, h)
                if not success:
                    return None
                if layer_mode == "background":
                    bg_image_path = dest_image_path
                else:
                    overlay_path = dest_image_path
            elif ext in (".jpg", ".jpeg"):
                dest_image_path = os.path.join(cat_dir, f"{safe_id}_bg{ext}")
                shutil.copy2(file_path, dest_image_path)
                bg_image_path = dest_image_path
            else: # .png
                dest_image_path = os.path.join(cat_dir, f"{safe_id}_overlay.png")
                shutil.copy2(file_path, dest_image_path)
                if layer_mode == "background":
                    bg_image_path = dest_image_path
                else:
                    overlay_path = dest_image_path

            # Khởi tạo các ô PhotoSlot ban đầu phù hợp với khổ in và số lượng ảnh
            slots = []
            if strip_type == "2x6":
                if num_slots == 4:
                    slot_h = 320
                    gap = 25
                    start_y = 50
                    for i in range(4):
                        slots.append(PhotoSlot(id=i+1, x=45, y=start_y + i * (slot_h + gap), w=510, h=slot_h, corner_radius=10, photo_index=i))
                elif num_slots == 2:
                    slots.append(PhotoSlot(id=1, x=45, y=80, w=510, h=560, corner_radius=10, photo_index=0))
                    slots.append(PhotoSlot(id=2, x=45, y=680, w=510, h=560, corner_radius=10, photo_index=1))
                elif num_slots == 1:
                    slots.append(PhotoSlot(id=1, x=45, y=100, w=510, h=1100, corner_radius=12, photo_index=0))
                else: # 3 slots
                    slots = [
                        PhotoSlot(id=1, x=45, y=60, w=510, h=380, corner_radius=10, photo_index=0),
                        PhotoSlot(id=2, x=45, y=470, w=510, h=380, corner_radius=10, photo_index=1),
                        PhotoSlot(id=3, x=45, y=880, w=510, h=380, corner_radius=10, photo_index=2),
                    ]
                text_layers = [
                    TextLayer(id="title", text=template_name, x=300, y=1340, font_size=38, alignment="center"),
                    TextLayer(id="date", text="{date}", x=300, y=1420, font_size=26, alignment="center")
                ]
            elif strip_type == "4x6_landscape":
                if num_slots == 2:
                    slots = [
                        PhotoSlot(id=1, x=60, y=80, w=800, h=800, corner_radius=12, photo_index=0),
                        PhotoSlot(id=2, x=940, y=80, w=800, h=800, corner_radius=12, photo_index=1),
                    ]
                else: # 3 slots
                    slots = [
                        PhotoSlot(id=1, x=60, y=80, w=520, h=680, corner_radius=12, photo_index=0),
                        PhotoSlot(id=2, x=640, y=80, w=520, h=680, corner_radius=12, photo_index=1),
                        PhotoSlot(id=3, x=1220, y=80, w=520, h=680, corner_radius=12, photo_index=2),
                    ]
                text_layers = [
                    TextLayer(id="title", text=template_name, x=900, y=840, font_size=46, alignment="center"),
                    TextLayer(id="date", text="{date}", x=900, y=930, font_size=30, alignment="center")
                ]
            else: # 4x6_portrait or 4x6_dual
                slots = [
                    PhotoSlot(id=1, x=60, y=60, w=520, h=520, corner_radius=10, photo_index=0),
                    PhotoSlot(id=2, x=620, y=60, w=520, h=520, corner_radius=10, photo_index=1),
                    PhotoSlot(id=3, x=60, y=620, w=520, h=520, corner_radius=10, photo_index=2),
                    PhotoSlot(id=4, x=620, y=620, w=520, h=520, corner_radius=10, photo_index=3),
                ]
                text_layers = [
                    TextLayer(id="title", text=template_name, x=600, y=1220, font_size=44, alignment="center"),
                    TextLayer(id="date", text="{date}", x=600, y=1300, font_size=28, alignment="center")
                ]

            is_dual = (strip_type == "4x6_dual")
            new_template = FrameTemplate(
                id=safe_id,
                name=template_name,
                category=category,
                type=strip_type,
                canvas_size=canvas_size,
                overlay_png_path=overlay_path,
                bg_image_path=bg_image_path,
                is_dual_strip=is_dual,
                has_cut_line=is_dual,
                notes=notes,
                slots=slots,
                text_layers=text_layers
            )

            self.save_frame(new_template)
            logger.info(f"Đã nhập thành công khung: {template_name} ({ext})")
            return new_template

        except Exception as e:
            logger.error(f"Lỗi khi nhập khung từ {file_path}: {e}")
            return None

    def import_external_png_overlay(
        self,
        png_path: str,
        template_name: str,
        category: str = "Custom",
        strip_type: str = "2x6"
    ) -> Optional[FrameTemplate]:
        """Tương thích ngược với các lệnh gọi cũ."""
        return self.import_external_frame(
            file_path=png_path,
            template_name=template_name,
            category=category,
            strip_type=strip_type,
            layer_mode="overlay"
        )

    def duplicate_frame(self, frame_id: str, new_name: str) -> Optional[FrameTemplate]:
        """Nhân bản một khung ảnh thành khung mới."""
        source = self.get_frame(frame_id)
        if not source:
            return None

        safe_id = "".join(c if c.isalnum() else "_" for c in new_name.lower()).strip("_")
        if not safe_id or safe_id == source.id:
            safe_id = f"{source.id}_copy_{int(os.path.getmtime(self.user_dir))}"

        cat_dir = os.path.join(self.user_dir, source.category)
        os.makedirs(cat_dir, exist_ok=True)

        new_overlay = None
        if source.overlay_png_path and os.path.exists(source.overlay_png_path):
            new_overlay = os.path.join(cat_dir, f"{safe_id}_overlay.png")
            shutil.copy2(source.overlay_png_path, new_overlay)

        new_bg = None
        if source.bg_image_path and os.path.exists(source.bg_image_path):
            ext = os.path.splitext(source.bg_image_path)[1]
            new_bg = os.path.join(cat_dir, f"{safe_id}_bg{ext}")
            shutil.copy2(source.bg_image_path, new_bg)

        import copy
        new_slots = copy.deepcopy(source.slots)
        new_texts = copy.deepcopy(source.text_layers)
        new_logos = copy.deepcopy(source.logo_layers)

        new_frame = FrameTemplate(
            id=safe_id,
            name=new_name,
            category=source.category,
            type=source.type,
            canvas_size=list(source.canvas_size),
            bg_color=source.bg_color,
            bg_image_path=new_bg,
            overlay_png_path=new_overlay,
            slots=new_slots,
            text_layers=new_texts,
            logo_layers=new_logos,
            is_dual_strip=source.is_dual_strip,
            has_cut_line=source.has_cut_line,
            notes=source.notes,
            version=source.version,
            author=source.author
        )

        self.save_frame(new_frame)
        logger.info(f"Đã nhân bản khung '{source.name}' thành '{new_name}' ({safe_id})")
        return new_frame

    def rename_frame(self, frame_id: str, new_name: str) -> bool:
        """Đổi tên một khung ảnh."""
        f = self.get_frame(frame_id)
        if not f:
            return False
        f.name = new_name.strip()
        return self.save_frame(f)

    def backup_frames_to_zip(self, zip_path: str) -> bool:
        """Sao lưu toàn bộ khung ảnh người dùng và tài nguyên ra file ZIP."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(zip_path)), exist_ok=True)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                if os.path.exists(self.user_dir):
                    for root, dirs, files in os.walk(self.user_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, self.user_dir)
                            zf.write(full_path, arcname=rel_path)
            logger.info(f"Đã sao lưu toàn bộ khung ảnh vào: {zip_path}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi sao lưu khung ảnh ra ZIP: {e}")
            return False

    def restore_frames_from_zip(self, zip_path: str) -> bool:
        """Khôi phục dữ liệu khung ảnh từ file ZIP sao lưu."""
        if not os.path.exists(zip_path) or not zipfile.is_zipfile(zip_path):
            logger.error(f"File ZIP khôi phục không hợp lệ: {zip_path}")
            return False

        try:
            os.makedirs(self.user_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(self.user_dir)
            self.reload_all_frames()
            logger.info(f"Đã khôi phục thành công khung ảnh từ {zip_path}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi khôi phục khung ảnh: {e}")
            return False

    @staticmethod
    def convert_svg_to_png(svg_path: str, out_png_path: str, width: int, height: int) -> bool:
        """Chuyển đổi an toàn tệp SVG vector thành ảnh raster PNG chuẩn in 300 DPI."""
        try:
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QImage, QPainter
            from PySide6.QtCore import Qt
            renderer = QSvgRenderer(svg_path)
            if not renderer.isValid():
                logger.error(f"Tệp SVG không hợp lệ: {svg_path}")
                return False

            qimg = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
            qimg.fill(Qt.transparent)
            painter = QPainter(qimg)
            renderer.render(painter)
            painter.end()
            return qimg.save(out_png_path, "PNG")
        except Exception as e:
            logger.error(f"Lỗi khi chuyển đổi SVG sang PNG: {e}")
            return False
