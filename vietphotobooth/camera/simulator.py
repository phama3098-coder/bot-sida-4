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
        """Tạo thẻ chuẩn hình ảnh kiểm thử (Calibration Test Pattern) thay vì vẽ hình người giả lập."""
        img = Image.new("RGB", (width, height), (11, 19, 43)) # Deep Navy
        draw = ImageDraw.Draw(img)

        # Lưới tọa độ studio chuyên nghiệp
        for x in range(0, width, 120):
            draw.line([(x, 0), (x, height)], fill=(20, 32, 60), width=1)
        for y in range(0, height, 120):
            draw.line([(0, y), (width, y)], fill=(20, 32, 60), width=1)

        center_x = width // 2
        center_y = height // 2

        # Dải màu chuẩn màu sắc (SMPTE Color Bar)
        colors = [
            (212, 175, 55), # Champagne Gold
            (255, 255, 255), # White
            (220, 20, 60),   # Red
            (30, 144, 255),  # Blue
            (50, 205, 50),   # Green
            (255, 165, 0),   # Orange
            (147, 112, 219), # Purple
            (60, 60, 60)     # Dark Gray
        ]
        bar_w = int(width * 0.7) // len(colors)
        bar_start_x = (width - len(colors) * bar_w) // 2
        bar_y = int(height * 0.65)
        bar_h = int(height * 0.12)
        for i, col in enumerate(colors):
            bx = bar_start_x + i * bar_w
            draw.rectangle([bx, bar_y, bx + bar_w, bar_y + bar_h], fill=col)

        # Khung viền căn lề an toàn
        draw.rectangle([40, 40, width - 40, height - 40], outline=(212, 175, 55), width=2)
        draw.rectangle([70, 70, width - 70, height - 70], outline=(70, 90, 130), width=1)

        # Vòng tròn tâm ngắm
        draw.ellipse([center_x - 120, center_y - 180, center_x + 120, center_y + 60], outline=(212, 175, 55), width=2)
        draw.line([(center_x - 140, center_y - 60), (center_x + 140, center_y - 60)], fill=(212, 175, 55), width=1)
        draw.line([(center_x, center_y - 200), (center_x, center_y + 80)], fill=(212, 175, 55), width=1)

        # Tiêu đề nhận diện thương hiệu
        font_large = ImageFont.load_default()
        draw.text((center_x, center_y - 100), "1998 STUDIO PHÓNG SỰ CƯỚI", fill=(247, 231, 206), anchor="mm")
        draw.text((center_x, center_y - 40), "HỆ THỐNG KIỂM THỬ TÍN HIỆU CAMERA (TEST PATTERN)", fill=(212, 175, 55), anchor="mm")
        draw.text((center_x, center_y + 10), "[ CHƯA KẾT NỐI CAMERA VẬT LÝ - ĐANG Ở CHẾ ĐỘ MÔ PHỎNG ]", fill=(200, 210, 230), anchor="mm")

        # Thông số kỹ thuật
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((60, height - 80), f"1998 TEAM Photobooth | {width}x{height} | {now_str}", fill=(180, 190, 210))
        # Nhãn nhận diện chế độ giả lập rõ ràng
        watermark_text = "1998 TEAM — PHOTOBOOTH [CHẾ ĐỘ MÔ PHỎNG]"
        draw.rectangle([20, 20, 520, 65], fill=(212, 175, 55))
        draw.text((35, 30), watermark_text, fill=(11, 19, 43))

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
            fy1 = center_y - focus_size // 2
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
