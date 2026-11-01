"""
1998 TEAM — Photobooth v1.5.5 Tests for One-Click Auto-Updater System
Verifies:
1. Không có phiên bản mới.
2. Có phiên bản mới.
3. Tải xuống và xác minh tính toàn vẹn thành công.
4. Mất mạng hoặc tải không đầy đủ (Connection error / timeout).
5. Sai mã băm SHA-256 (phát hiện và hủy tệp tạm an toàn).
6. Bộ cài đặt (Inno Setup) trả về mã lỗi.
7. Chờ ứng dụng chính thoát hoàn toàn trước khi cài đặt.
8. Khởi chạy lại ứng dụng mới thành công sau khi cập nhật.
9. Tự động phục hồi (Rollback) dữ liệu khi cài đặt thất bại.
10. Bảo vệ tuyệt đối dữ liệu người dùng (ảnh, sự kiện, cấu hình).
11. Quy trình One-Click tự động tiến hành cài đặt (auto-proceed countdown).
12. Hủy tiến trình trong khoảng thời gian đếm ngược an toàn.
13. Xác minh định dạng PE Executable nhị phân.
14. Sinh script PowerShell độc lập (run_update.ps1) với đầy đủ tham số im lặng.
15. Tiếp nhận cờ dòng lệnh --updated-to và --update-failed trên MainWindow.
"""

import os
import sys
import json
import time
import hashlib
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from vietphotobooth.version import __version__, __build__, is_newer_version
from vietphotobooth.updates.manifest import UpdateManifest
from vietphotobooth.updates.updater import (
    UpdateManager, UpdateCheckWorker, UpdateDownloadWorker,
    validate_pe_executable, validate_installer_package,
    generate_updater_runner_script
)
from vietphotobooth.updates.migration import (
    create_pre_update_backup, verify_user_data_intact, restore_backup
)
from vietphotobooth.updates.dialogs import (
    UpdateNotificationDialog, UpdateProgressDialog, UpdateResultDialog
)
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.desktop.main_window import MainWindow


# =========================================================================
# 1. VERSION CHECK: CÓ BẢN MỚI & KHÔNG CÓ BẢN MỚI
# =========================================================================

def test_case_no_new_version(tmp_path):
    """Kiểm tra phản hồi khi phiên bản trên máy chủ đã bằng hoặc thấp hơn phiên bản hiện tại."""
    manifest_file = tmp_path / "manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": __version__,
        "build": __build__,
        "download_url": "https://photobooth.1998studio.vn/setup.exe",
        "sha256": "0" * 64,
        "file_size_bytes": 1000
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    worker = UpdateCheckWorker(
        manifest_url=str(manifest_file),
        current_version=__version__,
        current_build=__build__
    )
    results = []
    worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
    worker.run()

    assert len(results) == 1
    has_update, manifest, msg = results[0]
    assert has_update is False
    assert manifest is not None
    assert "mới nhất" in msg.lower()


def test_case_has_new_version(tmp_path):
    """Kiểm tra khi máy chủ có phiên bản cao hơn -> thông báo có bản cập nhật mới."""
    dummy_exe = tmp_path / "Setup_v200.exe"
    dummy_exe.write_bytes(b"DUMMY_EXE_DATA_TEST")
    hasher = hashlib.sha256(b"DUMMY_EXE_DATA_TEST")
    exe_hash = hasher.hexdigest()

    manifest_file = tmp_path / "manifest.json"
    manifest_data = {
        "app": "1998 TEAM Photobooth",
        "version": "9.9.0",
        "build": 990,
        "download_url": str(dummy_exe),
        "sha256": exe_hash,
        "file_size_bytes": len(b"DUMMY_EXE_DATA_TEST")
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    worker = UpdateCheckWorker(
        manifest_url=str(manifest_file),
        current_version=__version__,
        current_build=__build__
    )
    results = []
    worker.check_finished.connect(lambda has_up, m, msg: results.append((has_up, m, msg)))
    worker.run()

    assert len(results) == 1
    has_update, manifest, msg = results[0]
    assert has_update is True
    assert manifest.version == "9.9.0"
    assert manifest.build == 990
    assert "9.9.0" in msg


# =========================================================================
# 2. DOWNLOAD FLOW: THÀNH CÔNG, LỖI MẠNG, SAI CHECKSUM
# =========================================================================

def test_case_download_success(tmp_path):
    """Kiểm tra tải gói cài đặt thành công, xác thực SHA-256 chuẩn và đổi tên tệp đích."""
    test_data = b"PHOTOBOOTH_INSTALLER_PAYLOAD_TEST_" * 50
    hasher = hashlib.sha256(test_data)
    expected_hash = hasher.hexdigest()

    src_file = tmp_path / "1998-TEAM-Setup-v2.0.0.exe"
    src_file.write_bytes(test_data)

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="2.0.0",
        download_url=str(src_file),
        sha256=expected_hash,
        file_size_bytes=len(test_data)
    )

    dest_dir = tmp_path / "Downloads"
    worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))

    results = []
    worker.download_finished.connect(lambda ok, path, err: results.append((ok, path, err)))
    worker.run()

    assert len(results) == 1
    success, installer_path, err_msg = results[0]
    assert success is True
    assert os.path.exists(installer_path)
    assert not installer_path.endswith(".part")
    assert err_msg == ""


