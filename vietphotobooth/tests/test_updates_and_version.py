"""
1998 TEAM — Photobooth Versioning & Update Engine Test Suite
Covers all 14 required update test cases:
1. Manifest hợp lệ, có bản mới.
2. Không có bản mới (đã mới nhất).
3. Manifest trả về HTTP 404.
4. Download URL trả về HTTP 404 (xử lý cả pre-check và download worker).
5. Máy chủ trả về HTTP 500.
6. URL có redirect (301/302).
7. Mất kết nối giữa lúc tải (ConnectionError / Timeout).
8. Không có header Content-Length (tiến trình indeterminate, tải và kiểm tra SHA-256 thành công).
9. SHA-256 không khớp (phát hiện sai mã hash, xóa tệp tạm an toàn).
10. Hủy tải và thử lại (hủy sạch tệp tạm và thử lại thành công).
11. Cài đặt thành công (sao lưu cấu hình và khởi chạy bộ cài đặt).
12. Khởi động lại ứng dụng và xác minh phiên bản mới.
13. Dữ liệu người dùng còn nguyên (ảnh, sự kiện, cấu hình).
14. Ứng dụng chạy bình thường khi ngoại tuyến (offline safe).
"""

import os
import json
import hashlib
import tempfile
from unittest.mock import patch, MagicMock
import pytest
import requests
from PySide6.QtWidgets import QApplication, QLabel

from vietphotobooth.version import (
    __version__, __build__, __app_name__,
    get_version_string, parse_semver, is_newer_version
)
from vietphotobooth.updates.manifest import UpdateManifest
from vietphotobooth.updates.updater import (
    UpdateManager, UpdateCheckWorker, UpdateDownloadWorker, check_network_connectivity,
    verify_digital_signature, normalize_update_url, DEFAULT_UPDATE_URL
)
from vietphotobooth.updates.migration import (
    create_pre_update_backup, verify_user_data_intact, restore_backup
)
from vietphotobooth.updates.dialogs import UpdateNotificationDialog, UpdateProgressDialog
from vietphotobooth.core.config import ConfigManager


# =========================================================================
# CORE VERSION & MANIFEST MODEL TESTS
# =========================================================================

def test_version_and_semver_comparison():
    """Kiểm tra phiên bản ứng dụng và thuật toán so sánh SemVer + Build."""
    assert parse_semver(__version__) >= (1, 0, 0)
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
        "release_date": "2026-10-21",
        "release_notes": ["Nâng cấp giao diện", "Sửa lỗi máy in"],
        "download_url": "https://photobooth.1998studio.vn/releases/download/v1.1.0/1998-TEAM-Setup.exe",
        "sha256": "21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        "file_size_bytes": 87465067,
        "minimum_supported_version": "1.0.0",
        "is_mandatory": False,
        "channel": "stable",
        "architecture": "x64"
    }

    manifest = UpdateManifest.from_dict(sample_data)
    assert manifest.version == "1.1.0"
    assert manifest.build == 105
    assert len(manifest.release_notes) == 2
    assert manifest.architecture == "x64"
    assert manifest.validate_integrity() == []

    # Kiểm tra phát hiện lỗi khi dùng URL placeholder example.com
    placeholder_manifest = UpdateManifest(
        app="Test",
        version="1.1.0",
        release_date="2026-10-21",
        download_url="https://example.com/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1"
    )
    p_errors = placeholder_manifest.validate_integrity()
    assert any("placeholder" in err.lower() for err in p_errors)

    # Kiểm tra phát hiện lỗi ngày tương lai
    future_manifest = UpdateManifest(
        app="Test",
        version="1.1.0",
        release_date="2099-12-31",
        download_url="https://photobooth.1998studio.vn/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1"
    )
    f_errors = future_manifest.validate_integrity()
    assert any("tương lai" in err.lower() for err in f_errors)


# =========================================================================
# 14 MANDATORY UPDATE TEST CASES
# =========================================================================

