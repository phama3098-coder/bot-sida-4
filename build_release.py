"""
Build and Release Automation Script for 1998 TEAM — Photobooth
Automates:
1. Version & Metadata discovery from vietphotobooth/version.py (Single Source of Truth).
2. Clean PyInstaller compilation with vietphotobooth.spec.
3. Inno Setup installer compilation with dynamic parameterized defines.
4. Strict naming rule: 1998-TEAM-Setup-v{VERSION}-Build{BUILD}.exe.
5. Verification of output binary, file size (bytes and MB), and SHA-256 calculation.
6. Safe non-destructive packaging (never overwrites or deletes prior versions in dist_installer/).
"""

import os
import sys
import shutil
import hashlib
import subprocess
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from vietphotobooth.version import (
    __version__, __build__, __release_date__, __app_name__, __publisher__
)
try:
    from vietphotobooth.version import __channel__
except ImportError:
    __channel__ = ""


def compute_sha256(file_path: Path) -> str:
    """Tính mã băm SHA-256 của file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_iscc() -> str:
    """Tìm trình biên dịch Inno Setup ISCC.exe."""
    # 1. Check in PATH
    iscc = shutil.which("iscc") or shutil.which("ISCC.exe")
    if iscc:
        return iscc

    # 2. Check standard Windows installation paths
    candidate_paths = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\ProgramData\chocolatey\bin\ISCC.exe"),
    ]
    for p in candidate_paths:
        if p.exists():
            return str(p)

    raise FileNotFoundError("Không tìm thấy trình biên dịch Inno Setup (ISCC.exe) trên hệ thống.")


def main():
    print("=" * 72)
    print(f"  {__app_name__} — AUTOMATED RELEASE BUILD PIPELINE")
    print("=" * 72)
    print(f"• Phiên bản:      v{__version__}")
    print(f"• Build Number:   {__build__}")
    if __channel__:
        print(f"• Release Channel:{__channel__}")
    print(f"• Ngày phát hành: {__release_date__}")
    print(f"• Nhà phát triển: {__publisher__}")
    print(f"• Thư mục gốc:    {PROJECT_ROOT}")
    print("-" * 72)

    # 1. Xác định quy tắc đặt tên file bộ cài
    channel_suffix = f"-{__channel__}" if __channel__ else ""
    output_base_filename = f"1998-TEAM-Setup-v{__version__}-Build{__build__}{channel_suffix}"
    expected_exe_name = f"{output_base_filename}.exe"
    dist_installer_dir = PROJECT_ROOT / "dist_installer"
    dist_installer_dir.mkdir(parents=True, exist_ok=True)
    target_installer_path = dist_installer_dir / expected_exe_name

    print(f"[1/4] Quy tắc đặt tên bộ cài đặt:")
    print(f"      Base Filename: {output_base_filename}")
    print(f"      Target Output: {target_installer_path}")
    print(f"      (Bảo toàn tất cả các bản cài đặt cũ trong dist_installer/)")

    # 2. Chạy PyInstaller
    print("\n[2/4] Chạy PyInstaller đóng gói ứng dụng...")
    spec_file = PROJECT_ROOT / "vietphotobooth.spec"
    if not spec_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file spec: {spec_file}")

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        str(spec_file),
        "--clean",
        "-y"
    ]
    print(f"      Lệnh: {' '.join(pyinstaller_cmd)}")
    result = subprocess.run(pyinstaller_cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"[LỖI] PyInstaller thất bại với mã lỗi {result.returncode}")
        sys.exit(result.returncode)

    built_exe = PROJECT_ROOT / "dist" / "1998TeamPhotobooth" / "1998TeamPhotobooth.exe"
    if not built_exe.exists():
        raise FileNotFoundError(f"Không tìm thấy file thực thi sau build: {built_exe}")
    print(f"      [OK] PyInstaller hoàn tất thành công: {built_exe}")

    # 3. Chạy Inno Setup Compiler
    print("\n[3/4] Biên dịch bộ cài đặt Windows bằng Inno Setup...")
    iscc_path = find_iscc()
    iss_file = PROJECT_ROOT / "VietPhotoBooth.iss"
    if not iss_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file kịch bản Inno Setup: {iss_file}")

    iscc_cmd = [
        iscc_path,
        f"/DMyAppVersion={__version__}",
        f"/DMyAppBuild={__build__}",
        f"/DMyOutputFilename={output_base_filename}",
        str(iss_file)
    ]
    print(f"      ISCC: {iscc_path}")
    print(f"      Lệnh: {' '.join(iscc_cmd)}")
    result = subprocess.run(iscc_cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"[LỖI] Inno Setup thất bại với mã lỗi {result.returncode}")
        sys.exit(result.returncode)

    # 4. Xác minh bộ cài đặt tạo ra
    print("\n[4/4] Xác minh tính toàn vẹn và tính mã băm bộ cài đặt...")
    if not target_installer_path.exists():
        raise FileNotFoundError(f"File cài đặt mục tiêu không tồn tại sau biên dịch: {target_installer_path}")

    file_size_bytes = target_installer_path.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)
    sha256_hash = compute_sha256(target_installer_path)

    # Tạo tệp companion .sha256 để kiểm tra tính toàn vẹn độc lập
    sha256_file = dist_installer_dir / f"{expected_exe_name}.sha256"
    sha256_file.write_text(f"{sha256_hash} *{expected_exe_name}\n", encoding="utf-8")

    # Tạo thêm bản sao với tên thân thiện: 1998-TEAM-Photobooth-Setup-v{__version__}[-channel].exe
    alt_exe_name = f"1998-TEAM-Photobooth-Setup-v{__version__}{channel_suffix}.exe"
    alt_installer_path = dist_installer_dir / alt_exe_name
    shutil.copy2(target_installer_path, alt_installer_path)
    alt_sha256_file = dist_installer_dir / f"{alt_exe_name}.sha256"
    alt_sha256_file.write_text(f"{sha256_hash} *{alt_exe_name}\n", encoding="utf-8")

    print("=" * 72)
    print("  XUẤT BẢN THÀNH CÔNG BỘ CÀI ĐẶT 1998 TEAM — PHOTOBOOTH")
    print("=" * 72)
    print(f"• Tên file:     {expected_exe_name}")
    print(f"• Bản phụ:      {alt_exe_name}")
    print(f"• Đường dẫn:    {target_installer_path}")
    print(f"• Kích thước:   {file_size_bytes:,} bytes (~{file_size_mb:.2f} MB)")
    print(f"• SHA-256 Hash: {sha256_hash}")
    print(f"• Hash File:    {sha256_file}")
    print("=" * 72)


if __name__ == "__main__":
    main()