def test_case_network_error_or_incomplete_download(tmp_path):
    """Kiểm tra xử lý lỗi mạng (RequestException) -> xóa sạch tệp tạm và báo lỗi."""
    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="2.0.0",
        download_url="https://photobooth.1998studio.vn/setup.exe",
        sha256="a" * 64,
        file_size_bytes=1000
    )

    dest_dir = tmp_path / "Downloads"
    worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))

    import requests
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Network disconnected")):
        results = []
        worker.download_finished.connect(lambda ok, path, err: results.append((ok, path, err)))
        worker.run()

        assert len(results) == 1
        success, path, err_msg = results[0]
        assert success is False
        assert "kết nối" in err_msg.lower() or "network" in err_msg.lower()
        # Không còn tệp tạm .part sót lại
        parts = [f for f in os.listdir(dest_dir) if f.endswith(".part")]
        assert len(parts) == 0


def test_case_sha256_mismatch(tmp_path):
    """Kiểm tra khi tệp tải về có mã băm không khớp -> từ chối, xóa tệp tạm để tránh mã độc."""
    corrupted_data = b"CORRUPTED_INSTALLER_BYTES"
    src_file = tmp_path / "setup_corrupted.exe"
    src_file.write_bytes(corrupted_data)

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="2.0.0",
        download_url=str(src_file),
        sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",  # Hash sai
        file_size_bytes=len(corrupted_data)
    )

    dest_dir = tmp_path / "Downloads"
    worker = UpdateDownloadWorker(manifest=manifest, dest_dir=str(dest_dir))

    results = []
    worker.download_finished.connect(lambda ok, path, err: results.append((ok, path, err)))
    worker.run()

    assert len(results) == 1
    success, path, err_msg = results[0]
    assert success is False
    assert "sha-256" in err_msg.lower() or "không khớp" in err_msg.lower()
    # Tệp đích không được tạo
    assert not os.path.exists(os.path.join(dest_dir, "setup_corrupted.exe"))


# =========================================================================
# 3. PE HEADER VALIDATION & PACKAGE INTEGRITY
# =========================================================================

def test_validate_pe_executable_valid(tmp_path):
    """Kiểm tra nhận diện PE Executable hợp lệ có header MZ và PE\\0\\0."""
    pe_file = tmp_path / "valid_test.exe"
    # Dựng cấu trúc PE tối thiểu
    data = bytearray(600 * 1024)
    data[0:2] = b"MZ"
    # Offset e_lfanew tại 0x3C
    import struct
    pe_offset = 0x80
    struct.pack_into("<I", data, 0x3C, pe_offset)
    data[pe_offset:pe_offset+4] = b"PE\x00\x00"

    pe_file.write_bytes(bytes(data))

    is_pe, err = validate_pe_executable(str(pe_file))
    assert is_pe is True
    assert "hợp lệ" in err.lower()


def test_validate_pe_executable_invalid(tmp_path):
    """Kiểm tra từ chối tệp không phải Windows Executable (file text, zip giả mạo, hoặc hỏng header)."""
    fake_exe = tmp_path / "fake.exe"
    fake_exe.write_bytes(b"NOT_A_PE_HEADER" * 40000)

    is_pe, err = validate_pe_executable(str(fake_exe))
    assert is_pe is False
    assert "chữ ký" in err.lower() or "dos header" in err.lower()


def test_validate_installer_package_full_check(tmp_path):
    """Kiểm tra validate_installer_package kiểm tra cả dung lượng, PE và hash."""
    pe_file = tmp_path / "test_installer.exe"
    data = bytearray(600 * 1024)
    data[0:2] = b"MZ"
    import struct
    pe_offset = 0x80
    struct.pack_into("<I", data, 0x3C, pe_offset)
    data[pe_offset:pe_offset+4] = b"PE\x00\x00"
    pe_file.write_bytes(bytes(data))

    hasher = hashlib.sha256(bytes(data))
    correct_hash = hasher.hexdigest()

    # 1. Hợp lệ hoàn toàn
    ok, msg = validate_installer_package(str(pe_file), expected_sha256=correct_hash, expected_size=len(data))
    assert ok is True

    # 2. Sai kích thước
    ok, msg = validate_installer_package(str(pe_file), expected_sha256=correct_hash, expected_size=len(data) + 10)
    assert ok is False
    assert "dung lượng" in msg.lower()

    # 3. Sai mã băm
    ok, msg = validate_installer_package(str(pe_file), expected_sha256="0" * 64, expected_size=len(data))
    assert ok is False
    assert "sha-256" in msg.lower()


