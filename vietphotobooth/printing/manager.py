"""
VietPhotoBooth Print Queue Manager
Manages print jobs, state lifecycle, error tolerance, and reprint capabilities.
"""

import os
import time
import uuid
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
from vietphotobooth.printing.spooler import WindowsPrintSpooler
from vietphotobooth.printing.dnp_rx1hs import DNPRX1HSProfile
from vietphotobooth.core.logger import get_logger

logger = get_logger()

# Các trạng thái của lệnh in
STATUS_PENDING = "Đang chờ (Pending)"
STATUS_SPOOLING = "Đang gửi tới Windows Spooler"
STATUS_SPOOLED = "Đã tiếp nhận vào Spooler"
STATUS_COMPLETED = "Hoàn thành (Completed)"
STATUS_ERROR = "Lỗi máy in (Error)"
STATUS_CANCELLED = "Đã hủy (Cancelled)"
STATUS_UNKNOWN = "Trạng thái chưa xác định"

class PrintJob:
    def __init__(
        self,
        job_id: str,
        image_path: str,
        printer_name: str,
        copies: int = 1,
        paper_size: str = "4x6",
        event_name: str = ""
    ):
        self.job_id = job_id
        self.image_path = image_path
        self.printer_name = printer_name
        self.copies = copies
        self.paper_size = paper_size
        self.event_name = event_name
        self.status = STATUS_PENDING
        self.error_message: Optional[str] = None
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "image_path": self.image_path,
            "filename": os.path.basename(self.image_path) if self.image_path else "",
            "printer_name": self.printer_name,
            "copies": self.copies,
            "paper_size": self.paper_size,
            "event_name": self.event_name,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }

