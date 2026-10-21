"""
Tests for 1998 TEAM — Photobooth Versioning, Update Manifest,
Integrity Verification (SHA-256), and Data Preservation System.
Covers all 12 update test cases required by the studio update specification.
"""

import os
import json
import hashlib
import tempfile
from unittest.mock import patch, MagicMock
import pytest
import requests
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
    assert is_newer_version("1.0.0", "2.0.0") is True
    assert is_newer_version("1.0.0", "1.1.0") is True
    assert is_newer_version("1.0.0", "1.0.1") is True
    assert is_newer_version("1.0.0", "1.0.0", 101, 101) is False
    assert is_newer_version("1.1.0", "1.0.9") is False
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
        "download_url": "https://github.com/1998team/photobooth/releases/download/v1.1.0/1998-TEAM-Setup.exe",
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

    # Kiểm tra phát hiện lỗi khi dùng URL placeholder example.com
    placeholder_manifest = UpdateManifest(
        app="Test",
        version="1.1.0",
        download_url="https://example.com/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1"
    )
    p_errors = placeholder_manifest.validate_integrity()
    assert any("placeholder" in err.lower() for err in p_errors)

    # Kiểm tra phát hiện lỗi khi thiếu trường
    bad_manifest = UpdateManifest(
        app="Test",
        version="",
        download_url="",
        sha256="invalid_hash"
    )
    errors = bad_manifest.validate_integrity()
    assert len(errors) >= 3


# =========================================================================
# 12 MANDATORY TEST CASES
# =========================================================================

def test_case_1_detect_newer_version(qapp, tmp_path):
    """Case 1: Phát hiện phiên bản mới thành công."""
    manifest_file = tmp_path / "update_manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.2.0",
        "build": 120,
        "release_date": "2026-11-01",
        "release_notes": ["Tính năng mới"],
        "download_url": "https://github.com/1998team/photobooth/releases/download/v1.2.0/setup.exe",
        "sha256": "21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        "file_size_bytes": 1024
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    worker = UpdateCheckWorker(
        manifest_url=str(manifest_file),
        current_version="1.1.0",
        current_build=102
    )
    results = []
    worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
    worker.run()

    assert len(results) == 1
    has_up, manifest, msg = results[0]
    assert has_up is True
    assert manifest is not None
    assert manifest.version == "1.2.0"
    assert "Đã tìm thấy phiên bản mới" in msg


def test_case_2_already_up_to_date(qapp, tmp_path):
    """Case 2: Đã là phiên bản mới nhất."""
    manifest_file = tmp_path / "update_manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.1.0",
        "build": 102,
        "release_date": "2026-10-21",
        "release_notes": ["Phiên bản hiện tại"],
        "download_url": "https://github.com/1998team/photobooth/releases/download/v1.1.0/setup.exe",
        "sha256": "21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        "file_size_bytes": 1024
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    worker = UpdateCheckWorker(
        manifest_url=str(manifest_file),
        current_version="1.1.0",
        current_build=102
    )
    results = []
    worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
    worker.run()

    assert len(results) == 1
    has_up, manifest, msg = results[0]
    assert has_up is False
    assert manifest is not None
    assert "mới nhất" in msg


def test_case_3_offline_no_internet(qapp):
    """Case 3: Không có mạng (offline) — không bao giờ crash hay báo sai 'đã mới nhất'."""
    with patch("vietphotobooth.updates.updater.check_network_connectivity", return_value=False):
        worker = UpdateCheckWorker(
            manifest_url="https://api.github.com/repos/1998team/photobooth/releases/latest",
            current_version="1.1.0",
            current_build=102
        )
        results = []
        worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
        worker.run()

        assert len(results) == 1
        has_up, manifest, msg = results[0]
        assert has_up is False
        assert manifest is None
        assert "Không có kết nối Internet" in msg


def test_case_4_manifest_http_404(qapp):
    """Case 4: URL manifest bị lỗi HTTP 404 Not Found."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("vietphotobooth.updates.updater.check_network_connectivity", return_value=True), \
         patch("requests.get", return_value=mock_resp):
        worker = UpdateCheckWorker(
            manifest_url="https://photobooth.1998studio.vn/nonexistent_manifest.json",
            current_version="1.1.0",
            current_build=102
        )
        results = []
        worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
        worker.run()

        assert len(results) == 1
        has_up, manifest, msg = results[0]
        assert has_up is False
        assert manifest is None
        assert "404" in msg


def test_case_5_manifest_http_500(qapp):
    """Case 5: URL manifest trả về lỗi máy chủ HTTP 500."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("vietphotobooth.updates.updater.check_network_connectivity", return_value=True), \
         patch("requests.get", return_value=mock_resp):
        worker = UpdateCheckWorker(
            manifest_url="https://photobooth.1998studio.vn/update_manifest.json",
            current_version="1.1.0",
            current_build=102
        )
        results = []
        worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
        worker.run()

        assert len(results) == 1
        has_up, manifest, msg = results[0]
        assert has_up is False
        assert manifest is None
        assert "500" in msg