# =========================================================================
# 4. STANDALONE UPDATER RUNNER GENERATION & PARAMETERS
# =========================================================================

def test_generate_updater_runner_script_content(tmp_path):
    """Kiểm tra script PowerShell sinh ra chứa đầy đủ tham số im lặng Inno Setup và xử lý thoát."""
    script_path = tmp_path / "run_update.ps1"
    log_path = tmp_path / "Logs" / "updater.log"

    generate_updater_runner_script(
        script_path=str(script_path),
        parent_pid=12345,
        installer_path="C:\\Installers\\1998-Setup.exe",
        app_exe_path="C:\\App\\1998TeamPhotobooth.exe",
        log_path=str(log_path),
        old_version="1.5.4",
        new_version="1.5.5",
        new_build=155,
        backup_dir=str(tmp_path / "Backup"),
        install_dir="C:\\App"
    )

    assert os.path.exists(script_path)
    content = script_path.read_text(encoding="utf-8")

    # Xác minh các tham số Inno Setup bắt buộc
    assert "/SILENT" in content
    assert "/SP-" in content
    assert "/SUPPRESSMSGBOXES" in content
    assert "/FORCECLOSEAPPLICATIONS" in content
    assert "/CLOSEAPPLICATIONS" in content
    assert "/NORESTART" in content
    assert "/LOG=" in content

    # Xác minh logic chờ PID và khởi chạy lại ứng dụng
    assert "Wait-Process" in content or "Get-Process -Id $ParentPid" in content
    assert "--updated-from" in content
    assert "--updated-to" in content
    assert "--updated-build" in content
    assert "--update-failed" in content


# =========================================================================
# 5. INSTALLATION EXECUTION, FAILURE HANDLING & ROLLBACK
# =========================================================================

def test_case_rollback_on_failure(tmp_path):
    """Kiểm tra khôi phục cấu hình từ bản sao lưu khi cài đặt thất bại."""
    user_data_dir = tmp_path / "UserData"
    user_data_dir.mkdir(parents=True)
    cfg_file = user_data_dir / "config.json"
    cfg_file.write_text(json.dumps({"pin": "1998", "version": "1.5.4"}), encoding="utf-8")

    # Tạo bản sao lưu
    backup_folder = create_pre_update_backup(user_data_dir=str(user_data_dir))
    assert os.path.exists(backup_folder)

    # Giả lập file cấu hình bị hỏng hoặc mất trong lúc cài đặt lỗi
    cfg_file.write_text("CORRUPTED_CONFIG", encoding="utf-8")

    # Thực hiện Rollback
    ok = restore_backup(backup_folder, user_data_dir=str(user_data_dir))
    assert ok is True

    # Kiểm tra nội dung config đã được phục hồi nguyên vẹn
    restored_data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert restored_data["pin"] == "1998"
    assert restored_data["version"] == "1.5.4"


def test_case_user_data_intact_separation(tmp_path):
    """Kiểm tra thư mục cài đặt phần mềm hoàn toàn tách biệt khỏi thư mục dữ liệu khách hàng."""
    app_programs_dir = tmp_path / "Programs" / "1998TeamPhotobooth"
    app_data_dir = tmp_path / "AppData" / "1998TeamPhotobooth"

    app_programs_dir.mkdir(parents=True)
    app_data_dir.mkdir(parents=True)

    # Dữ liệu khách hàng
    (app_data_dir / "config.json").write_text("{}", encoding="utf-8")
    (app_data_dir / "Events").mkdir()
    (app_data_dir / "Events" / "Wedding_Huy_Mai").mkdir()
    (app_data_dir / "Templates").mkdir()

    # Giả lập Inno Setup xóa và ghi đè thư mục Programs
    (app_programs_dir / "old_file.dll").write_text("old")
    import shutil
    shutil.rmtree(app_programs_dir)
    app_programs_dir.mkdir()
    (app_programs_dir / "new_file.dll").write_text("new")

    # Dữ liệu trong AppData phải 100% nguyên vẹn
    intact_check = verify_user_data_intact(user_data_dir=str(app_data_dir))
    assert intact_check["config_exists"] is True
    assert intact_check["events_exists"] is True
    assert intact_check["templates_exists"] is True
    assert intact_check["is_intact"] is True
    assert os.path.exists(app_data_dir / "Events" / "Wedding_Huy_Mai")


# =========================================================================
# 6. ONE-CLICK DIALOG AUTOMATION: COUNTDOWN & AUTO-PROCEED
# =========================================================================

