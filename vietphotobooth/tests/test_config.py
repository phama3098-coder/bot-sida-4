"""
Automated Tests for VietPhotoBooth Configuration Manager
"""

import os
import tempfile
import pytest
from vietphotobooth.core.config import ConfigManager

def test_config_defaults_and_save():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "test_config.json")
        cfg = ConfigManager(config_path=cfg_path)

        assert cfg.get("app_name") == "VietPhotoBooth"
        assert cfg.get("countdown_seconds") == 5
        assert cfg.get("photos_per_session") == 3

        # Test verification of default PIN (1234)
        assert cfg.verify_pin("1234") is True
        assert cfg.verify_pin("9999") is False

        # Test PIN update
        assert cfg.set_pin("5678") is True
        assert cfg.verify_pin("5678") is True
        assert cfg.verify_pin("1234") is False

        # Test persistent reload
        cfg.set("event_title", "Đám Cưới Minh & Linh")
        cfg.save()

        cfg2 = ConfigManager(config_path=cfg_path)
        assert cfg2.get("event_title") == "Đám Cưới Minh & Linh"
        assert cfg2.verify_pin("5678") is True