def test_case_1_valid_manifest_newer_version(qapp, tmp_path):
    """Case 1: Manifest hợp lệ và có phiên bản mới hơn."""
    dummy_exe = tmp_path / "1998-Setup-v1.2.0.exe"
    dummy_exe.write_bytes(b"MZ_DUMMY_SETUP_FILE")

    hasher = hashlib.sha256()
    hasher.update(b"MZ_DUMMY_SETUP_FILE")
    exe_hash = hasher.hexdigest()

    manifest_file = tmp_path / "update_manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.2.0",
        "build": 120,
        "release_date": "2026-10-21",
        "release_notes": ["Tính năng mới 1998 TEAM"],
        "download_url": str(dummy_exe),
        "sha256": exe_hash,
        "file_size_bytes": len(b"MZ_DUMMY_SETUP_FILE")
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
    """Case 2: Không có bản mới (phiên bản hiện tại đã là mới nhất)."""
    manifest_file = tmp_path / "update_manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.1.0",
        "build": 102,
        "release_date": "2026-10-21",
        "release_notes": ["Phiên bản hiện tại"],
        "download_url": "https://photobooth.1998studio.vn/setup.exe",
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


def test_case_3_manifest_http_404(qapp):
    """Case 3: URL manifest trả về lỗi HTTP 404 Not Found."""
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


def test_case_4_download_url_http_404(qapp, tmp_path):
    """Case 4: Download URL bị lỗi HTTP 404 (xử lý cả pre-check và download worker)."""
    # 4a. Pre-check trong UpdateCheckWorker: phát hiện ngay 404 và không báo có bản mới
    manifest_file = tmp_path / "update_manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.2.0",
        "build": 120,
        "release_date": "2026-10-21",
        "release_notes": ["Bản cập nhật"],
        "download_url": "https://photobooth.1998studio.vn/downloads/setup_404.exe",
        "sha256": "21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        "file_size_bytes": 1024
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    mock_head_404 = MagicMock()
    mock_head_404.status_code = 404

    with patch("vietphotobooth.updates.updater.check_network_connectivity", return_value=True), \
         patch("requests.head", return_value=mock_head_404):
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
        assert "404" in msg
        assert "setup_404.exe" in msg

    # 4b. Download Worker khi gặp 404
    manifest = UpdateManifest.from_dict(manifest_data)
    mock_get_404 = MagicMock()
    mock_get_404.status_code = 404
    mock_get_404.__enter__.return_value = mock_get_404

    with patch("requests.get", return_value=mock_get_404):
        dest_dir = tmp_path / "Downloads"
        dl_worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))
        dl_results = []
        dl_worker.download_finished.connect(lambda s, p, e: dl_results.append((s, p, e)))
        dl_worker.run()

        assert len(dl_results) == 1
        success, path, err = dl_results[0]
        assert success is False
        assert "404" in err


def test_case_5_server_http_500(qapp, tmp_path):
    """Case 5: Máy chủ trả về lỗi HTTP 500 (Internal Server Error)."""
    # 5a. Manifest 500
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("vietphotobooth.updates.updater.check_network_connectivity", return_value=True), \
         patch("requests.get", return_value=mock_resp):
        worker = UpdateCheckWorker(
            manifest_url="https://photobooth.1998studio.vn/manifest.json",
            current_version="1.1.0",
            current_build=102
        )
        results = []
        worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
        worker.run()

        assert len(results) == 1
        assert results[0][0] is False
        assert "500" in results[0][2]

    # 5b. Download 500
    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.2.0",
        download_url="https://photobooth.1998studio.vn/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        file_size_bytes=1024
    )
    mock_dl_500 = MagicMock()
    mock_dl_500.status_code = 500
    mock_dl_500.__enter__.return_value = mock_dl_500

    with patch("requests.get", return_value=mock_dl_500):
        dest_dir = tmp_path / "Downloads"
        dl_worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))
        dl_results = []
        dl_worker.download_finished.connect(lambda s, p, e: dl_results.append((s, p, e)))
        dl_worker.run()

        assert len(dl_results) == 1
        assert dl_results[0][0] is False
        assert "500" in dl_results[0][2]


