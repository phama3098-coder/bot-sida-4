"""
Tests for 1998 TEAM — Photobooth Versioning, Update Manifest,
Integrity Verification (SHA-256), and Data Preservation System.
"""

import os
import json
import hashlib
import tempfile
import pytest
from PySide6.QtWidgets import QApplication

from vietphotobooth.version import (
    __version__, __build__, __app_name__,
    get_version_string, parse_semver, is_newer_version
)
from vietphotobooth.updates.manifest import UpdateManifest
from vietphotobooth.updates.updater import (
    UpdateManager, UpdateCheckWorker, UpdateDownloadWorker, check_network_connectivity
)
from vietphotobooth.updates.migration import (
    create_pre_update_backup, verify_user_data_intact, restore_backup
)
from vietphotobooth.core.config import ConfigManager


def test_version_and_semver_comparison():
    """Kiểm tra tính đúng đắn của phiên bản ứng dụng và thuật toán so sánh SemVer + Build."""
    assert __version__ in ("1.0.0", "1.1.0")
    assert __build__ > 0
    assert "1998 TEAM" in __app_name__

    ver_str = get_version_string(include_build=True)
    assert f"{__version__} (Build {__build__})" == ver_str

    # 1. Kiểm tra parse_semver
    assert parse_semver("1.0.0") == (1, 0, 0)
    assert parse_semver("v1.2.3") == (1, 2, 3)
    assert parse_semver("2.1") == (2, 1, 0)
    assert parse_semver("invalid") == (0, 0, 0)

    # 2. Kiểm tra is_newer_version
    # Major cao hơn
    assert is_newer_version("1.0.0", "2.0.0") is True
    # Minor cao hơn
    assert is_newer_version("1.0.0", "1.1.0") is True
    # Patch cao hơn
    assert is_newer_version("1.0.0", "1.0.1") is True
    # Bằng nhau
    assert is_newer_version("1.0.0", "1.0.0", 101, 101) is False
    # Thấp hơn
    assert is_newer_version("1.1.0", "1.0.9") is False
    # Cùng SemVer nhưng Build cao hơn
    assert is_newer_version("1.0.0", "1.0.0", current_build=101, candidate_build=102) is True
    assert is_newer_version("1.0.0", "1.0.0", current_build=105, candidate_build=101) is False


def test_update_manifest_model():
    """Kiểm tra cấu trúc và tính hợp lệ của UpdateManifest."""
    sample_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.1.0",
        "build": 105,
        "release_date": "2026-10-25",
        "release_notes": ["Nâng cấp giao diện", "Sửa lỗi máy in"],
        "download_url": "https://example.com/downloads/1998-TEAM-Setup.exe",
        "sha256": "21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        "file_size_bytes": 87465067,
        "minimum_supported_version": "1.0.0",
        "is_mandatory": False,
        "channel": "stable"
    }

    manifest = UpdateManifest.from_dict(sample_data)
    assert manifest.version == "1.1.0"
    assert manifest.build == 105
    assert len(manifest.release_notes) == 2
    assert manifest.validate_integrity() == []

    # Kiểm tra phát hiện lỗi khi thiếu trường
    bad_manifest = UpdateManifest(
        app="Test",
        version="",
        download_url="",
        sha256="invalid_hash"
    )
    errors = bad_manifest.validate_integrity()
    assert len(errors) >= 3


