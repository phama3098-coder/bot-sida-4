"""
1998 TEAM — Photobooth Nikon D780 Native USB Camera Backend
Implements the CameraBackendBase contract using the Nikon MAID3 SDK for zero-latency direct USB communication.
"""

from typing import Dict, Any, List, Optional, Tuple, Callable
from PIL import Image
import logging

from vietphotobooth.camera.backends.base import CameraBackendBase
from vietphotobooth.camera.models import (
    ConnectionState, CameraError, CameraCapabilities, CameraDeviceInfo, FrameData
)
from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
from vietphotobooth.camera.backends.nikon_maid.camera_worker import NikonCameraWorker
from vietphotobooth.camera.backends.nikon_maid.maid_types import NkMAIDCapability

logger = logging.getLogger(__name__)


class NikonD780Backend(CameraBackendBase):
    """Backend kết nối máy ảnh Nikon D780 trực tiếp qua USB bằng Nikon MAID3 Type0026 SDK."""

    def __init__(self):
        self._session = NikonSession()
        self._worker: Optional[NikonCameraWorker] = None
        self._status = ConnectionState.DISCONNECTED
        self._last_error: Optional[CameraError] = None
        self._device_info: Optional[CameraDeviceInfo] = None

    @property
    def backend_type(self) -> str:
        return "nikon_maid"

    @property
    def display_name(self) -> str:
        return "Nikon D780 (Native USB MAID SDK)"

    def discover_devices(self) -> List[CameraDeviceInfo]:
        """Dò tìm máy ảnh Nikon D780 qua USB."""
        devices = []
        try:
            # Nếu thiết bị đang trong phiên kết nối hoạt động, trả về trực tiếp thông tin hiện tại
            if self._device_info and self._status in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE):
                return [self._device_info]

            # Kiểm tra nhanh Windows PnP Device cho Nikon D780 đang kết nối thực tế (VID 04B0, PID 0446)
            pnp_found = False
            try:
                import subprocess
                out = subprocess.check_output(
                    "pnputil /enum-devices /class WPD /connected",
                    text=True,
                    timeout=0.6,
                    stderr=subprocess.DEVNULL
                )
                if ("04B0&PID_0446" in out or "D780" in out) and "Status: Started" in out:
                    pnp_found = True
            except Exception:
                pass

            # Chỉ thăm dò qua SDK nếu PnP xác nhận có thiết bị hoặc đã mở module
            sources = []
            if pnp_found or getattr(self._session, "_is_mod_open", False):
                sources = self._session.enumerate_cameras(timeout_sec=0.5)

            if sources or pnp_found:
                device = CameraDeviceInfo(
                    id="nikon_d780_usb",
                    name="Nikon D780 (Native USB)",
                    backend=self.backend_type,
                    path="USB\\VID_04B0&PID_0446",
                    is_virtual=False,
                    is_default=True,
                    actual_width=6048,
                    actual_height=4024,
                    fps=38.0,
                    status_text="Sẵn sàng kết nối trực tiếp qua USB",
                    capabilities=self.get_capabilities()
                )
                devices.append(device)
        except Exception as ex:
            logger.error("Lỗi khi quét thiết bị Nikon MAID: %s", ex)
        return devices

    def connect(self, device_id: Any = None) -> bool:
        """Kết nối tới máy ảnh Nikon D780 và khởi tạo worker nền."""
        self._status = ConnectionState.CONNECTING
        self._last_error = None

        try:
            ok, msg = self._session.open_camera()
            if not ok:
                self._status = ConnectionState.ERROR
                self._last_error = CameraError(
                    code="NIKON_CONNECT_FAILED",
                    message="Không thể kết nối máy ảnh Nikon D780.",
                    tech_detail=msg,
                    suggestion="Đảm bảo máy ảnh đã bật nguồn, cắm cáp USB và tắt các ứng dụng khác đang chiếm quyền camera (NX Tether, digiCamControl)."
                )
                logger.error("Kết nối thất bại: %s", msg)
                return False

            cam_name = self._session.get_string_capability(NkMAIDCapability.NAME) or "Nikon D780"
            self._device_info = CameraDeviceInfo(
                id="nikon_d780_usb",
                name=f"{cam_name} (Native USB)",
                backend=self.backend_type,
                path="USB\\VID_04B0&PID_0446",
                actual_width=6048,
                actual_height=4024,
                fps=38.0,
                status_text="Đã kết nối trực tiếp qua USB",
                capabilities=self.get_capabilities()
            )

            # Khởi tạo worker nền
            self._worker = NikonCameraWorker(self._session)
            self._worker.start()

            self._status = ConnectionState.CONNECTED
            logger.info("Kết nối thành công máy ảnh Nikon D780.")
            return True

        except Exception as ex:
            self._status = ConnectionState.ERROR
            self._last_error = CameraError(
                code="NIKON_INIT_EXCEPTION",
                message="Xảy ra ngoại lệ khi kết nối Nikon D780.",
                tech_detail=str(ex),
                suggestion="Khởi động lại máy ảnh hoặc cắm lại cổng USB."
            )
            logger.exception("Ngoại lệ khi kết nối Nikon D780: %s", ex)
            return False

    def disconnect(self) -> None:
        """Ngắt kết nối an toàn và giải phóng tài nguyên phần cứng."""
        logger.info("Đang ngắt kết nối Nikon D780...")
        if self._worker is not None:
            self._worker.stop()
            self._worker = None

        self._session.close_camera()
        self._session.close_module()
        self._status = ConnectionState.DISCONNECTED
        self._device_info = None
        logger.info("Đã ngắt kết nối Nikon D780 hoàn toàn.")

    def get_status(self) -> ConnectionState:
        return self._status

    def get_error(self) -> Optional[CameraError]:
        return self._last_error

    def start_live_view(self) -> bool:
        """Bắt đầu luồng xem trước trực tiếp (Live View)."""
        if self._status not in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE):
            logger.warning("Không thể bật Live View khi camera chưa kết nối.")
            return False

        if self._worker is None:
            return False

        self._status = ConnectionState.LIVE_VIEW_STARTING
        ok = self._worker.enable_live_view()
        if ok:
            self._status = ConnectionState.LIVE_VIEW_ACTIVE
            logger.info("Live View hoạt động.")
            return True
        else:
            self._status = ConnectionState.CONNECTED
            self._last_error = CameraError(
                code="NIKON_LV_START_FAILED",
                message="Không thể bật Live View trên Nikon D780.",
                suggestion="Kiểm tra xem chế độ Live View trên máy ảnh có bị khóa không."
            )
            return False

    def read_frame(self) -> Optional[FrameData]:
        """Đọc 1 khung hình Live View hợp lệ từ bộ đệm O(1) của worker nền."""
        if self._worker is None or self._status != ConnectionState.LIVE_VIEW_ACTIVE:
            return None
        return self._worker.get_latest_frame()

    def stop_live_view(self) -> None:
        """Dừng luồng Live View."""
        if self._worker is not None:
            self._worker.disable_live_view()
        if self._status == ConnectionState.LIVE_VIEW_ACTIVE:
            self._status = ConnectionState.CONNECTED
        logger.info("Live View đã dừng.")

    def autofocus(
        self,
        callback: Optional[Callable[[bool, str], None]] = None,
        target_point: Optional[Tuple[float, float]] = None,
        frame_size: Optional[Tuple[float, float]] = None
    ) -> Tuple[bool, str]:
        """
        Kích hoạt lấy nét tự động một lần trên Nikon D780.
        Nếu truyền callback, thực hiện phi chặn (asynchronous) trên worker thread để UI không giật lag.
        target_point: (x, y) trong không gian tọa độ Live View để định vị Contrast AF box.
        frame_size: (w, h) của khung hình detector để tự động scale chính xác sang XGA (1024x680).
        """
        if self._status not in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE):
            msg = "Máy ảnh chưa kết nối để thực hiện lấy nét."
            if callback:
                callback(False, msg)
            return False, msg

        if self._worker is not None and callback is not None:
            self._worker.request_autofocus(callback=callback, target_point=target_point, frame_size=frame_size)
            return True, "Đang thực hiện lấy nét tự động..."
        else:
            return self._session.trigger_autofocus(target_point=target_point, frame_size=frame_size)

    def cancel_autofocus(self) -> bool:
        """Hủy thao tác lấy nét nếu đang diễn ra."""
        if self._worker is not None:
            return self._worker.cancel_autofocus()
        return self._session.cancel_autofocus()

    def diagnose_af(
        self,
        target_point: Optional[Tuple[float, float]] = None,
        frame_size: Optional[Tuple[float, float]] = None
    ) -> Dict[str, Any]:
        """
        Thực hiện một chu trình chẩn đoán AF chuyên sâu theo chuẩn Nikon MAID:
        - Kiểm tra Focus Mode (MF hay AF-S/AF-C).
        - Kiểm tra Live View Status.
        - Gửi đúng 1 lệnh AF (Contrast AF nếu Live View ON, Phase Detection nếu Live View OFF).
        - Ghi nhận thời gian phản hồi, trạng thái hoàn tất và mã kết quả.
        - Tuyệt đối không chụp ảnh, không gửi lệnh lặp lại liên tục.
        """
        t0 = time.perf_counter()
        diag: Dict[str, Any] = {
            "timestamp": time.time(),
            "connection_state": self._status.value,
            "live_view_active": (self._status == ConnectionState.LIVE_VIEW_ACTIVE),
            "target_point": target_point,
            "frame_size": frame_size,
            "backend": "nikon_maid",
        }

        # 1. Đọc Focus Mode
        focus_mode = self._session.get_unsigned_capability(NkMAIDCapability.FOCUS_MODE)
        diag["focus_mode_raw"] = focus_mode
        focus_mode_str = "MF (Manual Focus)" if focus_mode == 0 else f"AF (Mode {focus_mode})" if focus_mode is not None else "Unknown"
        diag["focus_mode_str"] = focus_mode_str

        # 2. Đọc Live View Status
        lv_status = self._session.get_unsigned_capability(NkMAIDCapability.LIVE_VIEW_STATUS)
        diag["live_view_status_raw"] = lv_status

        # 3. Đọc pin
        battery = self._session.get_unsigned_capability(NkMAIDCapability.BATTERY_LEVEL)
        diag["battery_percent"] = battery

        # Kiểm tra trước lệnh: Nếu MF thì báo từ chối
        if focus_mode == 0:
            diag["success"] = False
            diag["category"] = "MAID_REJECTED"
            diag["message"] = "Ống kính hoặc thân máy đang gạt ở chế độ lấy nét tay Manual Focus (MF). Vui lòng gạt sang M/A hoặc AF."
            diag["duration_ms"] = (time.perf_counter() - t0) * 1000.0
            return diag

        # 4. Kích hoạt đúng 1 lệnh AF đồng bộ để đo chính xác thời gian
        ok, msg = self._session.trigger_autofocus(target_point=target_point, frame_size=frame_size, timeout_sec=4.0)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        diag["duration_ms"] = dur_ms
        diag["success"] = ok
        diag["message"] = msg

        if ok:
            diag["category"] = "SUCCESS_IN_FOCUS"
        elif "out of focus" in msg.lower() or "mất nét" in msg.lower():
            diag["category"] = "MAID_COMPLETED_OUT_OF_FOCUS"
        elif "thời gian" in msg.lower() or "timeout" in msg.lower():
            diag["category"] = "MAID_NOT_COMPLETED"
        else:
            diag["category"] = "MAID_REJECTED"

        return diag

    def capture_photo(self, autofocus_first: bool = False, on_capture_start: Optional[Callable[[], None]] = None) -> Optional[Image.Image]:
        """Chụp ảnh tĩnh độ phân giải cao (6048 x 4024) và trả về PIL Image."""
        if self._worker is None or self._status not in (ConnectionState.CONNECTED, ConnectionState.LIVE_VIEW_ACTIVE):
            self._last_error = CameraError(
                code="NIKON_NOT_READY",
                message="Máy ảnh chưa sẵn sàng để chụp ảnh."
            )
            return None

        try:
            image = self._worker.capture(timeout_sec=12.0, autofocus_first=autofocus_first, on_capture_start=on_capture_start)
            if image is None:
                self._last_error = CameraError(
                    code="NIKON_CAPTURE_FAILED",
                    message="Không thể chụp ảnh hoặc tải ảnh từ Nikon D780.",
                    suggestion="Kiểm tra pin, thẻ nhớ hoặc chế độ lấy nét của ống kính."
                )
            return image
        except Exception as ex:
            self._last_error = CameraError(
                code="NIKON_CAPTURE_EXCEPTION",
                message="Lỗi ngoại lệ khi chụp ảnh.",
                tech_detail=str(ex)
            )
            logger.exception("Ngoại lệ khi chụp ảnh: %s", ex)
            return None

    def get_capabilities(self) -> CameraCapabilities:
        """Khả năng phần cứng của Nikon D780."""
        return CameraCapabilities(
            can_capture=True,
            can_liveview=True,
            can_download=True,
            can_adjust_parameters=True,
            can_autofocus=True,
            supported_resolutions=[
                (6048, 4024),  # Full 24.5 MP
                (4528, 3016),  # Medium
                (3024, 2016),  # Small
            ],
            supported_fps=[24.0, 30.0, 38.0],
            format_name="JPEG/RGB"
        )

    def get_parameters(self) -> Dict[str, Any]:
        """Đọc các thông số hiện tại của Nikon D780."""
        params = {}
        battery = self._session.get_unsigned_capability(NkMAIDCapability.BATTERY_LEVEL)
        if battery is not None:
            params["battery_percent"] = battery
        return params
