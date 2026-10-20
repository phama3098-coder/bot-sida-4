"""
Tests for Frame Manager, Frame Designer, 300 DPI Rendering, and Bleed Validation
"""

import os
import tempfile
from PIL import Image
import pytest

from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer
from vietphotobooth.frames.frame_designer import FrameDesigner
from vietphotobooth.frames.frame_manager import FrameManager

def test_frame_manager_initialization():
    fm = FrameManager()
    frames = fm.list_frames()
    assert len(frames) >= 4
    categories = set(f.category for f in frames)
    assert "Wedding" in categories
    assert "Birthday" in categories

def test_300dpi_composite_rendering():
    fm = FrameManager()
    wedding_frame = fm.get_frame("wedding_2x6_strip3")
    assert wedding_frame is not None

    photos = [
        Image.new("RGB", (800, 600), color=(255, 100, 100)),
        Image.new("RGB", (800, 600), color=(100, 255, 100)),
        Image.new("RGB", (800, 600), color=(100, 100, 255)),
    ]

    composite = FrameDesigner.render_composite(photos, wedding_frame, {"name": "Lễ Cưới Tuấn & Lan", "date": "20/10/2026"})
    assert composite.size == (600, 1800)
    assert composite.info.get("dpi") == (300, 300)

def test_dual_strip_4x6_rendering():
    fm = FrameManager()
    dual_frame = fm.get_frame("dual_strip_4x6_dnp")
    assert dual_frame is not None
    assert dual_frame.is_dual_strip is True

    photos = [
        Image.new("RGB", (800, 600), color=(200, 200, 50)),
        Image.new("RGB", (800, 600), color=(50, 200, 200)),
        Image.new("RGB", (800, 600), color=(200, 50, 200)),
    ]

    composite = FrameDesigner.render_composite(photos, dual_frame)
    assert composite.size == (1200, 1800)
    assert composite.info.get("dpi") == (300, 300)

def test_external_png_import_and_validation():
    with tempfile.TemporaryDirectory() as tmpdir:
        fm = FrameManager(base_dir=tmpdir)
        # Create a mock transparent PNG overlay
        overlay = Image.new("RGBA", (600, 1800), (0, 0, 0, 0))
        overlay_path = os.path.join(tmpdir, "my_custom_frame.png")
        overlay.save(overlay_path, "PNG")

        imported = fm.import_external_png_overlay(overlay_path, "My Custom Wedding", category="Custom", strip_type="2x6")
        assert imported is not None
        assert imported.name == "My Custom Wedding"
        assert os.path.exists(imported.overlay_png_path)

        warnings = FrameDesigner.validate_template(imported)
        # Verify validation runs and returns a list
        assert isinstance(warnings, list)
