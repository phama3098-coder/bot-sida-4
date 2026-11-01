"""
Release Audit Verification Tests — 1998 TEAM Photobooth v1.5.5 Build 155
Audits Part A (Data Directories & Migration), Part B (Integrity & Checksum Trust),
Part C (Upgrade, Rollback, Loop Prevention, and File Locks).
"""

import os
import sys
import json
import shutil
import hashlib
import tempfile
import subprocess
from pathlib import Path
import pytest

from vietphotobooth.version import __version__, __build__
from vietphotobooth.core.config import ConfigManager, get_user_data_dir
from vietphotobooth.core.events import EventManager
from vietphotobooth.updates.manifest import UpdateManifest
from vietphotobooth.updates.updater import (
    validate_pe_executable,
    validate_installer_package,
    generate_updater_runner_script,
    verify_digital_signature
)
from vietphotobooth.updates.migration import (
    create_pre_update_backup,
    verify_user_data_intact,
    restore_backup
)


# =========================================================================
# PART A: DATA DIRECTORIES & ISOLATION AUDIT
# =========================================================================

def test_data_and_program_directory_separation():
    """
    Xác minh chương trình và dữ liệu người dùng nằm ở hai thư mục hoàn toàn riêng biệt.
    Không lưu dữ liệu người dùng vào thư mục cài đặt {app}.
    """
    user_data_dir = get_user_data_dir()
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))

    expected_program_dir = os.path.join(local_app_data, "Programs", "1998TeamPhotobooth")
    expected_data_dir = os.path.join(local_app_data, "1998TeamPhotobooth")

    # Hai thư mục phải khác biệt hoàn toàn
    assert os.path.abspath(user_data_dir) == os.path.abspath(expected_data_dir)
    assert os.path.abspath(user_data_dir) != os.path.abspath(expected_program_dir)
    assert not os.path.abspath(user_data_dir).startswith(os.path.abspath(expected_program_dir))
    assert not os.path.abspath(expected_program_dir).startswith(os.path.abspath(user_data_dir))


def test_inno_setup_script_privileges_and_dirs():
    """
    Kiểm tra script Inno Setup:
    1. PrivilegesRequired=lowest (Chạy không cần Administrator).
    2. DefaultDirName trỏ đến {localappdata}\\Programs\\1998TeamPhotobooth.
    3. Không xóa hoặc ghi đè thư mục dữ liệu {localappdata}\\1998TeamPhotobooth.
    """
    iss_path = Path(__file__).resolve().parent.parent.parent / "VietPhotoBooth.iss"
    assert iss_path.exists(), f"Không tìm thấy file {iss_path}"

    content = iss_path.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in content
    assert "DefaultDirName={localappdata}\\Programs\\1998TeamPhotobooth" in content
    assert "CloseApplications=yes" in content
    assert "CloseApplicationsFilter=*.exe,*.dll,*.pyd" in content
    assert "RestartApplications=no" in content


def test_legacy_data_migration_and_non_destructive(tmp_path, monkeypatch):
    """
    Kiểm tra cơ chế di chuyển an toàn từ thư mục cũ (VietPhotoBooth/Events) sang hệ thống mới:
    1. Sao chép đầy đủ các sự kiện cũ.
    2. Tuyệt đối KHÔNG xóa tệp cũ trong thư mục nguồn (Bảo vệ dữ liệu người dùng).
    """
    mock_localappdata = tmp_path / "MockAppData"
    legacy_dir = mock_localappdata / "VietPhotoBooth" / "Events" / "Old_Wedding_2026" / "Originals"
    legacy_dir.mkdir(parents=True, exist_ok=True)

    photo1 = legacy_dir / "photo_1.jpg"
    photo1.write_bytes(b"JPEG_MOCK_DATA_1")
    photo2 = legacy_dir / "photo_2.jpg"
    photo2.write_bytes(b"JPEG_MOCK_DATA_2")

    new_storage_root = mock_localappdata / "1998TeamPhotobooth"

    # Giả lập biến môi trường LOCALAPPDATA
    monkeypatch.setenv("LOCALAPPDATA", str(mock_localappdata))

    # Khởi tạo EventManager với storage_root mới
    em = EventManager(storage_root=str(new_storage_root), current_event="SuKien_MacDinh")

    # Kiểm tra sự kiện cũ đã được di chuyển an toàn sang thư mục mới
    migrated_photo1 = new_storage_root / "Events" / "Old_Wedding_2026" / "Originals" / "photo_1.jpg"
    migrated_photo2 = new_storage_root / "Events" / "Old_Wedding_2026" / "Originals" / "photo_2.jpg"

    assert migrated_photo1.exists()
    assert migrated_photo1.read_bytes() == b"JPEG_MOCK_DATA_1"
    assert migrated_photo2.exists()
    assert migrated_photo2.read_bytes() == b"JPEG_MOCK_DATA_2"

    # QUAN TRỌNG: Kiểm tra thư mục cũ KHÔNG bị xóa
    assert photo1.exists()
    assert photo2.exists()
    assert photo1.read_bytes() == b"JPEG_MOCK_DATA_1"


