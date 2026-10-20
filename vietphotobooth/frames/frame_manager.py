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

logger = get_logger()

DEFAULT_FRAMES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Frames"))

CATEGORIES = ["Wedding", "Birthday", "Corporate", "Custom"]

class FrameManager:
    """Quản lý danh viện khung in ảnh, nhập khung từ file PNG bên ngoài và sao lưu."""

    def __init__(self, base_dir: str = DEFAULT_FRAMES_DIR):
        self.base_dir = os.path.abspath(base_dir)
        for cat in CATEGORIES:
            os.makedirs(os.path.join(self.base_dir, cat), exist_ok=True)

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
        """Quét và tải lại toàn bộ khung từ tất cả các danh mục."""
        self._templates.clear()
        for cat in os.listdir(self.base_dir):
            cat_dir = os.path.join(self.base_dir, cat)
            if not os.path.isdir(cat_dir):
                continue
            for fname in os.listdir(cat_dir):
                if fname.endswith(".json"):
                    tmpl = FrameTemplate.load_from_json(os.path.join(cat_dir, fname))
                    if tmpl:
                        self._templates[tmpl.id] = tmpl

        logger.info(f"Đã nạp tổng cộng {len(self._templates)} mẫu khung in ảnh.")

    def list_frames(self, category: Optional[str] = None) -> List[FrameTemplate]:
        """Lấy danh sách các khung theo danh mục (hoặc tất cả)."""
        if not category or category.lower() == "tất cả":
            return list(self._templates.values())
        return [t for t in self._templates.values() if t.category.lower() == category.lower()]

    def get_frame(self, frame_id: str) -> Optional[FrameTemplate]:
        """Lấy một khung theo ID."""
        return self._templates.get(frame_id)

    def save_frame(self, template: FrameTemplate) -> bool:
        """Lưu khung ảnh vào danh mục tương ứng."""
        cat_dir = os.path.join(self.base_dir, template.category)
        os.makedirs(cat_dir, exist_ok=True)
        target_json = os.path.join(cat_dir, f"{template.id}.json")
        success = template.save_to_json(target_json)
        if success:
            self._templates[template.id] = template
            logger.info(f"Đã lưu khung in ảnh: {template.name} ({template.id})")
        return success

    def delete_frame(self, frame_id: str) -> bool:
        """Xóa một khung ảnh."""
        tmpl = self.get_frame(frame_id)
        if not tmpl:
            return False
        cat_dir = os.path.join(self.base_dir, tmpl.category)
        target_json = os.path.join(cat_dir, f"{frame_id}.json")
        if os.path.exists(target_json):
            try:
                os.remove(target_json)
                self._templates.pop(frame_id, None)
                logger.info(f"Đã xóa khung {frame_id}")
                return True
            except Exception as e:
                logger.error(f"Lỗi khi xóa khung {frame_id}: {e}")
                return False
        return False

    def import_external_png_overlay(
        self,
        png_path: str,
        template_name: str,
        category: str = "Custom",
        strip_type: str = "2x6"
    ) -> Optional[FrameTemplate]:
        """
        Nhập một file ảnh PNG bên ngoài làm khung viền overlay cho Photobooth.
        Tự động xác thực:
        - Tồn tại kênh suốt (Alpha Channel).
        - Tính toán kích thước chuẩn in 300 DPI.
        - Khởi tạo các ô slot tương ứng.
        """
        if not os.path.exists(png_path):
            logger.error(f"File PNG không tồn tại: {png_path}")
            return None

        try:
            with Image.open(png_path) as img:
                if img.mode not in ("RGBA", "LA") and "transparency" not in img.info:
                    logger.warning(f"File {png_path} không có kênh trong suốt (Alpha). Vẫn tiếp tục xử lý dưới dạng ảnh viền.")

                w, h = img.size
                canvas_size = DPI_300_SIZES.get(strip_type, [w, h])

            # Sao chép file PNG vào thư mục Assets/Frames/<category>/
            cat_dir = os.path.join(self.base_dir, category)
            os.makedirs(cat_dir, exist_ok=True)

            safe_id = "".join(c if c.isalnum() else "_" for c in template_name.lower()).strip("_")
            if not safe_id:
                safe_id = f"custom_frame_{int(os.path.getmtime(png_path))}"

            dest_png = os.path.join(cat_dir, f"{safe_id}_overlay.png")
            shutil.copy2(png_path, dest_png)

            # Tạo các ô slots mẫu dựa trên kiểu khung
            if strip_type == "2x6":
                slots = [
                    PhotoSlot(id=1, x=45, y=60, w=510, h=380, corner_radius=8, photo_index=0),
                    PhotoSlot(id=2, x=45, y=470, w=510, h=380, corner_radius=8, photo_index=1),
                    PhotoSlot(id=3, x=45, y=880, w=510, h=380, corner_radius=8, photo_index=2),
                ]
                text_layers = [
                    TextLayer(id="title", text=template_name, x=300, y=1340, font_size=38, alignment="center"),
                    TextLayer(id="date", text="{date}", x=300, y=1420, font_size=26, alignment="center")
                ]
            else: # 4x6
                slots = [
                    PhotoSlot(id=1, x=60, y=60, w=520, h=520, corner_radius=8, photo_index=0),
                    PhotoSlot(id=2, x=620, y=60, w=520, h=520, corner_radius=8, photo_index=1),
                    PhotoSlot(id=3, x=60, y=620, w=520, h=520, corner_radius=8, photo_index=2),
                    PhotoSlot(id=4, x=620, y=620, w=520, h=520, corner_radius=8, photo_index=3),
                ]
                text_layers = [
                    TextLayer(id="title", text=template_name, x=600, y=1220, font_size=44, alignment="center"),
                    TextLayer(id="date", text="{date}", x=600, y=1300, font_size=28, alignment="center")
                ]

            new_template = FrameTemplate(
                id=safe_id,
                name=template_name,
                category=category,
                type=strip_type,
                canvas_size=list(canvas_size),
                overlay_png_path=dest_png,
                slots=slots,
                text_layers=text_layers
            )

            self.save_frame(new_template)
            logger.info(f"Đã nhập thành công khung ngoài: {template_name}")
            return new_template

        except Exception as e:
            logger.error(f"Lỗi khi nhập khung PNG từ {png_path}: {e}")
            return None
