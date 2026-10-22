"""
VietPhotoBooth Frame Designer & 300 DPI Rendering Engine
Renders high-resolution photobooth prints (2x6 strips, 4x6 portraits/landscapes, dual-cut strips),
applies PNG overlays with transparency, renders photo slots, text, and logos.
Guarantees 100% WYSIWYG parity between UI preview and printed output.
"""

import os
import datetime
from typing import List, Dict, Optional, Tuple, Any
from PIL import Image, ImageDraw, ImageFont, ImageOps

from vietphotobooth.core.logger import get_logger
from vietphotobooth.core.font_registry import FontRegistry
from vietphotobooth.processing.image_processor import ImageProcessor
from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, LogoLayer, DPI_300_SIZES

logger = get_logger()

# Hệ thống font Windows hỗ trợ tiếng Việt Unicode
FONT_VARIANTS: Dict[str, Dict[str, str]] = {
    "arial": {
        "regular": "arial.ttf",
        "bold": "arialbd.ttf",
        "italic": "ariali.ttf",
        "bold_italic": "arialbi.ttf"
    },
    "calibri": {
        "regular": "calibri.ttf",
        "bold": "calibrib.ttf",
        "italic": "calibrii.ttf",
        "bold_italic": "calibriz.ttf"
    },
    "segoeui": {
        "regular": "segoeui.ttf",
        "bold": "segoeuib.ttf",
        "italic": "segoeuii.ttf",
        "bold_italic": "segoeuiz.ttf"
    },
    "tahoma": {
        "regular": "tahoma.ttf",
        "bold": "tahomabd.ttf",
        "italic": "tahoma.ttf",
        "bold_italic": "tahomabd.ttf"
    },
    "times": {
        "regular": "times.ttf",
        "bold": "timesbd.ttf",
        "italic": "timesi.ttf",
        "bold_italic": "timesbi.ttf"
    }
}


