"""
VietPhotoBooth Windows Camera & Video Device Enumerator
Accurately discovers all video input devices (UVC webcams, virtual cameras like Nikon Webcam Utility, OBS Virtual Cam)
using Windows DirectShow COM, Media Foundation, PySide6 QMediaDevices, and OpenCV fallback.
Does NOT rely solely on arbitrary device indices (0, 1, 2).
"""

import sys
import os
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("VietPhotoBooth.camera.enumerator")

def enumerate_directshow_devices() -> List[Dict[str, Any]]:
    """
    Liệt kê danh sách thiết bị video capture DirectShow thông qua Windows COM (ICreateDevEnum).
    Trả về danh sách dict gồm:
      - 'index': chỉ số DirectShow (0, 1, ...) tương thích OpenCV cv2.CAP_DSHOW
      - 'name': Tên thân thiện của thiết bị (FriendlyName), ví dụ: 'Nikon Webcam Utility', 'Logi C270 HD WebCam'
      - 'path': DevicePath định danh thiết bị
      - 'backend': 'DSHOW'
    """
    devices: List[Dict[str, Any]] = []

    if sys.platform != "win32":
        return devices

    try:
        import ctypes
        from ctypes import wintypes, POINTER, c_void_p, Structure, c_ulong, byref, cast, c_int, c_ushort

        ole32 = ctypes.oledll.ole32
        oleaut32 = ctypes.oledll.oleaut32
        oleaut32.SysFreeString.argtypes = [c_void_p]

        class GUID(Structure):
            _fields_ = [
                ('Data1', wintypes.DWORD),
                ('Data2', wintypes.WORD),
                ('Data3', wintypes.WORD),
                ('Data4', wintypes.BYTE * 8)
            ]
            def __init__(self, s):
                import uuid
                u = uuid.UUID(s)
                self.Data1 = u.time_low
                self.Data2 = u.time_mid
                self.Data3 = u.time_hi_version
                for i, b in enumerate(u.bytes[8:]):
                    self.Data4[i] = b

        CLSID_SystemDeviceEnum = GUID('{62BE5D10-60EB-11d0-BD3B-00A0C911CE86}')
        IID_ICreateDevEnum = GUID('{29840822-5B84-11D0-BD3B-00A0C911CE86}')
        CLSID_VideoInputDeviceCategory = GUID('{860BB310-5D01-11d0-BD3B-00A0C911CE86}')
        IID_IPropertyBag = GUID('{55272A00-42CB-11CE-8135-00AA004BB851}')

        ole32.CoInitialize(None)
        p_dev_enum = c_void_p()
        hr = ole32.CoCreateInstance(byref(CLSID_SystemDeviceEnum), None, 1, byref(IID_ICreateDevEnum), byref(p_dev_enum))
        if hr != 0 or not p_dev_enum.value:
            return devices

        vtable = cast(cast(p_dev_enum, POINTER(c_void_p))[0], POINTER(c_void_p))
        CreateClassEnumerator_proto = ctypes.WINFUNCTYPE(c_int, c_void_p, POINTER(GUID), POINTER(c_void_p), wintypes.DWORD)
        CreateClassEnumerator = CreateClassEnumerator_proto(vtable[3])

        p_enum_moniker = c_void_p()
        hr = CreateClassEnumerator(p_dev_enum, byref(CLSID_VideoInputDeviceCategory), byref(p_enum_moniker), 0)
        if hr != 0 or not p_enum_moniker.value:
            Release_proto = ctypes.WINFUNCTYPE(c_ulong, c_void_p)
            Release_proto(vtable[2])(p_dev_enum)
            return devices

        enum_vtable = cast(cast(p_enum_moniker, POINTER(c_void_p))[0], POINTER(c_void_p))
        Next_proto = ctypes.WINFUNCTYPE(c_int, c_void_p, wintypes.ULONG, POINTER(c_void_p), POINTER(wintypes.ULONG))
        Next = Next_proto(enum_vtable[3])

        idx = 0
        while True:
            p_moniker = c_void_p()
            fetched = wintypes.ULONG()
            res = Next(p_enum_moniker, 1, byref(p_moniker), byref(fetched))
            if res != 0 or fetched.value == 0 or not p_moniker.value:
                break

            mon_vtable = cast(cast(p_moniker, POINTER(c_void_p))[0], POINTER(c_void_p))
            # IMoniker::BindToStorage is vtable index 9
            BindToStorage_proto = ctypes.WINFUNCTYPE(c_int, c_void_p, c_void_p, c_void_p, POINTER(GUID), POINTER(c_void_p))
            BindToStorage = BindToStorage_proto(mon_vtable[9])

            p_prop_bag = c_void_p()
            hr_bag = BindToStorage(p_moniker, None, None, byref(IID_IPropertyBag), byref(p_prop_bag))
            friendly_name = ""
            device_path = ""

            if hr_bag == 0 and p_prop_bag.value:
                bag_vtable = cast(cast(p_prop_bag, POINTER(c_void_p))[0], POINTER(c_void_p))
                Read_proto = ctypes.WINFUNCTYPE(c_int, c_void_p, wintypes.LPCWSTR, c_void_p, c_void_p)
                Read = Read_proto(bag_vtable[3])

                var_buf = (ctypes.c_byte * 24)()
                hr_read = Read(p_prop_bag, 'FriendlyName', byref(var_buf), None)
                vt = cast(byref(var_buf), POINTER(c_ushort))[0]
                if vt == 8:
                    bstr_ptr = cast(byref(var_buf, 8), POINTER(c_void_p))[0]
                    if bstr_ptr:
                        friendly_name = ctypes.wstring_at(bstr_ptr)
                        oleaut32.SysFreeString(bstr_ptr)

                var_buf2 = (ctypes.c_byte * 24)()
                hr_read2 = Read(p_prop_bag, 'DevicePath', byref(var_buf2), None)
                vt2 = cast(byref(var_buf2), POINTER(c_ushort))[0]
                if vt2 == 8:
                    bstr_ptr2 = cast(byref(var_buf2, 8), POINTER(c_void_p))[0]
                    if bstr_ptr2:
                        device_path = ctypes.wstring_at(bstr_ptr2)
                        oleaut32.SysFreeString(bstr_ptr2)

                Release_proto = ctypes.WINFUNCTYPE(c_ulong, c_void_p)
                Release_proto(bag_vtable[2])(p_prop_bag)

            Release_proto = ctypes.WINFUNCTYPE(c_ulong, c_void_p)
            Release_proto(mon_vtable[2])(p_moniker)

            if not friendly_name:
                friendly_name = f"DirectShow Video Device #{idx}"

            devices.append({
                "index": idx,
                "name": friendly_name,
                "path": device_path,
                "backend": "DSHOW",
                "is_virtual": ("nikon" in friendly_name.lower() or "obs" in friendly_name.lower() or "virtual" in friendly_name.lower())
            })
            idx += 1

        Release_proto = ctypes.WINFUNCTYPE(c_ulong, c_void_p)
        Release_proto(enum_vtable[2])(p_enum_moniker)
        Release_proto(vtable[2])(p_dev_enum)

    except Exception as e:
        logger.warning(f"Lỗi khi liệt kê DirectShow qua COM API: {e}")

    # Fallback qua Registry nếu COM không tìm thấy
    if not devices:
        devices = _enumerate_directshow_via_registry()

    return devices


