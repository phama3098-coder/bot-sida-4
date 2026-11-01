"""
1998 TEAM — Photobooth Update Engine
Handles asynchronous update checking, manifest verification, chunked secure downloading,
SHA-256 integrity checks, Windows Authenticode signature verification, and safe installer launching.
"""

import os
import sys
import re
import time
import shutil
import socket
import hashlib
import subprocess
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse
import json

import requests
from PySide6.QtCore import QObject, Signal, QThread

from vietphotobooth.version import (
    __version__, __build__, __app_name__, is_newer_version, get_version_string
)
from vietphotobooth.updates.manifest import UpdateManifest
from vietphotobooth.updates.migration import create_pre_update_backup
from vietphotobooth.core.config import ConfigManager, get_user_data_dir
from vietphotobooth.core.logger import get_logger

logger = get_logger()

def check_network_connectivity(host: str = "8.8.8.8", port: int = 53, timeout: float = 1.5) -> bool:
    """Kiểm tra kết nối Internet nhanh không làm nghẽn ứng dụng."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
        return True
    except Exception:
        return False

def verify_digital_signature(file_path: str, require_signed: bool = False) -> Dict[str, Any]:
    """
    Xác minh chữ ký số Windows Authenticode của tệp thực thi.
    Kiểm tra trạng thái chữ ký số qua PowerShell Authenticode Provider trên Windows.

    Tham số:
        file_path: Đường dẫn tệp cần xác minh.
        require_signed: Nếu True, tệp bắt buộc phải có chữ ký số hợp lệ (Valid);
                       nếu tệp chưa được ký (NotSigned), valid sẽ là False.

    Trả về dict có cấu trúc rõ ràng:
        {
            "signed": bool,       # True nếu có chữ ký (Valid, NotTrusted, HashMismatch, v.v.)
            "valid": bool,        # True nếu chữ ký hoàn toàn hợp lệ (Valid)
            "status": str,        # "Valid", "NotSigned", "HashMismatch", "NotTrusted", "UnknownError", "FileNotFound", "Error"
            "signer": str,        # Chủ thể chứng thư ký (Subject) nếu có
            "error": Optional[str]# Thông điệp chi tiết về lỗi nếu có
        }
    """
    if not sys.platform.startswith("win"):
        return {
            "signed": False,
            "valid": False,
            "status": "Not Windows",
            "signer": "",
            "error": "Xác minh chữ ký số chỉ hỗ trợ trên Windows"
        }

    if not file_path or not os.path.exists(file_path):
        return {
            "signed": False,
            "valid": False,
            "status": "FileNotFound",
            "signer": "",
            "error": f"Tệp không tồn tại: {file_path}"
        }

    # Truyền đường dẫn an toàn qua biến môi trường để chống chèn lệnh và lỗi khoảng trắng/ký tự đặc biệt
    env = os.environ.copy()
    env["PHOTOBOOTH_SIG_TARGET"] = os.path.abspath(file_path)

    ps_script = (
        "$ErrorActionPreference = 'Stop'; "
        "$target = $env:PHOTOBOOTH_SIG_TARGET; "
        "if (-not $target -or -not (Test-Path -LiteralPath $target)) { "
        "  [PSCustomObject]@{ status = 'FileNotFound'; valid = $false; signed = $false; signer = ''; error = 'File not found' } | ConvertTo-Json -Compress; "
        "  exit "
        "}; "
        "try { "
        "  $sig = Get-AuthenticodeSignature -LiteralPath $target -ErrorAction SilentlyContinue; "
        "  if ($null -eq $sig) { "
        "    [PSCustomObject]@{ status = 'Error'; valid = $false; signed = $false; signer = ''; error = 'Signature object is null' } | ConvertTo-Json -Compress; "
        "    exit "
        "  }; "
        "  $statusStr = if ($null -ne $sig.Status) { $sig.Status.ToString() } else { 'NotSigned' }; "
        "  $isValid = ($statusStr -eq 'Valid'); "
        "  $isSigned = ($statusStr -in @('Valid', 'NotTrusted', 'HashMismatch')); "
        "  $signer = if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { '' }; "
        "  $errMsg = if ($sig.StatusMessage) { $sig.StatusMessage } else { '' }; "
        "  [PSCustomObject]@{ status = $statusStr; valid = $isValid; signed = $isSigned; signer = $signer; error = $errMsg } | ConvertTo-Json -Compress "
        "} catch { "
        "  [PSCustomObject]@{ status = 'Error'; valid = $false; signed = $false; signer = ''; error = $_.Exception.Message } | ConvertTo-Json -Compress "
        "}"
    )

    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )
        out = res.stdout.strip()
        if out:
            data = json.loads(out)
            status = str(data.get("status", "Unknown"))
            signed = bool(data.get("signed", False))
            valid = bool(data.get("valid", False))
            signer = str(data.get("signer", ""))
            raw_err = str(data.get("error", "")).strip()
            error = raw_err if raw_err else None

            if require_signed and not (signed and valid):
                valid = False

            return {
                "signed": signed,
                "valid": valid,
                "status": status,
                "signer": signer,
                "error": error
            }
        else:
            err_msg = res.stderr.strip() or "PowerShell không trả về dữ liệu"
            return {
                "signed": False,
                "valid": False,
                "status": "Error",
                "signer": "",
                "error": err_msg
            }
    except subprocess.TimeoutExpired:
        logger.warning(f"Quá thời gian khi xác minh chữ ký số: {file_path}")
        return {
            "signed": False,
            "valid": False,
            "status": "Error",
            "signer": "",
            "error": "Quá thời gian khi kiểm tra chữ ký số (Timeout)"
        }
    except Exception as e:
        logger.warning(f"Không thể kiểm tra chữ ký số: {e}")
        return {
            "signed": False,
            "valid": False,
            "status": "Error",
            "signer": "",
            "error": str(e)
        }


def validate_pe_executable(file_path: str, min_size_bytes: int = 512 * 1024) -> Tuple[bool, str]:
    """
    Xác minh định dạng tệp thực thi Windows (PE - Portable Executable).
    Kiểm tra magic bytes 'MZ' tại offset 0 và chữ ký 'PE\\0\\0' tại offset e_lfanew.
    """
    if not os.path.exists(file_path):
        return False, f"Tệp không tồn tại: {file_path}"

    size = os.path.getsize(file_path)
    if size < min_size_bytes:
        return False, f"Dung lượng tệp ({size} bytes) quá nhỏ, không phải bộ cài đặt hợp lệ."

    try:
        with open(file_path, "rb") as f:
            header = f.read(1024)
            if len(header) < 64:
                return False, "Kích thước header tệp quá ngắn."
            if header[:2] != b"MZ":
                return False, "Tệp không chứa chữ ký DOS Header hợp lệ ('MZ')."

            import struct
            pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
            if pe_offset < 0x40 or pe_offset > size - 4:
                return False, f"Địa chỉ PE Header không hợp lệ (offset 0x{pe_offset:X})."

            f.seek(pe_offset)
            pe_sig = f.read(4)
            if pe_sig != b"PE\x00\x00":
                return False, "Tệp không chứa chữ ký PE Header hợp lệ ('PE\\0\\0')."
        return True, "Tệp thực thi Windows PE hợp lệ."
    except Exception as ex:
        return False, f"Lỗi phân tích PE Header: {ex}"


def validate_installer_package(
    installer_path: str,
    expected_sha256: str = "",
    expected_size: int = 0
) -> Tuple[bool, str]:
    """
    Kiểm tra toàn diện tính toàn vẹn và độ an toàn của gói cài đặt trước khi thực thi:
    1. Kiểm tra tồn tại và dung lượng tệp.
    2. Xác thực cấu trúc nhị phân Portable Executable (PE).
    3. Xác minh mã băm SHA-256 từ metadata tin cậy.
    4. Kiểm tra trạng thái chữ ký số Authenticode.
    """
    if not os.path.exists(installer_path):
        return False, f"Tệp gói cài đặt không tồn tại: {installer_path}"

    actual_size = os.path.getsize(installer_path)
    if actual_size == 0:
        return False, "Tệp gói cài đặt rỗng (0 bytes)."

    if expected_size > 0 and actual_size != expected_size:
        return False, f"Dung lượng tệp ({actual_size} bytes) không khớp với dung lượng công bố ({expected_size} bytes)."

    # Kiểm tra định dạng PE (nếu tệp đủ lớn)
    if actual_size >= 512 * 1024:
        is_pe, pe_err = validate_pe_executable(installer_path)
        if not is_pe:
            return False, pe_err

    # Xác minh mã băm SHA-256
    if expected_sha256:
        clean_expected = expected_sha256.lower().strip()
        hasher = hashlib.sha256()
        with open(installer_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_sha256 = hasher.hexdigest().lower()
        if actual_sha256 != clean_expected:
            return False, f"Mã SHA-256 thực tế ({actual_sha256[:12]}...) không khớp chữ ký ({clean_expected[:12]}...)."

    # Kiểm tra chữ ký số Authenticode nếu có
    sig_info = verify_digital_signature(installer_path)
    if sig_info.get("status") == "HashMismatch":
        return False, "Chữ ký số Authenticode của tệp bị hỏng hoặc bị can thiệp (HashMismatch)."

    return True, "Gói cài đặt hợp lệ và an toàn."


def generate_updater_runner_script(
    script_path: str,
    parent_pid: int,
    installer_path: str,
    app_exe_path: str,
    log_path: str,
    old_version: str,
    new_version: str,
    new_build: int,
    backup_dir: str = "",
    install_dir: str = "",
    user_data_dir: str = "",
    extra_inno_args: str = "",
    relaunch: bool = True
) -> str:
    """
    Sinh script PowerShell độc lập điều phối quy trình tự động cập nhật một lần bấm.
    Hoạt động ngoài tiến trình chính, chờ ứng dụng thoát sạch, chạy bộ cài Inno Setup
    ở chế độ im lặng, kiểm tra mã thoát và tự khởi chạy lại ứng dụng mới.
    """
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    inno_log_path = os.path.join(os.path.dirname(log_path), "inno_setup_install.log")

    def ps_esc(s: str) -> str:
        return str(s).replace("`", "``").replace('"', '`"').replace("$", "`$")

    script_content = f"""# 1998 TEAM Photobooth — Standalone Updater Runner
