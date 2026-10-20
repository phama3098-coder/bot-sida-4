"""
VietPhotoBooth Camera Simulator
Provides high-fidelity software camera simulation for testing and development without hardware.
Strictly labeled as SIMULATOR. Never masquerades as physical hardware.
"""

import io
import time
import math
from datetime import datetime
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont
from vietphotobooth.camera.base import CameraAdapter, CameraInfo
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class CameraSimulator(CameraAdapter):
    def __init__(self, sample_image_dir: str = None):
        self._connected = True
        self._brand = "Giả Lập (Simulator)"
        self._model = "VietPhotoBooth Virtual Camera v1.0"
        self._sample_dir = sample_image_dir
        self._frame_count = 0
        self._params = {
            "iso": "400",
            "shutter_speed": "1/125",
            "aperture": "f/4.0",
            "white_balance": "Tự động (Auto)",
            "battery_level": "98%"
        }
        self.simulate_disconnect = False

    def detect_devices(self) -> List[Dict[str, Any]]:
        return [{
            "id": "sim_0",
            "name": "Bộ Giả Lập Máy Ảnh (Simulator)",
            "brand": "VietPhotoBooth Simulator",
            "model": "Virtual Camera Engine",
            "is_simulator": True,
            "status": "Sẵn sàng"
        }]

    def connect(self, device_id: Any = None) -> bool:
        if self.simulate_disconnect:
            self._connected = False
            return False
        self._connected = True
        logger.info("Đã kết nối với Bộ Giả Lập Máy Ảnh (Camera Simulator).")
        return True

    def disconnect(self) -> None:
        self._connected = False
        logger.info("Đã ngắt kết nối Bộ Giả Lập Máy Ảnh.")

    def is_connected(self) -> bool:
        return self._connected and not self.simulate_disconnect

    def get_info(self) -> CameraInfo:
        return CameraInfo(
            name="Bộ Giả Lập Máy Ảnh (Camera Simulator)",
            brand=self._brand,
            model=self._model,
            backend_name="Camera Simulator Backend",
            is_simulator=True,
            status="Sẵn sàng (Đang hoạt động)" if self.is_connected() else "Mất kết nối",
            capabilities={
                "can_capture": True,
                "can_download": True,
                "can_liveview": True,
                "can_adjust_parameters": True
            },
            notes="Chế độ giả lập dùng để kiểm thử phần mềm khi chưa cắm máy ảnh vật lý."
        )

    def _render_scene(self, width: int = 1920, height: int = 1280, is_liveview: bool = False) -> Image.Image:
        """Tạo hình ảnh mẫu mô phỏng người chụp ảnh trong booth với gradient phông nền nghệ thuật."""
        img = Image.new("RGB", (width, height), (35, 39, 47))
        draw = ImageDraw.Draw(img)

        # Gradient background
        for y in range(height):
            r = int(35 + (y / height) * 40)
            g = int(39 + (y / height) * 35)
            b = int(47 + (y / height) * 70)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Phông nền studio trang trí
        center_x = width // 2
        center_y = height // 2

        # Vẽ ánh đèn studio phía sau
        draw.ellipse(
            [center_x - 350, center_y - 450, center_x + 350, center_y + 250],
            fill=(70, 75, 110)
        )

        # Vẽ hình người mẫu giả lập (stylized silhouette)
        # Đầu
        head_radius = int(height * 0.12)
        head_center_y = int(height * 0.38)
        draw.ellipse(
            [center_x - head_radius, head_center_y - head_radius,
             center_x + head_radius, head_center_y + head_radius],
            fill=(220, 185, 160)
        )
        # Tóc
        draw.arc(
            [center_x - head_radius - 10, head_center_y - head_radius - 10,
             center_x + head_radius + 10, head_center_y + head_radius],
            start=180, end=360, fill=(40, 25, 20), width=18
        )
        # Nụ cười / Biểu cảm
        draw.arc(
            [center_x - 30, head_center_y + 20, center_x + 30, head_center_y + 50],
            start=0, end=180, fill=(180, 50, 50), width=4
        )
        # Mắt
        draw.ellipse([center_x - 35, head_center_y - 10, center_x - 25, head_center_y], fill=(40, 30, 30))
        draw.ellipse([center_x + 25, head_center_y - 10, center_x + 35, head_center_y], fill=(40, 30, 30))

        # Thân áo
        shoulder_y = int(height * 0.52)
        draw.polygon(
            [
                (center_x, shoulder_y),
                (center_x - int(width * 0.28), height),
                (center_x + int(width * 0.28), height)
            ],
            fill=(45, 85, 140)
        )
        # Cổ áo / Vest
        draw.polygon(
            [
                (center_x - 35, shoulder_y),
                (center_x + 35, shoulder_y),
                (center_x, shoulder_y + 90)
            ],
            fill=(250, 250, 250)
        )
        draw.polygon(
            [
                (center_x - 15, shoulder_y + 20),
                (center_x + 15, shoulder_y + 20),
                (center_x, shoulder_y + 70)
            ],
            fill=(180, 30, 30)
        )

        # Nhãn nhận diện chế độ giả lập rõ ràng
        watermark_text = "ẢNH GIẢ LẬP / SIMULATOR - VIETPHOTOBOOTH"
        draw.rectangle([20, 20, 540, 70], fill=(200, 30, 30))
        draw.text((35, 30), watermark_text, fill=(255, 255, 255))

        # Thông tin camera giả lập
        info_str = f"ISO: {self._params['iso']} | T: {self._params['shutter_speed']} | F: {self._params['aperture']} | PIN: {self._params['battery_level']}"
        draw.rectangle([20, height - 70, 520, height - 20], fill=(0, 0, 0, 180))
        draw.text((35, height - 55), info_str, fill=(220, 220, 220))

        # Nếu là live view, vẽ thêm khung ngắm, timestamp và ô lấy nét động
        if is_liveview:
            self._frame_count += 1
            # Khung lưới 1/3 (Rule of thirds)
            draw.line([(width // 3, 0), (width // 3, height)], fill=(120, 120, 120, 60), width=1)
            draw.line([(2 * width // 3, 0), (2 * width // 3, height)], fill=(120, 120, 120, 60), width=1)
            draw.line([(0, height // 3), (width, height // 3)], fill=(120, 120, 120, 60), width=1)
            draw.line([(0, 2 * height // 3), (width, 2 * height // 3)], fill=(120, 120, 120, 60), width=1)

            # Ô lấy nét động dao động nhẹ theo thời gian
            pulse = math.sin(self._frame_count * 0.3) * 6
            focus_size = 90 + int(pulse)
            fx1 = center_x - focus_size // 2
            fy1 = head_center_y - focus_size // 2
            fx2 = fx1 + focus_size
            fy2 = fy1 + focus_size
            draw.rectangle([fx1, fy1, fx2, fy2], outline=(50, 230, 50), width=2)
            draw.text((fx1 + 5, fy1 - 18), "[ AF - LẤY NÉT ]", fill=(50, 230, 50))

            # Live view badge
            time_now = datetime.now().strftime("%H:%M:%S.%f")[:-4]
            draw.rectangle([width - 240, 20, width - 20, 70], fill=(0, 140, 0))
            draw.text((width - 220, 32), f"LIVE VIEW  {time_now}", fill=(255, 255, 255))

        return img

    def capture_image(self) -> Optional[Image.Image]:
        """Chụp ảnh chất lượng cao với mô phỏng độ trễ màn trập 100ms."""
        if not self.is_connected():
            logger.error("Camera Simulator: Mất kết nối, không thể chụp!")
            return None
        time.sleep(0.12)  # Mô phỏng độ trễ chụp thật
        img = self._render_scene(width=2400, height=1600, is_liveview=False)
        logger.info("Camera Simulator: Đã chụp và xuất ảnh mẫu thành công (2400x1600).")
        return img

    def get_liveview_frame(self) -> Optional[bytes]:
        """Lấy một khung hình live view nén JPEG bytes."""
        if not self.is_connected():
            return None
        # Khung hình liveview độ phân giải 960x640 để stream mượt mà
        img = self._render_scene(width=960, height=640, is_liveview=True)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return buf.getvalue()

    def get_parameters(self) -> Dict[str, Any]:
        return self._params.copy()

    def set_parameters(self, params: Dict[str, Any]) -> bool:
        for k, v in params.items():
            if k in self._params:
                self._params[k] = str(v)
        logger.info(f"Camera Simulator: Cập nhật thông số {params}")
        return True

    def check_health(self) -> bool:
        return self.is_connected()
