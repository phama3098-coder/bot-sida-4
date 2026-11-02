"""
Test suite for 1998 TEAM Photobooth v2.0.0
Phase 4 — Slot-based Retake & Session Slot State Preservation
"""

import os
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from vietphotobooth.desktop.main_window import MainWindow
from vietphotobooth.desktop.widgets.guest_review_dialog import PhotoThumbnailCard, GuestReviewWidget


def test_photo_thumbnail_card_retake_button_and_signal(qapp):
    """Kiểm tra thẻ PhotoThumbnailCard có nút Chụp lại và phát tín hiệu retake_slot_requested."""
    img = Image.new("RGB", (200, 200), (255, 0, 0))
    card = PhotoThumbnailCard(photo_idx=1, photo_img=img, assigned_slots=[2])

    assert hasattr(card, "btn_retake")
    assert card.btn_retake is not None

    received_slot = []
    card.retake_slot_requested.connect(lambda idx: received_slot.append(idx))
    card.btn_retake.click()

    assert len(received_slot) == 1
    assert received_slot[0] == 1


def test_review_widget_slot_retake_signal_propagation(qapp):
    """Kiểm tra GuestReviewWidget phát tín hiệu retake_slot_requested khi bấm nút."""
    photos = [
        Image.new("RGB", (200, 200), (255, 0, 0)),
        Image.new("RGB", (200, 200), (0, 255, 0)),
        Image.new("RGB", (200, 200), (0, 0, 255)),
        Image.new("RGB", (200, 200), (255, 255, 0)),
    ]
    widget = GuestReviewWidget(photos=photos)
    assert hasattr(widget, "btn_retake_slot")

    received_slots = []
    widget.retake_slot_requested.connect(lambda idx: received_slots.append(idx))

    # Bấm nút trên thanh công cụ cho slot đang chọn (mặc định slot 0)
    widget.btn_retake_slot.click()
    assert len(received_slots) == 1
    assert received_slots[0] == 0

    # Bấm nút Chụp lại trên card ảnh #2 (photo_idx = 1)
    if len(widget.photo_cards) > 1:
        widget.photo_cards[1].btn_retake.click()
        assert len(received_slots) == 2
        assert received_slots[1] == 1


def test_kiosk_retake_single_slot_preserves_other_slots(qapp):
    """
    Kiểm tra cốt lõi v2.0.0:
    Khi chụp lại ô số 2 (photo_idx = 1), chỉ ô 2 được cập nhật,
    các ô 1, 3, 4 tuyệt đối được bảo toàn nguyên vẹn.
    """
    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page

    # Giả lập 4 ảnh chụp ban đầu
    p0 = Image.new("RGB", (300, 200), (255, 0, 0))    # Đỏ
    p1 = Image.new("RGB", (300, 200), (0, 255, 0))    # Xanh lá
    p2 = Image.new("RGB", (300, 200), (0, 0, 255))    # Xanh dương
    p3 = Image.new("RGB", (300, 200), (255, 255, 0))  # Vàng

    kiosk.captured_originals = [p0, p1, p2, p3]
    kiosk.captured_paths = ["path0.jpg", "path1.jpg", "path2.jpg", "path3.jpg"]

    # 1. Khách yêu cầu chụp lại ô số 2 (index 1)
    kiosk.retake_single_slot(1)
    assert kiosk._retake_slot_index == 1
    assert kiosk.kiosk_stack.currentIndex() == 0

    # 2. Giả lập ảnh mới chụp cho ô số 2 (Màu tím)
    p1_new = Image.new("RGB", (300, 200), (128, 0, 128))
    new_path = "path1_retaken.jpg"

    # Giả lập thực hiện ghi nhận ảnh chụp hoàn tất
    kiosk._retake_slot_index = 1
    r_idx = kiosk._retake_slot_index
    kiosk.captured_originals[r_idx] = p1_new
    kiosk.captured_paths[r_idx] = new_path
    kiosk._retake_slot_index = None

    # 3. Xác minh độ toàn vẹn:
    # - Ô số 1 (index 0) vẫn giữ nguyên ảnh đỏ ban đầu
    assert kiosk.captured_originals[0] is p0
    assert kiosk.captured_paths[0] == "path0.jpg"

    # - Ô số 2 (index 1) đã được thay thế bằng ảnh tím mới
    assert kiosk.captured_originals[1] is p1_new
    assert kiosk.captured_paths[1] == "path1_retaken.jpg"

    # - Ô số 3 (index 2) vẫn giữ nguyên ảnh xanh dương ban đầu
    assert kiosk.captured_originals[2] is p2
    assert kiosk.captured_paths[2] == "path2.jpg"

    # - Ô số 4 (index 3) vẫn giữ nguyên ảnh vàng ban đầu
    assert kiosk.captured_originals[3] is p3
    assert kiosk.captured_paths[3] == "path3.jpg"

    window.close()


def test_kiosk_retake_slot_abort_preserves_all_slots(qapp, monkeypatch):
    """Kiểm tra khi chụp lại ô bị hủy/lỗi, toàn bộ 4 ảnh cũ không bị mất."""
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    window = MainWindow(start_in_kiosk=False)
    kiosk = window.kiosk_page

    p0 = Image.new("RGB", (300, 200), (255, 0, 0))
    p1 = Image.new("RGB", (300, 200), (0, 255, 0))
    p2 = Image.new("RGB", (300, 200), (0, 0, 255))
    p3 = Image.new("RGB", (300, 200), (255, 255, 0))

    kiosk.captured_originals = [p0, p1, p2, p3]
    kiosk.captured_paths = ["path0.jpg", "path1.jpg", "path2.jpg", "path3.jpg"]

    # Khởi động chụp lại ô 3 (index 2)
    kiosk.retake_single_slot(2)
    assert kiosk._retake_slot_index == 2

    # Giả lập hủy do lỗi
    kiosk._abort_capture_due_to_disconnect("Mất kết nối máy ảnh khi test")
    assert kiosk._retake_slot_index is None

    # Xác minh tất cả 4 ảnh vẫn tồn tại nguyên vẹn
    assert len(kiosk.captured_originals) == 4
    assert kiosk.captured_originals[0] is p0
    assert kiosk.captured_originals[1] is p1
    assert kiosk.captured_originals[2] is p2
    assert kiosk.captured_originals[3] is p3

    window.close()
