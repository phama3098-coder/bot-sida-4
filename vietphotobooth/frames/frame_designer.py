"""
VietPhotoBooth Frame Designer & 300 DPI Rendering Engine
Renders high-resolution photobooth prints (2x6 strips, 4x6 portraits/landscapes, dual-cut strips),
applies PNG overlays with transparency, renders photo slots, text, and logos.
"""

import os
import datetime
from typing import List, Dict, Optional, Tuple, Any
from PIL import Image, ImageDraw, ImageFont, ImageOps

from vietphotobooth.core.logger import get_logger
from vietphotobooth.processing.image_processor import ImageProcessor
from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, LogoLayer, DPI_300_SIZES

logger = get_logger()

# Tìm font chữ Windows hỗ trợ tiếng Việt có sẵn
def get_windows_font(font_name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Nạp font chữ tiếng Việt từ hệ thống Windows (Arial, Calibri, Segoe UI, Tahoma)."""
    system_font_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    candidates = [
        os.path.join(system_font_dir, font_name),
        os.path.join(system_font_dir, "arial.ttf"),
        os.path.join(system_font_dir, "calibri.ttf"),
        os.path.join(system_font_dir, "tahoma.ttf"),
        os.path.join(system_font_dir, "segoeui.ttf"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


class FrameDesigner:
    """Bộ tạo dựng bố cục khung in ảnh Photobooth chuẩn 300 DPI."""

    @staticmethod
    def render_composite(
        photos: List[Image.Image],
        template: FrameTemplate,
        event_info: Optional[Dict[str, str]] = None
    ) -> Image.Image:
        """
        Ghép danh sách ảnh vào khung template với độ phân giải chuẩn in 300 DPI.
        Hỗ trợ:
        - Tự động cắt & thu phóng theo tỷ lệ từng ô ảnh (Center Crop).
        - Bo góc viền ảnh tròn mềm mại.
        - Chèn hình nền (Background).
        - Đè khung viền hoa văn PNG có kênh suốt (Alpha Transparency Overlay).
        - Vẽ chữ nghệ thuật tiếng Việt (Tên tiệc, ngày tháng, lời chúc).
        - Nhân bản đôi 2 dải cho máy in DNP DS-RX1HS tự động cắt 2 inch.
        """
        if not photos:
            raise ValueError("Không có ảnh đầu vào để ghép khung.")

        event_info = event_info or {}
        w, h = template.canvas_size[0], template.canvas_size[1]

        # 1. Tạo Canvas nền
        canvas = Image.new("RGBA", (w, h), template.bg_color or "#FFFFFF")

        # 2. Áp dụng ảnh nền nếu có
        if template.bg_image_path and os.path.exists(template.bg_image_path):
            try:
                bg = Image.open(template.bg_image_path).convert("RGBA")
                bg_fitted = ImageProcessor.crop_and_resize(bg, w, h)
                canvas.paste(bg_fitted, (0, 0))
            except Exception as e:
                logger.warning(f"Không thể tải ảnh nền {template.bg_image_path}: {e}")

        # 3. Đặt các ảnh vào từng ô PhotoSlot (sắp xếp theo thứ tự lớp z_order)
        sorted_slots = sorted(template.slots, key=lambda s: getattr(s, 'z_order', 0))
        for slot in sorted_slots:
            idx = slot.photo_index % len(photos)
            raw_photo = photos[idx].convert("RGBA")

            # Cắt và thu phóng ảnh chuẩn tỷ lệ ô chứa
            slot_photo = ImageProcessor.crop_and_resize(raw_photo, slot.w, slot.h)

            # Xoay ảnh theo thuộc tính rotation nếu có (90, 180, 270 hoặc góc bất kỳ)
            if getattr(slot, 'rotation', 0) != 0:
                rot = slot.rotation % 360
                slot_photo = slot_photo.rotate(-rot, expand=True, resample=Image.Resampling.BICUBIC)
                slot_photo = ImageProcessor.crop_and_resize(slot_photo, slot.w, slot.h)

            # Bo góc tròn nếu yêu cầu
            if slot.corner_radius > 0:
                slot_photo = FrameDesigner._apply_corner_radius(slot_photo, slot.corner_radius)

            # Dán ảnh vào vị trí slot
            canvas.paste(slot_photo, (slot.x, slot.y), slot_photo)

            # Vẽ viền nếu có border_width > 0
            if slot.border_width > 0:
                draw = ImageDraw.Draw(canvas)
                for b_i in range(slot.border_width):
                    draw.rectangle(
                        [slot.x - b_i, slot.y - b_i, slot.x + slot.w + b_i, slot.y + slot.h + b_i],
                        outline=slot.border_color
                    )

            # Nếu là chế độ nhân đôi dải (Dual Strip 4x6), sao chép sang dải bên phải (x + 600)
            if template.is_dual_strip and w == 1200:
                right_x = slot.x + 600
                canvas.paste(slot_photo, (right_x, slot.y), slot_photo)
                if slot.border_width > 0:
                    draw = ImageDraw.Draw(canvas)
                    for b_i in range(slot.border_width):
                        draw.rectangle(
                            [right_x - b_i, slot.y - b_i, right_x + slot.w + b_i, slot.y + slot.h + b_i],
                            outline=slot.border_color
                        )

        # 4. Áp dụng lớp phủ viền PNG nghệ thuật (Overlay PNG) lên trên ảnh
        if template.overlay_png_path and os.path.exists(template.overlay_png_path):
            try:
                overlay = Image.open(template.overlay_png_path).convert("RGBA")
                if overlay.size != (w, h):
                    overlay = overlay.resize((w, h), Image.Resampling.LANCZOS)
                canvas.paste(overlay, (0, 0), overlay)
            except Exception as e:
                logger.warning(f"Không thể áp dụng lớp phủ overlay {template.overlay_png_path}: {e}")

        # 5. Vẽ các lớp chữ văn bản (Text Layers)
        draw = ImageDraw.Draw(canvas)
        today_str = datetime.date.today().strftime("%d/%m/%Y")
        for txt in template.text_layers:
            content = txt.text
            # Thay thế biến động
            content = content.replace("{event_name}", event_info.get("name", "VietPhotoBooth"))
            content = content.replace("{date}", event_info.get("date", today_str))
            content = content.replace("{location}", event_info.get("location", ""))

            font = get_windows_font(txt.font_name, txt.font_size)

            # Vẽ cho dải trái
            FrameDesigner._draw_aligned_text(draw, content, txt.x, txt.y, font, txt.font_color, txt.alignment, 600 if template.is_dual_strip else w)

            # Nếu nhân đôi dải (Dual Strip), vẽ cho dải phải
            if template.is_dual_strip and w == 1200:
                FrameDesigner._draw_aligned_text(draw, content, txt.x + 600, txt.y, font, txt.font_color, txt.alignment, 600)

        # 6. Chèn Logo layers nếu có
        for logo in template.logo_layers:
            if logo.image_path and os.path.exists(logo.image_path):
                try:
                    logo_img = Image.open(logo.image_path).convert("RGBA")
                    logo_img = logo_img.resize((logo.w, logo.h), Image.Resampling.LANCZOS)
                    if logo.opacity < 1.0:
                        r, g, b, a = logo_img.split()
                        a = a.point(lambda p: int(p * logo.opacity))
                        logo_img = Image.merge("RGBA", (r, g, b, a))

                    canvas.paste(logo_img, (logo.x, logo.y), logo_img)
                    if template.is_dual_strip and w == 1200:
                        canvas.paste(logo_img, (logo.x + 600, logo.y), logo_img)
                except Exception as e:
                    logger.warning(f"Lỗi khi dán logo {logo.image_path}: {e}")

        # 7. Vẽ đường cắt nét đứt (Cut line) nếu có has_cut_line
        if template.has_cut_line and w == 1200:
            cut_x = 600
            for dash_y in range(0, h, 30):
                draw.line([(cut_x, dash_y), (cut_x, min(dash_y + 15, h))], fill="#999999", width=2)

        # Chuyển đổi về RGB 300 DPI để in và lưu trữ
        final_rgb = canvas.convert("RGB")
        final_rgb.info["dpi"] = (300, 300)
        return final_rgb

    @staticmethod
    def _apply_corner_radius(img: Image.Image, radius: int) -> Image.Image:
        """Tạo bo góc mềm mại cho ảnh bằng mặt nạ alpha."""
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
        out = img.copy()
        out.putalpha(mask)
        return out

    @staticmethod
    def _draw_aligned_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        x: int,
        y: int,
        font: ImageFont.ImageFont,
        color: str,
        alignment: str,
        container_w: int
    ):
        """Vẽ chữ có căn chỉnh trái/giữa/phải chuẩn xác."""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]

        if alignment == "center":
            draw_x = x - (text_w // 2) if x > 0 else (container_w - text_w) // 2
        elif alignment == "right":
            draw_x = x - text_w
        else:
            draw_x = x

        draw.text((draw_x, y), text, font=font, fill=color)

    @staticmethod
    def render_preview(
        template: FrameTemplate,
        sample_photos: Optional[List[Image.Image]] = None,
        max_height: int = 700
    ) -> Image.Image:
        """Tạo ảnh xem trước nhanh (preview thu nhỏ) để hiển thị trong ứng dụng GUI."""
        if not sample_photos:
            # Tạo các ảnh mẫu màu pastel với số thứ tự
            sample_photos = []
            colors = ["#FFEAA7", "#81ECEC", "#74B9FF", "#A29BFE"]
            for i in range(4):
                sample_img = Image.new("RGB", (600, 450), color=colors[i % len(colors)])
                d = ImageDraw.Draw(sample_img)
                f = get_windows_font("arial.ttf", 60)
                d.text((250, 190), f"Ảnh {i+1}", font=f, fill="#2D3436")
                sample_photos.append(sample_img)

        full_render = FrameDesigner.render_composite(sample_photos, template)
        scale = max_height / float(full_render.height)
        new_w = int(full_render.width * scale)
        return full_render.resize((new_w, max_height), Image.Resampling.BILINEAR)

    @staticmethod
    def validate_template(template: FrameTemplate) -> List[str]:
        """Kiểm tra tính hợp lệ và cảnh báo vùng viền an toàn / mép cắt in ấn."""
        warnings = []
        w, h = template.canvas_size[0], template.canvas_size[1]
        bleed = template.bleed_px
        safe = template.safe_zone_px

        for i, slot in enumerate(template.slots):
            # Kiểm tra ô nằm ngoài canvas
            if slot.x < 0 or slot.y < 0 or (slot.x + slot.w) > w or (slot.y + slot.h) > h:
                warnings.append(f"Ô ảnh #{i+1} vượt ra ngoài kích thước khung in ({w}x{h}).")

            # Cảnh báo viền xén (bleed)
            if slot.x < bleed or slot.y < bleed or (slot.x + slot.w) > (w - bleed) or (slot.y + slot.h) > (h - bleed):
                warnings.append(f"Ô ảnh #{i+1} nằm sát mép cắt máy in ({bleed}px). Có nguy cơ bị xén mất một phần viền.")

        for txt in template.text_layers:
            if txt.y < safe or txt.y > (h - safe):
                warnings.append(f"Lớp chữ '{txt.text}' nằm quá gần mép trên/dưới (< {safe}px).")

        return warnings
