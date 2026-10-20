"""
VietPhotoBooth 3D LUT Parser & Processor (.cube format)
Provides high-performance 3D LUT parsing, trilinear interpolation via NumPy, and LUT export.
"""

import os
from typing import Optional, Tuple
import numpy as np
from PIL import Image
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class CubeLUTParser:
    """
    Parser and applicator for Adobe / DaVinci Resolve .cube 3D Look-Up Tables.
    Supports 3D LUTs with trilinear interpolation and intensity blending.
    """

    def __init__(self, filepath: Optional[str] = None):
        self.size: int = 0
        self.domain_min: np.ndarray = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.domain_max: np.ndarray = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.table: Optional[np.ndarray] = None  # Shape: (size, size, size, 3) where indexing is [r, g, b]
        self.title: str = ""
        self.filepath: Optional[str] = filepath

        if filepath and os.path.exists(filepath):
            self.load(filepath)

    def load(self, filepath: str) -> bool:
        """Đọc và phân tích cú pháp file .cube chuẩn."""
        try:
            self.filepath = filepath
            data_points = []
            size = None

            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split()
                    cmd = parts[0].upper()

                    if cmd == "TITLE":
                        self.title = " ".join(parts[1:]).strip('"\'')
                    elif cmd == "LUT_3D_SIZE":
                        size = int(parts[1])
                        self.size = size
                    elif cmd == "DOMAIN_MIN":
                        self.domain_min = np.array([float(parts[1]), float(parts[2]), float(parts[3])], dtype=np.float32)
                    elif cmd == "DOMAIN_MAX":
                        self.domain_max = np.array([float(parts[1]), float(parts[2]), float(parts[3])], dtype=np.float32)
                    elif cmd.startswith("LUT_1D"):
                        raise ValueError("Chỉ hỗ trợ LUT 3D (.cube 3D), không hỗ trợ định dạng 1D.")
                    else:
                        # Dữ liệu RGB float
                        try:
                            if len(parts) >= 3:
                                r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
                                data_points.append((r, g, b))
                        except ValueError:
                            continue

            if not size or len(data_points) != (size * size * size):
                logger.error(f"File .cube không hợp lệ: mong đợi {size}**3 = {size**3 if size else 0} điểm, tìm thấy {len(data_points)}")
                return False

            # Định dạng .cube chuẩn: Red thay đổi nhanh nhất, kế tiếp là Green, rồi đến Blue:
            # table[b, g, r] hoặc table[r, g, b].
            # Chúng ta định hình lại thành (size, size, size, 3) theo thứ tự (r, g, b)
            raw_array = np.array(data_points, dtype=np.float32)
            # Dữ liệu tuần tự theo vòng lặp: for b in 0..N-1: for g in 0..N-1: for r in 0..N-1
            # reshape: (N_b, N_g, N_r, 3)
            table_bgr = raw_array.reshape((size, size, size, 3))
            # Chuyển đổi trục để có indexing table[r, g, b, :]
            self.table = np.transpose(table_bgr, (2, 1, 0, 3))
            logger.info(f"Đã nạp thành công 3D LUT: '{self.title or os.path.basename(filepath)}' kích thước {size}x{size}x{size}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi đọc file 3D LUT {filepath}: {e}")
            return False

    def apply(self, img_np: np.ndarray, intensity: float = 1.0) -> np.ndarray:
        """
        Áp dụng 3D LUT lên ảnh dạng numpy array (uint8 RGB, kích thước H x W x 3).
        Sử dụng nội suy tam tuyến (trilinear interpolation).
        intensity: tỉ lệ pha trộn hiệu ứng từ 0.0 (nguyên bản) đến 1.0 (100% LUT).
        """
        if self.table is None or self.size <= 0 or intensity <= 0.0:
            return img_np

        intensity = max(0.0, min(1.0, float(intensity)))
        orig_dtype = img_np.dtype
        orig_img = img_np

        # Chuẩn hóa về miền [0.0, 1.0]
        if orig_dtype == np.uint8:
            norm_rgb = img_np.astype(np.float32) / 255.0
        else:
            norm_rgb = img_np.astype(np.float32)

        # Chuẩn hóa theo domain_min và domain_max
        domain_range = np.maximum(self.domain_max - self.domain_min, 1e-6)
        clamped_rgb = np.clip((norm_rgb - self.domain_min) / domain_range, 0.0, 1.0)

        # Tính toán tọa độ lưới
        n = self.size - 1
        coords = clamped_rgb * n

        r = coords[..., 0]
        g = coords[..., 1]
        b = coords[..., 2]

        r0 = np.floor(r).astype(np.int32)
        r1 = np.minimum(r0 + 1, n)
        dr = (r - r0)[..., np.newaxis]

        g0 = np.floor(g).astype(np.int32)
        g1 = np.minimum(g0 + 1, n)
        dg = (g - g0)[..., np.newaxis]

        b0 = np.floor(b).astype(np.int32)
        b1 = np.minimum(b0 + 1, n)
        db = (b - b0)[..., np.newaxis]

        # 8 góc của hình lập phương nội suy
        # c000 = table[r0, g0, b0]
        c000 = self.table[r0, g0, b0]
        c100 = self.table[r1, g0, b0]
        c010 = self.table[r0, g1, b0]
        c110 = self.table[r1, g1, b0]
        c001 = self.table[r0, g0, b1]
        c101 = self.table[r1, g0, b1]
        c011 = self.table[r0, g1, b1]
        c111 = self.table[r1, g1, b1]

        # Trilinear interpolation
        c00 = c000 * (1.0 - dr) + c100 * dr
        c10 = c010 * (1.0 - dr) + c110 * dr
        c01 = c001 * (1.0 - dr) + c101 * dr
        c11 = c011 * (1.0 - dr) + c111 * dr

        c0 = c00 * (1.0 - dg) + c10 * dg
        c1 = c01 * (1.0 - dg) + c11 * dg

        out_rgb = c0 * (1.0 - db) + c1 * db

        # Giới hạn về [0, 1] và đổi lại uint8
        out_rgb = np.clip(out_rgb * 255.0, 0.0, 255.0).astype(np.uint8)

        if intensity < 1.0:
            # Pha trộn với ảnh gốc theo intensity
            blended = (orig_img.astype(np.float32) * (1.0 - intensity) + out_rgb.astype(np.float32) * intensity)
            return np.clip(blended, 0.0, 255.0).astype(np.uint8)

        return out_rgb

    def apply_pil(self, img: Image.Image, intensity: float = 1.0) -> Image.Image:
        """Áp dụng 3D LUT trực tiếp lên ảnh PIL Image."""
        if self.table is None or intensity <= 0.0:
            return img
        rgb_img = img.convert("RGB")
        img_np = np.array(rgb_img)
        res_np = self.apply(img_np, intensity)
        return Image.fromarray(res_np, "RGB")

    @staticmethod
    def create_cube_file(filepath: str, title: str, size: int, generator_func) -> bool:
        """
        Tạo file .cube từ một hàm chuyển đổi màu f(r, g, b) -> (r', g', b').
        Rất hữu ích để tạo các preset LUT mẫu chuẩn điện ảnh.
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f'# VietPhotoBooth 3D LUT\n')
                f.write(f'TITLE "{title}"\n')
                f.write(f'LUT_3D_SIZE {size}\n')
                f.write(f'DOMAIN_MIN 0.0 0.0 0.0\n')
                f.write(f'DOMAIN_MAX 1.0 1.0 1.0\n\n')

                for b in range(size):
                    for g in range(size):
                        for r in range(size):
                            r_in = r / (size - 1)
                            g_in = g / (size - 1)
                            b_in = b / (size - 1)
                            r_out, g_out, b_out = generator_func(r_in, g_in, b_in)
                            r_out = max(0.0, min(1.0, float(r_out)))
                            g_out = max(0.0, min(1.0, float(g_out)))
                            b_out = max(0.0, min(1.0, float(b_out)))
                            f.write(f"{r_out:.6f} {g_out:.6f} {b_out:.6f}\n")
            return True
        except Exception as e:
            logger.error(f"Lỗi tạo file .cube {filepath}: {e}")
            return False
