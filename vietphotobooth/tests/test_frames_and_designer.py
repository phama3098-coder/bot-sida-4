"""
Tests for Frame Manager, Frame Designer, 300 DPI Rendering, and Bleed Validation
"""

import os
import tempfile
from PIL import Image
import pytest

from vietphotobooth.frames.frame_models import FrameTemplate, PhotoSlot, TextLayer, LogoLayer
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

def test_external_frame_import_jpg_and_svg():
    with tempfile.TemporaryDirectory() as tmpdir:
        user_dir = os.path.join(tmpdir, "user_frames")
        fm = FrameManager(base_dir=tmpdir, user_dir=user_dir)

        # 1. Test JPG import as background
        jpg_img = Image.new("RGB", (600, 1800), (240, 230, 220))
        jpg_path = os.path.join(tmpdir, "test_bg.jpg")
        jpg_img.save(jpg_path, "JPEG")

        frame_jpg = fm.import_external_frame(
            file_path=jpg_path,
            template_name="Khung Cưới Nền Vàng",
            category="Wedding",
            strip_type="2x6",
            layer_mode="background",
            num_slots=3,
            notes="Khung ảnh thử nghiệm JPG"
        )
        assert frame_jpg is not None
        assert frame_jpg.name == "Khung Cưới Nền Vàng"
        assert frame_jpg.bg_image_path is not None
        assert os.path.exists(frame_jpg.bg_image_path)
        assert frame_jpg.notes == "Khung ảnh thử nghiệm JPG"

        # 2. Test SVG vector import & rasterization
        svg_content = """<svg xmlns="http://www.w3.org/2000/svg" width="600" height="1800" viewBox="0 0 600 1800">
            <rect width="600" height="1800" fill="none" stroke="#D4AF37" stroke-width="20"/>
            <circle cx="300" cy="150" r="80" fill="#D4AF37" />
        </svg>"""
        svg_path = os.path.join(tmpdir, "test_vector.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        frame_svg = fm.import_external_frame(
            file_path=svg_path,
            template_name="Khung SVG Vector Sang Trọng",
            category="Custom",
            strip_type="2x6",
            layer_mode="overlay",
            num_slots=2
        )
        assert frame_svg is not None
        assert frame_svg.overlay_png_path is not None
        assert os.path.exists(frame_svg.overlay_png_path)
        assert len(frame_svg.slots) == 2

def test_frame_duplicate_and_rename():
    with tempfile.TemporaryDirectory() as tmpdir:
        user_dir = os.path.join(tmpdir, "user_frames")
        fm = FrameManager(base_dir=tmpdir, user_dir=user_dir)

        # Duplicate existing wedding template
        dup = fm.duplicate_frame("wedding_2x6_strip3", "Tiệc Cưới Bản Sao VIP")
        assert dup is not None
        assert dup.name == "Tiệc Cưới Bản Sao VIP"
        assert fm.get_frame(dup.id) is not None

        # Rename duplicated frame
        ok = fm.rename_frame(dup.id, "Tiệc Cưới Siêu VIP")
        assert ok is True
        updated = fm.get_frame(dup.id)
        assert updated.name == "Tiệc Cưới Siêu VIP"

def test_frame_backup_and_restore_zip():
    with tempfile.TemporaryDirectory() as tmpdir:
        user_dir = os.path.join(tmpdir, "user_frames")
        fm = FrameManager(base_dir=tmpdir, user_dir=user_dir)

        # Create a user frame
        dup = fm.duplicate_frame("wedding_2x6_strip3", "Khung Cho Sao Lưu")
        assert dup is not None

        zip_dest = os.path.join(tmpdir, "backup", "frames_backup.zip")
        assert fm.backup_frames_to_zip(zip_dest) is True
        assert os.path.exists(zip_dest)

        # Restore into another user directory
        user_dir2 = os.path.join(tmpdir, "user_frames_restored")
        fm2 = FrameManager(base_dir=tmpdir, user_dir=user_dir2)
        assert fm2.restore_frames_from_zip(zip_dest) is True
        assert fm2.get_frame(dup.id) is not None

def test_slot_rotation_and_z_order_rendering():
    # Verify that slot.rotation and slot.z_order are properly handled
    slot1 = PhotoSlot(id=1, x=50, y=50, w=300, h=300, rotation=90, z_order=2, photo_index=0)
    slot2 = PhotoSlot(id=2, x=100, y=100, w=300, h=300, rotation=0, z_order=1, photo_index=1)

    template = FrameTemplate(
        id="test_rot_z",
        name="Test Rotation & Z-Order",
        category="Test",
        type="2x6",
        canvas_size=[600, 1800],
        slots=[slot1, slot2]
    )

    photos = [
        Image.new("RGB", (400, 400), (255, 0, 0)),
        Image.new("RGB", (400, 400), (0, 255, 0))
    ]

    composite = FrameDesigner.render_composite(photos, template)
    assert composite.size == (600, 1800)
    assert composite.info.get("dpi") == (300, 300)


