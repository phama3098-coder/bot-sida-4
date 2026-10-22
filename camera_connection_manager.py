"""
Root alias for CameraConnectionManager
"""
from vietphotobooth.camera.connection_manager import CameraConnectionManager
from vietphotobooth.camera.models import ConnectionState, CameraError, CameraDeviceInfo

__all__ = ["CameraConnectionManager", "ConnectionState", "CameraError", "CameraDeviceInfo"]