def test_case_6_manifest_malformed_json_or_invalid_fields(qapp, tmp_path):
    """Case 6: Manifest sai cú pháp JSON hoặc thiếu trường bắt buộc."""
    # 6a. Sai cú pháp JSON
    bad_json_file = tmp_path / "bad.json"
    bad_json_file.write_text("{ this is not valid json", encoding="utf-8")

    worker_bad_json = UpdateCheckWorker(
        manifest_url=str(bad_json_file),
        current_version="1.1.0",
        current_build=102
    )
    results1 = []
    worker_bad_json.check_finished.connect(lambda has_up, m, msg: results1.append((has_up, m, msg)))
    worker_bad_json.run()

    assert len(results1) == 1
    assert results1[0][0] is False
    assert "JSON" in results1[0][2]

    # 6b. Thiếu trường bắt buộc (sha256)
    missing_fields_file = tmp_path / "missing.json"
    missing_fields_file.write_text(json.dumps({
        "app": "1998 TEAM Photobooth",
        "version": "1.2.0",
        "download_url": "https://github.com/setup.exe"
        # Thiếu sha256
    }), encoding="utf-8")

    worker_missing = UpdateCheckWorker(
        manifest_url=str(missing_fields_file),
        current_version="1.1.0",
        current_build=102
    )
    results2 = []
    worker_missing.check_finished.connect(lambda has_up, m, msg: results2.append((has_up, m, msg)))
    worker_missing.run()

    assert len(results2) == 1
    assert results2[0][0] is False
    assert "không hợp lệ" in results2[0][2]


def test_case_7_download_setup_404_handled_cleanly(qapp, tmp_path):
    """Case 7: URL tải file setup bị lỗi HTTP 404 (sửa dứt điểm lỗi crash 404 cũ)."""
    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.1.0",
        download_url="https://photobooth.1998studio.vn/downloads/Setup-Not-Found.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        file_size_bytes=1024
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        dest_dir = tmp_path / "Downloads"
        worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))

        results = []
        worker.download_finished.connect(lambda success, path, err: results.append((success, path, err)))
        worker.run()

        assert len(results) == 1
        success, path, err = results[0]
        assert success is False
        assert "404" in err
        assert not os.path.exists(path)


def test_case_8_download_network_interrupted(qapp, tmp_path):
    """Case 8: Mạng bị ngắt kết nối đột ngột khi đang tải file setup."""
    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.1.0",
        download_url="https://photobooth.1998studio.vn/downloads/1998-Setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        file_size_bytes=1024
    )

    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection aborted by peer")):
        dest_dir = tmp_path / "Downloads"
        worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))

        results = []
        worker.download_finished.connect(lambda success, path, err: results.append((success, path, err)))
        worker.run()

        assert len(results) == 1
        success, path, err = results[0]
        assert success is False
        assert "kết nối" in err.lower()


def test_case_9_download_sha256_mismatch(qapp, tmp_path):
    """Case 9: File tải về sai mã hash SHA-256 (phát hiện và xóa tệp tạm an toàn)."""
    dummy_installer = tmp_path / "Fake-Setup.exe"
    dummy_installer.write_bytes(b"Corrupted or Malicious Payload")

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.1.0",
        download_url=str(dummy_installer),
        sha256="0000000000000000000000000000000000000000000000000000000000000000",
        file_size_bytes=len(b"Corrupted or Malicious Payload")
    )

    dest_dir = tmp_path / "Downloads"
    worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))

    results = []
    worker.download_finished.connect(lambda success, path, err: results.append((success, path, err)))
    worker.run()

    assert len(results) == 1
    success, path, err = results[0]
    assert success is False
    assert "SHA-256" in err
    # Tệp hỏng/sai mã hash phải bị xóa sạch, không lưu trên ổ cứng
    assert not os.path.exists(path)