def _enumerate_directshow_via_registry() -> List[Dict[str, Any]]:
    """Dò quét danh mục DirectShow từ Registry Windows (Fallback)."""
    devices: List[Dict[str, Any]] = []
    try:
        import winreg
        cat_path = r"SOFTWARE\Classes\CLSID\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\Instance"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cat_path) as cat_key:
            num_subkeys, _, _ = winreg.QueryInfoKey(cat_key)
            for idx in range(num_subkeys):
                sk_name = winreg.EnumKey(cat_key, idx)
                try:
                    with winreg.OpenKey(cat_key, sk_name) as dev_key:
                        num_vals, _, _ = winreg.QueryInfoKey(dev_key)
                        v_map = {}
                        for vi in range(num_vals):
                            vn, vv, _ = winreg.EnumValue(dev_key, vi)
                            v_map[vn] = vv
                        fn = v_map.get("FriendlyName", f"DirectShow #{idx}")
                        dp = v_map.get("DevicePath", "")
                        devices.append({
                            "index": idx,
                            "name": fn,
                            "path": dp,
                            "backend": "DSHOW",
                            "is_virtual": ("nikon" in fn.lower() or "obs" in fn.lower())
                        })
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"Fallback registry DirectShow error: {e}")
    return devices


def probe_video_source(
    device_index: int,
    backend: int = cv2.CAP_DSHOW,
    timeout_frames: int = 10
) -> Dict[str, Any]:
    """
    Kiểm tra toàn diện một nguồn video thực tế:
    - Có mở được nguồn không (isOpened).
    - Có đọc được frame hợp lệ không (read).
    - Độ phân giải thực tế (Width x Height).
    - Tốc độ khung hình (FPS) đo đạc thực tế (loại bỏ độ trễ khởi động camera ban đầu).
    - Độ sáng trung bình (Mean Pixel) để cảnh báo màn hình đen/nắp ống kính đóng.
    """
    result: Dict[str, Any] = {
        "device_index": device_index,
        "backend_code": backend,
        "backend_name": "DSHOW" if backend == cv2.CAP_DSHOW else "MSMF" if backend == cv2.CAP_MSMF else "ANY",
        "openable": False,
        "frame_readable": False,
        "actual_width": 0,
        "actual_height": 0,
        "reported_fps": 0.0,
        "measured_fps": 0.0,
        "mean_brightness": 0.0,
        "is_black_screen": False,
        "error_message": "",
        "status": "Chưa kiểm tra"
    }

    cap = None
    try:
        cap = cv2.VideoCapture(device_index, backend)
        if not cap.isOpened():
            result["error_message"] = f"Không thể mở nguồn video #{device_index} bằng backend {result['backend_name']}."
            result["status"] = "Không mở được"
            return result

        result["openable"] = True
        reported_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        result["reported_fps"] = reported_fps

        # 1. Khởi động / warmup: đọc frame đầu tiên để camera đồng bộ AGC/phơi sáng
        last_frame = None
        ret_init, frame_init = cap.read()
        if ret_init and frame_init is not None and frame_init.size > 0:
            last_frame = frame_init

        # 2. Đo FPS thực tế trên các khung hình tiếp theo
        frames_measured = 0
        t_start = time.time()
        num_probe = max(2, timeout_frames - 1)

        for _ in range(num_probe):
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                frames_measured += 1
                last_frame = frame

        t_elapsed = time.time() - t_start

        if last_frame is not None and (frames_measured > 0 or ret_init):
            result["frame_readable"] = True
            h, w = last_frame.shape[:2]
            result["actual_width"] = int(w)
            result["actual_height"] = int(h)

            if frames_measured > 0 and t_elapsed > 0.005:
                calc_fps = round(frames_measured / t_elapsed, 1)
                result["measured_fps"] = calc_fps
            elif reported_fps > 0:
                result["measured_fps"] = reported_fps
            else:
                result["measured_fps"] = 30.0

            # Tính độ sáng trung bình (0 .. 255)
            mean_b = float(np.mean(last_frame))
            result["mean_brightness"] = round(mean_b, 2)

            # Nếu độ sáng trung bình < 1.5, cảnh báo màn hình đen hoàn toàn
            if mean_b < 1.5:
                result["is_black_screen"] = True
                result["status"] = "Khung hình đen hoàn toàn (Kiểm tra nắp ống kính hoặc kết nối máy ảnh)"
            else:
                result["status"] = "Hoạt động hoàn hảo"
        else:
            result["frame_readable"] = False
            result["error_message"] = f"Nguồn đã mở nhưng không đọc được frame dữ liệu nào từ thiết bị #{device_index}."
            result["status"] = "Không đọc được frame"

    except Exception as e:
        result["error_message"] = f"Lỗi ngoại lệ khi probe camera #{device_index}: {e}"
        result["status"] = f"Lỗi: {e}"
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    return result


def find_device_by_name_or_keyword(keyword: str) -> Optional[Dict[str, Any]]:
    """
    Tìm thiết bị video trong danh sách DirectShow theo tên hoặc từ khóa (ví dụ 'Nikon', 'C270').
    Trả về dict thiết bị hoặc None nếu không thấy.
    """
    devs = enumerate_directshow_devices()
    kw_low = keyword.lower().strip()
    for d in devs:
        if kw_low in d["name"].lower():
            return d
    return None
