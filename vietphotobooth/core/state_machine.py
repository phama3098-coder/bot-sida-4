"""
VietPhotoBooth Core State Machine & Session Manager
Coordinates the full interactive photobooth sequence: Start -> Countdown -> Capture -> Collage -> Preview/Print/QR.
"""

import os
import time
import uuid
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from PIL import Image

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.core.logger import get_logger
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.processing.template_engine import TemplateEngine
from vietphotobooth.processing.image_processor import ImageProcessor
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager

logger = get_logger()

# Các trạng thái chính của hệ thống Photobooth
STATE_IDLE = "IDLE"                    # Màn hình chờ
STATE_COUNTDOWN = "COUNTDOWN"          # Đang đếm ngược
STATE_CAPTURING = "CAPTURING"          # Đang chụp ảnh từ camera
STATE_PROCESSING = "PROCESSING"        # Đang ghép template và lưu ảnh
STATE_PREVIEW = "PREVIEW"              # Màn hình xem trước, in ảnh và quét QR
STATE_ERROR = "ERROR"                  # Báo lỗi

class SessionManager:
    def __init__(
        self,
        config: ConfigManager,
        event_mgr: EventManager,
        camera_mgr: CameraManager,
        template_engine: TemplateEngine,
        print_mgr: PrintManager,
        token_mgr: TokenManager
    ):
        self.config = config
        self.event_mgr = event_mgr
        self.camera_mgr = camera_mgr
        self.template_engine = template_engine
        self.print_mgr = print_mgr
        self.token_mgr = token_mgr

        self.state = STATE_IDLE
        self.session_id: Optional[str] = None
        self.current_shot_index: int = 0
        self.total_shots: int = self.config.get("photos_per_session", 3)
        self.countdown_remaining: int = 0
        self.captured_images: List[Image.Image] = []
        self.captured_file_paths: List[str] = []
        self.final_image: Optional[Image.Image] = None
        self.final_image_path: Optional[str] = None
        self.thumbnail_path: Optional[str] = None
        self.share_token: Optional[str] = None
        self.share_url: Optional[str] = None
        self.error_message: Optional[str] = None

        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_requested = False

    def get_status(self) -> Dict[str, Any]:
        """Lấy toàn bộ trạng thái thời gian thực để gửi về giao diện người dùng."""
        with self._lock:
            return {
                "state": self.state,
                "session_id": self.session_id,
                "current_shot": self.current_shot_index,
                "total_shots": self.total_shots,
                "countdown": self.countdown_remaining,
                "has_final": self.final_image_path is not None,
                "final_filename": os.path.basename(self.final_image_path) if self.final_image_path else None,
                "share_token": self.share_token,
                "share_url": self.share_url,
                "error_message": self.error_message,
                "camera_connected": self.camera_mgr.is_connected(),
                "event_name": self.event_mgr.current_event
            }

    def start_session(self) -> Dict[str, Any]:
        """Khách bấm 'BẮT ĐẦU' trên màn hình cảm ứng."""
        with self._lock:
            if self.state not in (STATE_IDLE, STATE_PREVIEW, STATE_ERROR):
                return {"success": False, "error": "Phiên chụp đang diễn ra."}

            # Kiểm tra trạng thái camera trước khi cho phép chụp
            if not self.camera_mgr.is_connected():
                self.state = STATE_ERROR
                self.error_message = "Máy ảnh chưa sẵn sàng hoặc đã mất kết nối! Vui lòng kiểm tra dây cắm hoặc chọn Camera Simulator."
                logger.error(self.error_message)
                return {"success": False, "error": self.error_message}

            self.session_id = f"SES_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4].upper()}"
            self.total_shots = int(self.config.get("photos_per_session", 3))
            self.current_shot_index = 0
            self.captured_images.clear()
            self.captured_file_paths.clear()
            self.final_image = None
            self.final_image_path = None
            self.thumbnail_path = None
            self.share_token = None
            self.share_url = None
            self.error_message = None
            self._stop_requested = False

            # Khởi động tiến trình chụp tự động trong background thread
            self._worker_thread = threading.Thread(target=self._run_capture_sequence, daemon=True)
            self._worker_thread.start()

            return {"success": True, "session_id": self.session_id}

    def cancel_session(self) -> Dict[str, Any]:
        """Hủy phiên chụp an toàn."""
        with self._lock:
            self._stop_requested = True
            self.state = STATE_IDLE
            self.error_message = None
            logger.info("Người dùng đã hủy phiên chụp.")
            return {"success": True, "message": "Đã hủy phiên chụp."}

    def reset_to_idle(self) -> Dict[str, Any]:
        """Kết thúc phiên và quay về màn hình chờ."""
        with self._lock:
            self.state = STATE_IDLE
            self.session_id = None
            self.error_message = None
            return {"success": True}

    def _run_capture_sequence(self) -> None:
        """Chuỗi hành động chụp loạt ảnh: Đếm ngược -> Chụp -> Nghỉ -> Ghép -> Xem trước."""
        logger.info(f"Bắt đầu chuỗi chụp cho phiên {self.session_id} ({self.total_shots} kiểu ảnh)")
        dirs = self.event_mgr.get_current_dirs()
        countdown_secs = int(self.config.get("countdown_seconds", 5))
        delay_between = int(self.config.get("delay_between_shots", 2))

        try:
            for shot_idx in range(1, self.total_shots + 1):
                if self._stop_requested:
                    return

                with self._lock:
                    self.current_shot_index = shot_idx
                    self.state = STATE_COUNTDOWN
                    self.countdown_remaining = countdown_secs

                # 1. Đếm ngược (Countdown)
                for sec in range(countdown_secs, 0, -1):
                    if self._stop_requested:
                        return
                    with self._lock:
                        self.countdown_remaining = sec
                    time.sleep(1.0)

                with self._lock:
                    self.countdown_remaining = 0
                    self.state = STATE_CAPTURING

                # 2. Chụp ảnh qua camera backend
                img = self.camera_mgr.capture()
                if img is None or self._stop_requested:
                    raise Exception(f"Không thể chụp bức ảnh số {shot_idx} từ máy ảnh.")

                # 3. Lưu ảnh gốc vào thư mục Originals/
                orig_filename = f"{self.session_id}_shot{shot_idx}.jpg"
                orig_path = os.path.join(dirs["originals"], orig_filename)
                img.save(orig_path, "JPEG", quality=98)
                
                with self._lock:
                    self.captured_images.append(img)
                    self.captured_file_paths.append(orig_path)
                logger.info(f"Đã lưu ảnh gốc #{shot_idx}: {orig_filename}")

                # Thời gian nghỉ giữa các bức ảnh để khách tạo dáng tiếp theo
                if shot_idx < self.total_shots:
                    time.sleep(delay_between)

            if self._stop_requested:
                return

            # 4. Ghép ảnh theo Template (Processing)
            with self._lock:
                self.state = STATE_PROCESSING

            template_id = self.config.get("template_id", "strip_2x6_3photos")
            event_info = {
                "title": self.config.get("event_title", "Kỷ Niệm Ngày Cưới"),
                "subtitle": self.config.get("event_subtitle", "Chúc Mừng Hạnh Phúc"),
                "date": self.config.get("event_date", datetime.now().strftime("%Y-%m-%d"))
            }

            final_img = self.template_engine.render(
                template_id=template_id,
                photos=self.captured_images,
                event_info=event_info,
                filter_name="none"
            )

            # 5. Lưu ảnh thành phẩm vào Final/
            final_filename = f"{self.session_id}_final.jpg"
            final_path = os.path.join(dirs["final"], final_filename)
            final_img.save(final_path, "JPEG", dpi=(300, 300), quality=98)

            # 6. Tạo thumbnail vào Thumbnails/
            thumb_img = ImageProcessor.make_thumbnail(final_img, (400, 600))
            thumb_path = os.path.join(dirs["thumbnails"], final_filename)
            thumb_img.save(thumb_path, "JPEG", quality=85)

            # 7. Sinh mã Token chia sẻ qua QR mạng LAN
            share_obj = self.token_mgr.create_share_token(
                file_path=final_path,
                event_name=self.event_mgr.current_event,
                expire_hours=int(self.config.get("share_token_expire_hours", 24))
            )
            share_url = self.token_mgr.get_share_url(share_obj.token)

            # 8. Chuyển sang màn hình Preview
            with self._lock:
                self.final_image = final_img
                self.final_image_path = final_path
                self.thumbnail_path = thumb_path
                self.share_token = share_obj.token
                self.share_url = share_url
                self.state = STATE_PREVIEW

            logger.info(f"Hoàn thành xử lý phiên {self.session_id}. File thành phẩm: {final_filename}")

            # 9. Tự động in nếu cấu hình auto_print được bật
            if self.config.get("auto_print", False):
                self.trigger_print(copies=1)

        except Exception as e:
            with self._lock:
                self.state = STATE_ERROR
                self.error_message = f"Lỗi trong quá trình chụp ảnh: {e}"
            logger.error(self.error_message)

    def trigger_print(self, copies: int = 1) -> Dict[str, Any]:
        """Kích hoạt in ảnh thành phẩm từ màn hình xem trước."""
        with self._lock:
            if not self.final_image_path or not os.path.exists(self.final_image_path):
                return {"success": False, "error": "Chưa có ảnh thành phẩm để in."}

            paper_size = self.config.get("printer_paper_size", "4x6")
            job = self.print_mgr.submit_job(
                image_path=self.final_image_path,
                copies=copies,
                paper_size=paper_size,
                event_name=self.event_mgr.current_event
            )
            return {"success": True, "job_id": job.job_id, "printer": job.printer_name}