def test_update_check_with_local_manifest(qapp, tmp_path):
    """Kiểm tra luồng kiểm tra bản cập nhật với manifest tệp cục bộ (Local / Offline LAN)."""
    manifest_file = tmp_path / "update_manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.1.0",
        "build": 105,
        "release_date": "2026-10-25",
        "release_notes": ["Tính năng mới"],
        "download_url": "https://example.com/setup.exe",
        "sha256": "21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        "file_size_bytes": 1024
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    # 1. Trường hợp có bản mới hơn
    worker = UpdateCheckWorker(
        manifest_url=str(manifest_file),
        current_version="1.0.0",
        current_build=101
    )
    results = []
    worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
    worker.run()

    assert len(results) == 1
    has_up, manifest, msg = results[0]
    assert has_up is True
    assert manifest is not None
    assert manifest.version == "1.1.0"
    assert "Đã tìm thấy phiên bản mới" in msg

    # 2. Trường hợp đang ở phiên bản mới nhất
    worker_same = UpdateCheckWorker(
        manifest_url=str(manifest_file),
        current_version="1.1.0",
        current_build=105
    )
    results_same = []
    worker_same.check_finished.connect(lambda has_up, m, msg: results_same.append((has_up, m, msg)))
    worker_same.run()

    assert len(results_same) == 1
    has_up2, manifest2, msg2 = results_same[0]
    assert has_up2 is False
    assert "phiên bản mới nhất" in msg2


def test_update_check_unreachable_or_empty_url(qapp):
    """Kiểm tra hành vi an toàn khi URL trống hoặc không kết nối được (không bao giờ crash)."""
    worker = UpdateCheckWorker(
        manifest_url="",
        current_version="1.0.0",
        current_build=101
    )
    results = []
    worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
    worker.run()

    assert len(results) == 1
    assert results[0][0] is False
    assert "Chưa cấu hình" in results[0][2]


def test_update_download_sha256_verification_success(qapp, tmp_path):
    """Kiểm tra tải bộ cài và xác thực mã băm SHA-256 khớp 100%."""
    # Tạo tệp giả lập bộ cài đặt hợp lệ
    dummy_installer = tmp_path / "1998-TEAM-Setup-v1.1.0.exe"
    payload = b"Fake Installer Binary 1998 TEAM Photobooth 2026"
    dummy_installer.write_bytes(payload)

    valid_sha256 = hashlib.sha256(payload).hexdigest()

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.1.0",
        download_url=str(dummy_installer),
        sha256=valid_sha256,
        file_size_bytes=len(payload)
    )

    dest_dir = tmp_path / "Downloads"
    worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))

    results = []
    worker.download_finished.connect(lambda success, path, err: results.append((success, path, err)))
    worker.run()

    assert len(results) == 1
    success, installer_path, err = results[0]
    assert success is True
    assert os.path.exists(installer_path)
    assert err == ""


def test_update_download_sha256_tamper_detection(qapp, tmp_path):
    """Kiểm tra phát hiện tệp bị thay đổi / giả mạo qua SHA-256 và tự động xóa bỏ an toàn."""
    dummy_installer = tmp_path / "Tampered-Setup.exe"
    dummy_installer.write_bytes(b"Tampered or Corrupted Payload")

    # Đặt hash sai
    wrong_sha256 = "0000000000000000000000000000000000000000000000000000000000000000"

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.1.0",
        download_url=str(dummy_installer),
        sha256=wrong_sha256,
        file_size_bytes=100
    )

    dest_dir = tmp_path / "Downloads"
    worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))

    results = []
    worker.download_finished.connect(lambda success, path, err: results.append((success, path, err)))
    worker.run()

    assert len(results) == 1
    success, installer_path, err = results[0]
    # Phải thất bại và báo lỗi SHA-256
    assert success is False
    assert "SHA-256" in err
    # Tệp hỏng/giả mạo phải bị dọn dẹp, không được lưu trên máy
    assert not os.path.exists(installer_path)


def test_pre_update_backup_and_data_intact(tmp_path):
    """Kiểm tra cơ chế sao lưu tự động cấu hình trước khi cập nhật để bảo toàn dữ liệu người dùng."""
    user_data_dir = tmp_path / "UserData"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    # Giả lập config.json và sync_registry.json
    cfg_file = user_data_dir / "config.json"
    cfg_file.write_text(json.dumps({"app_name": "1998 TEAM", "photos_per_session": 4}), encoding="utf-8")

    sync_file = user_data_dir / "sync_registry.json"
    sync_file.write_text(json.dumps({"files": {}}), encoding="utf-8")

    # Tạo backup
    backup_folder = create_pre_update_backup(user_data_dir=str(user_data_dir))
    assert os.path.exists(backup_folder)
    assert os.path.exists(os.path.join(backup_folder, "config.json"))
    assert os.path.exists(os.path.join(backup_folder, "sync_registry.json"))

    # Kiểm tra verify_user_data_intact
    status = verify_user_data_intact(user_data_dir=str(user_data_dir))
    assert status["config_exists"] is True
    assert status["is_intact"] is True