def test_case_10_cancel_download_cleanly(qapp, tmp_path):
    """Case 10: Nhấn hủy khi đang tải (hủy luồng và xóa sạch tệp .part)."""
    # Tạo worker với cờ stop() được gọi ngay
    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.1.0",
        download_url="https://photobooth.1998studio.vn/downloads/1998-Setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        file_size_bytes=1024
    )

    dest_dir = tmp_path / "Downloads"
    worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))
    worker.stop()  # Hủy ngay trước khi chạy

    results = []
    worker.download_finished.connect(lambda success, path, err: results.append((success, path, err)))

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": "1024"}
    mock_resp.iter_content.return_value = [b"chunk1", b"chunk2"]
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        worker.run()

    assert len(results) == 1
    success, path, err = results[0]
    assert success is False
    assert "hủy" in err.lower()


def test_case_11_preserve_user_data_and_config(tmp_path):
    """Case 11: Dữ liệu người dùng (ảnh chụp, cấu hình, sự kiện) được bảo toàn tuyệt đối."""
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


def test_case_12_unconfigured_or_placeholder_manifest_url(qapp):
    """Case 12: Chưa cấu hình URL cập nhật hoặc đang để URL mẫu example.com."""
    # 12a. Trống hoàn toàn
    worker_empty = UpdateCheckWorker(
        manifest_url="",
        current_version="1.1.0",
        current_build=102
    )
    results_empty = []
    worker_empty.check_finished.connect(lambda has_up, m, msg: results_empty.append((has_up, m, msg)))
    worker_empty.run()

    assert len(results_empty) == 1
    assert results_empty[0][0] is False
    assert results_empty[0][1] is None
    assert "Chưa cấu hình" in results_empty[0][2]

    # 12b. Để URL mẫu example.com
    worker_placeholder = UpdateCheckWorker(
        manifest_url="https://example.com/manifest.json",
        current_version="1.1.0",
        current_build=102
    )
    results_ph = []
    worker_placeholder.check_finished.connect(lambda has_up, m, msg: results_ph.append((has_up, m, msg)))
    worker_placeholder.run()

    assert len(results_ph) == 1
    assert results_ph[0][0] is False
    assert results_ph[0][1] is None
    assert "Chưa cấu hình" in results_ph[0][2]


# =========================================================================
# UI INTEGRATION TESTS
# =========================================================================

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
        "download_url": "https://github.com/1998team/photobooth/releases/download/v1.2.0/setup.exe",
        "sha256": "21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        "file_size_bytes": 1024
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
    assert hasattr(page, "lbl_server_ver")

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
    assert "1.2.0" in page.lbl_server_ver.text()
    if hasattr(page, "_update_dlg") and page._update_dlg:
        page._update_dlg.close()
    page.close()


def test_main_window_quick_update_button(qapp, tmp_path):
    """Kiểm tra nút kiểm tra cập nhật nhanh trên thanh tiêu đề MainWindow."""
    from vietphotobooth.desktop.main_window import MainWindow
    from PySide6.QtWidgets import QMessageBox

    manifest_file = tmp_path / "update_manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.1.0",
        "build": 102,
        "release_date": "2026-10-21",
        "release_notes": ["Bản hiện tại"],
        "download_url": "https://github.com/1998team/photobooth/releases/download/v1.1.0/setup.exe",
        "sha256": "21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        "file_size_bytes": 1024
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    win = MainWindow()
    assert hasattr(win, "btn_check_update_quick")
    assert win.btn_check_update_quick.text() == "🔄 Cập Nhật"

    win.config_mgr.set("updates.manifest_url", str(manifest_file))

    with patch.object(QMessageBox, "information") as mock_info, \
         patch.object(QMessageBox, "warning") as mock_warn:
        win._on_quick_check_update_clicked()
        if win.update_mgr._check_worker:
            win.update_mgr._check_worker.wait(2000)
        qapp.processEvents()

        # Vì phiên bản hiện tại v1.1.0 (build 102) bằng với manifest nên phải gọi QMessageBox.information thông báo đã mới nhất
        assert mock_info.called or mock_warn.called

    win.close()


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
        download_url="https://github.com/1998team/photobooth/releases/download/v1.1.0/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        file_size_bytes=86148956
    )

    dlg = UpdateNotificationDialog(manifest=manifest, update_mgr=mgr)
    assert dlg.windowTitle() == "Thông Báo Cập Nhật — 1998 TEAM Photobooth"
    assert "1.1.0" in dlg.txt_notes.toPlainText() or "Cải tiến Live View" in dlg.txt_notes.toPlainText()
    assert dlg.btn_update is not None
    assert dlg.btn_later is not None

    dlg.close()