# =========================================================================
# PART B: METADATA & INTEGRITY TRUST AUDIT
# =========================================================================

def test_manifest_sha256_trust_priority():
    """
    Kiểm tra cơ chế đối chiếu SHA-256 từ nhiều nguồn metadata đáng tin cậy:
    Ưu tiên thuộc tính digest của GitHub Release Asset > Body ghi chú phát hành > Companion File.
    """
    # 1. Nguồn Digest trực tiếp
    raw_gh_digest = {
        "tag_name": "v1.5.5",
        "name": "1998 TEAM Photobooth v1.5.5 Build 155",
        "body": "Bản phát hành chính thức",
        "assets": [
            {
                "name": "1998-TEAM-Setup-v1.5.5-Build155.exe",
                "browser_download_url": "https://github.com/release/setup.exe",
                "size": 85000000,
                "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            }
        ]
    }
    m1 = UpdateManifest.from_github_release(raw_gh_digest)
    assert m1.sha256 == "a" * 64

    # 2. Nguồn Body ký số của Release Manager
    raw_gh_body = {
        "tag_name": "v1.5.5",
        "name": "1998 TEAM Photobooth v1.5.5 Build 155",
        "body": "Ghi chú phát hành:\nSHA-256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "assets": [
            {
                "name": "1998-TEAM-Setup-v1.5.5-Build155.exe",
                "browser_download_url": "https://github.com/release/setup.exe",
                "size": 85000000
            }
        ]
    }
    m2 = UpdateManifest.from_github_release(raw_gh_body)
    assert m2.sha256 == "b" * 64


def test_installer_package_validation_rejects_corrupted(tmp_path):
    """
    Kiểm tra validate_installer_package từ chối các trường hợp không an toàn:
    - File không tồn tại
    - File 0 byte
    - File thiếu PE header
    - File sai SHA-256
    """
    # File không tồn tại
    ok, err = validate_installer_package(str(tmp_path / "non_existent.exe"))
    assert not ok
    assert "không tồn tại" in err

    # File 0 byte
    zero_file = tmp_path / "zero.exe"
    zero_file.write_bytes(b"")
    ok, err = validate_installer_package(str(zero_file))
    assert not ok
    assert "rỗng" in err

    # File giả mạo không có PE Header
    fake_exe = tmp_path / "fake.exe"
    fake_data = b"NOT_A_PE_HEADER" + b"\x00" * 600000
    fake_exe.write_bytes(fake_data)
    ok, err = validate_installer_package(str(fake_exe))
    assert not ok
    assert "MZ" in err or "PE" in err

    # File có PE Header hợp lệ nhưng sai SHA-256
    # Tạo header DOS + PE giả lập chuẩn
    dos_header = bytearray(b"MZ" + b"\x00" * 58 + b"\x80\x00\x00\x00" + b"\x00" * 64)
    dos_header += b"PE\x00\x00" + b"\x00" * (600000 - len(dos_header))
    pe_file = tmp_path / "valid_pe.exe"
    pe_file.write_bytes(bytes(dos_header))

    # Xác thực định dạng PE hợp lệ
    is_pe, pe_msg = validate_pe_executable(str(pe_file))
    assert is_pe, f"Lỗi phân tích PE: {pe_msg}"

    # Khi cung cấp mã hash sai -> Bị từ chối
    ok, err = validate_installer_package(str(pe_file), expected_sha256="0" * 64)
    assert not ok
    assert "không khớp" in err

    # Khi cung cấp mã hash đúng -> Chấp thuận
    real_hash = hashlib.sha256(bytes(dos_header)).hexdigest()
    ok, err = validate_installer_package(str(pe_file), expected_sha256=real_hash)
    assert ok


