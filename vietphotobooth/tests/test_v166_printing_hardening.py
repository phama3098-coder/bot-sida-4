"""
Unit & Integration Tests for 1998 TEAM v1.6.6 Printing Hardening
Verifies:
- PrintPresetRegistry and DNP/Citizen/Sinfonia/Generic matching
- Safety margin zoom (0.98) configuration and selective application
- Auto-orientation matching logic
- Thermal pacing delay configuration and multi-copy handling
- Preservation of v1.6.5 default printing behavior for generic printers
"""

import os
import time
import pytest
from PIL import Image

from vietphotobooth.printing.presets import (
    PrintPreset, PrintPresetRegistry, PRESET_DNP_RX1HS_4X6,
    PRESET_CITIZEN_CY02_4X6, PRESET_GENERIC_PHOTO
)
from vietphotobooth.printing.spooler import WindowsPrintSpooler
from vietphotobooth.printing.manager import PrintManager, PrintJob
from vietphotobooth.core.config import ConfigManager


@pytest.fixture
def temp_test_image(tmp_path):
    """Tạo một file ảnh mẫu 1200x1800 px (4x6 dọc)."""
    img_path = str(tmp_path / "test_photo.jpg")
    img = Image.new("RGB", (1200, 1800), color=(240, 240, 240))
    img.save(img_path, "JPEG")
    return img_path


@pytest.fixture
def temp_landscape_image(tmp_path):
    """Tạo một file ảnh mẫu 1800x1200 px (4x6 ngang)."""
    img_path = str(tmp_path / "test_landscape.jpg")
    img = Image.new("RGB", (1800, 1200), color=(200, 220, 240))
    img.save(img_path, "JPEG")
    return img_path


def test_preset_registry_matching():
    """Kiểm tra nhận diện đúng model máy in và fallback generic an toàn."""
    # 1. DNP DS-RX1HS
    preset_rx1 = PrintPresetRegistry.get_preset_for_printer("DNP DS-RX1")
    assert preset_rx1.is_dye_sub is True
    assert preset_rx1.supports_safety_margin is True
    assert preset_rx1.default_safety_margin_zoom == 0.98
    assert preset_rx1.supports_auto_orientation is True
    assert preset_rx1.default_thermal_pacing_sec == 2.0

    # 2. Citizen CY-02
    preset_citizen = PrintPresetRegistry.get_preset_for_printer("Citizen CY-02 Printer")
    assert preset_citizen.is_dye_sub is True
    assert preset_citizen.supports_safety_margin is True

    # 3. Generic / PDF / Virtual printer -> Fallback bảo toàn hành vi v1.6.5
    preset_generic = PrintPresetRegistry.get_preset_for_printer("Microsoft Print to PDF")
    assert preset_generic.is_dye_sub is False
    assert preset_generic.supports_safety_margin is False
    assert preset_generic.default_safety_margin_zoom == 1.0
    assert preset_generic.supports_auto_orientation is False
    assert preset_generic.default_thermal_pacing_sec == 0.0


def test_is_dye_sub_printer_signatures():
    """Kiểm tra hàm nhận diện máy in nhiệt thăng hoa."""
    assert PrintPresetRegistry.is_dye_sub_printer("DNP DS-RX1HS") is True
    assert PrintPresetRegistry.is_dye_sub_printer("DNP QW410") is True
    assert PrintPresetRegistry.is_dye_sub_printer("Sinfonia CHC-S6145") is True
    assert PrintPresetRegistry.is_dye_sub_printer("Canon Selphy CP1300") is False
    assert PrintPresetRegistry.is_dye_sub_printer("HP LaserJet 1020") is False
    assert PrintPresetRegistry.is_dye_sub_printer("") is False


def test_spooler_simulation_generic_preserves_default(temp_test_image):
    """Máy in generic không bị áp dụng safety margin zoom ngoài ý muốn."""
    res = WindowsPrintSpooler.send_image_to_printer(
        printer_name="Virtual Generic Test Printer",
        image_path=temp_test_image,
        copies=1,
        zoom=1.0
    )
    assert res["success"] is True
    assert res["effective_safety_zoom"] == 1.0
    assert res["combined_zoom"] == 1.0


def test_spooler_simulation_dnp_safety_margin(temp_test_image):
    """Máy in DNP tự động áp dụng safety margin zoom 0.98."""
    preset = PrintPresetRegistry.get_preset_for_printer("DNP DS-RX1")
    res = WindowsPrintSpooler.send_image_to_printer(
        printer_name="Virtual DNP DS-RX1 Printer",
        image_path=temp_test_image,
        copies=1,
        zoom=1.0,
        preset=preset,
        safety_margin_enabled=True,
        safety_margin_zoom=0.98
    )
    assert res["success"] is True
    assert res["effective_safety_zoom"] == 0.98
    assert abs(res["combined_zoom"] - 0.98) < 1e-4


def test_spooler_safety_margin_disabled_by_config(temp_test_image):
    """Khi người dùng tắt safety margin trong cấu hình, zoom được giữ nguyên 1.0."""
    preset = PrintPresetRegistry.get_preset_for_printer("DNP DS-RX1")
    res = WindowsPrintSpooler.send_image_to_printer(
        printer_name="Virtual DNP DS-RX1 Printer",
        image_path=temp_test_image,
        copies=1,
        zoom=1.0,
        preset=preset,
        safety_margin_enabled=False
    )
    assert res["success"] is True
    assert res["effective_safety_zoom"] == 1.0
    assert res["combined_zoom"] == 1.0


def test_spooler_thermal_pacing_simulation(temp_test_image):
    """Kiểm tra tính năng giãn cách lệnh in đa bản."""
    t_start = time.time()
    res = WindowsPrintSpooler.send_image_to_printer(
        printer_name="Virtual DNP DS-RX1 Printer",
        image_path=temp_test_image,
        copies=2,
        thermal_pacing_sec=0.1
    )
    t_elapsed = time.time() - t_start
    assert res["success"] is True
    assert res["effective_pacing"] == 0.1
    assert t_elapsed >= 0.09


def test_print_manager_settings_persistence(tmp_path):
    """Kiểm tra lưu trữ và tải cấu hình mới trong PrintManager."""
    cfg_file = str(tmp_path / "config.json")
    cfg = ConfigManager(config_path=cfg_file)

    mgr = PrintManager(config_mgr=cfg)
    mgr.safety_margin_enabled = True
    mgr.safety_margin_zoom = 0.97
    mgr.auto_orientation_enabled = True
    mgr.thermal_pacing_sec = 2.5
    mgr.save_settings()

    # Tải lại với instance mới
    cfg2 = ConfigManager(config_path=cfg_file)
    mgr2 = PrintManager(config_mgr=cfg2)
    assert mgr2.safety_margin_enabled is True
    assert abs(mgr2.safety_margin_zoom - 0.97) < 1e-4
    assert mgr2.auto_orientation_enabled is True
    assert abs(mgr2.thermal_pacing_sec - 2.5) < 1e-4
    mgr.stop()
    mgr2.stop()
