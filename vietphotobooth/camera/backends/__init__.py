"""
1998 TEAM — Photobooth Camera Backends Package
"""

from vietphotobooth.camera.backends.base import CameraBackendBase
from vietphotobooth.camera.backends.directshow_webcam import DirectShowWebcamBackend
from vietphotobooth.camera.backends.digicam_control import DigiCamControlBackend
from vietphotobooth.camera.backends.simulator import SimulatorBackend
from vietphotobooth.camera.backends.device_discovery import DeviceDiscoveryService

__all__ = [
    "CameraBackendBase",
    "DirectShowWebcamBackend",
    "DigiCamControlBackend",
    "SimulatorBackend",
    "DeviceDiscoveryService"
]