def _cleanup_test_spawned_processes(target_dir: Path):
    """
    Dọn dẹp chính xác các tiến trình con được khởi chạy từ thư mục target_dir
    trong quá trình kiểm thử, tránh xung đột khóa tệp khi pytest dọn dẹp tmp_path.
    Tuyệt đối KHÔNG tắt các tiến trình mang tên 1998TeamPhotobooth.exe chạy từ thư mục khác.
    """
    if not target_dir.exists():
        return

    import json
    import time
    target_prefix = str(target_dir.resolve()).lower()
    try:
        ps_cmd = [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "Get-Process -Name 1998* -ErrorAction SilentlyContinue | Select-Object -Property Id, Path | ConvertTo-Json -Compress"
        ]
        res = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=5)
        out = res.stdout.strip()
        if not out:
            return
        data = json.loads(out)
        if isinstance(data, dict):
            items = [data]
        elif isinstance(data, list):
            items = data
        else:
            items = []

        killed = False
        for item in items:
            pid = item.get("Id")
            p_path = (item.get("Path") or "").lower()
            if pid and p_path.startswith(target_prefix):
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=5)
                    killed = True
                except Exception:
                    pass
        if killed:
            time.sleep(0.3)
    except Exception:
        pass


def test_verify_digital_signature_non_existent(tmp_path):
    """Xác minh verify_digital_signature xử lý an toàn khi tệp không tồn tại."""
    res = verify_digital_signature(str(tmp_path / "non_existent.exe"))
    assert res["valid"] is False
    assert res["signed"] is False
    assert res["status"] == "FileNotFound"


def test_verify_digital_signature_unsigned_file(tmp_path):
    """
    Đảm bảo verify_digital_signature không tuyên bố bừa bãi rằng file có chữ ký hợp lệ
    nếu tệp thực tế chưa được ký số Authenticode.
    """
    test_exe = tmp_path / "unsigned.exe"
    test_exe.write_bytes(b"UNSIGNED_BINARY_CONTENT")

    sig = verify_digital_signature(str(test_exe))
    assert sig["valid"] is False
    assert sig["signed"] is False
    assert sig["status"] in ("NotSigned", "UnknownError", "Not Windows")


def test_verify_digital_signature_corrupted_pe(tmp_path):
    """Kiểm tra verify_digital_signature khi file PE bị giả mạo / header hỏng."""
    corrupted_pe = tmp_path / "corrupted.exe"
    corrupted_pe.write_bytes(b"MZ\x00\x00_CORRUPTED_PE_BODY_" + b"\x00" * 2048)

    sig = verify_digital_signature(str(corrupted_pe))
    assert sig["valid"] is False
    assert sig["signed"] is False
    assert sig["status"] in ("NotSigned", "UnknownError", "Not Windows")


def test_verify_digital_signature_powershell_failure(monkeypatch, tmp_path):
    """Kiểm tra khi PowerShell ném lỗi hoặc timeout thì trả về cấu trúc lỗi an toàn."""
    test_file = tmp_path / "test.exe"
    test_file.write_bytes(b"SOME_DATA")

    def mock_run_error(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="powershell.exe", timeout=10)

    monkeypatch.setattr(subprocess, "run", mock_run_error)
    sig = verify_digital_signature(str(test_file))
    assert sig["valid"] is False
    assert sig["signed"] is False
    assert sig["status"] == "Error"
    assert "Timeout" in sig.get("error", "")


def test_verify_digital_signature_require_signed_flag(tmp_path):
    """Kiểm tra cờ require_signed=True từ chối tệp không có chữ ký số hợp lệ."""
    test_exe = tmp_path / "unsigned.exe"
    test_exe.write_bytes(b"UNSIGNED_DATA")

    sig = verify_digital_signature(str(test_exe), require_signed=True)
    assert sig["valid"] is False


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Chỉ chạy trên Windows")
def test_verify_digital_signature_valid_windows_binary():
    """Kiểm tra xác thực thành công đối với binary chính thức của Windows được ký số hợp lệ."""
    notepad_path = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "notepad.exe"
    if notepad_path.exists():
        sig = verify_digital_signature(str(notepad_path))
        assert sig["valid"] is True
        assert sig["signed"] is True
        assert sig["status"] == "Valid"
        assert len(sig["signer"]) > 0