def get_windows_font(
    font_name: str,
    size: int,
    is_bold: bool = False,
    is_italic: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Nạp font chữ tiếng Việt từ Assets/Fonts hoặc hệ thống Windows hỗ trợ đậm/nghiêng."""
    # 1. Thử phân giải qua FontRegistry chuyên dụng
    resolved = FontRegistry.resolve_font_path(font_name)
    if resolved and os.path.exists(resolved):
        try:
            return ImageFont.truetype(resolved, size)
        except Exception:
            pass

    system_font_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    base_lower = os.path.splitext(os.path.basename(font_name))[0].lower().replace(" ", "")

    # Tìm biến thể đậm/nghiêng phù hợp
    target_variant = "regular"
    if is_bold and is_italic:
        target_variant = "bold_italic"
    elif is_bold:
        target_variant = "bold"
    elif is_italic:
        target_variant = "italic"

    candidate_filenames = []

    # 1. Kiểm tra bảng variant
    for family_key, variants in FONT_VARIANTS.items():
        if family_key in base_lower:
            candidate_filenames.append(variants.get(target_variant, variants["regular"]))
            if target_variant != "regular":
                candidate_filenames.append(variants["regular"])
            break

    # 2. Thêm file gốc và các font dự phòng
    candidate_filenames.extend([
        font_name,
        os.path.basename(font_name),
        "arialbd.ttf" if is_bold else "arial.ttf",
        "calibri.ttf",
        "segoeui.ttf",
        "tahoma.ttf"
    ])

    for fname in candidate_filenames:
        if os.path.isabs(fname) and os.path.exists(fname):
            try:
                return ImageFont.truetype(fname, size)
            except Exception:
                continue

        font_path = os.path.join(system_font_dir, fname)
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue

    return ImageFont.load_default()


class FrameDesigner:
    """Bộ tạo dựng bố cục khung in ảnh Photobooth chuẩn 300 DPI với WYSIWYG tuyệt đối."""

    get_windows_font = staticmethod(get_windows_font)

    @staticmethod
    def render_composite(
        photos: List[Image.Image],
        template: FrameTemplate,
        event_info: Optional[Dict[str, str]] = None
    ) -> Image.Image:
        """
        Ghép danh sách ảnh vào khung template với độ phân giải chuẩn in 300 DPI.
        Hỗ trợ:
        - Tự động căn chỉnh ảnh thông minh (Auto Photo Fitting: Cover/Contain, Center/Face, Zoom, Crop Offset).
        - Bo góc viền ảnh tròn mềm mại.
        - Chèn hình nền (Background).
        - Đè khung viền hoa văn PNG có kênh suốt (Alpha Transparency Overlay).
        - Vẽ chữ nghệ thuật tiếng Việt đa dòng, tự căn giữa, an toàn mép cắt.
        - Chèn Logo giữ nguyên tỷ lệ gốc và hỗ trợ các vị trí đặt nhanh.
        - Nhân bản đôi 2 dải cho máy in DNP DS-RX1HS tự động cắt 2 inch.
        """
        if not photos:
            raise ValueError("Không có ảnh đầu vào để ghép khung.")

        event_info = event_info or {}
        w, h = template.canvas_size[0], template.canvas_size[1]
        container_w = 600 if (template.is_dual_strip and w == 1200) else w

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

            fit_mode = getattr(slot, 'fit_mode', 'cover')
            position_mode = getattr(slot, 'position_mode', 'center')
            zoom = getattr(slot, 'zoom', 1.0)
            crop_offset_x = getattr(slot, 'crop_offset_x', 0.0)
            crop_offset_y = getattr(slot, 'crop_offset_y', 0.0)

            # Cắt và thu phóng ảnh chuẩn tỷ lệ ô chứa với thuật toán Auto Photo Fitting
            slot_photo = ImageProcessor.crop_and_resize(
                img=raw_photo,
                target_width=slot.w,
                target_height=slot.h,
                fit_mode=fit_mode,
                position_mode=position_mode,
                zoom=zoom,
                crop_offset_x=crop_offset_x,
                crop_offset_y=crop_offset_y,
                bg_color=template.bg_color or "#FFFFFF"
            )

            # Xoay ảnh theo thuộc tính rotation nếu có (90, 180, 270 hoặc góc bất kỳ)
            if getattr(slot, 'rotation', 0) != 0:
                rot = slot.rotation % 360
                slot_photo = slot_photo.rotate(-rot, expand=True, resample=Image.Resampling.BICUBIC)
                slot_photo = ImageProcessor.crop_and_resize(
                    slot_photo, slot.w, slot.h, fit_mode=fit_mode, position_mode=position_mode
                )

            # Lật ảnh theo trục ngang nếu có
            if getattr(slot, 'is_flipped_h', False):
                from PIL import ImageOps
                slot_photo = ImageOps.mirror(slot_photo)


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
            if not getattr(txt, 'is_visible', True):
                continue
            content = txt.text or ""
            # Thay thế biến động
            content = content.replace("{event_name}", event_info.get("name", "1998 TEAM"))
            content = content.replace("{date}", event_info.get("date", today_str))
            content = content.replace("{location}", event_info.get("location", ""))

            is_bold = getattr(txt, 'is_bold', False)
            is_italic = getattr(txt, 'is_italic', False)
            font = get_windows_font(txt.font_name, txt.font_size, is_bold=is_bold, is_italic=is_italic)

            FrameDesigner._render_text_layer(
                draw=draw,
                txt=txt,
                content=content,
                font=font,
                container_w=container_w,
                canvas_h=h,
                is_dual_strip=template.is_dual_strip and w == 1200
            )

        # 6. Chèn Logo layers nếu có
        for logo in template.logo_layers:
            if logo.image_path and os.path.exists(logo.image_path):
                try:
                    FrameDesigner._render_logo_layer(
                        canvas=canvas,
                        logo=logo,
                        container_w=container_w,
                        canvas_h=h,
                        is_dual_strip=template.is_dual_strip and w == 1200
                    )
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
    def _wrap_text_lines(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        max_width: int
    ) -> List[str]:
        """Tự động xuống dòng khi nội dung chữ vượt quá chiều rộng cho phép."""
        raw_lines = text.split("\n")
        wrapped_lines = []

        for raw_line in raw_lines:
            raw_line = raw_line.strip()
            if not raw_line:
                wrapped_lines.append("")
                continue

            words = raw_line.split(" ")
            curr_line = ""
            for word in words:
                test_line = f"{curr_line} {word}".strip() if curr_line else word
                bbox = draw.textbbox((0, 0), test_line, font=font)
                line_w = bbox[2] - bbox[0]
                if line_w <= max_width or not curr_line:
                    curr_line = test_line
                else:
                    wrapped_lines.append(curr_line)
                    curr_line = word
            if curr_line:
                wrapped_lines.append(curr_line)

        return wrapped_lines if wrapped_lines else [""]

    @staticmethod
    def get_text_layout_info(
        draw: ImageDraw.ImageDraw,
        txt: TextLayer,
        content: str,
        font: ImageFont.ImageFont,
        container_w: int,
        canvas_h: int
    ) -> Tuple[List[str], int, int, int, int]:
        """
        Tính toán chi tiết các dòng chữ và hộp bao bounding box chuẩn xác 300 DPI.
        Trả về: (lines, box_x, box_y, box_w, box_h)
        Không bao giờ tự ý đưa chữ về giữa nếu người dùng đã đặt hoặc kéo sang tọa độ x, y!
        """
        safe_margin = getattr(txt, 'safe_margin', 40)
        max_w = getattr(txt, 'max_width', None) or (container_w - 2 * safe_margin)
        max_w = max(100, max_w)

        lines = FrameDesigner._wrap_text_lines(draw, content, font, max_w)
        line_height = int(txt.font_size * 1.35)
        total_text_h = max(line_height, len(lines) * line_height)

        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
        max_line_w = max(line_widths) if line_widths else 100

        # Xác định vị trí Y
        pos_mode = getattr(txt, 'position_mode', 'custom')
        if pos_mode == "top":
            base_y = safe_margin
        elif pos_mode == "middle":
            base_y = max(safe_margin, (canvas_h - total_text_h) // 2)
        elif pos_mode == "bottom":
            base_y = max(safe_margin, canvas_h - safe_margin - total_text_h)
        else:
            base_y = getattr(txt, 'y', canvas_h - safe_margin - total_text_h)
            if base_y is None or base_y <= 0:
                base_y = canvas_h - safe_margin - total_text_h

        # Xác định vị trí X
        align = getattr(txt, 'alignment', 'center')
        if getattr(txt, 'x', None) is not None and (pos_mode == "custom" or txt.x > 0):
            base_x = txt.x
            if align == "center":
                box_x = base_x - max_line_w // 2
            elif align == "right":
                box_x = base_x - max_line_w
            else:
                box_x = base_x
        else:
            if align == "center":
                box_x = (container_w - max_line_w) // 2
            elif align == "right":
                box_x = container_w - safe_margin - max_line_w
            else:
                box_x = safe_margin

        box_y = base_y
        box_w = max_line_w
        box_h = total_text_h

        return lines, box_x, box_y, box_w, box_h

    @staticmethod
    def _render_text_layer(
        draw: ImageDraw.ImageDraw,
        txt: TextLayer,
        content: str,
        font: ImageFont.ImageFont,
        container_w: int,
        canvas_h: int,
        is_dual_strip: bool
    ):
        """Vẽ lớp chữ văn bản với đa dòng, căn lề, định vị tự do và bảo vệ vùng an toàn."""
        lines, box_x, box_y, box_w, box_h = FrameDesigner.get_text_layout_info(
            draw=draw, txt=txt, content=content, font=font, container_w=container_w, canvas_h=canvas_h
        )
        line_height = int(txt.font_size * 1.35)
        align = getattr(txt, 'alignment', 'center')

        for i, line in enumerate(lines):
            curr_y = box_y + i * line_height
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]

            if align == "center":
                draw_x = box_x + (box_w - line_w) // 2
            elif align == "right":
                draw_x = box_x + (box_w - line_w)
            else:
                draw_x = box_x

            # Vẽ trên dải trái
            draw.text((draw_x, curr_y), line, font=font, fill=txt.font_color)

            # Nhân đôi sang dải phải nếu là dual strip
            if is_dual_strip:
                draw.text((draw_x + 600, curr_y), line, font=font, fill=txt.font_color)

    @staticmethod
    def _render_logo_layer(
        canvas: Image.Image,
        logo: LogoLayer,
        container_w: int,
        canvas_h: int,
        is_dual_strip: bool
    ):
        """Chèn logo giữ nguyên tỷ lệ gốc và hỗ trợ các vị trí đặt nhanh."""
        logo_img = Image.open(logo.image_path).convert("RGBA")
        orig_w, orig_h = logo_img.size

        # Cập nhật kích thước gốc nếu chưa lưu
        if not getattr(logo, 'original_w', 0) or not getattr(logo, 'original_h', 0):
            logo.original_w = orig_w
            logo.original_h = orig_h

        # Tính kích thước đích giữ nguyên tỷ lệ
        scale = getattr(logo, 'scale', 1.0)
        if scale <= 0:
            scale = 1.0

        if logo.original_w > 0 and logo.original_h > 0:
            target_w = max(10, int(logo.original_w * scale))
            target_h = max(10, int(logo.original_h * scale))
        else:
            target_w = max(10, logo.w)
            target_h = max(10, logo.h)

        logo_resized = logo_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # Xử lý độ mờ (Opacity)
        opacity = getattr(logo, 'opacity', 1.0)
        if opacity < 1.0:
            r, g, b, a = logo_resized.split()
            a = a.point(lambda p: int(p * max(0.0, min(1.0, opacity))))
            logo_resized = Image.merge("RGBA", (r, g, b, a))

        # Tính tọa độ đặt theo position_mode
        pos_mode = getattr(logo, 'position_mode', 'custom')
        margin = 40

        if pos_mode == "top_left":
            lx = margin
            ly = margin
        elif pos_mode == "top_right":
            lx = max(0, container_w - target_w - margin)
            ly = margin
        elif pos_mode == "center":
            lx = max(0, (container_w - target_w) // 2)
            ly = max(0, (canvas_h - target_h) // 2)
        elif pos_mode == "bottom_left":
            lx = margin
            ly = max(0, canvas_h - target_h - margin)
        elif pos_mode == "bottom_right":
            lx = max(0, container_w - target_w - margin)
            ly = max(0, canvas_h - target_h - margin)
        else:
            lx = logo.x
            ly = logo.y

        # Dán lên canvas
        canvas.paste(logo_resized, (lx, ly), logo_resized)
        if is_dual_strip:
            canvas.paste(logo_resized, (lx + 600, ly), logo_resized)

    @staticmethod
    def render_preview(
        template: FrameTemplate,
        sample_photos: Optional[List[Image.Image]] = None,
        max_height: int = 700
    ) -> Image.Image:
        """
        Tạo ảnh xem trước (preview) bằng chính engine render_composite.
        Đảm bảo 100% WYSIWYG: những gì nhìn thấy là những gì được xuất và in ra.
        """
        if not sample_photos:
            sample_portrait_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "Assets", "Branding", "sample_slot_portrait.jpg"
            ))
            if os.path.exists(sample_portrait_path):
                try:
                    loaded_sample = Image.open(sample_portrait_path).convert("RGB")
                    sample_photos = [loaded_sample] * max(len(template.slots), 1)
                except Exception:
                    sample_photos = []

            if not sample_photos:
                sample_photos = []
                colors = ["#1E293B", "#0F172A", "#334155", "#475569"]
                for i in range(4):
                    sample_img = Image.new("RGB", (600, 450), color=colors[i % len(colors)])
                    d = ImageDraw.Draw(sample_img)
                    f = get_windows_font("arial.ttf", 52, is_bold=True)
                    d.text((200, 190), f"Ảnh Chụp #{i+1}", font=f, fill="#D4AF37")
                    sample_photos.append(sample_img)

        if not template.slots:
            dummy = Image.new("RGB", (400, 400), (240, 240, 240))
            full_render = FrameDesigner.render_composite([dummy], template)
        else:
            full_render = FrameDesigner.render_composite(sample_photos, template)

        scale = max_height / float(full_render.height)
        new_w = max(int(full_render.width * scale), 1)
        return full_render.resize((new_w, max_height), Image.Resampling.LANCZOS)

    @staticmethod
    def generate_thumbnail(
        template: FrameTemplate,
        max_width: int = 140,
        max_height: int = 180
    ) -> Image.Image:
        """Tạo ảnh thumbnail xem trước thực tế của mẫu khung dựa trên chính tệp khung."""
        preview = FrameDesigner.render_preview(template, max_height=max_height)
        preview.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        return preview

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
                warnings.append(f"Ô ảnh #{i+1} nằm sát mép cắt máy in ({bleed}px).")

        for txt in template.text_layers:
            pos_mode = getattr(txt, 'position_mode', 'bottom')
            if pos_mode == 'custom' and (txt.y < safe or txt.y > (h - safe)):
                warnings.append(f"Lớp chữ '{txt.text}' nằm quá gần mép trên/dưới (< {safe}px).")

        return warnings
