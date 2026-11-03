"""
1998 TEAM — Photobooth Nikon MAID3 Session & Hardware Controller
Direct USB controller for Nikon D780 implementing high-performance Live View and Still Capture.
"""

import time
import ctypes
import threading
from typing import Optional, List, Dict, Any, Tuple, Callable
import logging

from vietphotobooth.camera.backends.nikon_maid.maid_types import (
    NkMAIDObjectType, NkMAIDCommand, NkMAIDDataType, NkMAIDCapType,
    NkMAIDCapOperations, NkMAIDEvent, NkMAIDCapability,
    NkMAIDLiveViewStatus, NkMAIDLiveViewImageStatus, NkMAIDLiveViewImageSize, NkMAIDSaveMedia,
    NkMAIDResult, NkMAIDObject, NkMAIDCallback, NkMAIDCapInfo,
    NkMAIDString, NkMAIDArray, NkMAIDEnum, NkMAIDFileInfo,
    NkMAIDContrastAF, NkMAIDPoint,
    MAIDEventProc, MAIDCompletionProc, MAIDDataProc
)
from vietphotobooth.camera.backends.nikon_maid.maid_loader import get_loader

logger = logging.getLogger(__name__)


class NikonSession:
    """Quản lý phiên làm việc phần cứng máy ảnh Nikon qua MAID3 Type0026 SDK."""

    def __init__(self):
        self._loader = get_loader()
        self._lock = threading.RLock()

        # MAID Objects
        self._mod_obj: Optional[NkMAIDObject] = None
        self._src_obj: Optional[NkMAIDObject] = None

        # State tracking
        self._is_mod_open = False
        self._is_src_open = False
        self._is_live_view_active = False

        # Discovery & Events
        self._discovered_sources: List[int] = []
        self._new_items: List[int] = []
        self._last_event_time = 0.0

        # Persistent callbacks to prevent garbage collection
        self._mod_event_cb_func = MAIDEventProc(self._on_module_event)
        self._src_event_cb_func = MAIDEventProc(self._on_source_event)

        # Preallocated buffers for live view
        self._lv_array = NkMAIDArray()
        self._lv_buf = None
        self._lv_buf_size = 0
        self._lv_comp_done = False
        self._lv_comp_res = 0
        self._lv_comp_cb_func = MAIDCompletionProc(self._on_lv_complete)

    # --------------------------------------------------------------------------
    # CALLBACKS
    # --------------------------------------------------------------------------

    def _on_module_event(self, ref_client, ul_event, data):
        logger.debug("MAID Module Event: event=%d, data=0x%X", ul_event, data)
        if ul_event == NkMAIDEvent.ADD_CHILD:
            if data not in self._discovered_sources:
                self._discovered_sources.append(data)
                logger.info("Nikon MAID phát hiện thiết bị: Source ID 0x%X", data)
        elif ul_event == NkMAIDEvent.REMOVE_CHILD:
            if data in self._discovered_sources:
                self._discovered_sources.remove(data)
                logger.warning("Nikon MAID thiết bị ngắt kết nối: Source ID 0x%X", data)

    def _on_source_event(self, ref_client, ul_event, data):
        self._last_event_time = time.time()
        logger.debug("MAID Source Event: event=%d, data=0x%X", ul_event, data)
        if ul_event == NkMAIDEvent.ADD_CHILD:
            self._new_items.append(data)
            logger.info("Nikon MAID ảnh chụp mới sẵn sàng: Item ID 0x%X", data)

    def _on_lv_complete(self, p_obj, ul_cmd, ul_param, ul_dt, data, ref_comp, n_result):
        self._lv_comp_done = True
        self._lv_comp_res = n_result

    # --------------------------------------------------------------------------
    # LOW-LEVEL MAID DISPATCH
    # --------------------------------------------------------------------------

    def _entry(self, p_obj, ul_cmd, ul_param, ul_dt, data, pfn_comp, ref_comp) -> int:
        entry_point = self._loader.entry_point
        if entry_point is None:
            return NkMAIDResult.NOT_INITIALIZED if hasattr(NkMAIDResult, "NOT_INITIALIZED") else -117
        obj_addr = ctypes.addressof(p_obj) if p_obj is not None else 0
        fn_addr = ctypes.cast(pfn_comp, ctypes.c_void_p).value if pfn_comp is not None else 0
        return entry_point(
            obj_addr,
            int(ul_cmd),
            int(ul_param),
            int(ul_dt),
            int(data),
            fn_addr,
            int(ref_comp)
        )

    def pump_async(self) -> None:
        """Xử lý hàng đợi asynchronous của SDK."""
        with self._lock:
            if self._src_obj is not None:
                self._entry(self._src_obj, NkMAIDCommand.ASYNC, 0, NkMAIDDataType.NULL, 0, None, 0)
            elif self._mod_obj is not None:
                self._entry(self._mod_obj, NkMAIDCommand.ASYNC, 0, NkMAIDDataType.NULL, 0, None, 0)

    # --------------------------------------------------------------------------
    # MODULE LIFECYCLE
    # --------------------------------------------------------------------------

    def open_module(self) -> Tuple[bool, str]:
        """Khởi tạo Type0026 Module Object."""
        with self._lock:
            if self._is_mod_open and self._mod_obj is not None:
                return True, "Module đã mở."

            loaded, msg = self._loader.load()
            if not loaded:
                return False, msg

            self._mod_obj = NkMAIDObject()
            ret = self._entry(
                None,
                NkMAIDCommand.OPEN,
                0,
                NkMAIDDataType.OBJECT_PTR,
                ctypes.addressof(self._mod_obj),
                None,
                0
            )
            if ret != NkMAIDResult.NO_ERROR:
                self._mod_obj = None
                return False, f"Lỗi khởi tạo MAID Module (mã lỗi: {ret})"

            self._is_mod_open = True

            # Đăng ký EventProc cho Module
            cb = NkMAIDCallback(
                pProc=ctypes.cast(self._mod_event_cb_func, ctypes.c_void_p).value,
                refProc=0
            )
            self._entry(
                self._mod_obj,
                NkMAIDCommand.CAP_SET,
                NkMAIDCapability.EVENT_PROC,
                NkMAIDDataType.CALLBACK_PTR,
                ctypes.addressof(cb),
                None,
                0
            )

            return True, "MAID Module sẵn sàng."

    def close_module(self) -> None:
        """Đóng Module Object và giải phóng tài nguyên."""
        with self._lock:
            if self._is_src_open:
                self.close_camera()

            if self._is_mod_open and self._mod_obj is not None:
                try:
                    self._entry(self._mod_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
                except Exception as ex:
                    logger.warning("Lỗi đóng MAID Module: %s", ex)
                self._mod_obj = None
                self._is_mod_open = False
                self._discovered_sources.clear()

    # --------------------------------------------------------------------------
    # CAMERA ENUMERATION & CONNECTION
    # --------------------------------------------------------------------------

    def enumerate_cameras(self, timeout_sec: float = 1.5) -> List[int]:
        """Dò tìm các camera Nikon kết nối qua USB (kết hợp cả Async Event và Đồng bộ Capability Children)."""
        with self._lock:
            if not self._is_mod_open:
                ok, err = self.open_module()
                if not ok:
                    logger.error("Không thể mở module để dò camera: %s", err)
                    return []

            self._discovered_sources.clear()
            comp_flag = [False]

            self._enum_comp_cb = MAIDCompletionProc(lambda p, c, prm, dt, d, r, res: comp_flag.__setitem__(0, True))

            ret = self._entry(
                self._mod_obj,
                NkMAIDCommand.ENUM_CHILDREN,
                0,
                NkMAIDDataType.NULL,
                0,
                self._enum_comp_cb,
                0
            )
            if ret != NkMAIDResult.NO_ERROR and ret != NkMAIDResult.PENDING:
                logger.debug("EnumChildren code: %d", ret)

            start_t = time.time()
            while not comp_flag[0] and (time.time() - start_t < timeout_sec):
                self.pump_async()
                time.sleep(0.01)

            sources = list(self._discovered_sources)

            # Truy vấn đồng bộ kNkMAIDCapability_Children (7) theo chuẩn Nikon SDK Function.cpp:SelectSource
            if not sources and self._mod_obj is not None:
                try:
                    st_enum = NkMAIDEnum()
                    ret_cg = self._entry(
                        self._mod_obj,
                        NkMAIDCommand.CAP_GET,
                        NkMAIDCapability.CHILDREN,
                        NkMAIDDataType.ENUM_PTR,
                        ctypes.addressof(st_enum),
                        None,
                        0
                    )
                    if ret_cg == NkMAIDResult.NO_ERROR and st_enum.ulElements > 0:
                        buf = (ctypes.c_uint32 * st_enum.ulElements)()
                        st_enum.pData = ctypes.cast(buf, ctypes.c_void_p)
                        ret_cga = self._entry(
                            self._mod_obj,
                            NkMAIDCommand.CAP_GET_ARRAY,
                            NkMAIDCapability.CHILDREN,
                            NkMAIDDataType.ENUM_PTR,
                            ctypes.addressof(st_enum),
                            None,
                            0
                        )
                        if ret_cga == NkMAIDResult.NO_ERROR:
                            for cid in buf:
                                if cid not in sources:
                                    sources.append(int(cid))
                except Exception as ex:
                    logger.debug("Lỗi đọc Children capability: %s", ex)

            return sources

    def open_camera(self, src_id: Optional[int] = None) -> Tuple[bool, str]:
        """Mở phiên điều khiển phần cứng tới camera theo Source ID."""
        with self._lock:
            if self._is_src_open and self._src_obj is not None:
                return True, "Camera đã được kết nối."

            if not self._is_mod_open:
                ok, msg = self.open_module()
                if not ok:
                    return False, msg

            sources = self.enumerate_cameras()
            if not sources:
                return False, "Không tìm thấy máy ảnh Nikon D780 qua kết nối USB."

            target_id = src_id if (src_id is not None and src_id in sources) else sources[0]

            self._src_obj = NkMAIDObject()
            ret = self._entry(
                self._mod_obj,
                NkMAIDCommand.OPEN,
                target_id,
                NkMAIDDataType.OBJECT_PTR,
                ctypes.addressof(self._src_obj),
                None,
                0
            )
            if ret != NkMAIDResult.NO_ERROR:
                self._src_obj = None
                return False, f"Lỗi mở phiên làm việc máy ảnh (mã lỗi: {ret})"

            self._is_src_open = True

            # Đăng ký EventProc cho Camera Source
            cb = NkMAIDCallback(
                pProc=ctypes.cast(self._src_event_cb_func, ctypes.c_void_p).value,
                refProc=0
            )
            self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_SET,
                NkMAIDCapability.EVENT_PROC,
                NkMAIDDataType.CALLBACK_PTR,
                ctypes.addressof(cb),
                None,
                0
            )

            # Đọc tên thiết bị
            name = self.get_string_capability(NkMAIDCapability.NAME)
            logger.info("Đã kết nối Nikon Camera: '%s' (Source ID 0x%X)", name, target_id)
            return True, f"Kết nối thành công máy ảnh {name}."

    def close_camera(self) -> None:
        """Đóng phiên kết nối máy ảnh và trả lại tài nguyên cho hệ thống."""
        with self._lock:
            if self._is_live_view_active:
                self.stop_live_view()

            if self._is_src_open and self._src_obj is not None:
                try:
                    self._entry(self._src_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
                except Exception as ex:
                    logger.warning("Lỗi đóng phiên camera: %s", ex)
                self._src_obj = None
                self._is_src_open = False
                self._new_items.clear()

    # --------------------------------------------------------------------------
    # CAPABILITY ACCESSORS
    # --------------------------------------------------------------------------

    def get_string_capability(self, cap_id: int) -> str:
        """Đọc thuộc tính kiểu String từ máy ảnh."""
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                return ""
            maid_str = NkMAIDString()
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_GET,
                cap_id,
                NkMAIDDataType.STRING_PTR,
                ctypes.addressof(maid_str),
                None,
                0
            )
            if ret == NkMAIDResult.NO_ERROR:
                return maid_str.str.decode("utf-8", errors="ignore").strip()
            return ""

    def get_unsigned_capability(self, cap_id: int) -> Optional[int]:
        """Đọc giá trị số nguyên không dấu từ máy ảnh."""
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                return None
            val = ctypes.c_uint32(0)
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_GET,
                cap_id,
                NkMAIDDataType.UNSIGNED_PTR,
                ctypes.addressof(val),
                None,
                0
            )
            if ret == NkMAIDResult.NO_ERROR:
                return val.value
            return None

    def set_unsigned_capability(self, cap_id: int, value: int) -> bool:
        """Thiết lập giá trị số nguyên không dấu cho máy ảnh."""
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                return False
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_SET,
                cap_id,
                NkMAIDDataType.UNSIGNED,
                value,
                None,
                0
            )
            return ret == NkMAIDResult.NO_ERROR

    def get_enum_capability(self, cap_id: int) -> Optional[int]:
        """Đọc chỉ số lựa chọn hiện tại của capability kiểu Enum."""
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                return None
            st_enum = NkMAIDEnum()
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_GET,
                cap_id,
                NkMAIDDataType.ENUM_PTR,
                ctypes.addressof(st_enum),
                None,
                0
            )
            if ret == NkMAIDResult.NO_ERROR:
                return st_enum.ulValue
            return None

    def set_enum_capability(self, cap_id: int, value: int) -> bool:
        """Thiết lập giá trị cho capability kiểu Enum bằng cách tìm chỉ số tương ứng."""
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                return False

            st_enum = NkMAIDEnum()
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_GET,
                cap_id,
                NkMAIDDataType.ENUM_PTR,
                ctypes.addressof(st_enum),
                None,
                0
            )
            if ret != NkMAIDResult.NO_ERROR:
                # Thử fallback CAP_SET trực tiếp bằng kiểu UNSIGNED nếu CAP_GET thất bại
                ret_direct = self._entry(
                    self._src_obj,
                    NkMAIDCommand.CAP_SET,
                    cap_id,
                    NkMAIDDataType.UNSIGNED,
                    value,
                    None,
                    0
                )
                return ret_direct == NkMAIDResult.NO_ERROR

            target_idx = None
            if st_enum.ulElements > 0:
                elem_count = st_enum.ulElements
                elem_bytes = st_enum.wPhysicalBytes if st_enum.wPhysicalBytes > 0 else 4
                data_buf = (ctypes.c_uint32 * elem_count)()
                st_enum.pData = ctypes.cast(data_buf, ctypes.c_void_p).value

                ret_arr = self._entry(
                    self._src_obj,
                    NkMAIDCommand.CAP_GET_ARRAY,
                    cap_id,
                    NkMAIDDataType.ENUM_PTR,
                    ctypes.addressof(st_enum),
                    None,
                    0
                )
                if ret_arr == NkMAIDResult.NO_ERROR:
                    for i in range(elem_count):
                        if data_buf[i] == value:
                            target_idx = i
                            break

            if target_idx is not None:
                st_enum.ulValue = target_idx
            elif 0 <= value < st_enum.ulElements:
                st_enum.ulValue = value
            elif st_enum.ulElements > 0 and 0 < value <= st_enum.ulElements:
                st_enum.ulValue = value - 1
            else:
                st_enum.ulValue = value

            # Thử CAP_SET với ENUM_PTR
            ret_set = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_SET,
                cap_id,
                NkMAIDDataType.ENUM_PTR,
                ctypes.addressof(st_enum),
                None,
                0
            )
            if ret_set == NkMAIDResult.NO_ERROR:
                return True

            # Fallback 1: Thử CAP_SET với UNSIGNED truyền ulValue
            ret_fb1 = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_SET,
                cap_id,
                NkMAIDDataType.UNSIGNED,
                st_enum.ulValue,
                None,
                0
            )
            if ret_fb1 == NkMAIDResult.NO_ERROR:
                return True

            # Fallback 2: Thử CAP_SET với UNSIGNED truyền giá trị gốc (value)
            ret_fb2 = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_SET,
                cap_id,
                NkMAIDDataType.UNSIGNED,
                value,
                None,
                0
            )
            return ret_fb2 == NkMAIDResult.NO_ERROR

    def get_live_view_image_size(self) -> Optional[int]:
        """Đọc độ phân giải Live View hiện tại (1=QVGA 320x213, 2=VGA 640x424, 3=XGA 1024x680)."""
        return self.get_enum_capability(NkMAIDCapability.LIVE_VIEW_IMAGE_SIZE)

    def set_live_view_image_size(self, size: int = NkMAIDLiveViewImageSize.XGA) -> bool:
        """
        Thiết lập độ phân giải Live View (XGA = 1024x680, VGA = 640x424, QVGA = 320x213).
        Mặc định ưu tiên XGA (1024x680, tỷ lệ 3:2 chuẩn cảm biến full-frame) cho chất lượng cao nhất.
        """
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                return False
            ok = self.set_enum_capability(NkMAIDCapability.LIVE_VIEW_IMAGE_SIZE, int(size))
            if ok:
                logger.info("Đã thiết lập Live View Image Size: %d (XGA=3: 1024x680)", size)
            else:
                logger.warning("Không thể thiết lập Live View Image Size: %d", size)
            return ok

    # --------------------------------------------------------------------------
    # LIVE VIEW
    # --------------------------------------------------------------------------

    def start_live_view(self, timeout_sec: float = 3.0) -> bool:
        """Khởi động luồng Live View trên máy ảnh."""
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                logger.error("Chưa mở kết nối camera để bắt đầu Live View.")
                return False

            if self._is_live_view_active:
                return True

            # Kiểm tra trạng thái cấm Live View
            prohibit = self.get_unsigned_capability(NkMAIDCapability.LIVE_VIEW_PROHIBIT)
            if prohibit is not None and prohibit != 0:
                logger.warning("Camera đang cấm Live View: mã cấm 0x%X", prohibit)

            # Thiết lập độ phân giải Live View tối đa (XGA: 1024 × 680)
            self.set_live_view_image_size(NkMAIDLiveViewImageSize.XGA)

            # Bật Remote Live View (ON_RemoteLV = 3)
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_SET,
                NkMAIDCapability.LIVE_VIEW_STATUS,
                NkMAIDDataType.UNSIGNED,
                NkMAIDLiveViewStatus.ON_REMOTE_LV,
                None,
                0
            )
            if ret != NkMAIDResult.NO_ERROR:
                logger.error("Lỗi gửi lệnh kích hoạt Live View: mã lỗi %d", ret)
                return False

            # Đảm bảo Live View Image Size nhận cấu hình XGA
            self.set_live_view_image_size(NkMAIDLiveViewImageSize.XGA)

            # Đợi cảm biến và cơ cấu lật gương sẵn sàng (LiveViewImageStatus == CanAcquire)
            start_t = time.time()
            st_enum = NkMAIDEnum()
            can_acquire = False

            while (time.time() - start_t) < timeout_sec:
                self.pump_async()
                ret_st = self._entry(
                    self._src_obj,
                    NkMAIDCommand.CAP_GET,
                    NkMAIDCapability.LIVE_VIEW_IMAGE_STATUS,
                    NkMAIDDataType.ENUM_PTR,
                    ctypes.addressof(st_enum),
                    None,
                    0
                )
                if ret_st == NkMAIDResult.NO_ERROR and st_enum.ulValue == NkMAIDLiveViewImageStatus.CAN_ACQUIRE:
                    can_acquire = True
                    break
                time.sleep(0.02)

            if not can_acquire:
                logger.warning("Hết thời gian chờ LiveViewImageStatus sẵn sàng. Vẫn tiếp tục thử đọc.")

            self._is_live_view_active = True
            logger.info("Live View đã được kích hoạt thành công.")
            return True

    def fetch_live_view_frame(self) -> Optional[bytes]:
        """
        Đọc 1 khung hình Live View hiệu năng cao trực tiếp từ bộ đệm SDK.
        Trả về raw JPEG bytes hoặc None nếu chưa có khung hình mới.
        """
        with self._lock:
            if not self._is_live_view_active or self._src_obj is None:
                return None

            src_addr = ctypes.addressof(self._src_obj)

            # 1. Lấy thông tin kích thước mảng ảnh
            ret_cg = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_GET,
                NkMAIDCapability.GET_LIVE_VIEW_IMAGE,
                NkMAIDDataType.ARRAY_PTR,
                ctypes.addressof(self._lv_array),
                None,
                0
            )
            if ret_cg != NkMAIDResult.NO_ERROR:
                self.pump_async()
                return None

            total_bytes = self._lv_array.ulElements * (
                self._lv_array.wPhysicalBytes if self._lv_array.wPhysicalBytes > 0 else 1
            )
            if total_bytes <= 512:
                self.pump_async()
                return None

            # Tái sử dụng buffer bộ nhớ nếu kích thước không đổi để tối ưu GC
            if self._lv_buf is None or self._lv_buf_size != total_bytes:
                self._lv_buf = (ctypes.c_uint8 * total_bytes)()
                self._lv_buf_size = total_bytes

            self._lv_array.pData = ctypes.cast(self._lv_buf, ctypes.c_void_p).value
            self._lv_comp_done = False
            self._lv_comp_res = 0

            # 2. Đọc dữ liệu khung hình bất đồng bộ
            ret_ga = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_GET_ARRAY,
                NkMAIDCapability.GET_LIVE_VIEW_IMAGE,
                NkMAIDDataType.ARRAY_PTR,
                ctypes.addressof(self._lv_array),
                self._lv_comp_cb_func,
                0
            )
            if ret_ga != NkMAIDResult.NO_ERROR and ret_ga != NkMAIDResult.PENDING:
                self.pump_async()
                return None

            # Đợi hoàn thành tải khung hình (thường mất 5-15ms)
            poll_start = time.perf_counter()
            while not self._lv_comp_done and (time.perf_counter() - poll_start < 0.2):
                self._entry(self._src_obj, NkMAIDCommand.ASYNC, 0, NkMAIDDataType.NULL, 0, None, 0)
                time.sleep(0.001)

            if not self._lv_comp_done or self._lv_comp_res != NkMAIDResult.NO_ERROR:
                return None

            # 3. Trích xuất JPEG từ offset 512 (bỏ qua header điều khiển hiển thị)
            raw_bytes = bytes(self._lv_buf)
            if len(raw_bytes) <= 512:
                return None

            soi = raw_bytes.find(b"\xff\xd8", 500)
            if soi == -1:
                soi = raw_bytes.find(b"\xff\xd8")
            if soi == -1:
                return None

            eoi = raw_bytes.rfind(b"\xff\xd9")
            if eoi == -1 or eoi <= soi:
                return raw_bytes[soi:]

            return raw_bytes[soi:eoi + 2]

    def stop_live_view(self) -> None:
        """Dừng luồng Live View và đóng gương lật/cảm biến an toàn."""
        with self._lock:
            if not self._is_live_view_active:
                return

            if self._is_src_open and self._src_obj is not None:
                try:
                    self._entry(
                        self._src_obj,
                        NkMAIDCommand.CAP_SET,
                        NkMAIDCapability.LIVE_VIEW_STATUS,
                        NkMAIDDataType.UNSIGNED,
                        NkMAIDLiveViewStatus.OFF,
                        None,
                        0
                    )
                    time.sleep(0.15)
                    self.pump_async()
                except Exception as ex:
                    logger.warning("Lỗi khi tắt Live View: %s", ex)

            self._is_live_view_active = False
            logger.info("Live View đã được tắt.")

    # --------------------------------------------------------------------------
    # AUTOFOCUS CONTROLS
    # --------------------------------------------------------------------------

    def set_contrast_af_area(
        self,
        x: float,
        y: float,
        src_width: Optional[float] = None,
        src_height: Optional[float] = None
    ) -> bool:
        """
        Thiết lập tọa độ điểm lấy nét tự động (Contrast AF Area) trong Remote Live View.
        Tọa độ (x, y) tính theo không gian tọa độ Live View của Nikon D780 (chuẩn XGA 1024x680).
        Hỗ trợ tự động chuyển đổi tỉ lệ (scale) từ kích thước khung hình detector nguồn
        hoặc tọa độ chuẩn hóa [0.0 .. 1.0] sang chuẩn XGA 1024x680.
        """
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                return False

            # Xử lý tọa độ chuẩn hóa [0.0 .. 1.0]
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and (src_width is None or src_width <= 1.0):
                target_x = x * 1024.0
                target_y = y * 680.0
            # Xử lý co giãn từ kích thước frame nguồn bất kỳ sang không gian XGA 1024x680
            elif src_width and src_height and src_width > 0 and src_height > 0:
                target_x = (float(x) / float(src_width)) * 1024.0
                target_y = (float(y) / float(src_height)) * 680.0
            else:
                target_x = float(x)
                target_y = float(y)

            # Kẹp tọa độ trong phạm vi hợp lệ của XGA Live View (1024x680)
            clamped_x = max(0, min(1023, int(round(target_x))))
            clamped_y = max(0, min(679, int(round(target_y))))

            pt = NkMAIDPoint(x=clamped_x, y=clamped_y)
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_SET,
                NkMAIDCapability.CONTRAST_AF_AREA,
                NkMAIDDataType.POINT_PTR,
                ctypes.addressof(pt),
                None,
                0
            )
            if ret != NkMAIDResult.NO_ERROR:
                logger.debug("[NikonMAID] Không thể đặt ContrastAFArea (%d, %d): mã %d", clamped_x, clamped_y, ret)
                return False
            logger.info(
                "[NikonMAID] Đã đặt ContrastAFArea tại (%d, %d) [nguồn=(%.1f, %.1f), frame=%s]",
                clamped_x, clamped_y, x, y, f"{src_width}x{src_height}" if src_width else "1024x680"
            )
            return True

    def trigger_autofocus(
        self,
        target_point: Optional[Tuple[float, float]] = None,
        frame_size: Optional[Tuple[float, float]] = None,
        timeout_sec: float = 3.5
    ) -> Tuple[bool, str]:
        """
        Kích hoạt lệnh lấy nét tự động một lần tới Nikon D780:
        - Nếu Live View đang BẬT: Sử dụng giao thức Contrast AF (kNkMAIDCapability_ContrastAF = 0x8240).
          (Phase Detection AF Cap ID 29 bị cấm trong Live View theo tài liệu Nikon Type0026).
          Nếu có target_point (x, y), định vị điểm lấy nét bằng kNkMAIDCapability_ContrastAFArea (0x824A).
        - Nếu Live View đang TẮT: Sử dụng giao thức Phase Detection AF chuẩn (Cap ID 29, START).

        TUYỆT ĐỐI KHÔNG giải phóng màn trập / không chụp ảnh.
        Tối ưu hóa: Nhả lock trong chu kỳ đợi để luồng Live View tiếp tục đọc khung hình
        mượt mà (~30-40 FPS) mà không bị đóng băng/đơ khi mô-tơ lấy nét đang quay.
        """
        start_mono = time.perf_counter()

        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                return False, "Chưa kết nối máy ảnh để lấy nét."
            is_lv = self._is_live_view_active

        if is_lv:
            # ------------------------------------------------------------------
            # LUỒNG A: LIVE VIEW CONTRAST AF (D780 qua Live View)
            # ------------------------------------------------------------------
            if target_point is not None:
                try:
                    px, py = target_point[0], target_point[1]
                    fw = float(frame_size[0]) if frame_size else None
                    fh = float(frame_size[1]) if frame_size else None
                    if fw is not None and fh is not None:
                        self.set_contrast_af_area(px, py, src_width=fw, src_height=fh)
                    else:
                        self.set_contrast_af_area(px, py)
                except Exception as ex:
                    logger.debug("[NikonMAID] Bỏ qua lỗi thiết lập ContrastAFArea: %s", ex)

            # Phát lệnh START cho ContrastAF (0x00)
            with self._lock:
                logger.info("[NikonMAID] Phát lệnh CAP_SET(CONTRAST_AF=START, 0x8240) trong Live View...")
                ret = self._entry(
                    self._src_obj,
                    NkMAIDCommand.CAP_SET,
                    NkMAIDCapability.CONTRAST_AF,
                    NkMAIDDataType.UNSIGNED,
                    NkMAIDContrastAF.START,
                    None,
                    0
                )
                if ret != NkMAIDResult.NO_ERROR:
                    if ret == NkMAIDResult.NOT_SUPPORTED:
                        logger.warning("[NikonMAID] Contrast AF Not Supported (gạt MF hoặc không hỗ trợ AF trong Live View).")
                        return False, "Ống kính đang ở chế độ Manual Focus (MF) hoặc Contrast AF không khả dụng."
                    elif ret == NkMAIDResult.DEVICE_BUSY:
                        logger.warning("[NikonMAID] Máy ảnh đang bận (DEVICE_BUSY=152).")
                        return False, "Máy ảnh đang bận xử lý thao tác khác."
                    logger.error("[NikonMAID] Lỗi khởi động Contrast AF: mã %d", ret)
                    return False, f"Lỗi khởi động Contrast AF: mã {ret}"

            # Chờ hoàn thành: Định kỳ đọc trạng thái Contrast AF ngoài lock để không block luồng Live View
            start_t = time.time()
            final_status = None
            saw_busy = False
            time.sleep(0.04)  # Đợi 40ms để máy ảnh tiếp nhận lệnh và chuyển sang trạng thái BUSY (0x12)

            while (time.time() - start_t) < timeout_sec:
                self.pump_async()
                status_val = self.get_unsigned_capability(NkMAIDCapability.CONTRAST_AF)
                if status_val is not None:
                    if status_val == NkMAIDContrastAF.BUSY:
                        saw_busy = True
                    elif status_val == NkMAIDContrastAF.OK:
                        if saw_busy or (time.time() - start_t >= 0.08):
                            final_status = NkMAIDContrastAF.OK
                            break
                    elif status_val == NkMAIDContrastAF.OUT_OF_FOCUS:
                        if saw_busy or (time.time() - start_t >= 0.08):
                            final_status = NkMAIDContrastAF.OUT_OF_FOCUS
                            break
                time.sleep(0.025)

            elapsed_ms = (time.perf_counter() - start_mono) * 1000.0

            if final_status == NkMAIDContrastAF.OK:
                logger.info("[NikonMAID] Live View Contrast AF thành công (In Focus) trong %.1fms.", elapsed_ms)
                return True, "Lấy nét thành công (In Focus)."
            elif final_status == NkMAIDContrastAF.OUT_OF_FOCUS:
                logger.warning("[NikonMAID] Live View Contrast AF thất bại (Out of Focus) sau %.1fms.", elapsed_ms)
                return False, "Mất nét (Out of Focus). Vui lòng thử lại với chủ thể rõ nét hơn."
            else:
                self.cancel_autofocus()
                logger.warning("[NikonMAID] Hết thời gian chờ Contrast AF hoàn thành (timeout %.1fs, elapsed %.1fms)", timeout_sec, elapsed_ms)
                return False, "Quá thời gian phản hồi lấy nét từ máy ảnh."

        else:
            # ------------------------------------------------------------------
            # LUỒNG B: OVF / NON-LIVEVIEW PHASE-DETECTION AF (Cap ID 29)
            # ------------------------------------------------------------------
            af_done = [False]
            af_res = [0]

            @MAIDCompletionProc
            def on_af_complete(p_obj, ul_cmd, ul_param, ul_dt, data, ref_comp, n_result):
                af_done[0] = True
                af_res[0] = n_result

            with self._lock:
                logger.info("[NikonMAID] Phát lệnh CAP_START(AUTOFOCUS, CapID=29) tới Nikon D780...")
                ret = self._entry(
                    self._src_obj,
                    NkMAIDCommand.CAP_START,
                    NkMAIDCapability.AUTOFOCUS,
                    NkMAIDDataType.NULL,
                    0,
                    on_af_complete,
                    0
                )

                if ret != NkMAIDResult.NO_ERROR and ret != NkMAIDResult.PENDING:
                    if ret == NkMAIDResult.OUT_OF_FOCUS:
                        logger.warning("[NikonMAID] Máy ảnh báo Out of Focus ngay khi phát lệnh AF (mã 137).")
                        return False, "Không thể lấy nét (Out of Focus). Vui lòng điều chỉnh khoảng cách hoặc ánh sáng."
                    elif ret == NkMAIDResult.NOT_SUPPORTED:
                        logger.warning("[NikonMAID] Máy ảnh báo AF Not Supported (gạt MF hoặc không hỗ trợ AF).")
                        return False, "Ống kính đang gạt ở chế độ Manual Focus (MF) hoặc chế độ AF không khả dụng."
                    elif ret == NkMAIDResult.DEVICE_BUSY:
                        logger.warning("[NikonMAID] Máy ảnh đang bận (DEVICE_BUSY=152).")
                        return False, "Máy ảnh đang bận xử lý thao tác khác."
                    logger.error("[NikonMAID] Lỗi khởi động lấy nét tự động: mã %d", ret)
                    return False, f"Lỗi khởi động lấy nét tự động: mã {ret}"

            start_t = time.time()
            while not af_done[0] and (time.time() - start_t < timeout_sec):
                self.pump_async()
                time.sleep(0.015)

            elapsed_ms = (time.perf_counter() - start_mono) * 1000.0

            if not af_done[0]:
                logger.warning("[NikonMAID] Hết thời gian chờ phản hồi lấy nét (timeout %.1fs, elapsed %.1fms)", timeout_sec, elapsed_ms)
                return False, "Quá thời gian phản hồi lấy nét từ máy ảnh."

            res = af_res[0]
            if res == NkMAIDResult.NO_ERROR:
                logger.info("[NikonMAID] Nikon D780 lấy nét thành công (In Focus) trong %.1fms.", elapsed_ms)
                return True, "Lấy nét thành công (In Focus)."
            elif res == NkMAIDResult.OUT_OF_FOCUS:
                logger.warning("[NikonMAID] Nikon D780 mất nét (Out of Focus, mã 137) sau %.1fms.", elapsed_ms)
                return False, "Mất nét (Out of Focus). Vui lòng thử lại với chủ thể rõ nét hơn."
            elif res == NkMAIDResult.NOT_SUPPORTED:
                logger.warning("[NikonMAID] Nikon D780 báo NOT_SUPPORTED trong completion callback sau %.1fms.", elapsed_ms)
                return False, "Ống kính đang ở chế độ MF hoặc không hỗ trợ AF."
            elif res == NkMAIDResult.DEVICE_BUSY:
                logger.warning("[NikonMAID] Nikon D780 báo DEVICE_BUSY trong completion callback sau %.1fms.", elapsed_ms)
                return False, "Máy ảnh đang bận."
            else:
                logger.warning("[NikonMAID] Lấy nét thất bại với mã kết quả: %d sau %.1fms.", res, elapsed_ms)
                return False, f"Lấy nét thất bại: mã lỗi {res}"

    def cancel_autofocus(self) -> bool:
        """Hủy thao tác lấy nét tự động nếu đang diễn ra."""
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                return False
            is_lv = self._is_live_view_active

        if is_lv:
            logger.info("[NikonMAID] Dừng Contrast AF trong Live View (CAP_SET CONTRAST_AF=STOP)...")
            return self.set_unsigned_capability(NkMAIDCapability.CONTRAST_AF, NkMAIDContrastAF.STOP)
        else:
            with self._lock:
                try:
                    ret = self._entry(
                        self._src_obj,
                        NkMAIDCommand.ABORT,
                        0,
                        NkMAIDDataType.NULL,
                        0,
                        None,
                        0
                    )
                    return ret == NkMAIDResult.NO_ERROR
                except Exception as ex:
                    logger.debug("Lỗi gửi lệnh Abort AF: %s", ex)
                    return False

    # --------------------------------------------------------------------------
    # STILL CAPTURE
    # --------------------------------------------------------------------------

    def capture_photo(
        self,
        timeout_sec: float = 12.0,
        autofocus_first: bool = False,
        on_capture_start: Optional[Callable[[], None]] = None
    ) -> Optional[bytes]:
        """
        Kích hoạt màn trập, nhận luồng dữ liệu gốc và trả về ảnh JPEG nguyên bản.
        Hỗ trợ tự động xử lý chế độ Mup (Mirror Up) / 2-step release và tùy chọn lấy nét trước khi bấm máy.
        """
        with self._lock:
            if not self._is_src_open or self._src_obj is None:
                logger.error("Chưa mở kết nối camera để chụp ảnh.")
                return None

            if autofocus_first:
                logger.info("Thực hiện lấy nét tự động trước khi chụp ảnh...")
                af_ok, af_msg = self.trigger_autofocus(timeout_sec=2.5)
                logger.info("Kết quả lấy nét trước chụp: %s (%s)", af_ok, af_msg)

            # Tạm dừng Live View trước khi chụp nếu đang bật để tránh xung đột tài nguyên
            was_live_view = self._is_live_view_active
            if was_live_view:
                self.stop_live_view()
                time.sleep(0.1)

            # Thiết lập lưu trực tiếp vào SDRAM
            self.set_unsigned_capability(NkMAIDCapability.SAVE_MEDIA, NkMAIDSaveMedia.SDRAM)

            self._new_items.clear()
            cap_done = [False]
            cap_res = [0]

            @MAIDCompletionProc
            def on_cap_complete(p, c, prm, dt, d, r, res):
                cap_done[0] = True
                cap_res[0] = res

            # Bắn phát thứ nhất
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_START,
                NkMAIDCapability.CAPTURE,
                NkMAIDDataType.NULL,
                0,
                on_cap_complete,
                0
            )

            # Mốc capture-start thành công: kích hoạt âm thanh màn trập ngay khi camera chấp nhận lệnh
            if on_capture_start and ret in (NkMAIDResult.SUCCESS, NkMAIDResult.WAITING_2ND_RELEASE, 0):
                try:
                    on_capture_start()
                except Exception as ex:
                    logger.debug(f"[NikonSession] Ngoại lệ khi gọi on_capture_start callback: {ex}")

            time.sleep(0.3)
            self.pump_async()

            # Nếu máy ảnh ở chế độ Mirror-Up (Mup) hoặc Exposure Delay
            if cap_res[0] == NkMAIDResult.WAITING_2ND_RELEASE or ret == NkMAIDResult.WAITING_2ND_RELEASE:
                logger.info("Phát hiện chế độ Mirror-Up (Waiting_2ndRelease). Kích hoạt lần nhả màn trập thứ 2...")
                cap_done[0] = False
                self._entry(
                    self._src_obj,
                    NkMAIDCommand.CAP_START,
                    NkMAIDCapability.CAPTURE,
                    NkMAIDDataType.NULL,
                    0,
                    on_cap_complete,
                    0
                )

            # Chờ sự kiện ADD_CHILD báo ảnh đã sẵn sàng trong SDRAM
            wait_start = time.time()
            while len(self._new_items) == 0 and (time.time() - wait_start < timeout_sec):
                self.pump_async()
                time.sleep(0.01)

            if not self._new_items:
                logger.error("Hết thời gian chờ ảnh chụp từ camera (timeout %0.1fs).", timeout_sec)
                if was_live_view:
                    self.start_live_view()
                return None

            item_id = self._new_items.pop()
            item_obj = NkMAIDObject()
            ret_io = self._entry(
                self._src_obj,
                NkMAIDCommand.OPEN,
                item_id,
                NkMAIDDataType.OBJECT_PTR,
                ctypes.addressof(item_obj),
                None,
                0
            )
            if ret_io != NkMAIDResult.NO_ERROR:
                logger.error("Không thể mở Item Object (0x%X): mã lỗi %d", item_id, ret_io)
                if was_live_view:
                    self.start_live_view()
                return None

            # Mở DataObj (kNkMAIDDataObjType_Image = 1)
            dat_obj = NkMAIDObject()
            ret_do = self._entry(
                item_obj,
                NkMAIDCommand.OPEN,
                1,
                NkMAIDDataType.OBJECT_PTR,
                ctypes.addressof(dat_obj),
                None,
                0
            )
            if ret_do != NkMAIDResult.NO_ERROR:
                logger.error("Không thể mở Data Object: mã lỗi %d", ret_do)
                self._entry(item_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
                if was_live_view:
                    self.start_live_view()
                return None

            # Đăng ký DataProc để hứng các chunk dữ liệu tải về PC
            chunks = []

            @MAIDDataProc
            def on_chunk(ref_client, p_info, p_data):
                finfo = ctypes.cast(p_info, ctypes.POINTER(NkMAIDFileInfo)).contents
                chunk = bytes((ctypes.c_uint8 * finfo.ulLength).from_address(p_data))
                chunks.append(chunk)
                return NkMAIDResult.NO_ERROR

            data_cb = NkMAIDCallback(
                pProc=ctypes.cast(on_chunk, ctypes.c_void_p).value,
                refProc=0
            )
            self._entry(
                dat_obj,
                NkMAIDCommand.CAP_SET,
                NkMAIDCapability.DATA_PROC,
                NkMAIDDataType.CALLBACK_PTR,
                ctypes.addressof(data_cb),
                None,
                0
            )

            # Kích hoạt ACQUIRE
            acq_done = [False]

            @MAIDCompletionProc
            def on_acq_comp(p, c, prm, dt, d, r, res):
                acq_done[0] = True

            self._entry(
                dat_obj,
                NkMAIDCommand.CAP_START,
                NkMAIDCapability.ACQUIRE,
                NkMAIDDataType.NULL,
                0,
                on_acq_comp,
                0
            )

            acq_start = time.time()
            while not acq_done[0] and (time.time() - acq_start < timeout_sec):
                self._entry(dat_obj, NkMAIDCommand.ASYNC, 0, 0, 0, None, 0)
                time.sleep(0.005)

            full_data = b"".join(chunks)
            logger.info("Tải ảnh hoàn tất: %d bytes (trong %0.2fs)", len(full_data), time.time() - acq_start)

            # Đóng DataObj và ItemObj
            try:
                self._entry(dat_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
                self._entry(item_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
            except Exception as ex:
                logger.warning("Lỗi đóng đối tượng Item/Data: %s", ex)

            # Khôi phục Live View nếu trước đó đang bật
            if was_live_view:
                self.start_live_view()

            # Trích xuất JPEG hợp lệ
            soi = full_data.find(b"\xff\xd8")
            eoi = full_data.rfind(b"\xff\xd9")
            if soi != -1 and eoi != -1 and eoi > soi:
                return full_data[soi:eoi + 2]

            return full_data if len(full_data) > 0 else None