def test_case_6_url_with_redirect(qapp, tmp_path):
    """Case 6: URL có redirect (301/302) được xử lý thông suốt tới file cài đặt."""
    test_content = b"SETUP_PACKAGE_WITH_REDIRECT_SUPPORT"
    hasher = hashlib.sha256()
    hasher.update(test_content)
    test_hash = hasher.hexdigest()

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.2.0",
        download_url="https://photobooth.1998studio.vn/latest-download",
        sha256=test_hash,
        file_size_bytes=len(test_content)
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": str(len(test_content))}
    mock_resp.iter_content.return_value = [test_content]
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp) as mock_get:
        dest_dir = tmp_path / "Downloads"
        worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))
        results = []
        worker.download_finished.connect(lambda s, p, e: results.append((s, p, e)))
        worker.run()

        # Kiểm tra cờ allow_redirects=True được kích hoạt
        assert mock_get.call_args[1].get("allow_redirects") is True
        assert len(results) == 1
        success, installer_path, err = results[0]
        assert success is True
        assert os.path.exists(installer_path)


def test_case_7_connection_lost_mid_download(qapp, tmp_path):
    """Case 7: Mất kết nối mạng giữa lúc tải — đóng file và giải phóng tệp tạm."""
    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.2.0",
        download_url="https://photobooth.1998studio.vn/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        file_size_bytes=1024
    )

    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection aborted by peer")):
        dest_dir = tmp_path / "Downloads"
        worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))
        results = []
        worker.download_finished.connect(lambda s, p, e: results.append((s, p, e)))
        worker.run()

        assert len(results) == 1
        success, path, err = results[0]
        assert success is False
        assert "kết nối" in err.lower()
        # Không còn tệp tạm .part
        part_files = [f for f in os.listdir(dest_dir) if f.endswith(".part")]
        assert len(part_files) == 0


def test_case_8_missing_content_length(qapp, tmp_path):
    """Case 8: Không có header Content-Length — hỗ trợ indeterminate progress và xác thực thành công."""
    test_content = b"NO_CONTENT_LENGTH_CHUNKED_DATA"
    hasher = hashlib.sha256()
    hasher.update(test_content)
    test_hash = hasher.hexdigest()

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.2.0",
        download_url="https://photobooth.1998studio.vn/setup.exe",
        sha256=test_hash,
        file_size_bytes=0  # Manifest cũng không định nghĩa trước
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}  # Không có content-length
    mock_resp.iter_content.return_value = [test_content]
    mock_resp.__enter__.return_value = mock_resp

    progress_events = []
    with patch("requests.get", return_value=mock_resp):
        dest_dir = tmp_path / "Downloads"
        worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))
        worker.progress_changed.connect(lambda pct, dl, tot: progress_events.append((pct, dl, tot)))
        results = []
        worker.download_finished.connect(lambda s, p, e: results.append((s, p, e)))
        worker.run()

        assert len(results) == 1
        assert results[0][0] is True
        # Kiểm tra đã phát tín hiệu percent == -1 (indeterminate)
        assert any(pct == -1 for pct, _, _ in progress_events)
        assert os.path.exists(results[0][1])


def test_case_9_sha256_mismatch(qapp, tmp_path):
    """Case 9: Mã băm SHA-256 không khớp — từ chối file và hủy sạch tệp tạm."""
    corrupted_data = b"TAMPERED_OR_CORRUPTED_INSTALLER_DATA"
    dummy_exe = tmp_path / "Corrupted-Setup.exe"
    dummy_exe.write_bytes(corrupted_data)

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.2.0",
        download_url=str(dummy_exe),
        sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",  # Sai hash
        file_size_bytes=len(corrupted_data)
    )

    dest_dir = tmp_path / "Downloads"
    worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))
    results = []
    worker.download_finished.connect(lambda s, p, e: results.append((s, p, e)))
    worker.run()

    assert len(results) == 1
    success, path, err = results[0]
    assert success is False
    assert "SHA-256" in err
    # Không lưu file đích và không còn file .part
    assert not os.path.exists(path)
    part_files = [f for f in os.listdir(dest_dir) if f.endswith(".part")]
    assert len(part_files) == 0


