"""
VietPhotoBooth Frames & Templates Engine Package
"""

from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, LogoLayer, DPI_300_SIZES
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_manager import FrameManager

__all__ = [
    "FrameTemplate",
    "PhotoSlot",
    "TextLayer",
    "LogoLayer",
    "DPI_300_SIZES",
    "FrameDesigner",
    "FrameManager"
]