def test_dismiss_version_in_session(qapp, tmp_path):
    """Kiểm tra chức năng 'Để sau' không làm phiền người dùng lặp đi lặp lại trong cùng phiên."""
    cfg = ConfigManager()
    mgr = UpdateManager(cfg)

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.1.0",
        download_url="https://example.com/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1"
    )

    # 1. Người dùng chọn 'Để sau'
    mgr.dismiss_version_for_session("1.1.0")
    assert "1.1.0" in mgr._dismissed_versions_in_session

    # 2. Khi chạy kiểm tra tự động, phiên bản 1.1.0 sẽ bị bỏ qua
    results = []
    mgr._on_check_finished(has_update=True, manifest=manifest, msg="Found", manual=False)
    # _latest_manifest được lưu nhưng thông báo tự động bị tắt
    assert mgr._latest_manifest == manifest


def test_settings_page_update_ui_manual_check(qapp, tmp_path):
    """Kiểm tra giao diện kiểm tra cập nhật trên tab Cài Đặt (SettingsPage)."""
    from vietphotobooth.desktop.widgets.settings_page import SettingsPage
    from vietphotobooth.sharing.token_manager import TokenManager

    manifest_file = tmp_path / "update_manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.2.0",
        "build": 110,
        "release_date": "2026-10-28",
        "release_notes": ["Giao diện studio cưới nâng cao"],
        "download_url": "https://example.com/setup.exe",
        "sha256": "21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1"
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    cfg = ConfigManager()
    tm = TokenManager()
    page = SettingsPage(cfg, tm)

    # 1. Kiểm tra tồn tại các thành phần UI
    assert hasattr(page, "txt_manifest_url")
    assert hasattr(page, "chk_auto_update")
    assert hasattr(page, "btn_check_update")
    assert hasattr(page, "lbl_update_status")

    # 2. Cài đặt manifest URL là file tạm
    page.txt_manifest_url.setText(str(manifest_file))
    page._save_config()
    assert cfg.get("updates.manifest_url") == str(manifest_file)

    # 3. Kích hoạt kiểm tra thủ công
    page._manual_check_update()
    if page.update_mgr._check_worker:
        page.update_mgr._check_worker.wait(2000)
    qapp.processEvents()

    # Trạng thái phải hiển thị thông tin tìm thấy bản cập nhật
    assert "1.2.0" in page.lbl_update_status.text()
    if hasattr(page, "_update_dlg") and page._update_dlg:
        page._update_dlg.close()
    page.close()


def test_update_notification_dialog(qapp):
    """Kiểm tra hiển thị hộp thoại thông báo cập nhật thanh lịch chuẩn studio cưới."""
    from vietphotobooth.updates.dialogs import UpdateNotificationDialog

    cfg = ConfigManager()
    mgr = UpdateManager(cfg)

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.1.0",
        build=102,
        release_date="2026-10-25",
        release_notes=["Cải tiến Live View", "Thêm phông chữ mới"],
        download_url="https://example.com/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1"
    )

    dlg = UpdateNotificationDialog(manifest=manifest, update_mgr=mgr)
    assert dlg.windowTitle() == "Thông Báo Cập Nhật — 1998 TEAM Photobooth"
    assert "1.1.0" in dlg.txt_notes.toPlainText() or "Cải tiến Live View" in dlg.txt_notes.toPlainText()
    assert dlg.btn_update is not None
    assert dlg.btn_later is not None

    dlg.close()

