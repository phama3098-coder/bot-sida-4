"""
Test Suite: Responsive Layout, Connection Controls & Print Queue in Printing Page (Phân Hệ 3)
1998 TEAM Photobooth — Machine 2 (UI/UX Developer)
"""

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor

from vietphotobooth.printing.manager import (
    PrintManager, PrintJob, STATUS_COMPLETED, STATUS_SPOOLED, STATUS_ERROR, STATUS_PENDING
)
from vietphotobooth.desktop.widgets.printing_page import PrintingPage, PrintMarginPreviewWidget


@pytest.fixture
def print_page(qapp):
    pm = PrintManager()
    page = PrintingPage(pm)
    yield page
    page.close()
    pm.stop()


def test_printing_page_initialization(print_page):
    """Kiểm tra khởi tạo đầy đủ các thành phần điều khiển của PrintingPage."""
    pp = print_page

    # Header & controls
    assert pp.btn_refresh is not None
    assert pp.btn_refresh.minimumWidth() >= 90
    assert pp.btn_refresh.minimumHeight() >= 34

    # Dual routing cards
    assert pp.combo_strip is not None
    assert pp.combo_full is not None
    assert pp.lbl_strip_status is not None
    assert pp.lbl_full_status is not None
    assert pp.lbl_strip_preset is not None
    assert pp.lbl_full_preset is not None

    # Alignment & Preview
    assert pp.preview_widget is not None
    assert pp.spin_x is not None
    assert pp.spin_y is not None
    assert pp.spin_zoom is not None
    assert pp.btn_reset_align is not None
    assert pp.combo_orient is not None

    # Print Configuration
    assert pp.spin_copies is not None
    assert pp.chk_safety_margin is not None
    assert pp.chk_auto_orientation is not None
    assert pp.spin_thermal_pacing is not None

    # Paper Counter
    assert pp.lbl_paper_stats is not None
    assert pp.prog_paper is not None
    assert pp.spin_warning is not None

    # Print Queue Table
    assert pp.table_queue is not None
    assert pp.table_queue.columnCount() == 6
    assert pp.btn_refresh_queue is not None
    assert pp.btn_clear_completed is not None


@pytest.mark.parametrize("width,height", [
    (1920, 1080),
    (1366, 768),
    (1277, 752),
])
def test_printing_page_responsive_resolutions(qapp, width, height):
    """Kiểm tra bố cục PrintingPage tại 3 độ phân giải chuẩn, không vỡ layout."""
    pm = PrintManager()
    pp = PrintingPage(pm)
    pp.resize(QSize(width, height))
    pp.show()
    qapp.processEvents()

    # 1. ScrollArea hoạt động mượt mà
    assert pp.scroll_area is not None
    content = pp.scroll_area.widget()
    assert content is not None

    # 2. Chiều rộng của content widget khớp viewport (không tràn ngang)
    viewport_w = pp.scroll_area.viewport().width()
    content_w = content.width()
    assert content_w <= viewport_w + 5
    assert pp.scroll_area.horizontalScrollBar().maximum() == 0

    # 3. Nút Refresh Header không bị tràn hay co cụm
    assert pp.btn_refresh.isVisible()
    assert pp.btn_refresh.width() >= 90
    assert pp.btn_refresh.height() >= 34

    # 4. Các nút thao tác chính giữ nguyên kích thước tối thiểu
    assert pp.btn_save.width() >= 130
    assert pp.btn_save.height() >= 36
    assert pp.btn_test_print.width() >= 130
    assert pp.btn_test_print.height() >= 36

    # 5. Bảng Print Queue hiển thị chuẩn
    assert pp.table_queue.isVisible()
    assert pp.table_queue.horizontalHeader().isVisible()

    pp.close()
    pm.stop()


def test_print_margin_preview_widget_modes(print_page):
    """Kiểm tra widget xem trước lề in phản hồi mượt mà khi đổi hướng và điều chỉnh lề."""
    pp = print_page
    preview = pp.preview_widget

    # Mặc định dọc (Portrait)
    assert preview.orientation in ("portrait", "dọc (portrait)")
    assert preview.width() == 140
    assert preview.height() == 190

    # Chuyển sang ngang (Landscape)
    pp.combo_orient.setCurrentIndex(1)
    assert preview.orientation in ("landscape", "ngang (landscape)")
    assert preview.width() == 190
    assert preview.height() == 140

    # Điều chỉnh offset & zoom
    pp.spin_x.setValue(6)
    pp.spin_y.setValue(-4)
    pp.spin_zoom.setValue(1.08)
    assert preview.offset_x == 6
    assert preview.offset_y == -4
    assert preview.zoom == 1.08

    # Reset
    pp.btn_reset_align.click()
    assert pp.spin_x.value() == 0
    assert pp.spin_y.value() == 0
    assert pp.spin_zoom.value() == 1.0
    assert preview.offset_x == 0
    assert preview.offset_y == 0
    assert preview.zoom == 1.0


