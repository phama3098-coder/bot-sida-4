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


# Tập mã lỗi phần cứng / handle mất kết nối bắt buộc mở mạch ngắt (_device_lost = True)
DEVICE_LOST_MAID_RESULTS = frozenset(
    {
        -116,  # kNkMAIDResult_HardwareError
        -117,  # kNkMAIDResult_UnexpectedError
        -119,  # kNkMAIDResult_ZombieObject
        int(NkMAIDResult.HARDWARE_ERROR),
        int(NkMAIDResult.UNEXPECTED_ERROR),
        int(NkMAIDResult.ZOMBIE_OBJECT),
    }
)


class NikonSession:
    """Quản lý phiên làm việc phần cứng máy ảnh Nikon qua MAID3 Type0026 SDK.

    Ghi chú thiết kế an toàn (Phase 2.1):
    - Tất cả đối tượng callback ctypes CFUNCTYPE truyền xuống MAID SDK được giữ tham chiếu bền vững
      trên instance `self` (`_persistent_callbacks` & `_retained_callbacks`), tuyệt đối không bị
      Garbage Collector giải phóng khi hàm gọi bị timeout.
    - Hàng đợi `_new_items` được xử lý nghiêm ngặt theo thứ tự FIFO (`pop(0)`), không bị `.clear()`
      trước khi chụp.
    - Chỉ thực hiện drain SDRAM khi `_device_lost == False`. Không tuyên bố cứu được dữ liệu còn nằm
      trong SDRAM của máy ảnh sau khi cáp USB vật lý đã bị rút.
    - Buffer ảnh đã nhận đủ vào RAM Worker (`COMPLETE_IN_RAM`) chỉ được bảo đảm lưu khi Worker còn sống.
    - Khi nhận `REMOVE_CHILD` hoặc mã lỗi `-116`/`-117`/`-119`, mạch ngắt `_device_lost` lập tức kích hoạt
      và chặn mọi lời gọi `MAIDEntryPoint` tiếp theo vào `SourceObj`/`ItemObj`/`DataObj` đã mất kết nối.
    """

    def __init__(self):
        self._loader = get_loader()
        self._lock = threading.RLock()

        # MAID Objects
        self._mod_obj: Optional[NkMAIDObject] = None
        self._src_obj: Optional[NkMAIDObject] = None
        self._active_src_id: Optional[int] = None

        # State tracking & Device-Lost Circuit Breaker
        self._is_mod_open = False
        self._is_src_open = False
        self._is_live_view_active = False
        self._device_lost = False
        self._device_lost_reason = ""

        # Discovery & Events (FIFO Queue for SDRAM Item IDs)
        self._discovered_sources: List[int] = []
        self._new_items: List[int] = []
        self._recovered_sdram_items: List[Dict[str, Any]] = []
        self._last_event_time = 0.0

        # State variables for async completion / data callbacks
        self._enum_comp_done = False
        self._enum_comp_res = 0
        self._af_comp_done = False
        self._af_comp_res = 0
        self._cap_comp_done = False
        self._cap_comp_res = 0
        self._acq_comp_done = False
        self._acq_comp_res = 0
        self._acq_chunks: List[bytes] = []
        self._acq_expected_total_bytes = 0
        self._acq_received_bytes = 0
        self._last_capture_transfer_state = "NONE"
        self._last_captured_raw_bytes: Optional[bytes] = None

        # Preallocated buffers for live view
        self._lv_array = NkMAIDArray()
        self._lv_buf = None
        self._lv_buf_size = 0
        self._lv_comp_done = False
        self._lv_comp_res = 0

        # Persistent CFUNCTYPE callbacks to prevent garbage collection across timeouts
        self._mod_event_cb_func = MAIDEventProc(self._on_module_event)
        self._src_event_cb_func = MAIDEventProc(self._on_source_event)
        self._lv_comp_cb_func = MAIDCompletionProc(self._on_lv_complete)
        self._enum_comp_cb_func = MAIDCompletionProc(self._on_enum_complete)
        self._enum_comp_cb = self._enum_comp_cb_func
        self._af_comp_cb_func = MAIDCompletionProc(self._on_af_complete)
        self._cap_comp_cb_func = MAIDCompletionProc(self._on_cap_complete)
        self._data_proc_cb_func = MAIDDataProc(self._on_data_chunk)
        self._acq_comp_cb_func = MAIDCompletionProc(self._on_acq_complete)

        self._persistent_callbacks: Tuple[Any, ...] = (
            self._mod_event_cb_func,
            self._src_event_cb_func,
            self._lv_comp_cb_func,
            self._enum_comp_cb_func,
            self._af_comp_cb_func,
            self._cap_comp_cb_func,
            self._data_proc_cb_func,
            self._acq_comp_cb_func,
        )
        self._retained_callbacks: List[Any] = list(self._persistent_callbacks)

        # Persistent NkMAIDCallback structs
        self._mod_event_cb_struct = NkMAIDCallback(
            pProc=ctypes.cast(self._mod_event_cb_func, ctypes.c_void_p).value,
            refProc=0,
        )
        self._src_event_cb_struct = NkMAIDCallback(
            pProc=ctypes.cast(self._src_event_cb_func, ctypes.c_void_p).value,
            refProc=0,
        )
        self._data_proc_cb_struct = NkMAIDCallback(
            pProc=ctypes.cast(self._data_proc_cb_func, ctypes.c_void_p).value,
            refProc=0,
        )

    @property
    def device_lost(self) -> bool:
        """Trạng thái mạch ngắt khi thiết bị đã mất kết nối vật lý hoặc báo lỗi handle."""
        return self._device_lost

    @property
    def device_lost_reason(self) -> str:
        """Nguyên nhân kích hoạt mạch ngắt _device_lost."""
        return self._device_lost_reason

    @property
    def recovered_sdram_items(self) -> List[Dict[str, Any]]:
        """Danh sách các ảnh tồn đọng trong SDRAM đã được drain theo thứ tự FIFO khi kết nối còn sống."""
        return list(self._recovered_sdram_items)

    @property
    def last_capture_transfer_state(self) -> str:
        """Trạng thái truyền dữ liệu của lần chụp gần nhất: NONE | SDRAM_PENDING | PARTIAL_USB_TRANSFER | COMPLETE_IN_RAM."""
        return self._last_capture_transfer_state

    def get_last_captured_raw_bytes(self) -> Optional[bytes]:
        """Trả về nguyên bản buffer JPEG bytes (kèm 100% EXIF gốc) của lần chụp thành công gần nhất."""
        return self._last_captured_raw_bytes

    def _mark_device_lost(self, reason: str) -> None:
        """Kích hoạt mạch ngắt _device_lost để chặn tuyệt đối mọi lời gọi MAID tiếp theo trên handle đã mất."""
        if not self._device_lost:
            self._device_lost = True
            self._device_lost_reason = str(reason)
            self._is_live_view_active = False
            logger.error(
                "[NikonSession] Kích hoạt mạch ngắt DEVICE_LOST (%s). Ngừng mọi lệnh MAID trên handle hiện tại.",
                reason,
            )
            if self._new_items:
                logger.warning(
                    "[NikonSession] Còn %d item trong hàng đợi SDRAM (%s) khi mất kết nối USB; "
                    "không gọi MAID lên handle đã đứt kết nối.",
                    len(self._new_items),
                    [hex(x) for x in self._new_items],
                )

    def _check_maid_result(self, ret: int, context: str = "") -> int:
        """Kiểm tra mã trả về từ MAID; nếu thuộc nhóm lỗi mất thiết bị (-116/-117/-119) thì mở mạch ngắt."""
        code = int(ret)
        if code in DEVICE_LOST_MAID_RESULTS:
            self._mark_device_lost(f"MAID result {code} ({context})")
        return code

    # --------------------------------------------------------------------------
    # CALLBACKS (PERSISTENT BOUND METHODS)
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
            logger.warning("Nikon MAID thiết bị ngắt kết nối (REMOVE_CHILD): Source ID 0x%X", data)
            self._mark_device_lost(f"REMOVE_CHILD(source_id=0x{int(data):X})")

    def _on_source_event(self, ref_client, ul_event, data):
        self._last_event_time = time.time()
        logger.debug("MAID Source Event: event=%d, data=0x%X", ul_event, data)
        if ul_event == NkMAIDEvent.ADD_CHILD:
            self._new_items.append(int(data))
            logger.info("Nikon MAID ảnh chụp mới sẵn sàng (FIFO queue len=%d): Item ID 0x%X", len(self._new_items), data)
        elif ul_event == NkMAIDEvent.REMOVE_CHILD:
            logger.warning("Nikon MAID Source báo REMOVE_CHILD: data=0x%X", data)

    def _on_lv_complete(self, p_obj, ul_cmd, ul_param, ul_dt, data, ref_comp, n_result):
        self._lv_comp_done = True
        self._lv_comp_res = int(n_result)
        self._check_maid_result(self._lv_comp_res, "lv_complete")

    def _on_enum_complete(self, p_obj, ul_cmd, ul_param, ul_dt, data, ref_comp, n_result):
        self._enum_comp_done = True
        self._enum_comp_res = int(n_result)
        self._check_maid_result(self._enum_comp_res, "enum_complete")

    def _on_af_complete(self, p_obj, ul_cmd, ul_param, ul_dt, data, ref_comp, n_result):
        self._af_comp_done = True
        self._af_comp_res = int(n_result)
        self._check_maid_result(self._af_comp_res, "af_complete")

    def _on_cap_complete(self, p_obj, ul_cmd, ul_param, ul_dt, data, ref_comp, n_result):
        self._cap_comp_done = True
        self._cap_comp_res = int(n_result)
        self._check_maid_result(self._cap_comp_res, "cap_complete")

    def _on_data_chunk(self, ref_client, p_info, p_data) -> int:
        if not p_info or not p_data:
            return int(NkMAIDResult.NO_ERROR)
        finfo = ctypes.cast(p_info, ctypes.POINTER(NkMAIDFileInfo)).contents
        if finfo.ulTotalLength > 0:
            self._acq_expected_total_bytes = int(finfo.ulTotalLength)
        if finfo.ulLength > 0:
            chunk = bytes((ctypes.c_uint8 * finfo.ulLength).from_address(p_data))
            self._acq_chunks.append(chunk)
            self._acq_received_bytes += len(chunk)
            if self._acq_expected_total_bytes > 0 and self._acq_received_bytes >= self._acq_expected_total_bytes:
                self._last_capture_transfer_state = "COMPLETE_IN_RAM"
            else:
                self._last_capture_transfer_state = "PARTIAL_USB_TRANSFER"
        return int(NkMAIDResult.NO_ERROR)

    def _on_acq_complete(self, p_obj, ul_cmd, ul_param, ul_dt, data, ref_comp, n_result):
        self._acq_comp_done = True
        self._acq_comp_res = int(n_result)
        self._check_maid_result(self._acq_comp_res, "acq_complete")

    # --------------------------------------------------------------------------
    # LOW-LEVEL MAID DISPATCH
    # --------------------------------------------------------------------------

    def _entry(self, p_obj, ul_cmd, ul_param, ul_dt, data, pfn_comp, ref_comp) -> int:
        if self._device_lost:
            logger.debug(
                "[NikonSession] Chặn lệnh MAID (cmd=%d, param=0x%X) do _device_lost=True.",
                int(ul_cmd),
                int(ul_param),
            )
            return int(NkMAIDResult.ZOMBIE_OBJECT)

        if pfn_comp is not None and pfn_comp not in self._retained_callbacks:
            self._retained_callbacks.append(pfn_comp)

        entry_point = self._loader.entry_point
        if entry_point is None:
            return NkMAIDResult.NOT_INITIALIZED if hasattr(NkMAIDResult, "NOT_INITIALIZED") else -117
        obj_addr = ctypes.addressof(p_obj) if p_obj is not None else 0
        fn_addr = ctypes.cast(pfn_comp, ctypes.c_void_p).value if pfn_comp is not None else 0
        ret = entry_point(
            obj_addr,
            int(ul_cmd),
            int(ul_param),
            int(ul_dt),
            int(data),
            fn_addr,
            int(ref_comp)
        )
        return self._check_maid_result(ret, f"cmd={int(ul_cmd)},param=0x{int(ul_param):X}")

    def pump_async(self) -> None:
        """Xử lý hàng đợi asynchronous của SDK."""
        with self._lock:
            if self._device_lost:
                return
            if self._src_obj is not None:
                ret = self._entry(self._src_obj, NkMAIDCommand.ASYNC, 0, NkMAIDDataType.NULL, 0, None, 0)
                self._check_maid_result(ret, "pump_async(src)")
            elif self._mod_obj is not None:
                ret = self._entry(self._mod_obj, NkMAIDCommand.ASYNC, 0, NkMAIDDataType.NULL, 0, None, 0)
                self._check_maid_result(ret, "pump_async(mod)")

    # --------------------------------------------------------------------------
    # MODULE LIFECYCLE
    # --------------------------------------------------------------------------

    def open_module(self) -> Tuple[bool, str]:
        """Khởi tạo Type0026 Module Object."""
        with self._lock:
            if self._device_lost:
                return False, f"Phiên MAID đã mất kết nối thiết bị ({self._device_lost_reason})."

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
            self._check_maid_result(ret, "open_module(OPEN)")
            if ret != NkMAIDResult.NO_ERROR:
                self._mod_obj = None
                return False, f"Lỗi khởi tạo MAID Module (mã lỗi: {ret})"

            self._is_mod_open = True

            # Đăng ký EventProc bền vững cho Module
            self._mod_event_cb_struct.pProc = ctypes.cast(self._mod_event_cb_func, ctypes.c_void_p).value
            self._mod_event_cb_struct.refProc = 0
            ret_ev = self._entry(
                self._mod_obj,
                NkMAIDCommand.CAP_SET,
                NkMAIDCapability.EVENT_PROC,
                NkMAIDDataType.CALLBACK_PTR,
                ctypes.addressof(self._mod_event_cb_struct),
                None,
                0
            )
            self._check_maid_result(ret_ev, "open_module(EVENT_PROC)")

            return True, "MAID Module sẵn sàng."

    def close_module(self) -> None:
        """Đóng Module Object và giải phóng tài nguyên."""
        with self._lock:
            if self._is_src_open:
                self.close_camera()

            if self._is_mod_open and self._mod_obj is not None:
                if not self._device_lost:
                    try:
                        ret = self._entry(self._mod_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
                        self._check_maid_result(ret, "close_module(CLOSE)")
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
            if self._device_lost:
                return []

            if not self._is_mod_open:
                ok, err = self.open_module()
                if not ok:
                    logger.error("Không thể mở module để dò camera: %s", err)
                    return []

            self._discovered_sources.clear()
            self._enum_comp_done = False
            self._enum_comp_res = 0
            self._enum_comp_cb = self._enum_comp_cb_func

            ret = self._entry(
                self._mod_obj,
                NkMAIDCommand.ENUM_CHILDREN,
                0,
                NkMAIDDataType.NULL,
                0,
                self._enum_comp_cb_func,
                0
            )
            self._check_maid_result(ret, "enumerate_cameras(ENUM_CHILDREN)")
            if ret != NkMAIDResult.NO_ERROR and ret != NkMAIDResult.PENDING:
                logger.debug("EnumChildren code: %d", ret)

            start_t = time.time()
            while not self._enum_comp_done and not self._device_lost and (time.time() - start_t < timeout_sec):
                self.pump_async()
                time.sleep(0.01)

            sources = list(self._discovered_sources)

            # Truy vấn đồng bộ kNkMAIDCapability_Children (7) theo chuẩn Nikon SDK Function.cpp:SelectSource
            if not sources and self._mod_obj is not None and not self._device_lost:
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
                    self._check_maid_result(ret_cg, "enumerate_cameras(CAP_GET CHILDREN)")
                    if ret_cg == NkMAIDResult.NO_ERROR and st_enum.ulElements > 0 and not self._device_lost:
                        buf = (ctypes.c_uint32 * st_enum.ulElements)()
                        st_enum.pData = ctypes.cast(buf, ctypes.c_void_p).value
                        ret_cga = self._entry(
                            self._mod_obj,
                            NkMAIDCommand.CAP_GET_ARRAY,
                            NkMAIDCapability.CHILDREN,
                            NkMAIDDataType.ENUM_PTR,
                            ctypes.addressof(st_enum),
                            None,
                            0
                        )
                        self._check_maid_result(ret_cga, "enumerate_cameras(CAP_GET_ARRAY CHILDREN)")
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
            if self._device_lost:
                return False, f"Thiết bị đã mất kết nối ({self._device_lost_reason})."

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
            self._check_maid_result(ret, "open_camera(OPEN)")
            if ret != NkMAIDResult.NO_ERROR:
                self._src_obj = None
                return False, f"Lỗi mở phiên làm việc máy ảnh (mã lỗi: {ret})"

            self._is_src_open = True
            self._active_src_id = int(target_id)

            # Đăng ký EventProc bền vững cho Camera Source
            self._src_event_cb_struct.pProc = ctypes.cast(self._src_event_cb_func, ctypes.c_void_p).value
            self._src_event_cb_struct.refProc = 0
            ret_ev = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_SET,
                NkMAIDCapability.EVENT_PROC,
                NkMAIDDataType.CALLBACK_PTR,
                ctypes.addressof(self._src_event_cb_struct),
                None,
                0
            )
            self._check_maid_result(ret_ev, "open_camera(EVENT_PROC)")

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
                if not self._device_lost:
                    # Nếu còn ảnh tồn đọng trong SDRAM khi đóng phiên chủ động (USB còn sống), drain FIFO trước khi đóng
                    if self._new_items:
                        try:
                            self.drain_sdram_fifo(timeout_sec=3.0)
                        except Exception as ex:
                            logger.warning("Lỗi khi drain SDRAM FIFO trước lúc đóng camera: %s", ex)
                    try:
                        ret = self._entry(self._src_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
                        self._check_maid_result(ret, "close_camera(CLOSE)")
                    except Exception as ex:
                        logger.warning("Lỗi đóng phiên camera: %s", ex)
                else:
                    logger.warning(
                        "[NikonSession] Bỏ qua gọi CLOSE trên SourceObj do _device_lost=True (%s).",
                        self._device_lost_reason,
                    )
                self._src_obj = None
                self._is_src_open = False
                self._active_src_id = None

    # --------------------------------------------------------------------------
    # CAPABILITY ACCESSORS
    # --------------------------------------------------------------------------

    def get_string_capability(self, cap_id: int) -> str:
        """Đọc thuộc tính kiểu String từ máy ảnh."""
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
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
            self._check_maid_result(ret, f"get_string_capability(0x{int(cap_id):X})")
            if ret == NkMAIDResult.NO_ERROR:
                return maid_str.str.decode("utf-8", errors="ignore").strip()
            return ""

    def get_integer_capability(self, cap_id: int) -> Optional[int]:
        """Đọc giá trị số nguyên có dấu (kNkMAIDDataType_IntegerPtr = 5, c_int32) từ máy ảnh."""
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
                return None
            val = ctypes.c_int32(0)
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_GET,
                cap_id,
                NkMAIDDataType.INTEGER_PTR,
                ctypes.addressof(val),
                None,
                0
            )
            self._check_maid_result(ret, f"get_integer_capability(0x{int(cap_id):X})")
            if ret == NkMAIDResult.NO_ERROR:
                return int(val.value)
            return None

    def get_battery_level(self) -> Optional[int]:
        """Đọc dung lượng pin máy ảnh (kNkMAIDCapability_BatteryLevel = 0x0031, kiểu chuẩn INTEGER_PTR)."""
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
                return None
            val = self.get_integer_capability(NkMAIDCapability.BATTERY_LEVEL)
            if val is not None:
                return val
            if self._device_lost:
                return None
            uval = ctypes.c_uint32(0)
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_GET,
                NkMAIDCapability.BATTERY_LEVEL,
                NkMAIDDataType.UNSIGNED_PTR,
                ctypes.addressof(uval),
                None,
                0
            )
            self._check_maid_result(ret, "get_battery_level(UNSIGNED_PTR)")
            if ret == NkMAIDResult.NO_ERROR:
                return int(uval.value)
            return None

    def get_unsigned_capability(self, cap_id: int) -> Optional[int]:
        """Đọc giá trị số nguyên không dấu từ máy ảnh (tự động hỗ trợ INTEGER_PTR cho BATTERY_LEVEL)."""
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
                return None
            if int(cap_id) == int(NkMAIDCapability.BATTERY_LEVEL):
                return self.get_battery_level()
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
            self._check_maid_result(ret, f"get_unsigned_capability(0x{int(cap_id):X})")
            if ret == NkMAIDResult.NO_ERROR:
                return int(val.value)
            if ret == NkMAIDResult.UNEXPECTED_DATA_TYPE and not self._device_lost:
                return self.get_integer_capability(cap_id)
            return None

    def set_unsigned_capability(self, cap_id: int, value: int) -> bool:
        """Thiết lập giá trị số nguyên không dấu cho máy ảnh."""
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
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
            self._check_maid_result(ret, f"set_unsigned_capability(0x{int(cap_id):X})")
            return ret == NkMAIDResult.NO_ERROR

    def get_enum_capability(self, cap_id: int) -> Optional[int]:
        """Đọc chỉ số lựa chọn hiện tại của capability kiểu Enum."""
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
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
            self._check_maid_result(ret, f"get_enum_capability(0x{int(cap_id):X})")
            if ret == NkMAIDResult.NO_ERROR:
                return st_enum.ulValue
            return None

    def set_enum_capability(self, cap_id: int, value: int) -> bool:
        """Thiết lập giá trị cho capability kiểu Enum bằng cách tìm chỉ số tương ứng."""
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
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
            self._check_maid_result(ret, f"set_enum_capability(CAP_GET 0x{int(cap_id):X})")
            if self._device_lost:
                return False

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
                self._check_maid_result(ret_direct, f"set_enum_capability(UNSIGNED 0x{int(cap_id):X})")
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
                self._check_maid_result(ret_arr, f"set_enum_capability(CAP_GET_ARRAY 0x{int(cap_id):X})")
                if self._device_lost:
                    return False
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
            self._check_maid_result(ret_set, f"set_enum_capability(CAP_SET ENUM_PTR 0x{int(cap_id):X})")
            if ret_set == NkMAIDResult.NO_ERROR or self._device_lost:
                return ret_set == NkMAIDResult.NO_ERROR

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
            self._check_maid_result(ret_fb1, f"set_enum_capability(FB1 0x{int(cap_id):X})")
            if ret_fb1 == NkMAIDResult.NO_ERROR or self._device_lost:
                return ret_fb1 == NkMAIDResult.NO_ERROR

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
            self._check_maid_result(ret_fb2, f"set_enum_capability(FB2 0x{int(cap_id):X})")
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
            if self._device_lost or not self._is_src_open or self._src_obj is None:
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
        """Khởi động luồng Live View trên máy ảnh. Chỉ trả về True khi đạt CAN_ACQUIRE."""
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
                logger.error("Chưa mở kết nối camera (hoặc thiết bị đã mất) để bắt đầu Live View.")
                return False

            if self._is_live_view_active:
                return True

            # Kiểm tra trạng thái cấm Live View
            prohibit = self.get_unsigned_capability(NkMAIDCapability.LIVE_VIEW_PROHIBIT)
            if self._device_lost:
                return False
            if prohibit is not None and prohibit != 0:
                logger.warning("Camera đang cấm Live View: mã cấm 0x%X", prohibit)

            # Thiết lập độ phân giải Live View tối đa (XGA: 1024 × 680)
            self.set_live_view_image_size(NkMAIDLiveViewImageSize.XGA)
            if self._device_lost:
                return False

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
            self._check_maid_result(ret, "start_live_view(LIVE_VIEW_STATUS=ON_REMOTE_LV)")
            if ret != NkMAIDResult.NO_ERROR or self._device_lost:
                logger.error("Lỗi gửi lệnh kích hoạt Live View: mã lỗi %d", ret)
                self._is_live_view_active = False
                return False

            # Đảm bảo Live View Image Size nhận cấu hình XGA
            self.set_live_view_image_size(NkMAIDLiveViewImageSize.XGA)

            # Đợi cảm biến và cơ cấu lật gương sẵn sàng (LiveViewImageStatus == CanAcquire)
            start_t = time.time()
            st_enum = NkMAIDEnum()
            can_acquire = False

            while not self._device_lost and (time.time() - start_t) < timeout_sec:
                self.pump_async()
                if self._device_lost:
                    break
                ret_st = self._entry(
                    self._src_obj,
                    NkMAIDCommand.CAP_GET,
                    NkMAIDCapability.LIVE_VIEW_IMAGE_STATUS,
                    NkMAIDDataType.ENUM_PTR,
                    ctypes.addressof(st_enum),
                    None,
                    0
                )
                self._check_maid_result(ret_st, "start_live_view(LIVE_VIEW_IMAGE_STATUS)")
                if self._device_lost:
                    break
                if ret_st == NkMAIDResult.NO_ERROR and st_enum.ulValue == NkMAIDLiveViewImageStatus.CAN_ACQUIRE:
                    can_acquire = True
                    break
                time.sleep(0.02)

            if not can_acquire:
                logger.error(
                    "Không thể kích hoạt Live View: LiveViewImageStatus không đạt CAN_ACQUIRE sau %.2fs (status=%d).",
                    timeout_sec,
                    st_enum.ulValue,
                )
                self._is_live_view_active = False
                if not self._device_lost and self._is_src_open and self._src_obj is not None:
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
                    except Exception:
                        pass
                return False

            self._is_live_view_active = True
            logger.info("Live View đã được kích hoạt thành công (CAN_ACQUIRE).")
            return True

    def fetch_live_view_frame(self) -> Optional[bytes]:
        """
        Đọc 1 khung hình Live View hiệu năng cao trực tiếp từ bộ đệm SDK.
        Trả về raw JPEG bytes hoặc None nếu chưa có khung hình mới.
        """
        with self._lock:
            if self._device_lost or not self._is_live_view_active or self._src_obj is None:
                return None

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
            self._check_maid_result(ret_cg, "fetch_live_view_frame(CAP_GET)")
            if self._device_lost:
                return None
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
            self._check_maid_result(ret_ga, "fetch_live_view_frame(CAP_GET_ARRAY)")
            if self._device_lost:
                return None
            if ret_ga != NkMAIDResult.NO_ERROR and ret_ga != NkMAIDResult.PENDING:
                self.pump_async()
                return None

            # Đợi hoàn thành tải khung hình (thường mất 5-15ms)
            poll_start = time.perf_counter()
            while not self._lv_comp_done and not self._device_lost and (time.perf_counter() - poll_start < 0.2):
                ret_as = self._entry(self._src_obj, NkMAIDCommand.ASYNC, 0, NkMAIDDataType.NULL, 0, None, 0)
                self._check_maid_result(ret_as, "fetch_live_view_frame(ASYNC)")
                if self._device_lost:
                    return None
                time.sleep(0.001)

            if self._device_lost or not self._lv_comp_done or self._lv_comp_res != NkMAIDResult.NO_ERROR:
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

            if not self._device_lost and self._is_src_open and self._src_obj is not None:
                try:
                    ret = self._entry(
                        self._src_obj,
                        NkMAIDCommand.CAP_SET,
                        NkMAIDCapability.LIVE_VIEW_STATUS,
                        NkMAIDDataType.UNSIGNED,
                        NkMAIDLiveViewStatus.OFF,
                        None,
                        0
                    )
                    self._check_maid_result(ret, "stop_live_view(OFF)")
                    if not self._device_lost:
                        time.sleep(0.15)
                        self.pump_async()
                except Exception as ex:
                    logger.warning("Lỗi khi tắt Live View: %s", ex)
            else:
                logger.debug("[NikonSession] Bỏ qua gọi CAP_SET(LIVE_VIEW_STATUS=OFF) do _device_lost=True.")

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
            if self._device_lost or not self._is_src_open or self._src_obj is None:
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
            self._check_maid_result(ret, "set_contrast_af_area")
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
            if self._device_lost or not self._is_src_open or self._src_obj is None:
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
                if self._device_lost:
                    return False, "Mất kết nối máy ảnh."
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
                self._check_maid_result(ret, "trigger_autofocus(CONTRAST_AF=START)")
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

            while not self._device_lost and (time.time() - start_t) < timeout_sec:
                self.pump_async()
                if self._device_lost:
                    break
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
                if not self._device_lost:
                    self.cancel_autofocus()
                logger.warning("[NikonMAID] Hết thời gian chờ Contrast AF hoàn thành (timeout %.1fs, elapsed %.1fms)", timeout_sec, elapsed_ms)
                return False, "Quá thời gian phản hồi lấy nét từ máy ảnh."

        else:
            # ------------------------------------------------------------------
            # LUỒNG B: OVF / NON-LIVEVIEW PHASE-DETECTION AF (Cap ID 29)
            # Sử dụng persistent callback self._af_comp_cb_func để không bao giờ bị GC thu hồi khi timeout.
            # ------------------------------------------------------------------
            with self._lock:
                if self._device_lost:
                    return False, "Mất kết nối máy ảnh."
                self._af_comp_done = False
                self._af_comp_res = 0
                logger.info("[NikonMAID] Phát lệnh CAP_START(AUTOFOCUS, CapID=29) tới Nikon D780...")
                ret = self._entry(
                    self._src_obj,
                    NkMAIDCommand.CAP_START,
                    NkMAIDCapability.AUTOFOCUS,
                    NkMAIDDataType.NULL,
                    0,
                    self._af_comp_cb_func,
                    0
                )
                self._check_maid_result(ret, "trigger_autofocus(AUTOFOCUS)")

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
            while not self._af_comp_done and not self._device_lost and (time.time() - start_t < timeout_sec):
                self.pump_async()
                time.sleep(0.015)

            elapsed_ms = (time.perf_counter() - start_mono) * 1000.0

            if self._device_lost:
                return False, "Mất kết nối máy ảnh trong khi lấy nét."

            if not self._af_comp_done:
                logger.warning("[NikonMAID] Hết thời gian chờ phản hồi lấy nét (timeout %.1fs, elapsed %.1fms)", timeout_sec, elapsed_ms)
                return False, "Quá thời gian phản hồi lấy nét từ máy ảnh."

            res = self._af_comp_res
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
            if self._device_lost or not self._is_src_open or self._src_obj is None:
                return False
            is_lv = self._is_live_view_active

        if is_lv:
            logger.info("[NikonMAID] Dừng Contrast AF trong Live View (CAP_SET CONTRAST_AF=STOP)...")
            return self.set_unsigned_capability(NkMAIDCapability.CONTRAST_AF, NkMAIDContrastAF.STOP)
        else:
            with self._lock:
                if self._device_lost or self._src_obj is None:
                    return False
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
                    self._check_maid_result(ret, "cancel_autofocus(ABORT)")
                    return ret == NkMAIDResult.NO_ERROR
                except Exception as ex:
                    logger.debug("Lỗi gửi lệnh Abort AF: %s", ex)
                    return False

    # --------------------------------------------------------------------------
    # STILL CAPTURE & FIFO SDRAM ACQUISITION
    # --------------------------------------------------------------------------

    def _acquire_sdram_item(self, item_id: int, timeout_sec: float = 12.0) -> Optional[bytes]:
        """
        Tải dữ liệu ảnh của một Item ID từ SDRAM máy ảnh về RAM của tiến trình.

        Phân biệt rõ 3 trạng thái dữ liệu:
        1. COMPLETE_IN_RAM: Đã nhận đủ 100% số byte dự kiến và có đủ JPEG SOI..EOI (hoặc hoàn tất callback
           ACQUIRE). Nếu kết nối USB đứt ngay sau khi dữ liệu đã nằm trọn trong RAM, bỏ qua lệnh CLOSE
           trên handle đã chết và vẫn trả về đầy đủ buffer JPEG nguyên bản.
        2. PARTIAL_USB_TRANSFER: Đang nhận chunk dở dang qua USB thì đứt cáp hoặc hết timeout mà chưa đủ
           số byte / thiếu EOI. Hủy bỏ buffer cụt, tuyệt đối không cắt nhầm vào EOI của EXIF thumbnail.
        3. SDRAM_PENDING: Chưa nhận được chunk dữ liệu nào từ SDRAM.
        """
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
                self._last_capture_transfer_state = "SDRAM_PENDING"
                return None

            self._last_capture_transfer_state = "SDRAM_PENDING"
            item_obj = NkMAIDObject()
            ret_io = self._entry(
                self._src_obj,
                NkMAIDCommand.OPEN,
                int(item_id),
                NkMAIDDataType.OBJECT_PTR,
                ctypes.addressof(item_obj),
                None,
                0
            )
            self._check_maid_result(ret_io, f"_acquire_sdram_item(OPEN Item 0x{int(item_id):X})")
            if ret_io != NkMAIDResult.NO_ERROR or self._device_lost:
                logger.error("Không thể mở Item Object (0x%X): mã lỗi %d", item_id, ret_io)
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
            self._check_maid_result(ret_do, f"_acquire_sdram_item(OPEN DataObj Item 0x{int(item_id):X})")
            if ret_do != NkMAIDResult.NO_ERROR or self._device_lost:
                logger.error("Không thể mở Data Object: mã lỗi %d", ret_do)
                if not self._device_lost:
                    self._entry(item_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
                return None

            # Khởi tạo trạng thái nhận chunk cho lượt tải này (dùng persistent callback self._data_proc_cb_func)
            self._acq_chunks = []
            self._acq_expected_total_bytes = 0
            self._acq_received_bytes = 0
            self._acq_comp_done = False
            self._acq_comp_res = 0

            self._data_proc_cb_struct.pProc = ctypes.cast(self._data_proc_cb_func, ctypes.c_void_p).value
            self._data_proc_cb_struct.refProc = 0
            ret_dp = self._entry(
                dat_obj,
                NkMAIDCommand.CAP_SET,
                NkMAIDCapability.DATA_PROC,
                NkMAIDDataType.CALLBACK_PTR,
                ctypes.addressof(self._data_proc_cb_struct),
                None,
                0
            )
            self._check_maid_result(ret_dp, "_acquire_sdram_item(CAP_SET DATA_PROC)")
            if self._device_lost:
                return None

            # Kích hoạt ACQUIRE với persistent callback self._acq_comp_cb_func
            ret_acq = self._entry(
                dat_obj,
                NkMAIDCommand.CAP_START,
                NkMAIDCapability.ACQUIRE,
                NkMAIDDataType.NULL,
                0,
                self._acq_comp_cb_func,
                0
            )
            self._check_maid_result(ret_acq, "_acquire_sdram_item(CAP_START ACQUIRE)")

            acq_start = time.time()
            while not self._acq_comp_done and not self._device_lost and (time.time() - acq_start < timeout_sec):
                ret_as = self._entry(dat_obj, NkMAIDCommand.ASYNC, 0, 0, 0, None, 0)
                self._check_maid_result(ret_as, "_acquire_sdram_item(ASYNC)")
                if self._device_lost:
                    break
                time.sleep(0.005)

            full_data = b"".join(self._acq_chunks)
            logger.info(
                "Tải dữ liệu Item 0x%X: nhận %d/%d bytes (acq_done=%s, device_lost=%s, %.2fs)",
                item_id,
                len(full_data),
                self._acq_expected_total_bytes,
                self._acq_comp_done,
                self._device_lost,
                time.time() - acq_start,
            )

            # Đóng DataObj và ItemObj CHỈ KHI thiết bị chưa mất kết nối (_device_lost == False)
            if not self._device_lost:
                try:
                    null_cb = NkMAIDCallback(pProc=0, refProc=0)
                    self._entry(
                        dat_obj,
                        NkMAIDCommand.CAP_SET,
                        NkMAIDCapability.DATA_PROC,
                        NkMAIDDataType.CALLBACK_PTR,
                        ctypes.addressof(null_cb),
                        None,
                        0
                    )
                    self._entry(dat_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
                    self._entry(item_obj, NkMAIDCommand.CLOSE, 0, 0, 0, None, 0)
                except Exception as ex:
                    logger.warning("Lỗi đóng đối tượng Item/Data: %s", ex)

            if not full_data:
                self._last_capture_transfer_state = "SDRAM_PENDING"
                return None

            has_expected_len = (
                self._acq_expected_total_bytes == 0
                or len(full_data) >= self._acq_expected_total_bytes
            )
            has_complete_jpeg_envelope = (
                len(full_data) >= 4
                and full_data.startswith(b"\xff\xd8")
                and full_data.endswith(b"\xff\xd9")
            )

            # Nếu truyền dở dang (chưa đủ ulTotalLength hoặc chưa acq_done và thiếu SOI..EOI cuối file):
            if not has_expected_len or (not self._acq_comp_done and not has_complete_jpeg_envelope):
                self._last_capture_transfer_state = "PARTIAL_USB_TRANSFER"
                logger.error(
                    "[NikonSession] Huỷ bỏ buffer ảnh truyền dở qua USB (Item 0x%X: %d/%d bytes, acq_done=%s).",
                    item_id,
                    len(full_data),
                    self._acq_expected_total_bytes,
                    self._acq_comp_done,
                )
                return None

            # Nếu dữ liệu đã là luồng JPEG nguyên bản từ đầu (0xFFD8) tới cuối (0xFFD9),
            # giữ nguyên 100% byte gốc để bảo toàn tuyệt đối APP1/EXIF và embedded thumbnail.
            if has_complete_jpeg_envelope:
                self._last_capture_transfer_state = "COMPLETE_IN_RAM"
                self._last_captured_raw_bytes = full_data
                return full_data

            if self._acq_comp_done and self._acq_comp_res == NkMAIDResult.NO_ERROR:
                soi = full_data.find(b"\xff\xd8")
                eoi = full_data.rfind(b"\xff\xd9")
                if soi != -1 and eoi != -1 and eoi > soi:
                    raw_jpeg = full_data[soi:eoi + 2]
                else:
                    raw_jpeg = full_data
                self._last_capture_transfer_state = "COMPLETE_IN_RAM"
                self._last_captured_raw_bytes = raw_jpeg
                return raw_jpeg

            self._last_capture_transfer_state = "PARTIAL_USB_TRANSFER"
            return None

    def drain_sdram_fifo(self, timeout_sec: float = 5.0) -> List[bytes]:
        """
        Rút cạn các ảnh đang nằm chờ trong hàng đợi SDRAM (`self._new_items`) theo đúng thứ tự FIFO (`pop(0)`).

        QUY TẮC BẮT BUỘC:
        - Chỉ thực hiện khi `self._device_lost == False` và phiên camera đang mở.
        - Nếu `_device_lost == True`, dừng ngay lập tức và không gọi bất kỳ lệnh MAID nào lên handle đã mất.
        - Không tuyên bố có thể cứu dữ liệu còn nằm trong SDRAM của máy ảnh sau khi cáp USB đã bị rút.
        """
        drained_buffers: List[bytes] = []
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
                if self._new_items and self._device_lost:
                    logger.warning(
                        "[NikonSession] Không thể drain %d item trong SDRAM vì kết nối USB đã đứt (_device_lost=True).",
                        len(self._new_items),
                    )
                return drained_buffers

            while self._new_items and not self._device_lost:
                orphan_item_id = self._new_items.pop(0)
                logger.info("[NikonSession] Đang drain FIFO SDRAM item tồn đọng: Item ID 0x%X", orphan_item_id)
                raw_bytes = self._acquire_sdram_item(orphan_item_id, timeout_sec=timeout_sec)
                if raw_bytes is not None:
                    record = {
                        "item_id": int(orphan_item_id),
                        "raw_bytes": raw_bytes,
                        "timestamp": time.time(),
                    }
                    self._recovered_sdram_items.append(record)
                    drained_buffers.append(raw_bytes)
                elif self._device_lost:
                    break

        return drained_buffers

    def capture_photo(
        self,
        timeout_sec: float = 12.0,
        autofocus_first: bool = False,
        on_capture_start: Optional[Callable[[], None]] = None
    ) -> Optional[bytes]:
        """
        Kích hoạt màn trập, nhận luồng dữ liệu gốc theo chuẩn FIFO SDRAM và trả về raw JPEG bytes nguyên bản
        (giữ nguyên 100% metadata EXIF gốc của Nikon D780).
        Hỗ trợ tự động xử lý chế độ Mup (Mirror Up) / 2-step release và tùy chọn lấy nét trước khi bấm máy.
        """
        with self._lock:
            if self._device_lost or not self._is_src_open or self._src_obj is None:
                logger.error("Chưa mở kết nối camera (hoặc thiết bị đã mất) để chụp ảnh.")
                return None

            if autofocus_first:
                logger.info("Thực hiện lấy nét tự động trước khi chụp ảnh...")
                af_ok, af_msg = self.trigger_autofocus(timeout_sec=2.5)
                logger.info("Kết quả lấy nét trước chụp: %s (%s)", af_ok, af_msg)
                if self._device_lost:
                    return None

            # Tạm dừng Live View trước khi chụp nếu đang bật để tránh xung đột tài nguyên
            was_live_view = self._is_live_view_active
            if was_live_view:
                self.stop_live_view()
                if self._device_lost:
                    return None
                time.sleep(0.1)

            # Thiết lập lưu trực tiếp vào SDRAM
            self.set_unsigned_capability(NkMAIDCapability.SAVE_MEDIA, NkMAIDSaveMedia.SDRAM)
            if self._device_lost:
                return None

            # KHÔNG gọi self._new_items.clear() để tránh làm mất ảnh tồn đọng trong SDRAM!
            # Nếu có item tồn đọng từ trước trong khi kết nối USB đang sống, drain theo thứ tự FIFO trước.
            if self._new_items and not self._device_lost:
                self.drain_sdram_fifo(timeout_sec=min(5.0, timeout_sec))
                if self._device_lost:
                    return None

            self._cap_comp_done = False
            self._cap_comp_res = 0

            # Bắn phát thứ nhất (sử dụng persistent callback self._cap_comp_cb_func)
            ret = self._entry(
                self._src_obj,
                NkMAIDCommand.CAP_START,
                NkMAIDCapability.CAPTURE,
                NkMAIDDataType.NULL,
                0,
                self._cap_comp_cb_func,
                0
            )
            self._check_maid_result(ret, "capture_photo(CAP_START CAPTURE)")
            if self._device_lost:
                return None

            # Mốc capture-start thành công: kích hoạt âm thanh màn trập ngay khi camera chấp nhận lệnh
            if on_capture_start and ret in (NkMAIDResult.NO_ERROR, NkMAIDResult.WAITING_2ND_RELEASE, 0):
                try:
                    on_capture_start()
                except Exception as ex:
                    logger.debug(f"[NikonSession] Ngoại lệ khi gọi on_capture_start callback: {ex}")

            time.sleep(0.3)
            self.pump_async()
            if self._device_lost:
                return None

            # Nếu máy ảnh ở chế độ Mirror-Up (Mup) hoặc Exposure Delay
            if self._cap_comp_res == NkMAIDResult.WAITING_2ND_RELEASE or ret == NkMAIDResult.WAITING_2ND_RELEASE:
                logger.info("Phát hiện chế độ Mirror-Up (Waiting_2ndRelease). Kích hoạt lần nhả màn trập thứ 2...")
                self._cap_comp_done = False
                ret_2nd = self._entry(
                    self._src_obj,
                    NkMAIDCommand.CAP_START,
                    NkMAIDCapability.CAPTURE,
                    NkMAIDDataType.NULL,
                    0,
                    self._cap_comp_cb_func,
                    0
                )
                self._check_maid_result(ret_2nd, "capture_photo(CAP_START 2nd release)")
                if self._device_lost:
                    return None

            # Chờ sự kiện ADD_CHILD báo ảnh đã sẵn sàng trong SDRAM
            wait_start = time.time()
            while len(self._new_items) == 0 and not self._device_lost and (time.time() - wait_start < timeout_sec):
                self.pump_async()
                if self._device_lost:
                    break
                time.sleep(0.01)

            if self._device_lost:
                logger.error("Mất kết nối thiết bị trong khi chờ ảnh chụp từ SDRAM.")
                return None

            if not self._new_items:
                logger.error("Hết thời gian chờ ảnh chụp từ camera (timeout %0.1fs).", timeout_sec)
                if was_live_view and not self._device_lost:
                    self.start_live_view()
                return None

            # Lấy ảnh theo đúng thứ tự FIFO (pop(0) thay vì pop() LIFO)
            item_id = self._new_items.pop(0)
            raw_jpeg = self._acquire_sdram_item(item_id, timeout_sec=timeout_sec)

            # Khôi phục Live View nếu trước đó đang bật và kết nối vẫn còn sống
            if was_live_view and not self._device_lost:
                self.start_live_view()

            return raw_jpeg