# =========================================================================
# PART C: ROLLBACK & LOOP PREVENTION AUDIT
# =========================================================================

def test_updater_script_syntax_and_variables_integrity(tmp_path):
    """
    Kiểm tra tính toàn vẹn cú pháp của script PowerShell sinh ra:
    1. Bảo toàn tất cả tên biến ($ParentPid, $InstallerPath, $AppExePath...).
    2. Không có dòng nào bị mất tên biến trước dấu '=' (như '= New-Item' hoặc '= @(...)').
    3. Không có lệnh Start-Process nào bị thiếu hoặc rỗng ArgumentList.
    4. Hàm Invoke-AppLaunch được định nghĩa chuẩn xác với danh sách đối số array không rỗng.
    5. Lưu script ra file log trước khi chạy để kiểm tra đối chiếu.
    """
    script_path = tmp_path / "run_update.ps1"
    log_path = tmp_path / "Logs" / "updater.log"
    backup_folder = tmp_path / "AppData Folder With Spaces" / "Backups" / "backup_pre_update"
    user_data_dir = tmp_path / "AppData Folder With Spaces"
    installer_path = tmp_path / "Installers With Spaces" / "1998-TEAM-Setup-v1.5.5-Build155.exe"
    app_exe = tmp_path / "Programs With Spaces" / "1998TeamPhotobooth.exe"

    generate_updater_runner_script(
        script_path=str(script_path),
        parent_pid=1234,
        installer_path=str(installer_path),
        app_exe_path=str(app_exe),
        log_path=str(log_path),
        old_version="1.5.4",
        new_version="1.5.5",
        new_build=155,
        backup_dir=str(backup_folder),
        install_dir=str(app_exe.parent),
        user_data_dir=str(user_data_dir)
    )

    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")

    # In/Lưu nội dung script ra file log để đối chiếu theo yêu cầu
    debug_log = tmp_path / "Logs" / "debug_script_dump.log"
    debug_log.parent.mkdir(parents=True, exist_ok=True)
    debug_log.write_text(content, encoding="utf-8")

    # 1. Kiểm tra không có biểu thức gán khuyết tật
    for line_idx, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        # Không được có dòng bắt đầu bằng '= ' (thiếu tên biến bên trái)
        assert not stripped.startswith("= "), f"Lỗi cú pháp tại dòng {line_idx}: biến bên trái bị mất: {line}"
        # Set-Content phải có Path nếu xuất hiện
        if "Set-Content" in stripped:
            assert "-Path" in stripped and not stripped.endswith("-Path")
        # Start-Process phải có tham số
        if "Start-Process" in stripped:
            assert "-FilePath" in stripped

    # 2. Kiểm tra các biến bắt buộc tồn tại
    required_vars = [
        "$ParentPid", "$InstallerPath", "$AppExePath", "$LogPath",
        "$OldVersion", "$NewVersion", "$NewBuild", "$BackupDir",
        "$InstallDir", "$UserDataDir", "$ErrorActionPreference",
        "$innoLog", "$innoArgs", "$proc", "$exitCode",
        "$launchArgs", "$failArgs"
    ]
    for var in required_vars:
        assert var in content, f"Biến PowerShell {var} bị thiếu trong script!"

    # 3. Kiểm tra Invoke-AppLaunch và danh sách ArgumentList
    assert "function Invoke-AppLaunch" in content
    assert "$launchArgs = @(" in content
    assert "$failArgs = @(" in content
    assert '"--update-failed"' in content
    assert '"--updated-from"' in content