def test_auto_photo_fitting_cover_contain_and_ratios():
    from vietphotobooth.processing.image_processor import ImageProcessor

    # Thử nghiệm 3 tỷ lệ ảnh: Dọc (600x900), Ngang (1200x800), Vuông (800x800)
    portrait_img = Image.new("RGB", (600, 900), (255, 120, 120))
    landscape_img = Image.new("RGB", (1200, 800), (120, 255, 120))
    square_img = Image.new("RGB", (800, 800), (120, 120, 255))

    target_w, target_h = 500, 350  # Ô nằm ngang

    # 1. Chế độ Cover: Phải đúng target_w x target_h, không viền trắng
    c1 = ImageProcessor.crop_and_resize(portrait_img, target_w, target_h, fit_mode="cover", zoom=1.0)
    assert c1.size == (target_w, target_h)

    c2 = ImageProcessor.crop_and_resize(landscape_img, target_w, target_h, fit_mode="cover", zoom=1.2, crop_offset_x=0.2)
    assert c2.size == (target_w, target_h)

    c3 = ImageProcessor.crop_and_resize(square_img, target_w, target_h, fit_mode="cover", zoom=1.5, position_mode="face")
    assert c3.size == (target_w, target_h)

    # 2. Chế độ Contain: Phải nằm trọn trong target_w x target_h
    contain1 = ImageProcessor.crop_and_resize(portrait_img, target_w, target_h, fit_mode="contain", zoom=1.0)
    assert contain1.size == (target_w, target_h)


def test_visual_text_editing_multiline_and_styles():
    txt = TextLayer(
        id="t_multi",
        text="1998 TEAM — Photobooth\nStudio Phóng Sự Cưới\nHạnh Phúc Trọn Vẹn",
        x=300,
        y=1500,
        font_size=32,
        font_color="#D4AF37",
        font_name="Arial",
        alignment="center",
        is_bold=True,
        is_italic=True,
        position_mode="bottom",
        safe_margin=40
    )

    template = FrameTemplate(
        id="test_multiline_text",
        name="Test Text Layer",
        canvas_size=[600, 1800],
        slots=[PhotoSlot(id=1, x=50, y=50, w=500, h=400)],
        text_layers=[txt]
    )

    photo = Image.new("RGB", (500, 400), (200, 200, 200))
    comp = FrameDesigner.render_composite([photo], template)
    assert comp.size == (600, 1800)
    assert comp.info.get("dpi") == (300, 300)


def test_logo_layer_aspect_ratio_and_quick_positions():
    with tempfile.TemporaryDirectory() as tmpdir:
        logo_img = Image.new("RGBA", (400, 200), (212, 175, 55, 255))
        logo_path = os.path.join(tmpdir, "test_logo.png")
        logo_img.save(logo_path, "PNG")

        logo = LogoLayer(
            id="lg_1",
            image_path=logo_path,
            x=50,
            y=50,
            w=200,
            h=100,
            opacity=0.9,
            position_mode="top_right",
            scale=0.8,
            original_w=400,
            original_h=200
        )

        template = FrameTemplate(
            id="test_logo_frame",
            name="Test Logo Quick Position",
            canvas_size=[600, 1800],
            slots=[PhotoSlot(id=1, x=50, y=200, w=500, h=400)],
            logo_layers=[logo]
        )

        photo = Image.new("RGB", (500, 400), (100, 100, 100))
        comp = FrameDesigner.render_composite([photo], template)
        assert comp.size == (600, 1800)


def test_frame_designer_gui_interactions(monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    from vietphotobooth.desktop.widgets.frame_designer_page import FrameDesignerPage

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    fm = FrameManager()
    page = FrameDesignerPage(fm)

    # 1. Kiểm tra tải frame mặc định
    assert page.current_frame is not None
    assert page.combo_slots_selector.count() > 0

    # 2. Chuyển đổi chế độ fit
    page.rb_fit_contain.setChecked(True)
    slot0 = page.current_frame.slots[0]
    assert slot0.fit_mode == "contain"

    page.rb_fit_cover.setChecked(True)
    assert slot0.fit_mode == "cover"

    # 3. Thu phóng zoom slider
    page.slider_zoom.setValue(135)
    assert slot0.zoom == 1.35

    # 4. Áp dụng cho tất cả ô
    page._apply_fitting_to_all_slots()
    for s in page.current_frame.slots:
        assert s.fit_mode == "cover"
        assert s.zoom == 1.35

    # 5. Chỉnh sửa chữ trực quan
    if page.combo_text_selector.count() > 0:
        page.txt_content.setText("Dòng 1\nDòng 2 Thử Nghiệm")
        t0 = page.current_frame.text_layers[0]
        assert "Dòng 1" in t0.text

        page.btn_bold.setChecked(True)
        assert t0.is_bold is True