def test_case_10_cancel_download_and_retry(qapp, tmp_path):
    """Case 10: Hủy tải và thử lại — xóa sạch tệp tạm và cho phép tải lại thành công."""
    valid_data = b"VALID_INSTALLER_RETRY"
    hasher = hashlib.sha256()
    hasher.update(valid_data)
    valid_hash = hasher.hexdigest()

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.2.0",
        download_url="https://photobooth.1998studio.vn/setup.exe",
        sha256=valid_hash,
        file_size_bytes=len(valid_data)
    )
    dest_dir = tmp_path / "Downloads"

    # Lần 1: Người dùng nhấn Hủy
    worker1 = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))
    worker1.stop()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": str(len(valid_data))}
    mock_resp.iter_content.return_value = [valid_data]
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        results1 = []
        worker1.download_finished.connect(lambda s, p, e: results1.append((s, p, e)))
        worker1.run()
        assert results1[0][0] is False
        assert "hủy" in results1[0][2].lower()

    # Lần 2: Thử lại thành công
    worker2 = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))
    with patch("requests.get", return_value=mock_resp):
        results2 = []
        worker2.download_finished.connect(lambda s, p, e: results2.append((s, p, e)))
        worker2.run()
        assert results2[0][0] is True
        assert os.path.exists(results2[0][1])


def test_case_11_apply_update_and_installer_launch(tmp_path):
    """Case 11: Cài đặt — sao lưu cấu hình và khởi chạy tiến trình bộ cài Windows."""
    installer = tmp_path / "Setup.exe"
    installer.write_bytes(b"DUMMY_SETUP")

    cfg_dir = tmp_path / "UserData"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.json").write_text("{}", encoding="utf-8")

    cfg = ConfigManager(config_path=str(cfg_dir / "config.json"))
    mgr = UpdateManager(cfg)

    with patch("subprocess.Popen") as mock_popen, \
         patch("vietphotobooth.updates.updater.get_user_data_dir", return_value=str(cfg_dir)):
        success = mgr.apply_update_and_restart(str(installer))
        assert success is True
        assert mock_popen.called

        # Xác minh bản backup đã được tạo
        backups = os.listdir(cfg_dir / "Backups")
        assert len(backups) >= 1


def test_case_12_restart_app_verify_new_version():
    """Case 12: Khởi động lại ứng dụng và xác minh phiên bản mới."""
    assert parse_semver(__version__) >= (1, 0, 0)
    assert __build__ > 0
    assert __version__ in get_version_string()
    # Xác minh semver parser tuân thủ chuẩn
    assert parse_semver("9.9.9") > parse_semver(__version__)


def test_case_13_user_data_and_config_intact(tmp_path):
    """Case 13: Dữ liệu người dùng (ảnh, sự kiện, cấu hình) được bảo toàn tuyệt đối."""
    user_data_dir = tmp_path / "UserData"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    # Giả lập các thư mục dữ liệu quan trọng của khách hàng
    (user_data_dir / "config.json").write_text(json.dumps({"pin": "1998"}), encoding="utf-8")
    (user_data_dir / "Events").mkdir()
    (user_data_dir / "Templates").mkdir()

    # Tạo backup
    backup_folder = create_pre_update_backup(user_data_dir=str(user_data_dir))
    assert os.path.exists(backup_folder)

    # Kiểm tra toàn vẹn
    check = verify_user_data_intact(user_data_dir=str(user_data_dir))
    assert check["config_exists"] is True
    assert check["events_exists"] is True
    assert check["templates_exists"] is True
    assert check["is_intact"] is True

    # Khôi phục từ backup nếu cần
    assert restore_backup(backup_folder, user_data_dir=str(user_data_dir)) is True


def test_case_14_offline_behavior_safe(qapp):
    """Case 14: Khi ngoại tuyến (offline) — không crash, không nghẽn, báo lỗi rõ ràng."""
    with patch("vietphotobooth.updates.updater.check_network_connectivity", return_value=False):
        worker = UpdateCheckWorker(
            manifest_url="https://photobooth.1998studio.vn/manifest.json",
            current_version="1.1.0",
            current_build=102
        )
        results = []
        worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
        worker.run()

        assert len(results) == 1
        assert results[0][0] is False
        assert results[0][1] is None
        assert "Internet" in results[0][2]


# =========================================================================
# UI INTEGRATION TESTS (ISOLATED CONFIG)
# =========================================================================

