"""
Comprehensive tests for 1998 TEAM Redesign Panels:
- Panel 1: Thư viện chọn khung ảnh (FrameGalleryPage & FrameTabContainer)
- Panel 2: Cài đặt máy in (PrintingPage & PrintMarginPreviewWidget & dual routing)
- Panel 3: Màn hình chờ khách (GuestIdleScreen)
- Panel 4: Quản lý sự kiện (EventsPage & EventManager delete/create)
"""

import os
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from vietphotobooth.core.events import EventManager
from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.desktop.widgets.frame_gallery_page import FrameGalleryPage
from vietphotobooth.desktop.widgets.frame_tab_container import FrameTabContainer
from vietphotobooth.desktop.widgets.printing_page import PrintingPage, PrintMarginPreviewWidget
from vietphotobooth.desktop.widgets.guest_idle_screen import GuestIdleScreen
from vietphotobooth.desktop.widgets.events_page import EventsPage


# =========================================================================
# PANEL 1: THƯ VIỆN CHỌN KHUNG ẢNH
# =========================================================================
def test_frame_gallery_and_tab_container(qapp):
    fm = FrameManager()
    container = FrameTabContainer(fm)

    # 1. Kiểm tra Gallery Page khởi tạo đủ 16+ mẫu
    gallery = container.gallery_page
    assert gallery is not None
    assert len(gallery.cards) >= 16

    # 2. Kiểm tra bộ lọc tỷ lệ 2x6 và 4x6
    gallery._on_ratio_clicked("2x6")
    assert all("2x6" in card.template.type for card in gallery.cards.values())

    gallery._on_ratio_clicked("4x6")
    assert all("4x6" in card.template.type for card in gallery.cards.values())

    # 3. Kiểm tra tìm kiếm theo tên
    gallery._on_ratio_clicked("Tất cả")
    gallery.txt_search.setText("Basic")
    assert all("basic" in card.template.name.lower() for card in gallery.cards.values())

    # 4. Kiểm tra chọn khung phát tín hiệu
    selected_frames = []
    container.frame_selected.connect(lambda fid: selected_frames.append(fid))
    first_id = list(gallery.cards.keys())[0]
    gallery._on_card_clicked(first_id)
    assert len(selected_frames) == 1
    assert selected_frames[0] == first_id

    # 5. Kiểm tra ủy quyền thuộc tính sang designer_page
    assert hasattr(container, "scroll_area")
    assert hasattr(container, "combo_slots_selector")
    assert hasattr(container, "btn_apply_all_slots")

    container.close()


# =========================================================================
# PANEL 2: CÀI ĐẶT MÁY IN CHUYÊN NGHIỆP
# =========================================================================
def test_printing_page_redesign_and_dual_routing(qapp):
    pm = PrintManager()
    pp = PrintingPage(pm)

    # 1. Kiểm tra 2 thẻ phân luồng máy in Strip 2x6 và Full 4x6
    assert pp.combo_strip is not None
    assert pp.combo_full is not None
    assert pp.preview_widget is not None

    # 2. Kiểm tra bộ điều khiển bù lề Offset X, Y và Zoom
    pp.spin_x.setValue(5)
    pp.spin_y.setValue(-3)
    pp.spin_zoom.setValue(1.05)
    assert pp.preview_widget.offset_x == 5
    assert pp.preview_widget.offset_y == -3
    assert pp.preview_widget.zoom == 1.05

    # 3. Kiểm tra nút đặt lại (Reset)
    pp.btn_reset_align.click()
    assert pp.spin_x.value() == 0
    assert pp.spin_y.value() == 0
    assert pp.spin_zoom.value() == 1.0

    # 4. Kiểm tra bộ đếm giấy in và nạp nhanh +100
    initial_paper = pm.paper_count
    pp._refill_paper(100)
    assert pm.paper_count == initial_paper + 100

    pp.close()
    pm.stop()


# =========================================================================
# PANEL 3: MÀN HÌNH CHỜ DÀNH CHO KHÁCH (GUEST IDLE SCREEN)
# =========================================================================
def test_guest_idle_screen(qapp):
    screen = GuestIdleScreen()

    # 1. Kiểm tra các tín hiệu khởi động và quản trị
    started = []
    admin_exit = []
    screen.touch_to_start.connect(lambda: started.append(True))
    screen.admin_requested.connect(lambda: admin_exit.append(True))

    # Chạm màn hình để bắt đầu
    screen._on_screen_tapped()
    assert len(started) == 1

    # Nút bánh răng quản trị
    screen._on_admin_clicked()
    assert len(admin_exit) == 1

    # Kiểm tra phương thức hoạt ảnh an toàn
    screen.start_animations()
    screen.stop_animations()

    screen.close()


# =========================================================================
# PANEL 4: QUẢN LÝ SỰ KIỆN & THƯ VIỆN
# =========================================================================
def test_events_page_redesign_and_management(qapp, tmp_path):
    em = EventManager(storage_root=str(tmp_path))
    pm = PrintManager()
    tm = TokenManager()

    # 1. Tạo sự kiện mới
    test_evt_name = "DamCuoi_KhangNgoc_2026"
    assert em.create_event(test_evt_name) is True
    assert em.set_active_event(test_evt_name) is True
    assert em.get_active_event_name() == test_evt_name

    # 2. Khởi tạo EventsPage
    ep = EventsPage(em, pm, tm)
    assert ep.lbl_active_name.text() == test_evt_name
    assert ep.table_events.rowCount() >= 2  # SuKien_MacDinh và DamCuoi_KhangNgoc_2026

    # 3. Tìm kiếm sự kiện
    ep.txt_search_event.setText("KhangNgoc")
    assert ep.table_events.rowCount() == 1

    ep.txt_search_event.clear()
    assert ep.table_events.rowCount() >= 2

    # 4. Xóa an toàn sự kiện và tự động quay về sự kiện mặc định
    em.delete_event(test_evt_name)
    assert em.get_active_event_name() != test_evt_name

    ep.close()
    pm.stop()