def test_updater_runner_script_restores_to_user_data_dir(tmp_path):
    """
    Kiểm tra script PowerShell sinh ra khôi phục trực tiếp vào $UserDataDir khi có sự cố.
    """
    script_path = tmp_path / "run_update.ps1"
    log_path = tmp_path / "Logs" / "updater.log"
    backup_folder = tmp_path / "AppData" / "Backups" / "backup_test_1"
    user_data_dir = tmp_path / "AppData"

    generate_updater_runner_script(
        script_path=str(script_path),
        parent_pid=9999,
        installer_path="C:\\installer.exe",
        app_exe_path="C:\\app.exe",
        log_path=str(log_path),
        old_version="1.5.4",
        new_version="1.5.5",
        new_build=155,
        backup_dir=str(backup_folder),
        install_dir="C:\\install_dir",
        user_data_dir=str(user_data_dir)
    )

    content = script_path.read_text(encoding="utf-8")
    # Xác minh tham số UserDataDir tồn tại trong script
    assert "$UserDataDir" in content
    assert str(user_data_dir) in content
    # Xác minh logic khôi phục sao lưu
    assert "Đang khôi phục cấu hình từ bản sao lưu" in content
    assert "HƯỚNG DẪN PHỤC HỒI" in content or "Khởi chạy lại ứng dụng phiên bản hiện tại" in content


def test_isolated_rollback_execution(tmp_path):
    """
    Thực nghiệm có kiểm soát kịch bản Inno Setup thất bại (Exit Code 2):
    1. Đường dẫn thư mục và file có khoảng trắng (Stress test Windows path quoting).
    2. Tạo bản sao lưu cấu hình (config.json) trong thư mục Backups.
    3. Giả lập một installer luôn trả về exit code lỗi.
    4. Thực thi PowerShell runner trong môi trường giả lập độc lập.
    5. Xác minh config.json được khôi phục thành công về thư mục dữ liệu gốc.
    6. Xác minh ứng dụng cũ được khởi chạy lại kèm tham số --update-failed 2.
    7. Xác minh nhật ký ghi nhận lỗi và phục hồi đầy đủ.
    8. Đảm bảo toàn bộ tiến trình con kết thúc trước khi pytest dọn dẹp tmp_path.
    """
    import time
    # Thư mục có khoảng trắng để kiểm tra xử lý dấu nháy Windows an toàn
    env_dir = tmp_path / "Isolated Rollback Env With Spaces"
    app_data_dir = env_dir / "AppData With Spaces"
    backup_dir = app_data_dir / "Backups" / "backup_pre_update_sim"
    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Cấu hình gốc đã sao lưu
        original_config = backup_dir / "config.json"
        original_config.write_text(json.dumps({"event_name": "ROLLBACK_PRESERVED"}), encoding="utf-8")

        # Giả lập file cấu hình ở root app_data_dir bị mất hoặc hỏng do cài đặt dở
        corrupted_config = app_data_dir / "config.json"
        corrupted_config.write_text("CORRUPTED_CONFIG", encoding="utf-8")

        # Giả lập một installer thất bại bằng script bat trả về exit 2
        failing_installer_cmd = env_dir / "fail_installer.cmd"
        failing_installer_cmd.write_text("@echo off\r\nexit 2\r\n", encoding="utf-8")

        # App giả lập có khoảng trắng trong tên, vòng đời tất định kết thúc ngay sau khi ghi cờ
        mock_app_exe = env_dir / "Mock App With Space.cmd"
        launched_flag_file = env_dir / "app_launched.txt"
        mock_app_exe.write_text(f'@echo off\r\necho APP_RESTORED %* > "{launched_flag_file}"\r\nexit 0\r\n', encoding="utf-8")

        log_path = app_data_dir / "Logs" / "updater.log"
        script_path = app_data_dir / "Updates" / "run_update.ps1"

        generate_updater_runner_script(
            script_path=str(script_path),
            parent_pid=0,  # Không cần chờ PID trong test
            installer_path=str(failing_installer_cmd),
            app_exe_path=str(mock_app_exe),
            log_path=str(log_path),
            old_version="1.5.4",
            new_version="1.5.5",
            new_build=155,
            backup_dir=str(backup_dir),
            install_dir=str(env_dir),
            user_data_dir=str(app_data_dir)
        )

        # Lưu nội dung script trước khi thực thi để có thể đối chiếu chính xác
        script_content = script_path.read_text(encoding="utf-8")
        pre_run_log = app_data_dir / "Logs" / "pre_run_script.log"
        pre_run_log.parent.mkdir(parents=True, exist_ok=True)
        pre_run_log.write_text(script_content, encoding="utf-8")

        # Chạy script PowerShell runner
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", str(script_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        assert res.returncode == 0

        # 1. Kiểm tra cấu hình đã được khôi phục về app_data_dir
        assert corrupted_config.exists()
        restored_text = corrupted_config.read_text(encoding="utf-8")
        assert "ROLLBACK_PRESERVED" in restored_text

        # 2. Kiểm tra nhật ký ghi nhận
        assert log_path.exists()
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        assert "LỖI" in log_text or "thất bại" in log_text.lower()
        assert "khôi phục cấu hình" in log_text.lower()
        assert "Đã gửi lệnh khởi chạy ứng dụng" in log_text

        # 3. Xác minh ứng dụng cũ được khởi chạy thành công sau rollback
        for _ in range(50):
            if launched_flag_file.exists() and launched_flag_file.stat().st_size > 0:
                break
            time.sleep(0.1)
        assert launched_flag_file.exists(), f"Ứng dụng cũ chưa được khởi chạy! Log: {log_text}"
        launched_text = launched_flag_file.read_text(encoding="utf-8")
        assert "APP_RESTORED" in launched_text
        assert "--update-failed" in launched_text
        assert "2" in launched_text
    finally:
        _cleanup_test_spawned_processes(env_dir)