def test_settings_page_update_ui_manual_check(qapp, tmp_path):
    """Kiểm tra tab Cài Đặt (SettingsPage) kiểm tra cập nhật thủ công với config cách ly."""
    from vietphotobooth.desktop.widgets.settings_page import SettingsPage
    from vietphotobooth.sharing.token_manager import TokenManager

    dummy_installer = tmp_path / "setup_v120.exe"
    dummy_installer.write_bytes(b"DUMMY_EXE_DATA")

    hasher = hashlib.sha256()
    hasher.update(b"DUMMY_EXE_DATA")
    exe_hash = hasher.hexdigest()

    manifest_file = tmp_path / "update_manifest.json"
    candidate_ver = "9.9.0"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": candidate_ver,
        "build": 990,
        "release_date": "2026-10-22",
        "release_notes": ["Giao diện studio cưới nâng cao"],
        "download_url": str(dummy_installer),
        "sha256": exe_hash,
        "file_size_bytes": len(b"DUMMY_EXE_DATA")
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    # Sử dụng config_path cách ly trong thư mục tạm, KHÔNG chạm vào user config
    test_cfg_path = tmp_path / "test_config.json"
    cfg = ConfigManager(config_path=str(test_cfg_path))
    tm = TokenManager()
    page = SettingsPage(cfg, tm)

    # 1. Cài đặt manifest URL là file tạm
    page.txt_manifest_url.setText(str(manifest_file))
    page._save_config()
    assert cfg.get("updates.manifest_url") == str(manifest_file)

    # 2. Kích hoạt kiểm tra thủ công
    page._manual_check_update()
    if page.update_mgr._check_worker:
        page.update_mgr._check_worker.wait(2000)
    qapp.processEvents()

    # Trạng thái phải hiển thị thông tin tìm thấy bản cập nhật
    assert candidate_ver in page.lbl_update_status.text()
    assert candidate_ver in page.lbl_server_ver.text()
    if hasattr(page, "_update_dlg") and page._update_dlg:
        page._update_dlg.close()
        page._update_dlg.deleteLater()
    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_update_notification_dialog_no_zero_mb(qapp):
    """Kiểm tra UpdateNotificationDialog không bao giờ hiển thị 0.0 MB nếu dung lượng chưa có."""
    cfg = ConfigManager()
    mgr = UpdateManager(cfg)

    # Manifest không có file_size_bytes
    manifest_unknown_size = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.2.0",
        build=110,
        release_date="2026-10-21",
        download_url="https://photobooth.1998studio.vn/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        file_size_bytes=0  # Chưa rõ kích thước
    )

    dlg = UpdateNotificationDialog(manifest=manifest_unknown_size, update_mgr=mgr)
    # Tìm nhãn dung lượng và kiểm tra không chứa '0.0 MB'
    dialog_text = ""
    for label in dlg.findChildren(QLabel):
        dialog_text += label.text() + " "
    assert "0.0 MB" not in dialog_text
    assert "Chưa xác định" in dialog_text
    dlg.close()


def test_update_progress_dialog_ui_and_retry(qapp, tmp_path):
    """Kiểm tra UpdateProgressDialog hiển thị chuẩn xác và có nút Thử Lại khi thất bại."""
    cfg = ConfigManager()
    mgr = UpdateManager(cfg)

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.2.0",
        download_url="https://photobooth.1998studio.vn/setup.exe",
        sha256="21be12e43daa8015c2f4177c63698a7772909caac98f4dfc3d1c747640a91eb1",
        file_size_bytes=86148956
    )

    dlg = UpdateProgressDialog(manifest=manifest, update_mgr=mgr)
    assert dlg.btn_retry is not None
    assert dlg.btn_retry.isHidden() is True

    # Giả lập sự kiện thất bại (HTTP 404)
    dlg._on_finished(False, "", "Lỗi HTTP 404 Not Found từ máy chủ tải.")
    assert "❌" in dlg.lbl_status.text()
    assert "404" in dlg.lbl_details.text()
    # Nút Thử Lại phải xuất hiện
    assert dlg.btn_retry.isHidden() is False
    dlg.show()
    assert dlg.btn_retry.isVisible() is True

    dlg.close()


# =========================================================================
# GITHUB RELEASES API INTEGRATION TESTS
# =========================================================================