param(
    [int]$ParentPid = {parent_pid},
    [string]$InstallerPath = "{ps_esc(installer_path)}",
    [string]$AppExePath = "{ps_esc(app_exe_path)}",
    [string]$LogPath = "{ps_esc(log_path)}",
    [string]$OldVersion = "{ps_esc(old_version)}",
    [string]$NewVersion = "{ps_esc(new_version)}",
    [int]$NewBuild = {new_build},
    [string]$BackupDir = "{ps_esc(backup_dir)}",
    [string]$InstallDir = "{ps_esc(install_dir)}",
    [string]$UserDataDir = "{ps_esc(user_data_dir)}",
    [string]$ExtraInnoArgs = "{ps_esc(extra_inno_args)}",
    [bool]$Relaunch = ${str(relaunch).lower()}
)

$ErrorActionPreference = "Continue"

function Write-UpdateLog([string]$msg) {{
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    try {{
        $dir = Split-Path $LogPath -Parent
        if ($dir -and -not (Test-Path $dir)) {{
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }}
        Add-Content -Path $LogPath -Value $line -Encoding UTF8
    }} catch {{}}
}}

function Invoke-AppLaunch([string]$targetPath, [string[]]$argsList) {{
    if (-not $targetPath -or -not (Test-Path $targetPath)) {{
        Write-UpdateLog "Cảnh báo: Không tìm thấy file thực thi $targetPath"
        return
    }}
    $ext = [System.IO.Path]::GetExtension($targetPath).ToLower()
    try {{
        if ($ext -eq ".cmd" -or $ext -eq ".bat") {{
            # Khởi chạy script .cmd / .bat qua cmd.exe với lệnh call và đối số danh sách chuẩn, ẩn cửa sổ
            $cmdArgs = @("/c", "call", "`"$targetPath`"") + $argsList
            $p = Start-Process -FilePath "$env:ComSpec" -ArgumentList $cmdArgs -WindowStyle Hidden -PassThru
        }} else {{
            # Khởi chạy ứng dụng nhị phân Windows (.exe) với danh sách đối số
            $p = Start-Process -FilePath $targetPath -ArgumentList $argsList -PassThru
        }}
        if ($p) {{
            Write-UpdateLog "Đã gửi lệnh khởi chạy ứng dụng (PID $($p.Id)): $targetPath $($argsList -join ' ')"
        }} else {{
            Write-UpdateLog "Đã gửi lệnh khởi chạy ứng dụng: $targetPath $($argsList -join ' ')"
        }}
    }} catch {{
        Write-UpdateLog "Lỗi khi khởi chạy ứng dụng $($targetPath) - $_"
    }}
}}

Write-UpdateLog "=========================================================="
Write-UpdateLog "1998 TEAM PHOTOBOOTH — AUTO-UPDATER RUNNER KÍCH HOẠT"
Write-UpdateLog "Nâng cấp từ: v$OldVersion -> v$NewVersion (Build $NewBuild)"
Write-UpdateLog "Bộ cài đặt: $InstallerPath"
Write-UpdateLog "Đường dẫn ứng dụng: $AppExePath"

# 1. Chờ ứng dụng chính thoát hoàn toàn để giải phóng file locks
if ($ParentPid -gt 0) {{
    Write-UpdateLog "Đang chờ ứng dụng chính PID $ParentPid thoát sạch..."
    $timeoutSec = 20
    $waited = 0
    while ($waited -lt $timeoutSec) {{
        $p = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
        if (-not $p) {{
            Write-UpdateLog "Tiến trình chính PID $ParentPid đã thoát sạch."
            break
        }}
        Start-Sleep -Milliseconds 500
        $waited += 0.5
    }}

    $p = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
    if ($p) {{
        $pName = $p.ProcessName
        $pPath = try {{ $p.Path }} catch {{ "" }}
        $isOurApp = ($pName -match "^1998" -or $pName -match "python" -or ($pPath -and $InstallDir -and $pPath.StartsWith($InstallDir, [System.StringComparison]::OrdinalIgnoreCase)))
        if ($isOurApp) {{
            Write-UpdateLog "Cảnh báo: Ứng dụng chính ($pName) chưa thoát sau $timeoutSec giây. Đang yêu cầu dừng an toàn..."
            Stop-Process -Id $ParentPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }} else {{
            Write-UpdateLog "Cảnh báo: PID $ParentPid hiện không thuộc về 1998 TEAM Photobooth ($pName). Bỏ qua không dừng tiến trình này."
        }}
    }}
}}

# Dừng mọi tiến trình thuộc Photobooth trong thư mục cài đặt để giải phóng file locks, tuyệt đối không động chạm ứng dụng khác
if ($InstallDir -and (Test-Path $InstallDir)) {{
    try {{
        $normInstallDir = $InstallDir.TrimEnd('\') + '\'
        $lockingProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {{
            $_.ExecutablePath -and (
                $_.ExecutablePath.StartsWith($normInstallDir, [System.StringComparison]::OrdinalIgnoreCase) -or
                $_.ExecutablePath -ieq $InstallDir
            ) -and $_.ProcessId -ne $PID -and $_.ProcessId -gt 4
        }}
        foreach ($lp in $lockingProcs) {{
            Write-UpdateLog "Dừng tiến trình Photobooth còn lưu giữ file trong thư mục cài đặt: $($lp.Name) (PID $($lp.ProcessId))"
            Stop-Process -Id $lp.ProcessId -Force -ErrorAction SilentlyContinue
        }}
    }} catch {{
        Write-UpdateLog "Cảnh báo khi kiểm tra tiến trình trong thư mục cài đặt: $_"
    }}
}}

# Chờ thêm 1 giây để hệ điều hành giải phóng hoàn toàn file handles
Start-Sleep -Seconds 1

# 2. Xây dựng tham số gọi Inno Setup
$innoLog = "{ps_esc(inno_log_path)}"
$innoArgs = "/SILENT /SP- /SUPPRESSMSGBOXES /FORCECLOSEAPPLICATIONS /CLOSEAPPLICATIONS /NORESTART /LOG=`"$innoLog`""
if ($InstallDir -and (Test-Path $InstallDir)) {{
    $innoArgs += " /DIR=`"$InstallDir`""
}}
if ($ExtraInnoArgs) {{
    $innoArgs += " $ExtraInnoArgs"
}}

Write-UpdateLog "Chạy bộ cài đặt Inno Setup với tham số: $innoArgs"

$proc = Start-Process -FilePath $InstallerPath -ArgumentList $innoArgs -Wait -PassThru -NoNewWindow
$exitCode = $proc.ExitCode
Write-UpdateLog "Bộ cài đặt Inno Setup đã kết thúc với mã thoát: $exitCode"

# Nếu cài đặt thất bại và có log Inno Setup, ghi trích xuất log vào updater.log
if ($exitCode -ne 0 -and (Test-Path $innoLog)) {{
    try {{
        $tailLines = Get-Content -Path $innoLog -Tail 15 -ErrorAction SilentlyContinue
        if ($tailLines) {{
            Write-UpdateLog "--- [Inno Setup Log Tail] ---"
            foreach ($tLine in $tailLines) {{
                Write-UpdateLog "  $tLine"
            }}
            Write-UpdateLog "-----------------------------"
        }}
    }} catch {{}}
}}

# 3. Đánh giá mã thoát và khởi chạy lại ứng dụng
if ($exitCode -eq 0) {{
    Write-UpdateLog "Cài đặt nâng cấp v$NewVersion hoàn tất thành công 100%!"

    # Xác định đường dẫn thực thi chính xác sau khi cập nhật
    $targetExe = $AppExePath
    if (-not ($targetExe -and (Test-Path $targetExe))) {{
        if ($InstallDir -and (Test-Path (Join-Path $InstallDir "1998TeamPhotobooth.exe"))) {{
            $targetExe = Join-Path $InstallDir "1998TeamPhotobooth.exe"
        }} elseif ($env:LOCALAPPDATA -and (Test-Path (Join-Path $env:LOCALAPPDATA "Programs\1998TeamPhotobooth\1998TeamPhotobooth.exe"))) {{
            $targetExe = Join-Path $env:LOCALAPPDATA "Programs\1998TeamPhotobooth\1998TeamPhotobooth.exe"
        }}
    }}

    if (-not $Relaunch) {{
        Write-UpdateLog "Tự động khởi chạy lại ứng dụng bị vô hiệu hóa (Relaunch = false)."
    }} elseif ($targetExe -and (Test-Path $targetExe)) {{
        Write-UpdateLog "Khởi chạy lại ứng dụng chính đã cập nhật: $targetExe"
        $launchArgs = @("--updated-from", "$OldVersion", "--updated-to", "$NewVersion", "--updated-build", "$NewBuild")
        Invoke-AppLaunch -targetPath $targetExe -argsList $launchArgs
    }} else {{
        Write-UpdateLog "Cảnh báo: Không tìm thấy file thực thi sau khi cài đặt: $AppExePath"
    }}
}} else {{
    Write-UpdateLog "LỖI: Quá trình cài đặt thất bại với mã lỗi $exitCode."

    # Khôi phục dữ liệu từ bản sao lưu nếu có
    if ($BackupDir -and (Test-Path $BackupDir)) {{
        $targetRestoreDir = if ($UserDataDir -and (Test-Path $UserDataDir)) {{ $UserDataDir }} else {{ Split-Path (Split-Path $BackupDir -Parent) -Parent }}
        if ($targetRestoreDir -and (Test-Path $targetRestoreDir)) {{
            Write-UpdateLog "Đang khôi phục cấu hình từ bản sao lưu: $BackupDir vào: $targetRestoreDir"
            Get-ChildItem -Path $BackupDir | ForEach-Object {{
                Copy-Item -Path $_.FullName -Destination $targetRestoreDir -Force -Recurse -ErrorAction SilentlyContinue
            }}
            Write-UpdateLog "Đã hoàn tất khôi phục cấu hình an toàn."
        }}
    }}

    $targetExe = $AppExePath
    if (-not ($targetExe -and (Test-Path $targetExe))) {{
        if ($InstallDir -and (Test-Path (Join-Path $InstallDir "1998TeamPhotobooth.exe"))) {{
            $targetExe = Join-Path $InstallDir "1998TeamPhotobooth.exe"
        }} elseif ($env:LOCALAPPDATA -and (Test-Path (Join-Path $env:LOCALAPPDATA "Programs\1998TeamPhotobooth\1998TeamPhotobooth.exe"))) {{
            $targetExe = Join-Path $env:LOCALAPPDATA "Programs\1998TeamPhotobooth\1998TeamPhotobooth.exe"
        }}
    }}

    if (-not $Relaunch) {{
        Write-UpdateLog "Tự động khởi chạy lại ứng dụng bị vô hiệu hóa khi thất bại (Relaunch = false)."
    }} elseif ($targetExe -and (Test-Path $targetExe)) {{
        Write-UpdateLog "Khởi chạy lại ứng dụng phiên bản hiện tại kèm thông báo lỗi..."
        $failArgs = @("--update-failed", "$exitCode")
        Invoke-AppLaunch -targetPath $targetExe -argsList $failArgs
    }} else {{
        Write-UpdateLog "CẢNH BÁO: Không tìm thấy file thực thi $AppExePath sau khi cài đặt thất bại."
        Write-UpdateLog "HƯỚNG DẪN PHỤC HỒI: Vui lòng khởi động lại bộ cài đặt thủ công: $InstallerPath"
    }}
}}

Write-UpdateLog "Tiến trình Updater Runner kết thúc."
"""
    with open(script_path, "w", encoding="utf-8-sig") as f:
        f.write(script_content)

    return script_path


DEFAULT_GITHUB_REPO = "phama3098-coder/bot-sida-4"
DEFAULT_UPDATE_URL = "https://api.github.com/repos/phama3098-coder/bot-sida-4/releases/latest"

def normalize_update_url(url: str) -> str:
    """
    Chuẩn hóa URL cập nhật: nếu người dùng nhập URL trang web GitHub Release
    (như https://github.com/phama3098-coder/bot-sida-4/releases/latest),
    tự động chuyển thành endpoint GitHub Releases API chính thức.
    """
    clean_url = str(url or "").strip()
    if not clean_url:
        return DEFAULT_UPDATE_URL
    gh_match = re.match(
        r"^https?://github\.com/([^/]+)/([^/]+)(?:/releases(?:/(?:latest|tag/[^/]+))?)?/?$",
        clean_url,
        re.IGNORECASE
    )
    if gh_match:
        owner, repo = gh_match.group(1), gh_match.group(2)
        return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    return clean_url


class UpdateCheckWorker(QThread):
    """Worker luồng phụ kiểm tra phiên bản mới ngầm không làm gián đoạn chụp ảnh."""
    check_finished = Signal(bool, object, str)  # has_update: bool, manifest: Optional[UpdateManifest], message: str

    def __init__(self, manifest_url: str, current_version: str, current_build: int, parent=None):
        super().__init__(parent)
        self.manifest_url = normalize_update_url(manifest_url) if manifest_url else ""
        self.current_version = current_version
        self.current_build = current_build

    def run(self):
        # 1. Kiểm tra cấu hình URL
        if not self.manifest_url:
            self.check_finished.emit(
                False, None,
                "Chưa cấu hình máy chủ cập nhật (Manifest URL). Vui lòng cấu hình nguồn phát hành trong Cài Đặt."
            )
            return

        placeholder_domains = ["example.com", "example.org", "placeholder", "your-domain.com"]
        if any(p in self.manifest_url.lower() for p in placeholder_domains):
            self.check_finished.emit(
                False, None,
                "Chưa cấu hình máy chủ cập nhật (đang để URL mẫu example.com). Vui lòng cấu hình URL thật trong Cài đặt."
            )
            return

        is_local_file = os.path.exists(self.manifest_url) or self.manifest_url.startswith("file://")

        # 2. Nếu là URL từ xa, kiểm tra kết nối mạng trước
        if not is_local_file:
            if not check_network_connectivity():
                self.check_finished.emit(False, None, "Không có kết nối Internet để kiểm tra cập nhật.")
                return

        # 3. Lấy nội dung manifest
        try:
            content = ""
            if is_local_file:
                clean_path = self.manifest_url.replace("file:///", "").replace("file://", "")
                if not os.path.exists(clean_path):
                    self.check_finished.emit(False, None, f"Tệp manifest cập nhật không tồn tại: {clean_path}")
                    return
                with open(clean_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                try:
                    resp = requests.get(
                        self.manifest_url,
                        timeout=8.0,
                        allow_redirects=True,
                        headers={
                            "User-Agent": "1998TeamPhotobooth-Updater/1.0",
                            "Accept": "application/vnd.github.v3+json, application/json, text/plain, */*"
                        }
                    )
                except requests.exceptions.Timeout:
                    self.check_finished.emit(False, None, "Quá thời gian kết nối đến máy chủ cập nhật (Timeout).")
                    return
                except requests.exceptions.ConnectionError:
                    self.check_finished.emit(False, None, "Không thể kết nối đến máy chủ cập nhật. Vui lòng kiểm tra lại kết nối mạng hoặc địa chỉ URL.")
                    return
                except requests.exceptions.RequestException as req_err:
                    self.check_finished.emit(False, None, f"Lỗi kết nối máy chủ cập nhật: {req_err}")
                    return

                if resp.status_code == 404:
                    if "api.github.com" in self.manifest_url or "github.com" in self.manifest_url:
                        self.check_finished.emit(
                            False, None,
                            f"Không tìm thấy kho lưu trữ hoặc bản phát hành trên GitHub (Lỗi HTTP 404 Not Found tại {self.manifest_url}). Vui lòng kiểm tra lại repository."
                        )
                    else:
                        self.check_finished.emit(
                            False, None,
                            f"Máy chủ phản hồi: Tệp manifest cập nhật không tồn tại (Lỗi HTTP 404 Not Found tại {self.manifest_url})."
                        )
                    return
                elif resp.status_code == 403:
                    if resp.headers.get("x-ratelimit-remaining") == "0":
                        self.check_finished.emit(
                            False, None,
                            "Đã vượt quá giới hạn truy vấn tạm thời của GitHub API (Rate Limit 60 lượt/giờ đối với IP công cộng). Vui lòng thử lại sau vài phút."
                        )
                    else:
                        self.check_finished.emit(
                            False, None,
                            f"Máy chủ cập nhật từ chối truy cập (Lỗi HTTP 403 Forbidden tại {self.manifest_url})."
                        )
                    return
                elif resp.status_code >= 500:
                    self.check_finished.emit(
                        False, None,
                        f"Máy chủ cập nhật đang gặp sự cố nội bộ (Lỗi HTTP {resp.status_code} tại {self.manifest_url})."
                    )
                    return
                elif resp.status_code != 200:
                    self.check_finished.emit(
                        False, None,
                        f"Máy chủ cập nhật phản hồi mã lỗi HTTP {resp.status_code} tại {self.manifest_url}."
                    )
                    return

                content = resp.text

            # 4. Phân tích cú pháp JSON
            try:
                data = json.loads(content)
            except Exception as json_err:
                self.check_finished.emit(False, None, f"Tệp phản hồi từ máy chủ cập nhật không đúng định dạng JSON: {json_err}")
                return

            if not isinstance(data, dict):
                self.check_finished.emit(False, None, "Dữ liệu cập nhật từ máy chủ phải là một JSON Object.")
                return

            try:
                is_github_endpoint = (
                    "api.github.com" in self.manifest_url or
                    "github.com" in self.manifest_url or
                    UpdateManifest.is_github_release(data)
                )
                if is_github_endpoint:
                    logger.info(f"Phân tích dữ liệu theo chuẩn GitHub Releases API: {self.manifest_url}")
                    manifest = UpdateManifest.from_github_release(data)
                else:
                    logger.info(f"Phân tích dữ liệu theo chuẩn Manifest JSON nội bộ: {self.manifest_url}")
                    manifest = UpdateManifest.from_dict(data)
            except Exception as parse_err:
                self.check_finished.emit(False, None, f"Lỗi phân tích bản cập nhật: {parse_err}")
                return

            # 5. Xác thực tính toàn vẹn của metadata manifest
            errors = manifest.validate_integrity()
            if errors:
                err_str = "; ".join(errors)
                self.check_finished.emit(False, None, f"Dữ liệu bản cập nhật không hợp lệ: {err_str}")
                return

            # 6. So sánh phiên bản
            has_update = is_newer_version(
                current_ver=self.current_version,
                candidate_ver=manifest.version,
                current_build=self.current_build,
                candidate_build=manifest.build
            )

            if not has_update:
                msg = f"Phiên bản hiện tại (v{self.current_version}) đã là mới nhất."
                self.check_finished.emit(False, manifest, msg)
                return

            # 7. Kiểm tra trước nguồn tải bộ cài (Pre-check Download URL)
            # Ngăn chặn tình trạng thông báo có bản mới nhưng link tải trả về 404
            dl_url = manifest.download_url
            if os.path.exists(dl_url) or dl_url.startswith("file://"):
                local_installer = dl_url.replace("file:///", "").replace("file://", "")
                if not os.path.exists(local_installer):
                    err_msg = f"Nguồn tải gói cài đặt không hợp lệ hoặc không tồn tại (Tệp không tìm thấy: {local_installer}). Vui lòng kiểm tra lại cấu hình phát hành."
                    logger.error(err_msg)
                    self.check_finished.emit(False, None, err_msg)
                    return
                if manifest.file_size_bytes <= 0:
                    manifest.file_size_bytes = os.path.getsize(local_installer)
            else:
                try:
                    # Gửi yêu cầu kiểm tra sự tồn tại của tệp cài đặt trên máy chủ
                    check_resp = requests.head(
                        dl_url,
                        timeout=5.0,
                        allow_redirects=True,
                        headers={"User-Agent": "1998TeamPhotobooth-Updater/1.0"}
                    )
                    if check_resp.status_code == 405:
                        check_resp = requests.get(
                            dl_url,
                            stream=True,
                            timeout=5.0,
                            allow_redirects=True,
                            headers={"User-Agent": "1998TeamPhotobooth-Updater/1.0"}
                        )

                    if check_resp.status_code == 404:
                        err_msg = f"Nguồn tải gói cài đặt không tồn tại trên máy chủ (Lỗi HTTP 404 Not Found - URL: {dl_url}). Vui lòng kiểm tra lại cấu hình phát hành."
                        logger.error(err_msg)
                        self.check_finished.emit(False, None, err_msg)
                        return
                    elif check_resp.status_code >= 500:
                        err_msg = f"Máy chủ lưu trữ gói cài đặt đang gặp sự cố nội bộ (Lỗi HTTP {check_resp.status_code} - URL: {dl_url})."
                        logger.error(err_msg)
                        self.check_finished.emit(False, None, err_msg)
                        return
                    elif check_resp.status_code != 200:
                        err_msg = f"Không thể truy cập tệp cài đặt (Mã lỗi HTTP {check_resp.status_code} - URL: {dl_url})."
                        logger.error(err_msg)
                        self.check_finished.emit(False, None, err_msg)
                        return

                    # Nếu máy chủ trả Content-Length và manifest chưa có size, tự động bổ sung
                    cl_header = check_resp.headers.get("content-length")
                    if cl_header and cl_header.isdigit():
                        server_size = int(cl_header)
                        if manifest.file_size_bytes <= 0:
                            manifest.file_size_bytes = server_size
                        elif manifest.file_size_bytes != server_size:
                            logger.warning(
                                f"Dung lượng công bố ({manifest.file_size_bytes}) khác Content-Length máy chủ ({server_size}). Sử dụng kích thước thực tế máy chủ."
                            )
                            manifest.file_size_bytes = server_size
                except requests.exceptions.RequestException as dl_err:
                    err_msg = f"Lỗi kết nối khi kiểm tra nguồn tải bộ cài ({dl_url}): {dl_err}"
                    logger.error(err_msg)
                    self.check_finished.emit(False, None, err_msg)
                    return

            msg = f"Đã tìm thấy phiên bản mới: v{manifest.version} (Build {manifest.build})"
            self.check_finished.emit(True, manifest, msg)

        except Exception as e:
            logger.warning(f"Lỗi khi kiểm tra cập nhật từ {self.manifest_url}: {e}")
            self.check_finished.emit(False, None, f"Lỗi không xác định khi kiểm tra cập nhật: {e}")


class UpdateDownloadWorker(QThread):
    """Worker tải gói cài đặt an toàn, hỗ trợ redirect, streaming chunk, và xác thực SHA-256."""
    progress_changed = Signal(int, int, int)  # percent (-1 nếu không rõ tổng kích thước), downloaded_bytes, total_bytes
    download_finished = Signal(bool, str, str)  # success, installer_path, error_msg

    def __init__(self, manifest: UpdateManifest, dest_dir: str, parent=None):
        super().__init__(parent)
        self.manifest = manifest
        self.dest_dir = dest_dir
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        url = self.manifest.download_url
        placeholder_domains = ["example.com", "example.org", "placeholder", "your-domain.com"]
        if any(p in url.lower() for p in placeholder_domains):
            self.download_finished.emit(
                False, "",
                "Đường dẫn tải gói cài đặt là URL mẫu (example.com), chưa được cấu hình máy chủ phát hành thực tế."
            )
            return

        os.makedirs(self.dest_dir, exist_ok=True)
        raw_name = os.path.basename(urlparse(url).path) or f"1998-TEAM-Setup-v{self.manifest.version}.exe"
        if not raw_name.endswith(".exe"):
            raw_name += ".exe"

        dest_file = os.path.join(self.dest_dir, raw_name)
        temp_file = dest_file + ".part"

        # Nếu tệp tạm cũ còn sót lại từ lần trước, xóa dọn dẹp
        self._cleanup_temp(temp_file)

        try:
            # 1. Hỗ trợ tệp cục bộ (Local Testing / LAN Share)
            if os.path.exists(url) or url.startswith("file://"):
                src_path = url.replace("file:///", "").replace("file://", "")
                if not os.path.exists(src_path):
                    self.download_finished.emit(False, "", f"Không tìm thấy tệp cài đặt tại: {src_path}")
                    return

                total_bytes = os.path.getsize(src_path)
                downloaded = 0
                with open(src_path, "rb") as f_in, open(temp_file, "wb") as f_out:
                    while self._running:
                        chunk = f_in.read(65536)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        downloaded += len(chunk)
                        percent = min(100, int((downloaded / total_bytes) * 100)) if total_bytes > 0 else -1
                        self.progress_changed.emit(percent, downloaded, total_bytes)

                if not self._running:
                    self._cleanup_temp(temp_file)
                    self.download_finished.emit(False, "", "Tiến trình tải xuống đã bị hủy bởi người dùng.")
                    return
            else:
                # 2. Tải qua HTTP/HTTPS hỗ trợ đầy đủ redirects (301, 302, 307, 308)
                try:
                    resp = requests.get(
                        url,
                        stream=True,
                        timeout=12.0,
                        allow_redirects=True,
                        headers={"User-Agent": "1998TeamPhotobooth-Updater/1.0"}
                    )
                except requests.exceptions.Timeout:
                    self._cleanup_temp(temp_file)
                    self.download_finished.emit(False, "", "Quá thời gian chờ máy chủ phản hồi khi tải gói cài đặt (Timeout).")
                    return
                except requests.exceptions.ConnectionError:
                    self._cleanup_temp(temp_file)
                    self.download_finished.emit(False, "", "Không thể kết nối đến máy chủ tải bộ cài. Vui lòng kiểm tra lại mạng Internet.")
                    return
                except requests.exceptions.RequestException as req_err:
                    self._cleanup_temp(temp_file)
                    self.download_finished.emit(False, "", f"Lỗi kết nối tải gói cài đặt: {req_err}")
                    return

                with resp:
                    if resp.status_code == 404:
                        self._cleanup_temp(temp_file)
                        self.download_finished.emit(
                            False, "",
                            f"Tệp cài đặt không tồn tại trên máy chủ (Lỗi HTTP 404 Not Found - URL: {url}). Vui lòng kiểm tra lại cấu hình phát hành."
                        )
                        return
                    elif resp.status_code >= 500:
                        self._cleanup_temp(temp_file)
                        self.download_finished.emit(
                            False, "",
                            f"Máy chủ lưu trữ bộ cài gặp sự cố nội bộ (Mã lỗi HTTP {resp.status_code} - URL: {url})."
                        )
                        return
                    elif resp.status_code != 200:
                        self._cleanup_temp(temp_file)
                        self.download_finished.emit(
                            False, "",
                            f"Không thể tải bộ cài đặt (Mã lỗi HTTP {resp.status_code} - URL: {url})."
                        )
                        return

                    # Xác định kích thước: Content-Length từ header hoặc manifest
                    cl_header = resp.headers.get("content-length")
                    content_length = int(cl_header) if (cl_header and cl_header.isdigit()) else 0
                    total_bytes = content_length or self.manifest.file_size_bytes
                    downloaded = 0

                    with open(temp_file, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if not self._running:
                                self._cleanup_temp(temp_file)
                                self.download_finished.emit(False, "", "Tiến trình tải xuống đã bị hủy bởi người dùng.")
                                return
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_bytes > 0:
                                    percent = min(100, int((downloaded / total_bytes) * 100))
                                else:
                                    percent = -1  # Không có Content-Length: indeterminate
                                self.progress_changed.emit(percent, downloaded, total_bytes)

            # Kiểm tra trạng thái hủy
            if not self._running:
                self._cleanup_temp(temp_file)
                self.download_finished.emit(False, "", "Tiến trình tải xuống đã bị hủy bởi người dùng.")
                return

            # Kiểm tra tệp tạm có dữ liệu không
            if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                self._cleanup_temp(temp_file)
                self.download_finished.emit(False, "", "Tệp tải về rỗng (0 bytes).")
                return

            # 3. Tính toán và xác minh mã băm SHA-256
            hasher = hashlib.sha256()
            with open(temp_file, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            actual_sha256 = hasher.hexdigest().lower()

            expected_sha256 = self.manifest.sha256.lower().strip()
            if not expected_sha256:
                self._cleanup_temp(temp_file)
                err = "Gói cài đặt chưa có mã băm SHA-256 đáng tin cậy được công bố. Cài đặt tự động bị từ chối để đảm bảo an toàn."
                logger.error(err)
                self.download_finished.emit(False, "", err)
                return
            elif actual_sha256 != expected_sha256:
                self._cleanup_temp(temp_file)
                err = f"Xác thực tính toàn vẹn thất bại: Mã SHA-256 thực tế ({actual_sha256[:12]}...) không khớp với chữ ký ({expected_sha256[:12]}...). Tệp tạm đã bị hủy bỏ."
                logger.error(err)
                self.download_finished.emit(False, "", err)
                return

            # 4. Kiểm tra dung lượng tệp nếu manifest có định nghĩa
            actual_size = os.path.getsize(temp_file)
            if self.manifest.file_size_bytes > 0 and actual_size != self.manifest.file_size_bytes:
                self._cleanup_temp(temp_file)
                err = f"Dung lượng tệp tải về ({actual_size} bytes) không khớp với dung lượng công bố ({self.manifest.file_size_bytes} bytes)."
                logger.error(err)
                self.download_finished.emit(False, "", err)
                return

            # 5. Xác thực cấu trúc tệp thực thi Windows (PE) nếu dung lượng >= 512KB
            if actual_size >= 512 * 1024:
                is_pe, pe_err = validate_pe_executable(temp_file)
                if not is_pe:
                    self._cleanup_temp(temp_file)
                    err = f"Tệp tải về không phải gói cài đặt Windows PE hợp lệ: {pe_err}"
                    logger.error(err)
                    self.download_finished.emit(False, "", err)
                    return

            # 6. Kiểm tra chữ ký số nếu có
            sig_info = verify_digital_signature(temp_file)
            if sig_info.get("status") == "HashMismatch":
                self._cleanup_temp(temp_file)
                err = "Chữ ký số Authenticode của tệp cài đặt bị hỏng hoặc không hợp lệ (HashMismatch)."
                logger.error(err)
                self.download_finished.emit(False, "", err)
                return
            elif sig_info.get("valid"):
                logger.info(f"Đã xác minh chữ ký số Authenticode hợp lệ cho: {dest_file}")

            # 7. Đổi tên tệp tạm hoàn chỉnh sang tệp đích
            if os.path.exists(dest_file):
                try:
                    os.remove(dest_file)
                except Exception:
                    pass
            os.rename(temp_file, dest_file)

            logger.info(f"Đã tải và xác thực thành công bộ cài mới: {dest_file} ({actual_size} bytes)")
            self.download_finished.emit(True, dest_file, "")

        except Exception as e:
            self._cleanup_temp(temp_file)
            logger.error(f"Lỗi khi tải bộ cài: {e}")
            self.download_finished.emit(False, "", f"Lỗi khi tải bộ cài: {e}")

    def _cleanup_temp(self, temp_file: str):
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass


class UpdateManager(QObject):
    """Bộ quản lý kiểm tra, thông báo, tải xuống và áp dụng bản cập nhật cho 1998 TEAM Photobooth."""
    check_started = Signal()
    check_completed = Signal(bool, object, str)  # has_update, manifest, msg
    download_progress = Signal(int, int, int)
    download_completed = Signal(bool, str, str)

    def __init__(self, config_mgr: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_mgr = config_mgr
        self._check_worker: Optional[UpdateCheckWorker] = None
        self._download_worker: Optional[UpdateDownloadWorker] = None
        self._latest_manifest: Optional[UpdateManifest] = None
        self._dismissed_versions_in_session = set()

    @property
    def manifest_url(self) -> str:
        url = self.config_mgr.get("updates.manifest_url", "")
        if not url:
            return DEFAULT_UPDATE_URL
        return normalize_update_url(str(url))

    @manifest_url.setter
    def manifest_url(self, url: str):
        self.config_mgr.set("updates.manifest_url", str(url).strip())
        self.config_mgr.save()

    @property
    def is_auto_check_enabled(self) -> bool:
        return bool(self.config_mgr.get("updates.auto_check_on_startup", True))

    @is_auto_check_enabled.setter
    def is_auto_check_enabled(self, enabled: bool):
        self.config_mgr.set("updates.auto_check_on_startup", bool(enabled))
        self.config_mgr.save()

    def check_for_updates(self, manual: bool = False):
        """Khởi chạy luồng kiểm tra cập nhật (ngăn chặn chạy đồng thời)."""
        if (self._check_worker and self._check_worker.isRunning()) or (self._download_worker and self._download_worker.isRunning()):
            logger.info("Tiến trình cập nhật đang chạy, bỏ qua yêu cầu kiểm tra mới.")
            return

        self.check_started.emit()
        url = self.manifest_url

        self._check_worker = UpdateCheckWorker(
            manifest_url=url,
            current_version=__version__,
            current_build=__build__,
            parent=self
        )
        self._check_worker.check_finished.connect(
            lambda has_up, m, msg: self._on_check_finished(has_up, m, msg, manual=manual)
        )
        self._check_worker.start()

    def _on_check_finished(self, has_update: bool, manifest: Optional[UpdateManifest], msg: str, manual: bool = False):
        if manifest:
            self._latest_manifest = manifest

        # Nếu kiểm tra tự động mà người dùng đã chọn "Để sau" trong phiên này thì không nhắc lại
        if has_update and not manual and manifest:
            if manifest.version in self._dismissed_versions_in_session:
                has_update = False

        self.check_completed.emit(has_update, manifest, msg)

    def dismiss_version_for_session(self, version: str):
        """Ghi nhớ người dùng đã chọn 'Để sau' cho phiên làm việc này."""
        self._dismissed_versions_in_session.add(version)

    @property
    def latest_manifest(self) -> Optional[UpdateManifest]:
        return self._latest_manifest

    def cancel_download(self):
        """Hủy tiến trình tải bộ cài đặt hiện tại và dọn dẹp an toàn."""
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.stop()

    def start_download(self, manifest: UpdateManifest):
        """Khởi chạy luồng tải bộ cài (ngăn chặn chạy đồng thời)."""
        if self._download_worker and self._download_worker.isRunning():
            logger.info("Tiến trình tải xuống đang chạy.")
            return

        app_dir = get_user_data_dir()
        download_dir = os.path.join(app_dir, "Downloads")

        self._download_worker = UpdateDownloadWorker(manifest, download_dir, parent=self)
        self._download_worker.progress_changed.connect(self.download_progress.emit)
        self._download_worker.download_finished.connect(self.download_completed.emit)
        self._download_worker.start()

    def apply_update_and_restart(
        self,
        installer_path: str,
        user_data_dir: Optional[str] = None,
        target_version: str = "",
        target_build: int = 0
    ) -> bool:
        """
        Thực hiện quy trình cập nhật tự động một lần bấm:
        1. Kiểm tra sự tồn tại của tệp cài đặt.
        2. Tự động sao lưu cấu hình người dùng (config.json, sync_registry.json...).
        3. Sinh và khởi chạy Updater Runner độc lập (run_update.ps1) chạy ngầm.
        4. Thoát sạch ứng dụng chính để nhường quyền ghi đè tệp cho bộ cài Inno Setup.
        """
        if not os.path.exists(installer_path) or os.path.getsize(installer_path) == 0:
            logger.error(f"Tệp bộ cài đặt không tồn tại hoặc rỗng: {installer_path}")
            return False

        try:
            # 1. Xác định thư mục dữ liệu người dùng và tạo bản sao lưu an toàn
            backup_dir = user_data_dir
            if not backup_dir and hasattr(self.config_mgr, "config_path") and self.config_mgr.config_path:
                backup_dir = os.path.dirname(self.config_mgr.config_path)
            if not backup_dir:
                backup_dir = get_user_data_dir()

            backup_folder = create_pre_update_backup(user_data_dir=backup_dir)

            # 2. Xác định đường dẫn tệp thực thi chính và thư mục cài đặt
            if getattr(sys, "frozen", False):
                app_exe = sys.executable
                install_dir = os.path.dirname(app_exe)
            else:
                local_app_data = os.environ.get("LOCALAPPDATA", "")
                candidate_exe = os.path.join(local_app_data, "Programs", "1998TeamPhotobooth", "1998TeamPhotobooth.exe")
                if os.path.exists(candidate_exe):
                    app_exe = candidate_exe
                    install_dir = os.path.dirname(candidate_exe)
                else:
                    app_exe = sys.executable
                    install_dir = os.path.dirname(sys.executable)

            # 3. Chuẩn bị đường dẫn log và script runner độc lập
            logs_dir = os.path.join(backup_dir, "Logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_path = os.path.join(logs_dir, "updater.log")

            updates_dir = os.path.join(backup_dir, "Updates")
            os.makedirs(updates_dir, exist_ok=True)
            runner_script_path = os.path.join(updates_dir, "run_update.ps1")

            new_ver = target_version or (self._latest_manifest.version if self._latest_manifest else __version__)
            new_bld = target_build or (self._latest_manifest.build if self._latest_manifest else __build__)

            generate_updater_runner_script(
                script_path=runner_script_path,
                parent_pid=os.getpid(),
                installer_path=os.path.abspath(installer_path),
                app_exe_path=os.path.abspath(app_exe),
                log_path=os.path.abspath(log_path),
                old_version=__version__,
                new_version=new_ver,
                new_build=new_bld,
                backup_dir=os.path.abspath(backup_folder),
                install_dir=os.path.abspath(install_dir),
                user_data_dir=os.path.abspath(backup_dir)
            )

            # 4. Khởi chạy tiến trình độc lập (CREATE_NO_WINDOW + CREATE_NEW_PROCESS_GROUP)
            ps_cmd = [
                "powershell.exe",
                "-WindowStyle", "Hidden",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", runner_script_path
            ]

            creation_flags = 0
            if sys.platform == "win32":
                # CREATE_NO_WINDOW (0x08000000) | CREATE_NEW_PROCESS_GROUP (0x00000200)
                # Tuyệt đối không dùng DETACHED_PROCESS (0x00000008) vì powershell.exe console subsystem
                # sẽ bị lỗi khởi tạo console và thoát ngay lập tức mà không chạy script.
                creation_flags = 0x08000000 | 0x00000200

            subprocess.Popen(
                ps_cmd,
                creationflags=creation_flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )
            logger.info(f"Đã kích hoạt Updater Runner độc lập: {runner_script_path}")

            # 5. Đóng sạch tất cả các cửa sổ để kích hoạt cleanup (giải phóng camera, threads, locks)
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                try:
                    app.closeAllWindows()
                except Exception as close_err:
                    logger.warning(f"Lỗi khi đóng các cửa sổ: {close_err}")
                app.quit()
            return True
        except Exception as e:
            logger.error(f"Không thể khởi chạy quy trình cập nhật tự động: {e}")
            return False
