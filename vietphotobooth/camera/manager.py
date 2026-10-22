"""
VietPhotoBooth Camera Manager (Backward Compatible Wrapper)
Inherits from CameraConnectionManager, preserving 100% API compatibility for existing modules and tests.
"""

from typing import Optional, Any
from vietphotobooth.camera.connection_manager import CameraConnectionManager
from vietphotobooth.core.config import ConfigManager


class CameraManager(CameraConnectionManager):
    """CameraManager kết thừa đầy đủ từ CameraConnectionManager."""

    def __init__(
        self,
        default_backend: str = "simulator",
        device_index: int = 0,
        device_name: Optional[str] = None,
        config_mgr: Optional[ConfigManager] = None
    ):
        super().__init__(
            default_backend=default_backend,
            device_id=device_index,
            device_name=device_name,
            config_mgr=config_mgr
        )