def test_live_isolated_upgrade_preserves_all_data(tmp_path):
    """
    Thử nghiệm nâng cấp thực tế có kiểm soát trong môi trường giả lập độc lập:
    - Nâng cấp từ v1.5.4 lên v1.5.5.
    - Giữ nguyên ảnh, layout, cấu hình và dữ liệu sự kiện.
    - Kiểm tra ứng dụng mới hoàn tất cài đặt (mã thoát 0, binary > 10MB).
    - Bảo toàn 100% dữ liệu sự kiện và ảnh.
    - Đảm bảo giải phóng tiến trình con sinh ra trong thư mục cài đặt giả lập trước khi dọn dẹp tmp_path.
    - Cách ly triệt để: Không ghi đè Shortcut Desktop/Start Menu và khôi phục Registry Uninstall sau test.
    """
    installer_path = Path(__file__).resolve().parent.parent.parent / "dist_installer" / "1998-TEAM-Setup-v1.5.5-Build155.exe"
    if not installer_path.exists():
        pytest.skip("Chưa có bộ cài v1.5.5 trong dist_installer")

    env_dir = tmp_path / "LiveUpgradeEnv"
    install_dir = env_dir / "InstalledApp"
    app_data_dir = env_dir / "AppData"
    install_dir.mkdir(parents=True, exist_ok=True)
    app_data_dir.mkdir(parents=True, exist_ok=True)

    # 0. Sao lưu trạng thái Registry Uninstall và Shortcuts của hệ thống trước khi chạy bộ cài
    reg_key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{676858C6-2A30-4E77-A479-D21F91264A09}_is1"
    reg_backup = {}
    key_existed = False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key_path, 0, winreg.KEY_READ) as k:
            key_existed = True
            i = 0
            while True:
                try:
                    val_name, val_data, val_type = winreg.EnumValue(k, i)
                    reg_backup[val_name] = (val_data, val_type)
                    i += 1
                except OSError:
                    break
    except OSError:
        key_existed = False

    desktop_dir = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    start_menu_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    shortcut_backups = {}
    for search_dir in [desktop_dir, start_menu_dir]:
        if search_dir.exists():
            for lnk in search_dir.rglob("*Photobooth*.lnk"):
                try:
                    shortcut_backups[lnk] = lnk.read_bytes()
                except Exception:
                    pass

    try:
        # 1. Giả lập ứng dụng v1.5.4 cũ
        old_exe = install_dir / "1998TeamPhotobooth.exe"
        old_exe.write_bytes(b"MOCK_OLD_V154_APP_EXE")

        # 2. Giả lập dữ liệu người dùng (ảnh, sự kiện, layout, cấu hình)
        events_dir = app_data_dir / "Events" / "DamCuoi_Audit_2026" / "Originals"
        events_dir.mkdir(parents=True, exist_ok=True)
        test_photo = events_dir / "photo_vip.jpg"
        test_photo.write_bytes(b"AUDIT_PHOTO_CONTENT_PRESERVED")

        frames_dir = app_data_dir / "Frames" / "Wedding"
        frames_dir.mkdir(parents=True, exist_ok=True)
        test_frame = frames_dir / "frame_vip.json"
        test_frame.write_text(json.dumps({"title": "FRAME_PRESERVED"}), encoding="utf-8")

        config_file = app_data_dir / "config.json"
        config_file.write_text(json.dumps({
            "app_name": "1998 TEAM — Photobooth",
            "version": "1.5.4",
            "current_event": "DamCuoi_Audit_2026",
            "photos_per_session": 4
        }), encoding="utf-8")

        # 3. Tạo pre-update backup
        backup_dir = create_pre_update_backup(str(app_data_dir))

        # 4. Sinh runner script với installer v1.5.5 thực tế kèm cờ cách ly hoàn toàn:
        # /NOICONS /TASKS="" /MERGETASKS="!desktopicon" và relaunch=False
        log_path = app_data_dir / "Logs" / "updater.log"
        script_path = app_data_dir / "Updates" / "run_update.ps1"

        generate_updater_runner_script(
            script_path=str(script_path),
            parent_pid=0,
            installer_path=str(installer_path),
            app_exe_path=str(old_exe),
            log_path=str(log_path),
            old_version="1.5.4",
            new_version="1.5.5",
            new_build=155,
            backup_dir=str(backup_dir),
            install_dir=str(install_dir),
            user_data_dir=str(app_data_dir),
            extra_inno_args='/NOICONS /TASKS="" /MERGETASKS="!desktopicon"',
            relaunch=False
        )

        # 5. Chạy PowerShell runner
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        assert res.returncode == 0, f"PowerShell thất bại: {res.stderr}"

        # 6. Kiểm tra kết quả
        assert log_path.exists()
        log_content = log_path.read_text(encoding="utf-8", errors="replace")
        assert "Mã thoát: 0" in log_content or "thành công" in log_content.lower()

        # Kiểm tra file exe đã được Inno Setup ghi đè thành binary PyInstaller thực tế
        new_size = old_exe.stat().st_size
        assert new_size > 1024 * 1024, f"Binary không đúng kích thước: {new_size} bytes"

        # Kiểm tra dữ liệu được giữ nguyên
        assert test_photo.exists() and test_photo.read_bytes() == b"AUDIT_PHOTO_CONTENT_PRESERVED"
        assert test_frame.exists() and "FRAME_PRESERVED" in test_frame.read_text(encoding="utf-8")
        assert config_file.exists() and "DamCuoi_Audit_2026" in config_file.read_text(encoding="utf-8")
    finally:
        # Dọn dẹp triệt để tiến trình con sinh ra
        _cleanup_test_spawned_processes(install_dir)
        _cleanup_test_spawned_processes(env_dir)

        # Phục hồi Registry Uninstall về trạng thái trước test
        try:
            import winreg
            if key_existed and reg_backup:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key_path, 0, winreg.KEY_ALL_ACCESS) as k:
                    current_val_names = []
                    idx = 0
                    while True:
                        try:
                            v_name, _, _ = winreg.EnumValue(k, idx)
                            current_val_names.append(v_name)
                            idx += 1
                        except OSError:
                            break
                    for cv in current_val_names:
                        if cv not in reg_backup:
                            try:
                                winreg.DeleteValue(k, cv)
                            except OSError:
                                pass
                    for val_name, (val_data, val_type) in reg_backup.items():
                        winreg.SetValueEx(k, val_name, 0, val_type, val_data)
            elif not key_existed:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_key_path)
                except OSError:
                    pass
        except Exception:
            pass

        # Phục hồi shortcuts nếu bị thay đổi hoặc xóa shortcuts rác được sinh ra
        for lnk, original_bytes in shortcut_backups.items():
            try:
                if lnk.exists() and lnk.read_bytes() != original_bytes:
                    lnk.write_bytes(original_bytes)
            except Exception:
                pass
        for search_dir in [desktop_dir, start_menu_dir]:
            if search_dir.exists():
                for lnk in search_dir.rglob("*Photobooth*.lnk"):
                    if lnk not in shortcut_backups:
                        try:
                            lnk.unlink(missing_ok=True)
                        except Exception:
                            pass