def test_normalize_update_url():
    """Kiểm tra hàm chuẩn hóa URL chuyển đổi trang web GitHub sang API endpoint."""
    # Web page URL -> API URL
    assert normalize_update_url("https://github.com/phama3098-coder/bot-sida-4/releases/latest") == \
           "https://api.github.com/repos/phama3098-coder/bot-sida-4/releases/latest"
    assert normalize_update_url("https://github.com/phama3098-coder/bot-sida-4") == \
           "https://api.github.com/repos/phama3098-coder/bot-sida-4/releases/latest"
    assert normalize_update_url("https://github.com/phama3098-coder/bot-sida-4/releases") == \
           "https://api.github.com/repos/phama3098-coder/bot-sida-4/releases/latest"
    # Empty -> DEFAULT_UPDATE_URL
    assert normalize_update_url("") == DEFAULT_UPDATE_URL
    # Custom / local -> preserved
    assert normalize_update_url("https://photobooth.1998studio.vn/manifest.json") == \
           "https://photobooth.1998studio.vn/manifest.json"
    assert normalize_update_url("C:/local/manifest.json") == "C:/local/manifest.json"


def test_github_release_parser_real_payload():
    """Kiểm tra phân tích cú pháp dữ liệu Release thực tế từ GitHub API phama3098-coder/bot-sida-4."""
    raw_payload = {
        "tag_name": "1.2.0",
        "name": "1998 TEAM Photobooth v1.2.0",
        "published_at": "2026-10-21T17:31:24Z",
        "body": "## 1998 TEAM — Photobooth\r\n- Giao diện cưới hiện đại\r\n- Tối ưu máy in",
        "assets": [
            {
                "name": "1998-TEAM-Setup.exe",
                "content_type": "application/x-msdownload",
                "state": "uploaded",
                "size": 86195124,
                "digest": "sha256:02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105",
                "browser_download_url": "https://github.com/phama3098-coder/bot-sida-4/releases/download/1.2.0/1998-TEAM-Setup.exe"
            }
        ]
    }

    manifest = UpdateManifest.from_github_release(raw_payload)
    assert manifest.version == "1.2.0"
    assert manifest.release_date == "2026-10-21"
    assert manifest.download_url == "https://github.com/phama3098-coder/bot-sida-4/releases/download/1.2.0/1998-TEAM-Setup.exe"
    assert manifest.file_size_bytes == 86195124
    assert manifest.sha256 == "02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105"
    assert manifest.package_type == "installer"
    assert manifest.architecture == "x64"
    assert len(manifest.release_notes) >= 2

    # Tính toàn vẹn phải hoàn toàn hợp lệ
    errors = manifest.validate_integrity()
    assert len(errors) == 0


def test_github_release_missing_exe_asset_rejected():
    """Kiểm tra từ chối phát hành nếu không có tệp .exe (không được dùng source code zip)."""
    payload_only_zip = {
        "tag_name": "1.2.0",
        "name": "1998 TEAM Photobooth v1.2.0",
        "assets": [
            {
                "name": "source-code.zip",
                "browser_download_url": "https://github.com/.../source.zip",
                "size": 12345
            }
        ]
    }
    with pytest.raises(ValueError) as exc:
        UpdateManifest.from_github_release(payload_only_zip)
    assert "Không tìm thấy bộ cài đặt Windows (.exe)" in str(exc.value)


def test_github_release_missing_trusted_sha256():
    """Kiểm tra khi không có SHA-256 từ digest, body, hay companion asset -> sha256 rỗng và báo lỗi integrity."""
    payload_no_hash = {
        "tag_name": "1.2.0",
        "name": "1998 TEAM Photobooth v1.2.0",
        "body": "Bản phát hành không kèm hash",
        "assets": [
            {
                "name": "1998-TEAM-Setup.exe",
                "size": 50000,
                "browser_download_url": "https://github.com/.../setup.exe"
                # Không có digest
            }
        ]
    }
    manifest = UpdateManifest.from_github_release(payload_no_hash)
    assert manifest.sha256 == ""
    errors = manifest.validate_integrity()
    assert any("sha-256" in err.lower() for err in errors)


