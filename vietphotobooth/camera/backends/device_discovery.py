"""
1998 TEAM — Photobooth Device Discovery Service
Asynchronously scans and aggregates all available camera devices across DirectShow, digiCamControl, and Simulator.
"""

from typing import Dict, List, Any
import logging

from vietphotobooth.camera.models import CameraDeviceInfo
from vietphotobooth.camera.backends.directshow_webcam import DirectShowWebcamBackend
from vietphotobooth.camera.backends.digicam_control import DigiCamControlBackend
from vietphotobooth.camera.backends.simulator import SimulatorBackend

logger = logging.getLogger("VietPhotoBooth.camera.discovery")


class DeviceDiscoveryService:
    """Dịch vụ quét và tổng hợp toàn bộ thiết bị camera kết nối với hệ thống."""

    @staticmethod
    def discover_all_devices() -> Dict[str, List[CameraDeviceInfo]]:
        """Dò quét toàn diện tất cả các backend camera."""
        results: Dict[str, List[CameraDeviceInfo]] = {
            "nikon_maid": [],
            "directshow": [],
            "digicam": [],
            "simulator": []
        }

        # 1. Nikon MAID Native USB (DSLR Nikon D780)
        try:
            from vietphotobooth.camera.backends.nikon_maid import NikonD780Backend
            nikon = NikonD780Backend()
            results["nikon_maid"] = nikon.discover_devices()
        except Exception as e:
            logger.debug(f"Nikon MAID discovery: {e}")

        # 2. DirectShow Webcam
        try:
            dshow = DirectShowWebcamBackend()
            results["directshow"] = dshow.discover_devices()
        except Exception as e:
            logger.warning(f"Lỗi quét thiết bị DirectShow: {e}")

        # 2. digiCamControl
        try:
            dc = DigiCamControlBackend()
            results["digicam"] = dc.discover_devices()
        except Exception as e:
            logger.warning(f"Lỗi quét thiết bị digiCamControl: {e}")

        # 3. Simulator
        try:
            sim = SimulatorBackend()
            results["simulator"] = sim.discover_devices()
        except Exception as e:
            logger.warning(f"Lỗi quét thiết bị Simulator: {e}")

        return results