class PrintManager:
    def __init__(self, default_printer: str = "", config_mgr=None):
        self.config_mgr = config_mgr
        self.selected_printer = default_printer or WindowsPrintSpooler.get_default_printer()
        self.strip_printer_name = ""
        self.full_printer_name = ""
        self.offset_x = 0
        self.offset_y = 0
        self.zoom = 1.0
        self.orientation = "portrait"
        self.paper_count = 120
        self.paper_max = 400
        self.paper_warning_threshold = 50

        if self.config_mgr:
            self.load_settings()

        self.jobs: List[PrintJob] = []
        self._lock = threading.Lock()
        self._running = True
        self._worker_thread = threading.Thread(target=self._process_queue_loop, daemon=True)
        self._worker_thread.start()

    def load_settings(self) -> None:
        """Đọc toàn bộ cấu hình máy in, căn lề và bộ đếm giấy từ ConfigManager."""
        if not self.config_mgr:
            return
        self.strip_printer_name = str(self.config_mgr.get("printer.strip_printer_name", "")).strip()
        self.full_printer_name = str(self.config_mgr.get("printer.full_printer_name", "")).strip()
        self.offset_x = int(self.config_mgr.get("printer.offset_x", 0))
        self.offset_y = int(self.config_mgr.get("printer.offset_y", 0))
        self.zoom = float(self.config_mgr.get("printer.zoom", 1.0))
        self.orientation = str(self.config_mgr.get("printer.orientation", "portrait"))
        self.paper_count = int(self.config_mgr.get("printer.paper_count", 120))
        self.paper_max = int(self.config_mgr.get("printer.paper_max", 400))
        self.paper_warning_threshold = int(self.config_mgr.get("printer.paper_warning_threshold", 50))
        sp = self.config_mgr.get("printer_name", "")
        if sp:
            self.selected_printer = sp

    def save_settings(self) -> None:
        """Lưu toàn bộ cài đặt máy in, căn chỉnh lề và bộ đếm giấy vào ConfigManager."""
        if not self.config_mgr:
            return
        self.config_mgr.set("printer.strip_printer_name", self.strip_printer_name)
        self.config_mgr.set("printer.full_printer_name", self.full_printer_name)
        self.config_mgr.set("printer.offset_x", self.offset_x)
        self.config_mgr.set("printer.offset_y", self.offset_y)
        self.config_mgr.set("printer.zoom", self.zoom)
        self.config_mgr.set("printer.orientation", self.orientation)
        self.config_mgr.set("printer.paper_count", self.paper_count)
        self.config_mgr.set("printer.paper_max", self.paper_max)
        self.config_mgr.set("printer.paper_warning_threshold", self.paper_warning_threshold)
        if self.selected_printer:
            self.config_mgr.set("printer_name", self.selected_printer)
        self.config_mgr.save()

    def refill_paper(self, amount: int) -> int:
        """Nạp thêm giấy in vào khay."""
        self.paper_count = max(0, min(self.paper_max, self.paper_count + amount))
        self.save_settings()
        logger.info(f"Đã nạp thêm {amount} tờ giấy. Hiện có: {self.paper_count}/{self.paper_max} tờ.")
        return self.paper_count

    def stop(self) -> None:
        """Dừng tiến trình nền in ấn một cách an toàn."""
        self._running = False
        if hasattr(self, "_worker_thread") and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.6)

    def get_printers(self) -> List[Dict[str, Any]]:
        return WindowsPrintSpooler.get_installed_printers()

    def set_selected_printer(self, printer_name: str) -> bool:
        self.selected_printer = printer_name
        logger.info(f"Đã chọn máy in làm việc: {self.selected_printer}")
        return True

    def get_selected_printer(self) -> str:
        if not self.selected_printer:
            self.selected_printer = WindowsPrintSpooler.get_default_printer()
        return self.selected_printer

    def submit_job(
        self,
        image_path: str,
        copies: int = 1,
        paper_size: str = "4x6",
        event_name: str = ""
    ) -> PrintJob:
        """Thêm một lệnh in mới vào hàng đợi, tự động định tuyến máy in strip hoặc full."""
        job_id = f"JOB-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

        target_printer = self.get_selected_printer()
        if "2x6" in paper_size and self.strip_printer_name:
            target_printer = self.strip_printer_name
        elif "4x6" in paper_size and self.full_printer_name:
            target_printer = self.full_printer_name

        job = PrintJob(
            job_id=job_id,
            image_path=image_path,
            printer_name=target_printer,
            copies=max(1, copies),
            paper_size=paper_size,
            event_name=event_name
        )
        with self._lock:
            self.jobs.append(job)
        logger.info(f"Đã thêm lệnh in {job_id} vào hàng đợi ({copies} bản, khổ: {paper_size}, máy in: '{job.printer_name}')")
        return job

    def cancel_job(self, job_id: str) -> bool:
        """Hủy lệnh in nếu lệnh vẫn đang chờ."""
        with self._lock:
            for job in self.jobs:
                if job.job_id == job_id:
                    if job.status == STATUS_PENDING:
                        job.status = STATUS_CANCELLED
                        logger.info(f"Đã hủy lệnh in {job_id}")
                        return True
                    else:
                        logger.warning(f"Không thể hủy lệnh in {job_id} vì trạng thái là: {job.status}")
                        return False
        return False

    def retry_job(self, job_id: str) -> bool:
        """Thử lại lệnh in bị lỗi."""
        with self._lock:
            for job in self.jobs:
                if job.job_id == job_id:
                    if job.status in (STATUS_ERROR, STATUS_CANCELLED, STATUS_UNKNOWN):
                        job.status = STATUS_PENDING
                        job.error_message = None
                        logger.info(f"Đã đưa lệnh in {job_id} trở lại hàng đợi để thử lại.")
                        return True
        return False

    def get_queue(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [j.to_dict() for j in reversed(self.jobs)]

    def _process_queue_loop(self) -> None:
        """Tiến trình nền xử lý tuần tự từng lệnh in trong hàng đợi."""
        while getattr(self, "_running", True):
            job_to_process = None
            with self._lock:
                for job in self.jobs:
                    if job.status == STATUS_PENDING:
                        job_to_process = job
                        break

            if job_to_process:
                self._execute_print_job(job_to_process)
            else:
                time.sleep(0.1)

    def _execute_print_job(self, job: PrintJob) -> None:
        job.status = STATUS_SPOOLING
        logger.info(f"Đang xử lý lệnh in {job.job_id}...")

        # 1. Kiểm tra file ảnh tồn tại
        if not os.path.exists(job.image_path):
            job.status = STATUS_ERROR
            job.error_message = f"Không tìm thấy file ảnh: {job.image_path}"
            logger.error(job.error_message)
            return

        # 2. Kiểm tra trạng thái máy in trước khi in
        status_info = WindowsPrintSpooler.get_printer_status(job.printer_name)
        if not status_info.get("is_online", True):
            job.status = STATUS_ERROR
            job.error_message = f"Máy in '{job.printer_name}' không sẵn sàng: {status_info.get('status_text')}"
            logger.error(job.error_message)
            return

        # 3. Gửi lệnh in vào Windows Spooler với đầy đủ căn chỉnh lề, zoom và hướng giấy
        res = WindowsPrintSpooler.send_image_to_printer(
            printer_name=job.printer_name,
            image_path=job.image_path,
            copies=job.copies,
            job_title=f"1998 TEAM Photobooth [{job.job_id}]",
            offset_x=self.offset_x,
            offset_y=self.offset_y,
            zoom=self.zoom,
            orientation=self.orientation
        )

        if res.get("success"):
            job.status = STATUS_SPOOLED
            # Cập nhật trừ giấy in thực tế
            self.paper_count = max(0, self.paper_count - job.copies)
            self.save_settings()
            if self.paper_count <= self.paper_warning_threshold:
                logger.warning(f"CẢNH BÁO: Giấy in sắp hết! Còn lại {self.paper_count}/{self.paper_max} tờ.")

            time.sleep(1.0)
            job.status = STATUS_COMPLETED
            job.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Lệnh in {job.job_id} hoàn thành thành công. Giấy còn lại: {self.paper_count} tờ.")
        else:
            job.status = STATUS_ERROR
            job.error_message = res.get("error", "Lỗi không xác định khi gửi tới Spooler.")
            logger.error(f"Lệnh in {job.job_id} thất bại: {job.error_message}")

    def create_test_print_card(self, output_path: str) -> str:
        """Tạo một thẻ in thử nghiệm (Test Card) chuẩn khổ 4x6 1200x1800 px."""
        w, h = 1200, 1800
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Viền căn lề an toàn
        draw.rectangle([30, 30, w - 30, h - 30], outline=(0, 0, 0), width=4)
        draw.rectangle([50, 50, w - 50, h - 50], outline=(200, 0, 0), width=2)

        # Tiêu đề
        draw.rectangle([60, 60, w - 60, 220], fill=(20, 35, 60))
        draw.text((w // 2, 140), "VIETPHOTOBOOTH - BẢN IN KIỂM TRA MÁY IN", fill=(255, 255, 255), anchor="mm")

        # Thông tin máy in và hệ thống
        draw.text((100, 280), f"Máy in: {self.get_selected_printer()}", fill=(0, 0, 0))
        draw.text((100, 340), f"Thời gian tạo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fill=(0, 0, 0))
        draw.text((100, 400), "Độ phân giải danh định: 300 DPI (1200 x 1800 px)", fill=(0, 0, 0))
        draw.text((100, 460), "Hệ màu: RGB 24-bit sRGB Standard", fill=(0, 0, 0))

        # Dải màu kiểm tra chất lượng in (Color Bar)
        colors = [
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
            (255, 255, 0), (0, 255, 255), (255, 0, 255),
            (0, 0, 0), (128, 128, 128), (200, 200, 200)
        ]
        bar_w = (w - 200) // len(colors)
        for i, col in enumerate(colors):
            bx = 100 + i * bar_w
            draw.rectangle([bx, 550, bx + bar_w, 750], fill=col)

        # Đường chỉ cắt 2x6 ở giữa (để kiểm tra dao cắt DNP RX1HS)
        draw.line([(w // 2, 850), (w // 2, h - 200)], fill=(180, 0, 0), width=3)
        draw.text((w // 2, 820), "<- ĐƯỜNG CẮT 2x6 INCH Ở GIỮA ->", fill=(180, 0, 0), anchor="mm")

        # Khung ảnh mẫu trái và phải
        draw.rectangle([100, 900, 550, 1500], outline=(100, 100, 100), width=3)
        draw.text((325, 1200), "DẢI 1 (TRÁI)", fill=(100, 100, 100), anchor="mm")

        draw.rectangle([650, 900, 1100, 1500], outline=(100, 100, 100), width=3)
        draw.text((875, 1200), "DẢI 2 (PHẢI)", fill=(100, 100, 100), anchor="mm")

        # Footer
        draw.text((w // 2, h - 80), "VietPhotoBooth Windows Photo Printing System v1.0", fill=(120, 120, 120), anchor="mm")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "JPEG", dpi=(300, 300), quality=100)
        logger.info(f"Đã tạo file in thử tại {output_path}")
        return output_path

    def print_image(self, image_path: str, copies: int = 1, paper_size: str = "4x6", event_name: str = "") -> bool:
        """Đưa ảnh vào hàng đợi in."""
        try:
            job = self.submit_job(image_path=image_path, copies=copies, paper_size=paper_size, event_name=event_name)
            return job is not None
        except Exception as e:
            logger.error(f"Lỗi khi gửi lệnh in ảnh {image_path}: {e}")
            return False

    def print_test_page(self) -> bool:
        """Tạo thẻ in kiểm tra màu sắc & độ căn lề rồi gửi trực tiếp tới máy in."""
        import tempfile
        tmp_dir = tempfile.gettempdir()
        test_card_path = os.path.join(tmp_dir, "vietphotobooth_test_card.jpg")
        self.create_test_print_card(test_card_path)
        return self.print_image(test_card_path, copies=1, paper_size="4x6")

    def get_job_queue(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các lệnh in trong hàng đợi."""
        return self.get_queue()

    def clear_completed_jobs(self):
        """Xóa các lệnh in đã hoàn tất khỏi hàng đợi hiển thị."""
        with self._lock:
            self.jobs = [j for j in self.jobs if j.status not in (STATUS_COMPLETED, STATUS_CANCELLED)]