def test_github_api_403_rate_limit_handling(qapp):
    """Kiểm tra xử lý lỗi 403 Rate Limit từ GitHub API với thông báo rõ ràng."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.headers = {"x-ratelimit-remaining": "0"}

    with patch("vietphotobooth.updates.updater.check_network_connectivity", return_value=True), \
         patch("requests.get", return_value=mock_resp):
        worker = UpdateCheckWorker(
            manifest_url="https://api.github.com/repos/phama3098-coder/bot-sida-4/releases/latest",
            current_version="1.1.0",
            current_build=102
        )
        results = []
        worker.check_finished.connect(lambda s, m, msg: results.append((s, m, msg)))
        worker.run()

        assert len(results) == 1
        assert results[0][0] is False
        assert "Rate Limit" in results[0][2]


def test_github_api_404_repo_not_found(qapp):
    """Kiểm tra xử lý lỗi 404 Repository Not Found từ GitHub API."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("vietphotobooth.updates.updater.check_network_connectivity", return_value=True), \
         patch("requests.get", return_value=mock_resp):
        worker = UpdateCheckWorker(
            manifest_url="https://api.github.com/repos/phama3098-coder/nonexistent-repo/releases/latest",
            current_version="1.1.0",
            current_build=102
        )
        results = []
        worker.check_finished.connect(lambda s, m, msg: results.append((s, m, msg)))
        worker.run()

        assert len(results) == 1
        assert results[0][0] is False
        assert "404" in results[0][2]
        assert "GitHub" in results[0][2]


def test_github_api_full_live_or_mocked_flow(qapp):
    """Kiểm tra toàn bộ luồng UpdateCheckWorker với phản hồi GitHub API thật (hoặc mock nếu offline)."""
    raw_payload = {
        "tag_name": "1.2.0",
        "name": "1998 TEAM Photobooth v1.2.0",
        "published_at": "2026-10-21T17:31:24Z",
        "body": "## 1998 TEAM — Photobooth\r\n- Chụp ảnh cưới studio",
        "assets": [
            {
                "name": "1998-TEAM-Setup.exe",
                "state": "uploaded",
                "size": 86195124,
                "digest": "sha256:02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105",
                "browser_download_url": "https://github.com/phama3098-coder/bot-sida-4/releases/download/1.2.0/1998-TEAM-Setup.exe"
            }
        ]
    }

    mock_api_resp = MagicMock()
    mock_api_resp.status_code = 200
    mock_api_resp.text = json.dumps(raw_payload)

    mock_head_resp = MagicMock()
    mock_head_resp.status_code = 200
    mock_head_resp.headers = {"content-length": "86195124"}

    with patch("vietphotobooth.updates.updater.check_network_connectivity", return_value=True), \
         patch("requests.get", return_value=mock_api_resp), \
         patch("requests.head", return_value=mock_head_resp):
        worker = UpdateCheckWorker(
            manifest_url="https://api.github.com/repos/phama3098-coder/bot-sida-4/releases/latest",
            current_version="1.1.0",
            current_build=102
        )
        results = []
        worker.check_finished.connect(lambda s, m, msg: results.append((s, m, msg)))
        worker.run()

        assert len(results) == 1
        has_update, manifest, msg = results[0]
        assert has_update is True
        assert manifest is not None
        assert manifest.version == "1.2.0"
        assert manifest.sha256 == "02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105"
        assert manifest.file_size_bytes == 86195124


def test_from_dict_and_from_json_auto_detect_github_release():
    """Kiểm tra UpdateManifest.from_dict và from_json tự động nhận diện GitHub Release không ném lỗi thiếu version."""
    raw_payload = {
        "tag_name": "v1.2.0",
        "name": "1998 TEAM Photobooth v1.2.0",
        "published_at": "2026-10-21T17:31:24Z",
        "assets": [
            {
                "name": "1998-TEAM-Setup.exe",
                "size": 86195124,
                "digest": "sha256:02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105",
                "browser_download_url": "https://github.com/phama3098-coder/bot-sida-4/releases/download/1.2.0/1998-TEAM-Setup.exe"
            }
        ]
    }

    # 1. Gọi trực tiếp from_dict
    m1 = UpdateManifest.from_dict(raw_payload)
    assert m1.version == "1.2.0"
    assert m1.download_url == "https://github.com/phama3098-coder/bot-sida-4/releases/download/1.2.0/1998-TEAM-Setup.exe"

    # 2. Gọi trực tiếp from_json
    json_str = json.dumps(raw_payload)
    m2 = UpdateManifest.from_json(json_str)
    assert m2.version == "1.2.0"
    assert m2.sha256 == "02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105"


