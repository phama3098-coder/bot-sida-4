"""
1998 TEAM — Photobooth Nikon MAID Background Worker
Runs frame polling and command processing in a dedicated high-priority background thread
ensuring the UI thread remains 100% responsive at all times.
"""

import time
import threading
from typing import Optional, Callable, Tuple
import logging
from PIL import Image
import io

from vietphotobooth.camera.models import FrameData
from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession

logger = logging.getLogger(__name__)


class NikonCameraWorker:
    """Worker luồng nền xử lý luồng Live View và tác vụ chụp ảnh của Nikon D780."""

    def __init__(self, session: NikonSession):
        self._session = session
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._live_view_enabled = False

        # Atomic single-frame buffer
        self._latest_frame: Optional[FrameData] = None
        self._frame_lock = threading.Lock()

        # FPS metrics
        self._frame_count = 0
        self._fps_start_time = 0.0
        self._current_fps = 0.0
        self._last_frame_time = 0.0

        # Callback for new frame notification (optional)
        self.on_frame_ready: Optional[Callable[[FrameData], None]] = None
        self._is_af_in_progress = False

    @property
    def is_af_in_progress(self) -> bool:
        return self._is_af_in_progress

    def request_autofocus(
        self,
        callback: Optional[Callable[[bool, str], None]] = None,
        target_point: Optional[Tuple[float, float]] = None,
        frame_size: Optional[Tuple[float, float]] = None
    ) -> None:
        """Kích hoạt lấy nét tự động trên worker luồng nền, đảm bảo UI hoàn toàn không bị đơ/block."""
        if self._is_af_in_progress:
            if callback:
                callback(False, "Đang có một tác vụ lấy nét đang diễn ra.")
            return

        def _af_task():
            self._is_af_in_progress = True
            try:
                ok, msg = self._session.trigger_autofocus(
                    target_point=target_point,
                    frame_size=frame_size,
                    timeout_sec=3.5
                )
                if callback:
                    callback(ok, msg)
            except Exception as ex:
                logger.error("Lỗi khi thực hiện AF trong worker: %s", ex)
                if callback:
                    callback(False, f"Lỗi ngoại lệ AF: {ex}")
            finally:
                self._is_af_in_progress = False

        threading.Thread(target=_af_task, name="NikonMAID-AF-Thread", daemon=True).start()

    def cancel_autofocus(self) -> bool:
        """Hủy thao tác AF nếu khả dụng."""
        return self._session.cancel_autofocus()

    @property
    def is_running(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())

    def start(self) -> None:
        """Bắt đầu luồng worker nền."""
        if self.is_running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="NikonMAID-Worker",
            daemon=True
        )
        self._thread.start()
        logger.info("NikonCameraWorker thread started.")

    def stop(self) -> None:
        """Dừng worker nền."""
        self._running = False
        self._live_view_enabled = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        logger.info("NikonCameraWorker thread stopped.")

    def enable_live_view(self) -> bool:
        """Bật chế độ đọc Live View trong worker."""
        if not self.is_running:
            self.start()

        ok = self._session.start_live_view()
        if ok:
            self._live_view_enabled = True
            self._fps_start_time = time.time()
            self._frame_count = 0
        return ok

    def disable_live_view(self) -> None:
        """Tắt chế độ đọc Live View."""
        self._live_view_enabled = False
        self._session.stop_live_view()
        with self._frame_lock:
            self._latest_frame = None

    def get_latest_frame(self) -> Optional[FrameData]:
        """Lấy khung hình xem trước mới nhất (O(1), không block worker)."""
        with self._frame_lock:
            return self._latest_frame

    def capture(self, timeout_sec: float = 12.0, autofocus_first: bool = False) -> Optional[Image.Image]:
        """
        Thực hiện chụp ảnh tĩnh trên worker và trả về đối tượng PIL Image.
        """
        was_live_view = self._live_view_enabled
        self._live_view_enabled = False

        try:
            raw_jpeg = self._session.capture_photo(timeout_sec=timeout_sec, autofocus_first=autofocus_first)
            if not raw_jpeg:
                return None

            image = Image.open(io.BytesIO(raw_jpeg))
            # Load bytes into memory completely
            image.load()
            return image
        finally:
            if was_live_view:
                self.enable_live_view()

    def _worker_loop(self) -> None:
        """Vòng lặp chính chạy trên luồng nền."""
        frame_window = []

        while self._running:
            if not self._live_view_enabled:
                # Nếu không bật Live View, chỉ pump async định kỳ với tần suất thấp (50ms)
                self._session.pump_async()
                time.sleep(0.05)
                continue

            t_start = time.perf_counter()
            frame_bytes = self._session.fetch_live_view_frame()

            if frame_bytes:
                now = time.time()
                self._frame_count += 1
                frame_window.append(now)

                # Giữ rolling window 1 giây để tính FPS chính xác
                while frame_window and (now - frame_window[0] > 1.0):
                    frame_window.pop(0)

                self._current_fps = len(frame_window) / (now - frame_window[0]) if len(frame_window) > 1 else 30.0

                # Giải mã JPEG sang RGB ngay trên worker thread để UI thread hoàn toàn không bị giật lag
                rgb = None
                try:
                    import cv2
                    import numpy as np
                    nparr = np.frombuffer(frame_bytes, np.uint8)
                    bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if bgr is not None:
                        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                except Exception as ex:
                    logger.debug("Lỗi giải mã JPEG sang RGB trên worker: %s", ex)

                w = rgb.shape[1] if rgb is not None else 1024
                h = rgb.shape[0] if rgb is not None else 680

                frame = FrameData(
                    rgb=rgb,
                    jpeg=frame_bytes,
                    width=w,
                    height=h,
                    fps=self._current_fps,
                    sequence_id=self._frame_count,
                    timestamp=now,
                    is_valid=True
                )

                with self._frame_lock:
                    self._latest_frame = frame

                if self.on_frame_ready:
                    try:
                        self.on_frame_ready(frame)
                    except Exception as ex:
                        logger.debug("on_frame_ready error: %s", ex)

                # Tần số nhắm đến ~30-40 FPS, yield CPU siêu ngắn
                dur = (time.perf_counter() - t_start)
                if dur < 0.02:
                    time.sleep(0.005)
            else:
                self._session.pump_async()
                time.sleep(0.01)
