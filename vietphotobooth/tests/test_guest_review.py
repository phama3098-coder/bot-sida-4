"""
Unit tests for Guest Review, Frame Selection, Slot Photo Swap, Text & Sticker Editing workflow.
"""

import sys
import os
import pytest
from PIL import Image

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from vietphotobooth.desktop.widgets.guest_review_dialog import GuestReviewDialog
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.core.config import ConfigManager

# Khởi tạo QApplication cho pytest nếu chưa có
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


@pytest.fixture
def sample_photos():
    """Tạo 4 ảnh chụp mẫu với các màu khác nhau."""
    colors = [(220, 38, 38), (37, 99, 235), (22, 163, 74), (202, 138, 4)]
    photos = []
    for c in colors:
        im = Image.new("RGB", (1200, 800), color=c)
        photos.append(im)
    return photos


@pytest.fixture
def frame_manager():
    mgr = FrameManager()
    return mgr


def test_guest_review_dialog_init(sample_photos, frame_manager):
    """Kiểm tra khởi tạo hộp thoại cho khách: nạp ảnh, clone template an toàn, gán slot tự động."""
    dlg = GuestReviewDialog(
        photos=sample_photos,
        frame_mgr=frame_manager,
        event_name="DamCuoi_TuanLan",
        session_id="Session_Test01"
    )

    assert dlg.current_template is not None
    assert len(dlg.photos) == 4
    assert len(dlg.thumb_widgets) == 4

    # Kiểm tra các ô ảnh slot được gán ảnh tự động (slot 0 -> ảnh 0, slot 1 -> ảnh 1...)
    for i, slot in enumerate(dlg.current_template.slots):
        assert slot.photo_index == (i % len(sample_photos))

    # Kiểm tra template là bản sao độc lập (Deep copy)
    orig_template = frame_manager.get_frame(dlg.current_template.id)
    if orig_template:
        dlg.current_template.slots[0].x += 99
        assert orig_template.slots[0].x != dlg.current_template.slots[0].x

    dlg.close()


def test_guest_review_slot_photo_swap(sample_photos, frame_manager):
    """Kiểm tra chức năng hoán đổi ảnh giữa các ô."""
    dlg = GuestReviewDialog(
        photos=sample_photos,
        frame_mgr=frame_manager
    )

    assert len(dlg.current_template.slots) > 0

    # Giả lập chọn ô #0 và gán Ảnh #3
    dlg.canvas.selected_type = "slot"
    dlg.canvas.selected_index = 0
    dlg._assign_photo_to_selected_slot(photo_index=3)

    assert dlg.current_template.slots[0].photo_index == 3
    dlg.close()


def test_guest_review_slot_zoom_and_crop(sample_photos, frame_manager):
    """Kiểm tra phóng to thu nhỏ và căn giữa ảnh trong ô."""
    dlg = GuestReviewDialog(
        photos=sample_photos,
        frame_mgr=frame_manager
    )

    slot = dlg.current_template.slots[0]
    dlg.canvas.selected_type = "slot"
    dlg.canvas.selected_index = 0

    # 1. Điều chỉnh zoom lên 150%
    dlg._on_slot_zoom_slider_changed(150)
    assert slot.zoom == 1.5

    # 2. Dịch chuyển góc pan
    slot.crop_offset_x = 0.25
    slot.crop_offset_y = -0.15

    # 3. Bấm căn giữa
    dlg._reset_selected_slot_pan()
    assert slot.crop_offset_x == 0.0
    assert slot.crop_offset_y == 0.0
    assert slot.zoom == 1.0

    dlg.close()


def test_guest_review_text_editing(sample_photos, frame_manager):
    """Kiểm tra khách thêm lời chúc tiệc cưới, chọn phông chữ và đổi vị trí."""
    dlg = GuestReviewDialog(
        photos=sample_photos,
        frame_mgr=frame_manager
    )

    init_text_count = len(dlg.current_template.text_layers)

    # Thêm lời chúc nhanh
    dlg.txt_guest_input.setText("💍 Happy Wedding Tuấn & Lan")
    dlg._on_text_color_chosen("#D4AF37")
    dlg._add_guest_text()

    assert len(dlg.current_template.text_layers) == init_text_count + 1
    new_txt = dlg.current_template.text_layers[-1]
    assert new_txt.text == "💍 Happy Wedding Tuấn & Lan"
    assert new_txt.font_color == "#D4AF37"

    # Xóa chữ vừa thêm
    dlg.canvas.selected_type = "text"
    dlg.canvas.selected_index = len(dlg.current_template.text_layers) - 1
    dlg._delete_selected_text()
    assert len(dlg.current_template.text_layers) == init_text_count

    dlg.close()


def test_guest_review_sticker_adding_and_removing(sample_photos, frame_manager):
    """Kiểm tra thêm và xóa hình dán (Sticker)."""
    dlg = GuestReviewDialog(
        photos=sample_photos,
        frame_mgr=frame_manager
    )

    init_sticker_count = len(dlg.current_template.logo_layers)

    # Đường dẫn sticker mẫu
    test_sticker_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "Assets", "Stickers", "wedding", "heart.png"
    ))

    if os.path.exists(test_sticker_path):
        dlg._add_sticker(test_sticker_path)
        assert len(dlg.current_template.logo_layers) == init_sticker_count + 1
        st = dlg.current_template.logo_layers[-1]
        assert st.image_path == test_sticker_path
        assert st.scale > 0

        # Xóa sticker
        dlg.canvas.selected_type = "sticker"
        dlg.canvas.selected_index = len(dlg.current_template.logo_layers) - 1
        dlg._delete_selected_sticker()
        assert len(dlg.current_template.logo_layers) == init_sticker_count

    dlg.close()


def test_guest_review_undo(sample_photos, frame_manager):
    """Kiểm tra tính năng Hoàn Tác (Undo) khi khách thao tác nhầm."""
    dlg = GuestReviewDialog(
        photos=sample_photos,
        frame_mgr=frame_manager
    )

    init_slots_photo = [s.photo_index for s in dlg.current_template.slots]

    # Thay đổi ảnh ô 0
    dlg.canvas.selected_type = "slot"
    dlg.canvas.selected_index = 0
    dlg._assign_photo_to_selected_slot(2)
    assert dlg.current_template.slots[0].photo_index == 2

    # Bấm Hoàn tác
    dlg._undo()
    assert dlg.current_template.slots[0].photo_index == init_slots_photo[0]

    dlg.close()


def test_guest_review_confirm_and_render_parity(sample_photos, frame_manager):
    """Kiểm tra xuất ảnh thành phẩm 300 DPI chuẩn xác sau khi khách hoàn tất."""
    dlg = GuestReviewDialog(
        photos=sample_photos,
        frame_mgr=frame_manager,
        event_name="LeCuoi_1998"
    )

    dlg._on_confirm_and_render()
    assert dlg.final_composite is not None

    cw, ch = dlg.current_template.canvas_size
    assert dlg.final_composite.size == (cw, ch)
    assert dlg.final_composite.info.get("dpi") == (300, 300)

    dlg.close()


def test_guest_review_retake_flow(sample_photos, frame_manager):
    """Kiểm tra luồng Chụp lại: hủy bỏ session hiện tại và quay về màn hình chụp."""
    dlg = GuestReviewDialog(
        photos=sample_photos,
        frame_mgr=frame_manager
    )

    # Giả lập bấm Chụp Lại (is_retake = True)
    dlg.is_retake = True
    dlg.reject()

    assert dlg.is_retake is True
    assert dlg.final_composite is None
    dlg.close()
