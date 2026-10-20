"""
VietPhotoBooth Extensible Filter & LUT Engine
Provides 12 built-in photo presets, a 14-parameter parametric adjustment pipeline,
3D LUT application, soft skin smoothing, and non-destructive image processing.
"""

import os
import json
import math
import copy
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import cv2
from PIL import Image, ImageEnhance, ImageOps

from vietphotobooth.core.logger import get_logger
from vietphotobooth.filters.lut_parser import CubeLUTParser

logger = get_logger()

from vietphotobooth.core.config import get_user_data_dir

# Thư mục lưu trữ filter preset của người dùng (nằm ngoài thư mục cài đặt để bảo toàn khi cập nhật)
DEFAULT_USER_FILTERS_DIR = os.path.join(get_user_data_dir(), "Filters")
DEFAULT_USER_LUTS_DIR = os.path.join(get_user_data_dir(), "LUTs")
DEFAULT_BUILTIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Filters", "BuiltIn"))


@dataclass
class FilterPreset:
    """Mô hình dữ liệu Preset bộ lọc có định danh, tên tiếng Việt và các tham số xử lý."""
    id: str
    name: str
    category: str = "Tùy Chỉnh"
    description: str = ""
    is_builtin: bool = False
    version: str = "1.0"

    # 14 Tham số chỉnh sửa ảnh chuẩn mực
    exposure: float = 0.0        # -100 đến 100 (Bù sáng EV)
    brightness: float = 0.0      # -100 đến 100 (Độ sáng)
    contrast: float = 0.0        # -100 đến 100 (Độ tương phản)
    saturation: float = 0.0      # -100 đến 100 (Độ bão hòa màu)
    temperature: float = 0.0     # -100 đến 100 (Nhiệt độ màu: xanh lạnh < 0 < vàng ấm)
    tint: float = 0.0            # -100 đến 100 (Sắc độ: xanh lá < 0 < hồng tím)
    highlights: float = 0.0      # -100 đến 100 (Vùng sáng)
    shadows: float = 0.0         # -100 đến 100 (Vùng tối)
    gamma: float = 1.0           # 0.2 đến 3.0 (Gamma)
    sharpness: float = 0.0       # 0 đến 100 (Độ sắc nét)
    fade: float = 0.0            # 0 đến 100 (Hiệu ứng mờ phim / nâng đen)
    vignette: float = 0.0        # 0 đến 100 (Tối 4 góc)
    grayscale: bool = False      # True / False (Chuyển trắng đen)
    sepia: float = 0.0           # 0 đến 100 (Sắc nâu hoài niệm)

    # Làm mịn da (Skin smoothing) & 3D LUT
    soft_skin: float = 0.0       # 0 đến 100 (Làm mịn da giữ khối)
    lut_filename: Optional[str] = None  # Tên file .cube trong thư mục LUTs
    lut_intensity: float = 1.0   # 0.0 đến 1.0 (Cường độ áp dụng LUT)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterPreset":
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def save_to_json(self, filepath: str) -> bool:
        """Lưu preset ra file JSON."""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Lỗi khi lưu preset {self.id} vào {filepath}: {e}")
            return False

    @classmethod
    def load_from_json(cls, filepath: str) -> Optional["FilterPreset"]:
        """Nạp preset từ file JSON."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            logger.error(f"Lỗi khi đọc preset từ {filepath}: {e}")
            return None


class FilterEngine:
    """
    Bộ máy xử lý bộ lọc ảnh chuyên nghiệp cho 1998 TEAM — Photobooth.
    Khởi tạo thư viện bộ lọc sạch, cho phép người dùng tự do thêm/sửa/nhập/xuất bộ lọc.
    """

    def __init__(self, builtin_dir: str = DEFAULT_BUILTIN_DIR, custom_dir: str = DEFAULT_USER_FILTERS_DIR, luts_dir: str = DEFAULT_USER_LUTS_DIR):
        self.builtin_dir = os.path.abspath(builtin_dir)
        self.custom_dir = os.path.abspath(custom_dir)
        self.luts_dir = os.path.abspath(luts_dir)

        os.makedirs(self.builtin_dir, exist_ok=True)
        os.makedirs(self.custom_dir, exist_ok=True)
        os.makedirs(self.luts_dir, exist_ok=True)

        self._presets: Dict[str, FilterPreset] = {}
        self._lut_cache: Dict[str, CubeLUTParser] = {}

        # Khởi tạo thư viện sạch, không tự sinh preset giả
        self.reload_all_presets()

    # -------------------------------------------------------------
    # 12 PRESET MẶC ĐỊNH CHUẨN PHOTOBOOTH THƯƠNG MẠI
    # -------------------------------------------------------------
    def _create_default_presets(self) -> List[FilterPreset]:
        return [
            FilterPreset(
                id="natural",
                name="Tự Nhiên",
                category="Chung",
                description="Màu sắc trung thực, trong trẻo, phù hợp với mọi điều kiện ánh sáng.",
                is_builtin=True,
                exposure=0.0,
                brightness=2.0,
                contrast=5.0,
                saturation=5.0,
                sharpness=10.0,
                soft_skin=15.0
            ),
            FilterPreset(
                id="warm",
                name="Ấm Áp",
                category="Tiệc tùng",
                description="Tông màu vàng ấm áp, tạo cảm giác thân mật, lãng mạn cho tiệc tối.",
                is_builtin=True,
                temperature=28.0,
                tint=6.0,
                brightness=4.0,
                contrast=8.0,
                saturation=12.0,
                highlights=5.0,
                shadows=8.0,
                soft_skin=20.0
            ),
            FilterPreset(
                id="cool",
                name="Tươi Mát",
                category="Chung",
                description="Tông xanh mát mẻ, hiện đại, thích hợp cho sự kiện trẻ trung năng động.",
                is_builtin=True,
                temperature=-25.0,
                tint=-5.0,
                brightness=5.0,
                contrast=12.0,
                saturation=10.0,
                highlights=10.0,
                sharpness=15.0
            ),
            FilterPreset(
                id="vintage",
                name="Cổ Điển",
                category="Cổ điển",
                description="Phong cách hoài niệm thập niên 70, tông ấm nhẹ và tối 4 góc dịu dàng.",
                is_builtin=True,
                temperature=18.0,
                sepia=22.0,
                contrast=10.0,
                fade=25.0,
                vignette=30.0,
                highlights=-10.0,
                shadows=15.0
            ),
            FilterPreset(
                id="retro",
                name="Hoài Cổ 80s",
                category="Cổ điển",
                description="Chất ảnh máy film cổ điển với vùng đen nâng sáng và tông màu đậm đà.",
                is_builtin=True,
                temperature=15.0,
                tint=12.0,
                fade=35.0,
                contrast=18.0,
                saturation=-8.0,
                vignette=40.0,
                sharpness=5.0
            ),
            FilterPreset(
                id="bw_art",
                name="Trắng Đen Nghệ Thuật",
                category="Nghệ thuật",
                description="Ảnh đơn sắc độ tương phản cao, tôn vinh đường nét và biểu cảm khuôn mặt.",
                is_builtin=True,
                grayscale=True,
                contrast=30.0,
                brightness=2.0,
                sharpness=25.0,
                vignette=20.0,
                highlights=15.0,
                shadows=-15.0
            ),
            FilterPreset(
                id="sepia_nostalgia",
                name="Nâu Hoài Niệm",
                category="Cổ điển",
                description="Sắc nâu sepia cổ kính truyền thống, phong cách album kỷ niệm xưa.",
                is_builtin=True,
                grayscale=True,
                sepia=80.0,
                contrast=15.0,
                fade=15.0,
                vignette=35.0
            ),
            FilterPreset(
                id="soft_skin",
                name="Mịn Da Rạng Rỡ",
                category="Chân dung",
                description="Làm mịn và sáng da tự nhiên, xóa mờ khuyết điểm mà vẫn giữ nét đôi mắt.",
                is_builtin=True,
                soft_skin=55.0,
                brightness=8.0,
                saturation=6.0,
                highlights=12.0,
                shadows=5.0,
                contrast=4.0
            ),
            FilterPreset(
                id="bright_pop",
                name="Tươi Sáng Rực Rỡ",
                category="Tiệc tùng",
                description="Độ sáng và bão hòa rực rỡ, thích hợp cho tiệc sinh nhật thiếu nhi và sự kiện ngoài trời.",
                is_builtin=True,
                exposure=12.0,
                brightness=10.0,
                contrast=16.0,
                saturation=25.0,
                highlights=15.0,
                sharpness=15.0
            ),
            FilterPreset(
                id="high_contrast",
                name="Tương Phản Ấn Tượng",
                category="Nghệ thuật",
                description="Khối sáng tối sắc nét, góc cạnh và mạnh mẽ, tạo chiều sâu cho ảnh.",
                is_builtin=True,
                contrast=42.0,
                highlights=20.0,
                shadows=-22.0,
                sharpness=30.0,
                saturation=8.0,
                vignette=25.0
            ),
            FilterPreset(
                id="wedding_dream",
                name="Hôn Lễ Lãng Mạn",
                category="Đám cưới",
                description="Ánh sáng êm dịu, tông da trắng hồng ngọc ngà, lý tưởng cho tiệc cưới sang trọng.",
                is_builtin=True,
                brightness=9.0,
                temperature=10.0,
                tint=12.0,
                contrast=2.0,
                saturation=8.0,
                soft_skin=45.0,
                fade=18.0,
                highlights=20.0,
                shadows=10.0
            ),
            FilterPreset(
                id="film_cinema",
                name="Điện Ảnh Cinematic",
                category="Nghệ thuật",
                description="Tông màu phim điện ảnh Teal & Orange với vùng tối xanh lơ và da người ấm áp.",
                is_builtin=True,
                contrast=24.0,
                fade=20.0,
                shadows=18.0,
                highlights=-8.0,
                vignette=25.0,
                sharpness=18.0,
                lut_filename="Cinematic_Teal_Orange.cube",
                lut_intensity=0.75
            ),
        ]

    def _init_sample_luts(self):
        """Khởi tạo một số LUT .cube mẫu chuẩn điện ảnh nếu chưa có."""
        teal_orange_path = os.path.join(self.luts_dir, "Cinematic_Teal_Orange.cube")
        if not os.path.exists(teal_orange_path):
            def teal_orange_func(r, g, b):
                # Vùng tối nghiêng về Teal (Cyan lá-xanh), vùng sáng ấm vàng cam
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                # Tone split
                shadow_weight = (1.0 - lum) ** 1.5
                hi_weight = lum ** 1.2
                r_out = r + hi_weight * 0.18 - shadow_weight * 0.08
                g_out = g + hi_weight * 0.05 + shadow_weight * 0.06
                b_out = b - hi_weight * 0.15 + shadow_weight * 0.22
                return r_out, g_out, b_out

            CubeLUTParser.create_cube_file(teal_orange_path, "Cinematic Teal Orange", 17, teal_orange_func)

        kodak_path = os.path.join(self.luts_dir, "Kodak_Portra_Warm.cube")
        if not os.path.exists(kodak_path):
            def kodak_func(r, g, b):
                # Tông màu film Kodak Portra: da mịn vàng hồng, shadow ngả xanh rêu nhẹ, highlight dịu
                r_out = (r ** 0.92) * 1.05
                g_out = (g ** 0.95) * 1.01
                b_out = (b ** 1.05) * 0.94
                return r_out, g_out, b_out

            CubeLUTParser.create_cube_file(kodak_path, "Kodak Portra Warm", 17, kodak_func)

    def _init_builtin_presets(self):
        """Tạo các file JSON preset mặc định nếu chưa tồn tại."""
        for preset in self._create_default_presets():
            target_file = os.path.join(self.builtin_dir, f"{preset.id}.json")
            if not os.path.exists(target_file):
                preset.save_to_json(target_file)

    def reload_all_presets(self):
        """Tải lại tất cả preset từ BuiltIn và Custom directories."""
        self._presets.clear()

        # 1. Tải Built-in
        if os.path.exists(self.builtin_dir):
            for fname in os.listdir(self.builtin_dir):
                if fname.endswith(".json"):
                    p = FilterPreset.load_from_json(os.path.join(self.builtin_dir, fname))
                    if p:
                        p.is_builtin = True
                        self._presets[p.id] = p

        # 2. Tải Custom (ghi đè hoặc bổ sung)
        if os.path.exists(self.custom_dir):
            for fname in os.listdir(self.custom_dir):
                if fname.endswith(".json"):
                    p = FilterPreset.load_from_json(os.path.join(self.custom_dir, fname))
                    if p:
                        p.is_builtin = False
                        self._presets[p.id] = p

        logger.info(f"Đã nạp tổng cộng {len(self._presets)} preset bộ lọc.")

    # -------------------------------------------------------------
    # QUẢN LÝ PRESET (CRUD, IMPORT, EXPORT)
    # -------------------------------------------------------------
    def get_presets(self) -> List[FilterPreset]:
        """Lấy danh sách tất cả preset hiện có."""
        return list(self._presets.values())

    def get_preset(self, preset_id: str) -> Optional[FilterPreset]:
        """Lấy preset theo ID."""
        return self._presets.get(preset_id)

    def save_custom_preset(self, preset: FilterPreset) -> bool:
        """Lưu một preset người dùng tùy chỉnh vào thư mục Custom."""
        preset.is_builtin = False
        target_path = os.path.join(self.custom_dir, f"{preset.id}.json")
        success = preset.save_to_json(target_path)
        if success:
            self._presets[preset.id] = preset
            logger.info(f"Đã lưu preset tùy chỉnh: {preset.name} ({preset.id})")
        return success

    def duplicate_preset(self, src_id: str, new_id: str, new_name: str) -> Optional[FilterPreset]:
        """Nhân bản một preset có sẵn để tùy biến."""
        src = self.get_preset(src_id)
        if not src:
            return None
        new_preset = copy.deepcopy(src)
        new_preset.id = new_id
        new_preset.name = new_name
        new_preset.is_builtin = False
        if self.save_custom_preset(new_preset):
            return new_preset
        return None

    def delete_preset(self, preset_id: str) -> bool:
        """Xóa một preset tùy chỉnh (không cho phép xóa preset gốc)."""
        preset = self.get_preset(preset_id)
        if not preset:
            return False
        if preset.is_builtin:
            logger.warning(f"Không thể xóa preset hệ thống tích hợp: {preset_id}")
            return False

        target_path = os.path.join(self.custom_dir, f"{preset_id}.json")
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
                self._presets.pop(preset_id, None)
                logger.info(f"Đã xóa preset {preset_id}")
                return True
            except Exception as e:
                logger.error(f"Lỗi khi xóa preset {preset_id}: {e}")
                return False
        return False

    def export_preset_to_file(self, preset_id: str, export_path: str) -> bool:
        """Xuất preset ra file JSON chỉ định."""
        p = self.get_preset(preset_id)
        if not p:
            return False
        return p.save_to_json(export_path)

    def import_preset_from_file(self, import_path: str) -> Optional[FilterPreset]:
        """Nhập preset từ file JSON bên ngoài vào danh mục Custom."""
        p = FilterPreset.load_from_json(import_path)
        if not p:
            return None
        p.is_builtin = False
        # Đảm bảo ID không bị trùng lặp với preset hệ thống
        if p.id in self._presets and self._presets[p.id].is_builtin:
            p.id = f"{p.id}_custom"
        self.save_custom_preset(p)
        return p

    def get_available_luts(self) -> List[str]:
        """Lấy danh sách các file .cube có sẵn trong thư mục LUTs."""
        if not os.path.exists(self.luts_dir):
            return []
        return [f for f in os.listdir(self.luts_dir) if f.lower().endswith(".cube")]

    def get_lut_parser(self, lut_filename: str) -> Optional[CubeLUTParser]:
        """Lấy bộ phân tích LUT được cache để tăng tốc xử lý."""
        if not lut_filename:
            return None
        if lut_filename in self._lut_cache:
            return self._lut_cache[lut_filename]

        full_path = os.path.join(self.luts_dir, lut_filename)
        if not os.path.exists(full_path):
            # Thử kiểm tra đường dẫn tuyệt đối
            if os.path.exists(lut_filename):
                full_path = lut_filename
            else:
                return None

        parser = CubeLUTParser(full_path)
        if parser.table is not None:
            self._lut_cache[lut_filename] = parser
            return parser
        return None

    # -------------------------------------------------------------
    # PIPELINE XỬ LÝ ẢNH KHÔNG PHÁ HỦY (NON-DESTRUCTIVE)
    # -------------------------------------------------------------
    def apply_preset(self, img: Image.Image, preset: FilterPreset, intensity: float = 1.0) -> Image.Image:
        """
        Áp dụng toàn bộ preset vào ảnh PIL Image và trả về ảnh mới hoàn chỉnh.
        Không thay đổi ảnh gốc ban đầu.
        intensity: cường độ tổng thể của preset từ 0.0 (không đổi) đến 1.0 (100%).
        """
        if intensity <= 0.0:
            return img.copy()

        # 1. Chuyển đổi sang numpy uint8 RGB
        rgb_img = img.convert("RGB")
        img_np = np.array(rgb_img, dtype=np.uint8)

        # 2. Xử lý làm mịn da (nếu có soft_skin > 0)
        eff_soft_skin = preset.soft_skin * intensity
        if eff_soft_skin > 0:
            img_np = self._apply_soft_skin(img_np, eff_soft_skin)

        # 3. Xử lý các tham số chỉnh màu cơ bản bằng mảng số học float
        img_np = self._apply_parametric_adjustments(img_np, preset, intensity)

        # 4. Áp dụng 3D LUT nếu được chỉ định
        if preset.lut_filename:
            lut_parser = self.get_lut_parser(preset.lut_filename)
            if lut_parser:
                lut_eff = preset.lut_intensity * intensity
                img_np = lut_parser.apply(img_np, lut_eff)

        # 5. Xử lý tối góc Vignette
        eff_vignette = preset.vignette * intensity
        if eff_vignette > 0:
            img_np = self._apply_vignette(img_np, eff_vignette)

        # 6. Đổi lại ảnh PIL Image
        out_pil = Image.fromarray(img_np, "RGB")

        # 7. Xử lý độ sắc nét Sharpness (PIL unsharp mask)
        eff_sharpness = preset.sharpness * intensity
        if eff_sharpness > 0:
            factor = 1.0 + (eff_sharpness / 100.0) * 1.5
            enhancer = ImageEnhance.Sharpness(out_pil)
            out_pil = enhancer.enhance(factor)

        return out_pil

    def _apply_soft_skin(self, img_np: np.ndarray, amount: float) -> np.ndarray:
        """
        Làm mịn da bằng phương pháp Bilateral Filter có trọng số theo vùng da người (YCbCr skin detection).
        Giữ nguyên độ sắc nét của tóc, viền mắt, chân mày và môi.
        """
        amount = max(0.0, min(100.0, amount))
        d = int(5 + (amount / 100.0) * 10)  # đường kính lân cận 5..15
        sigma_color = 20.0 + (amount / 100.0) * 60.0  # 20..80
        sigma_space = 20.0 + (amount / 100.0) * 60.0

        # Làm mịn toàn diện
        smoothed = cv2.bilateralFilter(img_np, d, sigma_color, sigma_space)

        # Phát hiện vùng da người qua không gian màu YCrCb
        ycrcb = cv2.cvtColor(img_np, cv2.COLOR_RGB2YCrCb)
        cr = ycrcb[:, :, 1]
        cb = ycrcb[:, :, 2]

        # Vùng da người đặc trưng: Cr trong khoảng 133..173, Cb trong khoảng 77..127
        skin_mask = (cr >= 130) & (cr <= 175) & (cb >= 75) & (cb <= 130)
        mask_float = skin_mask.astype(np.float32)

        # Làm mờ biên vùng chọn da để việc hòa trộn không bị gắt
        mask_blur = cv2.GaussianBlur(mask_float, (15, 15), 0)
        mask_3d = mask_blur[:, :, np.newaxis]

        # Tỉ lệ pha trộn da mịn
        blend_factor = (amount / 100.0) * 0.85
        final_blend = img_np.astype(np.float32) * (1.0 - mask_3d * blend_factor) + smoothed.astype(np.float32) * (mask_3d * blend_factor)
        return np.clip(final_blend, 0, 255).astype(np.uint8)

    def _apply_parametric_adjustments(self, img_np: np.ndarray, preset: FilterPreset, intensity: float) -> np.ndarray:
        """Xử lý mảng ma trận: Exposure, Brightness, Contrast, Saturation, Temperature, Tint, Highlights, Shadows, Gamma, Fade, Sepia, Grayscale."""
        arr = img_np.astype(np.float32) / 255.0

        # 1. Grayscale
        if preset.grayscale:
            gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            gray_3d = np.repeat(gray[:, :, np.newaxis], 3, axis=2)
            arr = arr * (1.0 - intensity) + gray_3d * intensity

        # 2. Exposure (-100..100) -> 2^(ev)
        eff_exp = preset.exposure * intensity
        if eff_exp != 0:
            ev = (eff_exp / 100.0) * 1.5  # tối đa +/- 1.5 EV
            arr = arr * (2.0 ** ev)

        # 3. Brightness (-100..100)
        eff_bri = preset.brightness * intensity
        if eff_bri != 0:
            arr = arr + (eff_bri / 100.0) * 0.35

        # 4. Contrast (-100..100)
        eff_con = preset.contrast * intensity
        if eff_con != 0:
            factor = (1.0 + eff_con / 100.0) if eff_con >= 0 else (1.0 + eff_con / 150.0)
            arr = (arr - 0.5) * factor + 0.5

        # 5. Temperature (-100..100: <0 là Cool/Xanh, >0 là Warm/Vàng)
        eff_temp = preset.temperature * intensity
        if eff_temp != 0:
            temp_shift = (eff_temp / 100.0) * 0.25
            arr[:, :, 0] += temp_shift          # Kênh Đỏ tăng/giảm
            arr[:, :, 2] -= temp_shift * 0.85   # Kênh Xanh dương ngược chiều

        # 6. Tint (-100..100: <0 là Xanh lá, >0 là Hồng tím)
        eff_tint = preset.tint * intensity
        if eff_tint != 0:
            tint_shift = (eff_tint / 100.0) * 0.20
            arr[:, :, 1] -= tint_shift          # Kênh Lục giảm khi hồng tím, tăng khi xanh lá
            arr[:, :, 0] += tint_shift * 0.4
            arr[:, :, 2] += tint_shift * 0.4

        # 7. Highlights & Shadows
        eff_hi = preset.highlights * intensity
        eff_sh = preset.shadows * intensity
        if eff_hi != 0 or eff_sh != 0:
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            lum_3d = np.repeat(lum[:, :, np.newaxis], 3, axis=2)

            if eff_hi != 0:
                hi_mask = np.clip((lum_3d - 0.5) * 2.0, 0.0, 1.0) ** 1.5
                arr = arr + (eff_hi / 100.0) * 0.3 * hi_mask

            if eff_sh != 0:
                sh_mask = np.clip((0.5 - lum_3d) * 2.0, 0.0, 1.0) ** 1.5
                arr = arr + (eff_sh / 100.0) * 0.3 * sh_mask

        # 8. Saturation (-100..100)
        eff_sat = preset.saturation * intensity
        if eff_sat != 0 and not preset.grayscale:
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            lum_3d = np.repeat(lum[:, :, np.newaxis], 3, axis=2)
            sat_factor = 1.0 + (eff_sat / 100.0)
            arr = lum_3d + (arr - lum_3d) * sat_factor

        # 9. Gamma
        eff_gamma = 1.0 + (preset.gamma - 1.0) * intensity
        if abs(eff_gamma - 1.0) > 0.01 and eff_gamma > 0.1:
            arr = np.clip(arr, 0.0, 1.0) ** (1.0 / eff_gamma)

        # 10. Fade (Hiệu ứng mờ phim / nâng black point)
        eff_fade = preset.fade * intensity
        if eff_fade > 0:
            fade_amount = (eff_fade / 100.0) * 0.25
            arr = arr * (1.0 - fade_amount) + fade_amount

        # 11. Sepia
        eff_sepia = preset.sepia * intensity
        if eff_sepia > 0:
            sepia_matrix = np.array([
                [0.393, 0.769, 0.189],
                [0.349, 0.686, 0.168],
                [0.272, 0.534, 0.131]
            ], dtype=np.float32)
            sepia_img = np.dot(arr, sepia_matrix.T)
            sep_ratio = eff_sepia / 100.0
            arr = arr * (1.0 - sep_ratio) + sepia_img * sep_ratio

        # Giới hạn về miền [0, 255]
        return np.clip(arr * 255.0, 0.0, 255.0).astype(np.uint8)

    def _apply_vignette(self, img_np: np.ndarray, amount: float) -> np.ndarray:
        """Tạo hiệu ứng tối dần 4 góc (Vignette)."""
        h, w = img_np.shape[:2]
        x = np.linspace(-1, 1, w, dtype=np.float32)
        y = np.linspace(-1, 1, h, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        radius = np.sqrt(xx**2 + yy**2)

        # Chuẩn hóa bán kính: tâm = 0, góc = sqrt(2) ~ 1.414
        radius = radius / 1.414
        vignette_curve = 1.0 - (amount / 100.0) * np.clip((radius - 0.25) / 0.75, 0.0, 1.0) ** 1.8
        vignette_curve = vignette_curve[:, :, np.newaxis]

        out = img_np.astype(np.float32) * vignette_curve
        return np.clip(out, 0, 255).astype(np.uint8)

    def generate_preview_thumbnail(self, base_thumb: Image.Image, preset_id: str) -> Image.Image:
        """Tạo ảnh thumbnail xem trước với kích thước nhỏ để hiển thị mượt trên dải bộ lọc."""
        preset = self.get_preset(preset_id)
        if not preset:
            return base_thumb
        return self.apply_preset(base_thumb, preset)
