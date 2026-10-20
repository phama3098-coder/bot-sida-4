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
    # Thư viện khởi tạo sạch, không sinh bộ lọc giả/mẫu theo yêu cầu
    assert isinstance(presets, list)
    # Khởi tạo rỗng, người dùng tự thêm hoặc nhập bộ lọc của riêng mình
    assert len(presets) == 0

def test_non_destructive_filter_application():
    fe = FilterEngine()
    # Create test image with distinct pixel values
    orig_img = Image.new("RGB", (100, 100), color=(120, 150, 180))
    orig_pixels_before = np.array(orig_img).copy()

    # Tạo preset thử nghiệm
    test_preset = FilterPreset(
        id="test_vintage",
        name="Test Vintage",
        brightness=15.0,
        contrast=20.0,
        temperature=25.0
    )
    assert fe.save_custom_preset(test_preset) is True
    preset = fe.get_preset("test_vintage")
    assert preset is not None
    result_img = fe.apply_preset(orig_img, preset, intensity=1.0)

    orig_pixels_after = np.array(orig_img)
    # Original image must NOT be altered (non-destructive pipeline)
    np.testing.assert_array_equal(orig_pixels_before, orig_pixels_after)
    assert result_img.size == orig_img.size
    # Result image must have transformed pixel values
    assert not np.array_equal(np.array(result_img), orig_pixels_before)
    # Clean up
    fe.delete_preset("test_vintage")

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

        # Tạo mới một preset
        base_preset = FilterPreset(id="custom_film", name="1998 Film Warm", brightness=5.0, temperature=18.0)
        assert fe.save_custom_preset(base_preset) is True

        # Duplicate preset
        dup = fe.duplicate_preset("custom_film", "custom_film_plus", "1998 Film Warm Plus")
        assert dup is not None
        assert dup.id == "custom_film_plus"
        assert dup.is_builtin is False

        # Modify and save
        dup.temperature = 45.0
        assert fe.save_custom_preset(dup)
        loaded = fe.get_preset("custom_film_plus")
        assert loaded is not None
        assert loaded.temperature == 45.0

        # Export and Import
        export_file = os.path.join(tmpdir, "exported.json")
        assert fe.export_preset_to_file("custom_film_plus", export_file)
        assert os.path.exists(export_file)

        imported = fe.import_preset_from_file(export_file)
        assert imported is not None

        # Delete
        assert fe.delete_preset("custom_film_plus")
        assert fe.get_preset("custom_film_plus") is None
        assert fe.delete_preset("custom_film")
