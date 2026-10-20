"""
Automated Tests for Windows Print Spooler and Print Queue Manager
"""

import os
import tempfile
import pytest
from vietphotobooth.printing.spooler import WindowsPrintSpooler
from vietphotobooth.printing.manager import PrintManager, STATUS_PENDING, STATUS_COMPLETED
from vietphotobooth.printing.dnp_rx1hs import DNPRX1HSProfile

def test_printer_enumeration():
    printers = WindowsPrintSpooler.get_installed_printers()
    assert isinstance(printers, list)
    assert len(printers) > 0

    default_pr = WindowsPrintSpooler.get_default_printer()
    assert isinstance(default_pr, str)

def test_dnp_rx1hs_profile():
    assert DNPRX1HSProfile.is_dye_sub_printer("DNP DS-RX1HS Printer") is True
    assert DNPRX1HSProfile.is_dye_sub_printer("Citizen CY-02") is True
    assert DNPRX1HSProfile.is_dye_sub_printer("HP LaserJet 1020") is False

    guide = DNPRX1HSProfile.get_hardware_guidelines()
    assert "2-inch Cut" in guide["cut_feature_name"]

def test_print_manager_queue_and_test_card():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_img_path = os.path.join(tmpdir, "test_print_sample.jpg")

        mgr = PrintManager()
        # Tạo test print card
        mgr.create_test_print_card(test_img_path)
        assert os.path.exists(test_img_path)

        # Kiểm tra kích thước test print card chuẩn 1200x1800
        valid, msg = DNPRX1HSProfile.validate_image_for_print(test_img_path, "4x6")
        assert valid is True

        # Gửi lệnh in vào hàng đợi
        job = mgr.submit_job(
            image_path=test_img_path,
            copies=2,
            paper_size="4x6",
            event_name="TestEvent"
        )
        assert job.job_id.startswith("JOB-")
        assert job.copies == 2

        queue = mgr.get_queue()
        assert any(j["job_id"] == job.job_id for j in queue)