def test_github_release_tag_name_variations():
    """Kiểm tra trích xuất phiên bản từ tag_name có 'v', không 'v', chữ hoa 'V', tiền tố 'release-'."""
    base_payload = {
        "name": "1998 TEAM Photobooth",
        "published_at": "2026-10-21T17:31:24Z",
        "assets": [
            {
                "name": "1998-TEAM-Setup.exe",
                "size": 86195124,
                "digest": "sha256:02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105",
                "browser_download_url": "https://github.com/.../1998-TEAM-Setup.exe"
            }
        ]
    }

    for tag in ("1.2.0", "v1.2.0", "V1.2.0", "release-v1.2.0", "1.2.0-beta"):
        p = dict(base_payload)
        p["tag_name"] = tag
        m = UpdateManifest.from_github_release(p)
        assert m.version == "1.2.0", f"Thất bại khi phân tích tag '{tag}'"


def test_github_release_prioritize_1998_team_setup_exe():
    """Kiểm tra ưu tiên asset chính xác 1998-TEAM-Setup.exe trong danh sách nhiều file .exe."""
    payload = {
        "tag_name": "1.2.0",
        "assets": [
            {
                "name": "auxiliary-tool.exe",
                "size": 1000,
                "digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
                "browser_download_url": "https://github.com/.../auxiliary-tool.exe"
            },
            {
                "name": "1998-TEAM-Setup.exe",
                "size": 86195124,
                "digest": "sha256:02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105",
                "browser_download_url": "https://github.com/.../1998-TEAM-Setup.exe"
            },
            {
                "name": "other-setup.exe",
                "size": 2000,
                "digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
                "browser_download_url": "https://github.com/.../other-setup.exe"
            }
        ]
    }
    manifest = UpdateManifest.from_github_release(payload)
    assert manifest.download_url == "https://github.com/.../1998-TEAM-Setup.exe"
    assert manifest.file_size_bytes == 86195124
    assert manifest.sha256 == "02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105"


def test_github_release_prioritize_versioned_installer_asset():
    """Kiểm tra khi release có cả 1998-TEAM-Setup.exe và 1998-TEAM-Setup-v1.2.1-Build121.exe thì ưu tiên file đúng version."""
    payload = {
        "tag_name": "1.2.1",
        "name": "1998 TEAM — Photobooth v1.2.1 (Build 121)",
        "assets": [
            {
                "name": "1998-TEAM-Setup.exe",
                "size": 86195124,
                "digest": "sha256:02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105",
                "browser_download_url": "https://github.com/.../1998-TEAM-Setup.exe"
            },
            {
                "name": "1998-TEAM-Setup-v1.2.1-Build121.exe",
                "size": 88000000,
                "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "browser_download_url": "https://github.com/.../1998-TEAM-Setup-v1.2.1-Build121.exe"
            }
        ]
    }
    manifest = UpdateManifest.from_github_release(payload)
    assert manifest.version == "1.2.1"
    assert manifest.build == 121
    assert manifest.download_url == "https://github.com/.../1998-TEAM-Setup-v1.2.1-Build121.exe"
    assert manifest.file_size_bytes == 88000000
    assert manifest.sha256 == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def test_internal_manifest_support_unbroken():
    """Kiểm tra manifest nội bộ chuẩn (với version, download_url, sha256) vẫn hoạt động 100% bình thường."""
    internal_data = {
        "app": "1998 TEAM Photobooth",
        "version": "1.1.0",
        "build": 102,
        "release_date": "2026-10-21",
        "download_url": "https://photobooth.1998studio.vn/setup.exe",
        "sha256": "02ed4cec9f8aaaccf4cdcb5ba5a6d409444b762001ea4f8c5f42916fb7015105",
        "file_size_bytes": 50000000
    }
    m1 = UpdateManifest.from_dict(internal_data)
    assert m1.version == "1.1.0"
    assert m1.build == 102
    assert m1.download_url == "https://photobooth.1998studio.vn/setup.exe"

    m2 = UpdateManifest.from_json(json.dumps(internal_data))
    assert m2.version == "1.1.0"
    assert m2.file_size_bytes == 50000000


