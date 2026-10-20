"""
Tests for Filter Engine, Parametric Processor, and 3D LUT Parser
"""

import os
import tempfile
import numpy as np
from PIL import Image
import pytest

from vietphotobooth.filters.filter_engine import FilterEngine, FilterPreset
from vietphotobooth.filters.lut_parser import CubeLUTParser

def test_filter_engine_initialization():
    fe = FilterEngine()
    presets = fe.get_presets()
    assert len(presets) >= 12
    ids = [p.id for p in presets]
    assert "natural" in ids
    assert "wedding_dream" in ids
    assert "film_cinema" in ids
    assert "bw_art" in ids
    assert "sepia_nostalgia" in ids

def test_non_destructive_filter_application():
    fe = FilterEngine()
    # Create test image with distinct pixel values
    orig_img = Image.new("RGB", (100, 100), color=(120, 150, 180))
    orig_pixels_before = list(orig_img.getdata())

    preset = fe.get_preset("vintage")
    assert preset is not None
    result_img = fe.apply_preset(orig_img, preset, intensity=1.0)

    orig_pixels_after = list(orig_img.getdata())
    # Original image must NOT be altered
    assert orig_pixels_before == orig_pixels_after
    assert result_img.size == orig_img.size
    # Result image must have transformed pixel values
    result_pixels = list(result_img.getdata())
    assert result_pixels != orig_pixels_before

def test_cube_lut_parser_and_application():
    with tempfile.TemporaryDirectory() as tmpdir:
        lut_path = os.path.join(tmpdir, "test.cube")
        # Invert colors generator
        def invert_gen(r, g, b):
            return 1.0 - r, 1.0 - g, 1.0 - b

        assert CubeLUTParser.create_cube_file(lut_path, "Test Invert", 17, invert_gen)
        parser = CubeLUTParser(lut_path)
        assert parser.size == 17
        assert parser.table is not None

        # Test on numpy image
        img_np = np.full((10, 10, 3), 0, dtype=np.uint8) # Pure black
        applied = parser.apply(img_np, intensity=1.0)
        # Inverted black should be close to 255 (white)
        assert applied[0, 0, 0] >= 250
        assert applied[0, 0, 1] >= 250
        assert applied[0, 0, 2] >= 250

def test_custom_preset_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        b_dir = os.path.join(tmpdir, "builtin")
        c_dir = os.path.join(tmpdir, "custom")
        l_dir = os.path.join(tmpdir, "luts")
        fe = FilterEngine(builtin_dir=b_dir, custom_dir=c_dir, luts_dir=l_dir)

        # Duplicate preset
        dup = fe.duplicate_preset("natural", "custom_warm_plus", "Custom Warm Plus")
        assert dup is not None
        assert dup.id == "custom_warm_plus"
        assert dup.is_builtin is False

        # Modify and save
        dup.temperature = 45.0
        assert fe.save_custom_preset(dup)
        loaded = fe.get_preset("custom_warm_plus")
        assert loaded is not None
        assert loaded.temperature == 45.0

        # Export and Import
        export_file = os.path.join(tmpdir, "exported.json")
        assert fe.export_preset_to_file("custom_warm_plus", export_file)
        assert os.path.exists(export_file)

        imported = fe.import_preset_from_file(export_file)
        assert imported is not None

        # Delete
        assert fe.delete_preset("custom_warm_plus")
        assert fe.get_preset("custom_warm_plus") is None