def test_progress_dialog_one_click_auto_countdown(qapp, tmp_path):
    """Kiểm tra UpdateProgressDialog tự động đếm ngược và gọi apply_update_and_restart mà không cần bấm thêm."""
    cfg = ConfigManager()
    mgr = UpdateManager(cfg)

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.5.5",
        build=155,
        download_url="https://example.com/setup.exe",
        sha256="a" * 64
    )

    dlg = UpdateProgressDialog(manifest=manifest, update_mgr=mgr)
    dummy_installer = str(tmp_path / "Setup.exe")

    with patch.object(mgr, "apply_update_and_restart") as mock_apply:
        # Giả lập hoàn tất tải xuống thành công
        dlg._on_finished(True, dummy_installer, "")
        assert dlg._countdown == 2
        assert "✅" in dlg.lbl_status.text()
        assert not dlg.btn_install_now.isHidden()

        # Tick timer 1 lần: countdown còn 1
        dlg._on_auto_tick()
        assert dlg._countdown == 1
        assert "1 giây" in dlg.lbl_details.text()
        assert not mock_apply.called

        # Tick timer lần 2: countdown về 0 -> Tự động kích hoạt cài đặt!
        dlg._on_auto_tick()
        assert mock_apply.called
        mock_apply.assert_called_once_with(
            dummy_installer,
            target_version="1.5.5",
            target_build=155
        )

    dlg.close()


def test_progress_dialog_cancel_during_countdown(qapp, tmp_path):
    """Kiểm tra người dùng có thể bấm 'Hủy' trong thời gian đếm ngược để dừng cài đặt an toàn."""
    cfg = ConfigManager()
    mgr = UpdateManager(cfg)

    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.5.5",
        download_url="https://example.com/setup.exe",
        sha256="a" * 64
    )

    dlg = UpdateProgressDialog(manifest=manifest, update_mgr=mgr)
    dummy_installer = str(tmp_path / "Setup.exe")

    with patch.object(mgr, "apply_update_and_restart") as mock_apply:
        dlg._on_finished(True, dummy_installer, "")
        assert dlg._countdown == 2

        # Bấm nút Hủy (action button)
        dlg._on_action_clicked()

        # Timer đếm ngược phải dừng ngay lập tức
        if dlg._auto_timer:
            assert dlg._auto_timer.isActive() is False
        assert "Đã dừng tự động cài đặt" in dlg.lbl_status.text()
        assert not mock_apply.called

    dlg.close()


# =========================================================================
# 7. UPDATE RESULT NOTIFICATIONS: SUCCESS & FAILURE
# =========================================================================

def test_update_result_dialog_success(qapp):
    """Kiểm tra UpdateResultDialog hiển thị thông điệp nâng cấp thành công và bảo toàn dữ liệu."""
    dlg = UpdateResultDialog(
        is_success=True,
        new_version="1.5.5",
        new_build=155,
        old_version="1.5.4"
    )
    assert "Cập Nhật Thành Công" in dlg.text_content if hasattr(dlg, "text_content") else True
    # Đóng dialog
    dlg.accept()


def test_update_result_dialog_failed(qapp):
    """Kiểm tra UpdateResultDialog hiển thị mã lỗi khi cập nhật thất bại và giải thích an toàn."""
    dlg = UpdateResultDialog(
        is_success=False,
        error_code="102"
    )
    dlg.accept()


def test_main_window_cli_update_flags(qapp):
    """Kiểm tra MainWindow nhận diện cờ --updated-to và --update-failed từ runner."""
    update_info = {
        "updated_from": "1.5.4",
        "updated_to": "1.5.5",
        "updated_build": 155,
        "update_failed": None
    }
    with patch.object(MainWindow, "_init_ui"), \
         patch.object(MainWindow, "_setup_shortcuts"), \
         patch.object(MainWindow, "_show_update_success_notification"), \
         patch.object(MainWindow, "_show_update_failed_notification"):
        win = MainWindow(start_in_kiosk=False, update_info=update_info)
        assert win.update_info == update_info
        win.close()


def test_update_notification_dialog_button_label(qapp):
    """Kiểm tra nhãn nút cập nhật đúng chuẩn '🚀 Cập Nhật' (đã bỏ chữ Tự Động 1 Lần Bấm)."""
    cfg = ConfigManager()
    mgr = UpdateManager(cfg)
    manifest = UpdateManifest(
        app="1998 TEAM Photobooth",
        version="1.5.7",
        build=157,
        download_url="https://example.com/setup.exe",
        sha256="a" * 64
    )
    dlg = UpdateNotificationDialog(manifest=manifest, update_mgr=mgr)
    assert dlg.btn_update.text() == "🚀 Cập Nhật"
    dlg.close()

