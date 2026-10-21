"""
VietPhotoBooth Image Processor
High-performance image handling: aspect ratio preservation, center cropping, color filters, EXIF auto-rotation.
"""

from typing import Tuple, Optional
import sys
import os
import cv2
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from vietphotobooth.core.logger import get_logger

logger = get_logger()

def _find_yunet_model() -> str:
    """Tìm đường dẫn tệp mô hình nhận diện khuôn mặt YuNet trong môi trường phát triển và đóng gói."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "Assets", "Models", "face_detection_yunet.onnx"))
    candidates.extend([
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Models", "face_detection_yunet.onnx")),
        os.path.abspath(os.path.join(os.getcwd(), "Assets", "Models", "face_detection_yunet.onnx")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Assets", "Models", "face_detection_yunet.onnx")),
    ])
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]

# Đường dẫn mô hình nhận diện khuôn mặt YuNet
YUNET_MODEL_PATH = _find_yunet_model()

_yunet_detector = None


def get_face_detector():
    """Khởi tạo bộ nhận diện khuôn mặt YuNet hiệu năng cao."""
    global _yunet_detector
    if _yunet_detector is None and os.path.exists(YUNET_MODEL_PATH):
        try:
            _yunet_detector = cv2.FaceDetectorYN_create(YUNET_MODEL_PATH, "", (320, 320))
        except Exception as e:
            logger.debug(f"Không thể khởi tạo YuNet detector: {e}")
            _yunet_detector = None
    return _yunet_detector


class ImageProcessor:
    @staticmethod
    def fix_exif_orientation(img: Image.Image) -> Image.Image:
        """Tự động xoay ảnh theo cảm biến EXIF Orientation mà không làm méo."""
        try:
            return ImageOps.exif_transpose(img)
        except Exception:
            return img

    @staticmethod
    def detect_face_center(img: Image.Image) -> Optional[Tuple[int, int]]:
        """
        Phát hiện tâm khuôn mặt chính trong ảnh bằng YuNet.
        Trả về tọa độ (center_x, center_y) trên ảnh gốc, hoặc None nếu không thấy mặt.
        """
        detector = get_face_detector()
        if not detector:
            return None

        try:
            w, h = img.size
            # Thu nhỏ ảnh về kích thước tối đa 320px để phát hiện siêu nhanh (< 15ms)
            scale = 320.0 / max(w, h)
            dw, dh = max(int(w * scale), 1), max(int(h * scale), 1)
            detector.setInputSize((dw, dh))

            np_rgb = np.array(img.convert("RGB"))
            np_bgr = cv2.cvtColor(np_rgb, cv2.COLOR_RGB2BGR)
            resized_bgr = cv2.resize(np_bgr, (dw, dh))

            _, faces = detector.detect(resized_bgr)
            if faces is not None and len(faces) > 0:
                # Chọn khuôn mặt lớn nhất (diện tích w*h lớn nhất)
                best_face = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = best_face[:4]
                # Tọa độ tâm trên ảnh gốc, nhích nhẹ lên phía mắt/trán để ảnh chân dung đẹp tự nhiên
                orig_cx = int((fx + fw / 2.0) / scale)
                orig_cy = int((fy + fh * 0.42) / scale)
                return (orig_cx, orig_cy)
        except Exception as e:
            logger.debug(f"Lỗi nhận diện khuôn mặt: {e}")
        return None

    @staticmethod
    def crop_and_resize(
        img: Image.Image,
        target_width: int,
        target_height: int,
        fit_mode: str = "cover",
        position_mode: str = "center",
        zoom: float = 1.0,
        crop_offset_x: float = 0.0,
        crop_offset_y: float = 0.0,
        bg_color: str = "#FFFFFF"
    ) -> Image.Image:
        """
        Tự động căn chỉnh ảnh thông minh vào ô ảnh mục tiêu (Auto Photo Fitting).
        Hỗ trợ:
        - fit_mode = "cover" (Lấp đầy khung / Fill): lấp kín 100% ô, không viền trắng, không méo tỷ lệ.
        - fit_mode = "contain" (Hiển thị toàn ảnh / Fit): trọn vẹn toàn bộ ảnh gốc, giữ nguyên tỷ lệ.
        - position_mode = "center": căn giữa tự động.
        - position_mode = "face": ưu tiên căn theo tâm khuôn mặt người.
        - zoom: thu phóng tỷ lệ (1.0 = 100%, 1.25 = 125%,...).
        - crop_offset_x, crop_offset_y: dịch chuyển vùng cắt (panning / drag).
        """
        img = ImageProcessor.fix_exif_orientation(img)
        orig_w, orig_h = img.size
        target_width = max(1, target_width)
        target_height = max(1, target_height)
        zoom = max(0.5, min(float(zoom), 3.0))

        # -------------------------------------------------------------
        # 1. CHẾ ĐỘ HIỂN THỊ TOÀN ẢNH (FIT / CONTAIN)
        # -------------------------------------------------------------
        if fit_mode == "contain":
            base_scale = min(target_width / float(orig_w), target_height / float(orig_h))
            scale = base_scale * zoom
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))

            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Tạo khung nền đệm
            if img.mode == "RGBA":
                container = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
            else:
                container = Image.new("RGBA", (target_width, target_height), bg_color or "#FFFFFF")

            # Tính vị trí dán căn giữa kèm offset
            dx = int(crop_offset_x * (target_width / 2.0)) if abs(crop_offset_x) <= 1.0 else int(crop_offset_x)
            dy = int(crop_offset_y * (target_height / 2.0)) if abs(crop_offset_y) <= 1.0 else int(crop_offset_y)

            paste_x = (target_width - new_w) // 2 + dx
            paste_y = (target_height - new_h) // 2 + dy

            if resized.mode == "RGBA":
                container.paste(resized, (paste_x, paste_y), resized)
            else:
                container.paste(resized, (paste_x, paste_y))
            return container

        # -------------------------------------------------------------
        # 2. CHẾ ĐỘ LẤP ĐẦY KHUNG (FILL / COVER) - MẶC ĐỊNH
        # -------------------------------------------------------------
        target_ratio = target_width / float(target_height)
        orig_ratio = orig_w / float(orig_h)

        # Tính kích thước cửa sổ cắt chuẩn tỷ lệ ô ảnh
        if orig_ratio > target_ratio:
            base_crop_h = orig_h
            base_crop_w = int(orig_h * target_ratio)
        else:
            base_crop_w = orig_w
            base_crop_h = int(orig_w / target_ratio)

        # Áp dụng thu phóng (zoom càng lớn thì cửa sổ cắt càng nhỏ để phóng to)
        crop_w = max(10, min(int(base_crop_w / zoom), orig_w))
        crop_h = max(10, min(int(base_crop_h / zoom), orig_h))

        # Xác định tâm điểm cắt (Center point)
        center_x = orig_w // 2
        center_y = orig_h // 2

        # Nếu chọn ưu tiên khuôn mặt
        if position_mode == "face":
            detected_center = ImageProcessor.detect_face_center(img)
            if detected_center:
                center_x, center_y = detected_center

        # Dịch chuyển tâm theo offset người dùng kéo thả
        if abs(crop_offset_x) <= 1.0:
            max_pan_x = (orig_w - crop_w) / 2.0
            center_x += int(crop_offset_x * max_pan_x)
        else:
            center_x += int(crop_offset_x)

        if abs(crop_offset_y) <= 1.0:
            max_pan_y = (orig_h - crop_h) / 2.0
            center_y += int(crop_offset_y * max_pan_y)
        else:
            center_y += int(crop_offset_y)

        # Giới hạn vùng cắt nghiêm ngặt trong biên ảnh gốc (không tạo viền trống)
        left = max(0, min(int(center_x - crop_w / 2.0), orig_w - crop_w))
        top = max(0, min(int(center_y - crop_h / 2.0), orig_h - crop_h))
        right = left + crop_w
        bottom = top + crop_h

        cropped = img.crop((left, top, right, bottom))
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