def test_printer_status_and_spooler_display(print_page):
    """Kiểm tra cập nhật trạng thái máy in và hàng đợi spooler."""
    pp = print_page

    # Giả lập gán trạng thái máy in Strip
    pp.lbl_strip_preset.setText("DNP DS-RX1HS Dye-Sub (300 DPI)")
    pp.lbl_strip_status.setText("🟢 Sẵn sàng (Ready)")
    pp.lbl_strip_detail.setText("Spooler: 2 tác vụ đang chờ")

    assert "Sẵn sàng" in pp.lbl_strip_status.text()
    assert "2 tác vụ" in pp.lbl_strip_detail.text()
    assert "DNP DS-RX1HS" in pp.lbl_strip_preset.text()

    # Giả lập gán trạng thái máy in Full bận hoặc ngoại tuyến
    pp.lbl_full_preset.setText("Citizen CY-02 Dye-Sub (300 DPI)")
    pp.lbl_full_status.setText("🔴 Ngoại tuyến (Offline)")
    pp.lbl_full_detail.setText("Spooler: Không có")

    assert "Ngoại tuyến" in pp.lbl_full_status.text()
    assert "Không có" in pp.lbl_full_detail.text()


def test_paper_counter_and_refill_logic(print_page):
    """Kiểm tra logic nạp giấy, thanh tiến trình và cảnh báo hết giấy."""
    pp = print_page
    pm = pp.print_mgr

    # Đặt số lượng giấy về 15 (dưới ngưỡng cảnh báo mặc định 20)
    pm.paper_count = 15
    pp._update_paper_ui()
    assert "15" in pp.lbl_paper_stats.text()
    assert "#EF4444" in pp.lbl_paper_stats.styleSheet()

    # Nạp nhanh +100
    pp._refill_paper(100)
    assert pm.paper_count == 115
    assert pp.prog_paper.value() == 115
    assert "#EF4444" not in pp.lbl_paper_stats.styleSheet()

    # Nạp nhanh +200
    pp._refill_paper(200)
    assert pm.paper_count == 315
    assert pp.prog_paper.value() == 315

    # Đặt lại bộ đếm về 0
    pp._refill_paper(-pm.paper_count)
    assert pm.paper_count == 0
    assert "0" in pp.lbl_paper_stats.text()
    assert "#EF4444" in pp.lbl_paper_stats.styleSheet()


def test_print_queue_table_population_and_actions(print_page, qapp):
    """Kiểm tra bảng Print Queue & History hiển thị dữ liệu và thao tác xóa hàng đợi."""
    pp = print_page
    pm = pp.print_mgr

    # Thêm 3 PrintJob giả lập vào print manager
    job1 = PrintJob("JOB-001", "strip_001.jpg", "DNP DS-RX1HS", copies=2, paper_size="2x6")
    job1.status = STATUS_COMPLETED
    job2 = PrintJob("JOB-002", "photo_002.jpg", "Citizen CY-02", copies=1, paper_size="4x6")
    job2.status = STATUS_SPOOLED
    job3 = PrintJob("JOB-003", "photo_003.jpg", "Citizen CY-02", copies=1, paper_size="4x6")
    job3.status = STATUS_ERROR
    job3.error_message = "Out of Paper"
    pm.jobs = [job1, job2, job3]

    pp._refresh_queue_table()
    qapp.processEvents()

    assert pp.table_queue.rowCount() == 3

    # Kiểm tra các dòng (Lưu ý: get_queue() đảo ngược thứ tự danh sách jobs)
    job_ids = [pp.table_queue.item(r, 0).text() for r in range(3)]
    assert "JOB-001" in job_ids
    assert "JOB-002" in job_ids
    assert "JOB-003" in job_ids

    # Tìm dòng của từng job để kiểm tra chi tiết
    row_001 = job_ids.index("JOB-001")
    assert "2x6" in pp.table_queue.item(row_001, 1).text()
    assert "2 bản" in pp.table_queue.item(row_001, 3).text()
    assert "Hoàn thành" in pp.table_queue.item(row_001, 4).text()

    row_002 = job_ids.index("JOB-002")
    assert "Đang xử lý" in pp.table_queue.item(row_002, 4).text()

    row_003 = job_ids.index("JOB-003")
    assert "Lỗi" in pp.table_queue.item(row_003, 4).text()

    # Thao tác Clear Completed Jobs
    pp.btn_clear_completed.click()
    qapp.processEvents()

    # Sau khi xóa job hoàn thành, chỉ còn 2 jobs
    assert pp.table_queue.rowCount() == 2
    remaining_ids = [pp.table_queue.item(r, 0).text() for r in range(pp.table_queue.rowCount())]
    assert "JOB-001" not in remaining_ids
    assert "JOB-002" in remaining_ids
    assert "JOB-003" in remaining_ids
