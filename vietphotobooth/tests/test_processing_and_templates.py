"""
Automated Tests for Image Processing and 300 DPI Template Engine
"""

import os
import tempfile
import pytest
from PIL import Image
from vietphotobooth.processing.image_processor import ImageProcessor
from vietphotobooth.processing.template_engine import TemplateEngine, PRINT_DPI

def test_image_processor():
    # Tạo ảnh mẫu 1920x1080 (16:9)
    sample = Image.new("RGB", (1920, 1080), (100, 150, 200))

    # Cắt sang khổ 4:3 (800x600)
    cropped = ImageProcessor.crop_and_resize(sample, 800, 600)
    assert cropped.size == (800, 600)

    # Thử các bộ lọc
    bw = ImageProcessor.apply_filter(sample, "bw")
    assert bw.size == sample.size

    vintage = ImageProcessor.apply_filter(sample, "vintage")
    assert vintage.size == sample.size

    # Thumbnail
    thumb = ImageProcessor.make_thumbnail(sample, (200, 200))
    assert thumb.size[0] <= 200 and thumb.size[1] <= 200

def test_template_2x6_strip():
    engine = TemplateEngine()
    photos = [
        Image.new("RGB", (1200, 800), (200, 50, 50)),
        Image.new("RGB", (1200, 800), (50, 200, 50)),
        Image.new("RGB", (1200, 800), (50, 50, 200))
    ]

    event_info = {
        "title": "Lễ Thành Hôn",
        "subtitle": "Trọng & Thảo",
        "date": "2026-10-20"
    }

    output = engine.render(
        template_id="strip_2x6_3photos",
        photos=photos,
        event_info=event_info
    )

    assert output.size == (600, 1800)
    assert output.info.get("dpi") == (PRINT_DPI, PRINT_DPI)

def test_template_4x6_dual_strip_dnp():
    """Kiểm tra template ghép đôi 2 dải 2x6 trên khổ 4x6 cho dao cắt máy DNP DS-RX1HS."""
    engine = TemplateEngine()
    photos = [
        Image.new("RGB", (1200, 800), (200, 50, 50)),
        Image.new("RGB", (1200, 800), (50, 200, 50)),
        Image.new("RGB", (1200, 800), (50, 50, 200))
    ]

    event_info = {
        "title": "Happy Wedding",
        "subtitle": "Nam & Mai",
        "date": "2026-10-20"
    }

    output = engine.render(
        template_id="dual_strip_4x6_3photos",
        photos=photos,
        event_info=event_info
    )

    assert output.size == (1200, 1800)
    assert output.info.get("dpi") == (PRINT_DPI, PRINT_DPI)

def test_template_4x6_landscape():
    engine = TemplateEngine()
    photos = [
        Image.new("RGB", (800, 1200), (100, 100, 100)),
        Image.new("RGB", (800, 1200), (150, 150, 150)),
        Image.new("RGB", (800, 1200), (200, 200, 200))
    ]

    output = engine.render(
        template_id="landscape_4x6_3photos",
        photos=photos,
        event_info={"title": "Hội Nghị Khách Hàng", "subtitle": "Công Ty ABC", "date": "2026-10-20"}
    )

    assert output.size == (1800, 1200)
    assert output.info.get("dpi") == (PRINT_DPI, PRINT_DPI)
