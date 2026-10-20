"""
VietPhotoBooth Template Engine
Generates physical 300 DPI templates for 2x6 strips and 4x6 prints with dual-cut support for DNP RX1HS.
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from vietphotobooth.processing.image_processor import ImageProcessor
from vietphotobooth.core.logger import get_logger

logger = get_logger()

# Chuẩn DPI in ấn cho Photobooth
PRINT_DPI = 300

# Kích thước pixel chuẩn 300 DPI
DIMENSIONS = {
    "2x6": (600, 1800),             # 2 inch x 6 inch
    "4x6_portrait": (1200, 1800),   # 4 inch x 6 inch dọc
    "4x6_landscape": (1800, 1200),  # 6 inch x 4 inch ngang
}

DEFAULT_TEMPLATES = {
    # 1. Dải 2x6 truyền thống - 3 ảnh
    "strip_2x6_3photos": {
        "id": "strip_2x6_3photos",
        "name": "Dải Photobooth 2x6 inch (3 Ảnh)",
        "type": "2x6",
        "canvas_size": [600, 1800],
        "bg_color": "#FFFFFF",
        "text_color": "#222222",
        "slots": [
            {"x": 40, "y": 60, "w": 520, "h": 390},
            {"x": 40, "y": 480, "w": 520, "h": 390},
            {"x": 40, "y": 900, "w": 520, "h": 390}
        ],
        "text_area": {
            "title_y": 1360,
            "subtitle_y": 1450,
            "date_y": 1540,
            "footer_y": 1620
        }
    },
    # 2. Dải 2x6 truyền thống - 4 ảnh
    "strip_2x6_4photos": {
        "id": "strip_2x6_4photos",
        "name": "Dải Photobooth 2x6 inch (4 Ảnh)",
        "type": "2x6",
        "canvas_size": [600, 1800],
        "bg_color": "#FFFFFF",
        "text_color": "#222222",
        "slots": [
            {"x": 40, "y": 50, "w": 520, "h": 340},
            {"x": 40, "y": 415, "w": 520, "h": 340},
            {"x": 40, "y": 780, "w": 520, "h": 340},
            {"x": 40, "y": 1145, "w": 520, "h": 340}
        ],
        "text_area": {
            "title_y": 1530,
            "subtitle_y": 1600,
            "date_y": 1670,
            "footer_y": 1720
        }
    },
    # 3. Khổ 4x6 ghép đôi 2 dải 2x6 (3 ảnh) - Dành riêng cho máy in nhiệt thăng hoa (DNP DS-RX1HS) tự cắt
    "dual_strip_4x6_3photos": {
        "id": "dual_strip_4x6_3photos",
        "name": "Ghép Đôi 2 Dải 2x6 trên Khổ 4x6 (3 Ảnh - Cắt Máy DNP)",
        "type": "4x6_dual",
        "canvas_size": [1200, 1800],
        "bg_color": "#FFFFFF",
        "text_color": "#222222",
        "has_cut_line": True,
        # 3 ảnh bên trái (x=30..570) và 3 ảnh đối xứng bên phải (x=630..1170)
        "slots": [
            # Strip 1 (Trái)
            {"x": 40, "y": 60, "w": 520, "h": 390},
            {"x": 40, "y": 480, "w": 520, "h": 390},
            {"x": 40, "y": 900, "w": 520, "h": 390},
            # Strip 2 (Phải - Nhân bản để cắt)
            {"x": 640, "y": 60, "w": 520, "h": 390},
            {"x": 640, "y": 480, "w": 520, "h": 390},
            {"x": 640, "y": 900, "w": 520, "h": 390}
        ],
        "is_dual_strip": True,
        "strip_count": 3
    },
    # 4. Khổ 4x6 Lưới 4 ảnh (2x2 Grid)
    "grid_4x6_4photos": {
        "id": "grid_4x6_4photos",
        "name": "Khổ 4x6 inch Lưới 4 Ảnh (2x2 Grid)",
        "type": "4x6_portrait",
        "canvas_size": [1200, 1800],
        "bg_color": "#FFFFFF",
        "text_color": "#222222",
        "slots": [
            {"x": 60, "y": 60, "w": 520, "h": 580},
            {"x": 620, "y": 60, "w": 520, "h": 580},
            {"x": 60, "y": 680, "w": 520, "h": 580},
            {"x": 620, "y": 680, "w": 520, "h": 580}
        ],
        "text_area": {
            "title_y": 1350,
            "subtitle_y": 1450,
            "date_y": 1550,
            "footer_y": 1650
        }
    },
    # 5. Khổ 4x6 Ngang 3 ảnh (Landscape)
    "landscape_4x6_3photos": {
        "id": "landscape_4x6_3photos",
        "name": "Khổ 4x6 inch Ngang (3 Ảnh + Khung Chữ)",
        "type": "4x6_landscape",
        "canvas_size": [1800, 1200],
        "bg_color": "#FAFAFA",
        "text_color": "#111111",
        "slots": [
            {"x": 50, "y": 50, "w": 530, "h": 780},
            {"x": 635, "y": 50, "w": 530, "h": 780},
            {"x": 1220, "y": 50, "w": 530, "h": 780}
        ],
        "text_area": {
            "title_y": 890,
            "subtitle_y": 970,
            "date_y": 1050,
            "footer_y": 1110
        }
    }
}

class TemplateEngine:
    def __init__(self, templates_dir: str = None):
        self.templates_dir = templates_dir
        self.templates: Dict[str, Dict[str, Any]] = DEFAULT_TEMPLATES.copy()
        if self.templates_dir:
            os.makedirs(self.templates_dir, exist_ok=True)
            self._load_custom_templates()

    def _load_custom_templates(self) -> None:
        if not self.templates_dir or not os.path.exists(self.templates_dir):
            return
        for fname in os.listdir(self.templates_dir):
            if fname.lower().endswith(".json"):
                fpath = os.path.join(self.templates_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        tpl = json.load(f)
                        if "id" in tpl:
                            self.templates[tpl["id"]] = tpl
                except Exception as e:
                    logger.warning(f"Không thể đọc file template {fpath}: {e}")

    def list_templates(self) -> List[Dict[str, Any]]:
        return list(self.templates.values())

    def get_template(self, template_id: str) -> Dict[str, Any]:
        return self.templates.get(template_id, DEFAULT_TEMPLATES["strip_2x6_3photos"])

    def save_template(self, tpl: Dict[str, Any]) -> bool:
        if "id" not in tpl:
            return False
        self.templates[tpl["id"]] = tpl
        if self.templates_dir:
            fpath = os.path.join(self.templates_dir, f"{tpl['id']}.json")
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(tpl, f, ensure_ascii=False, indent=2)
                logger.info(f"Đã lưu template {tpl['id']} vào đĩa.")
                return True
            except Exception as e:
                logger.error(f"Lỗi khi lưu template: {e}")
                return False
        return True

    def render(
        self,
        template_id: str,
        photos: List[Image.Image],
        event_info: Dict[str, str],
        filter_name: str = "none"
    ) -> Image.Image:
        """
        Ghép loạt ảnh vào khung template theo chuẩn in 300 DPI, bảo toàn tỷ lệ và chèn thông tin sự kiện.
        """
        tpl = self.get_template(template_id)
        w, h = tpl["canvas_size"]

        # 1. Tạo Canvas
        bg_color = tpl.get("bg_color", "#FFFFFF")
        canvas = Image.new("RGB", (w, h), bg_color)
        draw = ImageDraw.Draw(canvas)

        # 2. Xử lý trường hợp Dual Strip (Cắt đôi tự động cho máy DNP RX1HS)
        slots = tpl["slots"]
        is_dual = tpl.get("is_dual_strip", False)

        if is_dual:
            # photos có thể có 3 ảnh. Nhân bản để điền cả 6 slots (3 trái, 3 phải)
            strip_len = tpl.get("strip_count", len(photos))
            active_photos = photos[:strip_len]
            # Điền bên trái
            for i in range(min(len(active_photos), strip_len)):
                slot = slots[i]
                processed = ImageProcessor.crop_and_resize(active_photos[i], slot["w"], slot["h"])
                processed = ImageProcessor.apply_filter(processed, filter_name)
                canvas.paste(processed, (slot["x"], slot["y"]))
            # Điền bên phải (nhân đôi ảnh để in 2 dải cùng lúc)
            for i in range(min(len(active_photos), strip_len)):
                slot = slots[i + strip_len]
                processed = ImageProcessor.crop_and_resize(active_photos[i], slot["w"], slot["h"])
                processed = ImageProcessor.apply_filter(processed, filter_name)
                canvas.paste(processed, (slot["x"], slot["y"]))

            # Vẽ đường đứt nét định vị cắt (Cut Line Guide) nếu bật
            if tpl.get("has_cut_line", False):
                center_x = w // 2
                for cy in range(0, h, 20):
                    draw.line([(center_x, cy), (center_x, cy + 10)], fill=(210, 210, 210), width=2)

            # Vẽ chữ cho cả 2 dải
            self._draw_dual_texts(draw, w, h, event_info, tpl.get("text_color", "#222222"))
        else:
            # Render thông thường theo slots
            for i, slot in enumerate(slots):
                if i < len(photos):
                    processed = ImageProcessor.crop_and_resize(photos[i], slot["w"], slot["h"])
                    processed = ImageProcessor.apply_filter(processed, filter_name)
                    canvas.paste(processed, (slot["x"], slot["y"]))

            # Vẽ chữ thông tin sự kiện
            text_area = tpl.get("text_area")
            if text_area:
                self._draw_single_texts(draw, w, h, text_area, event_info, tpl.get("text_color", "#222222"))

        # Gắn DPI metadata vào ảnh xuất xưởng
        canvas.info["dpi"] = (PRINT_DPI, PRINT_DPI)
        return canvas

    def _draw_single_texts(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        text_area: Dict[str, int],
        event_info: Dict[str, str],
        text_color: str
    ) -> None:
        title = event_info.get("title", "Kỷ Niệm Ngày Cưới")
        subtitle = event_info.get("subtitle", "Chúc Mừng Hạnh Phúc")
        date_str = event_info.get("date", "2026-10-20")

        # Sử dụng hệ thống text vẽ trung tâm
        try:
            font_title = ImageFont.load_default(size=36)
            font_sub = ImageFont.load_default(size=24)
            font_date = ImageFont.load_default(size=20)
        except Exception:
            font_title = ImageFont.load_default()
            font_sub = font_title
            font_date = font_title

        # Title
        ty = text_area.get("title_y", height - 200)
        draw.text((width // 2, ty), title, fill=text_color, font=font_title, anchor="mm")

        # Subtitle
        sy = text_area.get("subtitle_y", height - 140)
        draw.text((width // 2, sy), subtitle, fill=text_color, font=font_sub, anchor="mm")

        # Date
        dy = text_area.get("date_y", height - 80)
        draw.text((width // 2, dy), date_str, fill="#666666", font=font_date, anchor="mm")

    def _draw_dual_texts(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        event_info: Dict[str, str],
        text_color: str
    ) -> None:
        """Vẽ chữ đối xứng cho 2 dải 2x6 trên khổ 4x6."""
        half_w = width // 2
        title = event_info.get("title", "Kỷ Niệm Ngày Cưới")
        subtitle = event_info.get("subtitle", "Chúc Mừng Hạnh Phúc")
        date_str = event_info.get("date", "2026-10-20")

        try:
            font_title = ImageFont.load_default(size=34)
            font_sub = ImageFont.load_default(size=22)
            font_date = ImageFont.load_default(size=18)
        except Exception:
            font_title = ImageFont.load_default()
            font_sub = font_title
            font_date = font_title

        base_y = 1380
        # Dải trái (trục x = half_w // 2 = 300)
        draw.text((half_w // 2, base_y), title, fill=text_color, font=font_title, anchor="mm")
        draw.text((half_w // 2, base_y + 80), subtitle, fill=text_color, font=font_sub, anchor="mm")
        draw.text((half_w // 2, base_y + 150), date_str, fill="#666666", font=font_date, anchor="mm")

        # Dải phải (trục x = half_w + half_w // 2 = 900)
        draw.text((half_w + half_w // 2, base_y), title, fill=text_color, font=font_title, anchor="mm")
        draw.text((half_w + half_w // 2, base_y + 80), subtitle, fill=text_color, font=font_sub, anchor="mm")
        draw.text((half_w + half_w // 2, base_y + 150), date_str, fill="#666666", font=font_date, anchor="mm")
