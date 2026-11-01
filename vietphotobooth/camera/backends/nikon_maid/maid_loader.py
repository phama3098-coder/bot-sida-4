"""
1998 TEAM — Photobooth Nikon MAID3 SDK Binary Loader
Locates, validates architecture and safely loads Nikon Type0026.md3 alongside its WPD dependencies.
"""

import os
import sys
import ctypes
from typing import Optional, Tuple
from pathlib import Path

from vietphotobooth.camera.backends.nikon_maid.maid_types import (
    MAIDEntryPointProc
)


class NikonSDKLoader:
    """Quản lý tìm kiếm, nạp và giải phóng thư viện Nikon MAID3 SDK."""

    def __init__(self):
        self._lib: Optional[ctypes.CDLL] = None
        self._entry_point: Optional[MAIDEntryPointProc] = None
        self._sdk_dir: Optional[str] = None
        self._dll_cookie = None

    @property
    def is_loaded(self) -> bool:
        return self._entry_point is not None

    @property
    def entry_point(self) -> Optional[MAIDEntryPointProc]:
        return self._entry_point

    @property
    def sdk_directory(self) -> Optional[str]:
        return self._sdk_dir

    def get_candidate_directories(self) -> list[str]:
        """Danh sách các thư mục ưu tiên tìm kiếm Type0026.md3 và DLL phụ thuộc."""
        candidates = []

        # 1. Biến môi trường tùy chỉnh nếu có
        env_dir = os.environ.get("NIKON_SDK_DIR")
        if env_dir and os.path.isdir(env_dir):
            candidates.append(env_dir)

        # 2. Thư mục bin/x64 tích hợp trong package vietphotobooth
        pkg_bin = Path(__file__).resolve().parent / "bin" / "x64"
        if pkg_bin.is_dir():
            candidates.append(str(pkg_bin))

        # 3. Đường dẫn SDK chuẩn nếu chạy trong môi trường phát triển
        dev_sdk = Path(r"c:\Users\Admin\Downloads\Compressed\S-SDKD780-005BF-ALLIN\S-SDKD780-005BF-ALLIN\Module\Win\Binary Files\x64")
        if dev_sdk.is_dir():
            candidates.append(str(dev_sdk))

        # 4. Thư mục hiện tại của tiến trình
        cwd_bin = Path.cwd() / "x64"
        if cwd_bin.is_dir():
            candidates.append(str(cwd_bin))

        return candidates

    def find_sdk_directory(self) -> Optional[str]:
        """Tìm thư mục hợp lệ chứa Type0026.md3 và các DLL cần thiết."""
        required_files = ["Type0026.md3", "NkdPTP.dll", "NkRoyalmile.dll", "dnssd.dll"]
        for directory in self.get_candidate_directories():
            all_present = True
            for fname in required_files:
                if not os.path.exists(os.path.join(directory, fname)):
                    all_present = False
                    break
            if all_present:
                return directory
        return None

    def load(self) -> Tuple[bool, str]:
        """
        Nạp Type0026.md3 vào tiến trình hiện tại.
        Trả về (success: bool, message: str).
        """
        if self._entry_point is not None:
            return True, "SDK đã được nạp trước đó."

        # Kiểm tra nền tảng
        if sys.platform != "win32":
            return False, f"Hệ điều hành '{sys.platform}' không được hỗ trợ bởi Nikon MAID Win32/Win64 SDK."

        if ctypes.sizeof(ctypes.c_void_p) != 8:
            return False, "Yêu cầu Python 64-bit để nạp thư viện Nikon MAID x64."

        sdk_dir = self.find_sdk_directory()
        if not sdk_dir:
            return False, "Không tìm thấy thư mục chứa Nikon MAID Type0026.md3 và các DLL phụ thuộc."

        md3_path = os.path.join(sdk_dir, "Type0026.md3")

        try:
            # Thêm thư mục DLL an toàn cho Windows 10/11
            if hasattr(os, "add_dll_directory"):
                self._dll_cookie = os.add_dll_directory(sdk_dir)

            # Bổ sung PATH để các dependent DLLs luôn được load thành công
            if sdk_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = sdk_dir + os.pathsep + os.environ.get("PATH", "")

            # Nạp Type0026.md3
            self._lib = ctypes.cdll.LoadLibrary(md3_path)
            raw_entry = getattr(self._lib, "MAIDEntryPoint", None)
            if raw_entry is None:
                return False, "Không tìm thấy symbol 'MAIDEntryPoint' trong Type0026.md3."

            # Ép kiểu sang function prototype chuẩn
            self._entry_point = MAIDEntryPointProc(
                ctypes.cast(raw_entry, ctypes.c_void_p).value
            )
            self._sdk_dir = sdk_dir
            return True, f"Nạp Nikon Type0026 SDK thành công từ: {sdk_dir}"

        except Exception as ex:
            self._lib = None
            self._entry_point = None
            return False, f"Lỗi khi nạp Type0026.md3: {ex}"

    def unload(self) -> None:
        """Giải phóng DLL nếu cần."""
        self._entry_point = None
        self._lib = None
        if self._dll_cookie and hasattr(self._dll_cookie, "close"):
            try:
                self._dll_cookie.close()
            except Exception:
                pass
            self._dll_cookie = None


# Singleton instance toàn cục
_default_loader = NikonSDKLoader()

def get_loader() -> NikonSDKLoader:
    return _default_loader
