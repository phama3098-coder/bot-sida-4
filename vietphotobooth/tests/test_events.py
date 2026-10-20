"""
Automated Tests for Event Management and Directory Hierarchy
"""

import os
import tempfile
import pytest
from vietphotobooth.core.events import EventManager

def test_event_hierarchy_and_management():
    with tempfile.TemporaryDirectory() as tmpdir:
        em = EventManager(storage_root=tmpdir, current_event="DamCuoi_2026")

        dirs = em.get_current_dirs()
        assert os.path.exists(dirs["originals"])
        assert os.path.exists(dirs["final"])
        assert os.path.exists(dirs["thumbnails"])
        assert os.path.exists(dirs["templates"])
        assert os.path.exists(dirs["logs"])

        # Create new event
        assert em.create_event("SinhNhat_BaoAn") is True
        # Duplicate name should fail
        assert em.create_event("SinhNhat_BaoAn") is False

        # Switch event
        assert em.set_active_event("SinhNhat_BaoAn") is True
        assert em.current_event == "SinhNhat_BaoAn"

        # Rename event
        assert em.rename_event("SinhNhat_BaoAn", "SinhNhat_BaoAn_1Tuoi") is True
        assert em.current_event == "SinhNhat_BaoAn_1Tuoi"

        # List events
        events = em.list_events()
        event_names = [e["name"] for e in events]
        assert "DamCuoi_2026" in event_names
        assert "SinhNhat_BaoAn_1Tuoi" in event_names

        # Disk space check
        disk = em.check_disk_space(warning_threshold_gb=1.0)
        assert disk["total_gb"] > 0
        assert disk["free_gb"] > 0
