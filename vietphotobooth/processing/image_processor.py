"""
VietPhotoBooth Image Processor
High-performance image handling: aspect ratio preservation, center cropping, color filters, EXIF auto-rotation.
"""

from typing import Tuple, Optional
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class ImageProcessor:
    @staticmethod
    def fix_exif_orientation(img: Image.Image) -> Image.Image:
        """Tự động xoay ảnh theo cảm biến EXIF Orientation mà không làm méo."""
        try:
            return ImageOps.exif_transpose(img)
        except Exception:
            return img

    @staticmethod
    def crop_and_resize(img: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """
        Cắt và thu phóng ảnh chuẩn xác theo kích thước mục tiêu với trọng tâm trung tâm (Center Crop).
        Đảm bảo không bị kéo dãn hoặc méo tỷ lệ ảnh gốc (Aspect-Ratio Safe).
        """
        img = ImageProcessor.fix_exif_orientation(img)
        orig_w, orig_h = img.size
        target_ratio = target_width / target_height
        orig_ratio = orig_w / orig_h

        if orig_ratio > target_ratio:
            # Ảnh gốc bè hơn -> cắt bớt hai bên
            new_w = int(orig_h * target_ratio)
            left = (orig_w - new_w) // 2
            top = 0
            right = left + new_w
            bottom = orig_h
        else:
            # Ảnh gốc cao hơn -> cắt bớt trên dưới
            new_h = int(orig_w / target_ratio)
            top = (orig_h - new_h) // 2
            left = 0
            right = orig_w
            bottom = top + new_h

        cropped = img.crop((left, top, right, bottom))
        # Dùng bộ lọc Lanczos chất lượng cao nhất cho in ấn
        return cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)

    @staticmethod
    def apply_filter(img: Image.Image, filter_name: str = "none") -> Image.Image:
        """Áp dụng bộ lọc màu nghệ thuật Photobooth."""
        f = filter_name.lower()
        if f == "none" or not f:
            return img

        if f in ("bw", "grayscale", "trang_den"):
            return ImageOps.grayscale(img).convert("RGB")
        elif f in ("vintage", "retro"):
            # Tăng độ ấm, hơi ngả vàng/sepia
            gray = ImageOps.grayscale(img)
            sepia = ImageOps.colorize(gray, "#2e1a05", "#fae4b8")
            return Image.blend(img, sepia, 0.45)
        elif f in ("vibrant", "tuoi_sang"):
            enhancer_col = ImageEnhance.Color(img)
            img = enhancer_col.enhance(1.3)
            enhancer_con = ImageEnhance.Contrast(img)
            return enhancer_con.enhance(1.1)
        elif f in ("warm", "am_ap"):
            r, g, b = img.split()
            r = ImageEnhance.Brightness(r).enhance(1.08)
            b = ImageEnhance.Brightness(b).enhance(0.92)
            return Image.merge("RGB", (r, g, b))
        return img

    @staticmethod
    def make_thumbnail(img: Image.Image, max_size: Tuple[int, int] = (400, 400)) -> Image.Image:
        """Tạo ảnh thumbnail xem nhanh."""
        thumb = img.copy()
        thumb.thumbnail(max_size, Image.Resampling.LANCZOS)
        return thumb
