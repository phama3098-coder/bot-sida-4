"""
VietPhotoBooth Camera Diagnostic & Verification Tool
Comprehensive diagnostic suite to test, verify, and report:
1. DirectShow video capture devices (friendly names, device paths, indices).
2. Media Foundation & OpenCV backend capabilities.
3. Device openability, frame validity, actual resolution, measured FPS, and brightness.
4. digiCamControl (DIGICAM) status: CLI and REST API.
5. Generates human-readable and structured diagnostic reports for studio troubleshooting.
"""

import sys
import os
import time
import json
import logging
from typing import Dict, Any, List, Optional
import cv2
import numpy as np

from vietphotobooth.camera.enumerator import (
    enumerate_directshow_devices, probe_video_source
)
from vietphotobooth.core.config import get_user_data_dir

logger = logging.getLogger("VietPhotoBooth.camera.diagnostics")


def check_digicam_status() -> Dict[str, Any]:
    """Kiểm tra trạng thái hệ thống điều khiển máy ảnh digiCamControl."""
    cli_path = r"C:\Program Files (x86)\digiCamControl\CameraControlCmd.exe"
    rest_url = "http://127.0.0.1:5513"

    res = {
        "backend": "digiCamControl (DIGICAM)",
        "cli_installed": os.path.exists(cli_path),
        "cli_path": cli_path,
        "rest_api_url": rest_url,
        "rest_api_online": False,
        "detected_camera_name": "Không phát hiện",
        "liveview_stream_active": False,
        "status_summary": ""
    }

    # 1. Kiểm tra REST API
    try:
        import requests
        resp = requests.get(f"{rest_url}/?sl=get&param=camera.name", timeout=1.0)
        if resp.status_code == 200 and resp.text.strip():
            res["rest_api_online"] = True
            res["detected_camera_name"] = resp.text.strip()

        # Kiểm tra Live View stream
        lv_resp = requests.get(f"{rest_url}/liveview.jpg", timeout=1.0)
        if lv_resp.status_code == 200 and len(lv_resp.content) > 1000:
            res["liveview_stream_active"] = True
    except Exception:
        pass

    # Đưa ra kết luận tóm tắt
    if res["rest_api_online"]:
        if res["liveview_stream_active"]:
            res["status_summary"] = f"Hoạt động đầy đủ (Camera: {res['detected_camera_name']}, Live View: BẬT)"
        else:
            res["status_summary"] = f"Đã kết nối máy ảnh ({res['detected_camera_name']}), nhưng Live View chưa bật trong digiCamControl."
    elif res["cli_installed"]:
        res["status_summary"] = "Đã cài đặt digiCamControl CLI (Chế độ chụp ảnh tĩnh độ phân giải cao). Web Server chưa mở."
    else:
        res["status_summary"] = "Chưa cài đặt digiCamControl trên máy tính."

    return res


def run_full_camera_diagnostics() -> Dict[str, Any]:
    """Chạy toàn bộ quy trình chẩn đoán các nguồn video và camera trên máy tính."""
    report: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": sys.platform,
        "python_version": sys.version.split()[0],
        "opencv_version": cv2.__version__,
        "directshow_devices": [],
        "digicam_status": {},
        "summary": {}
    }

    # 1. Dò tìm DirectShow qua COM API
    dshow_devices = enumerate_directshow_devices()
    tested_devices: List[Dict[str, Any]] = []

    for dev in dshow_devices:
        idx = dev["index"]
        probe_info = probe_video_source(idx, cv2.CAP_DSHOW)

        merged = dict(dev)
        merged["probe"] = probe_info
        tested_devices.append(merged)

    report["directshow_devices"] = tested_devices

    # 2. Kiểm tra digiCamControl
    report["digicam_status"] = check_digicam_status()

    # 3. Tổng hợp khuyến nghị
    has_nikon_webcam = any("nikon" in d["name"].lower() for d in tested_devices)
    has_logitech = any("logi" in d["name"].lower() or "c270" in d["name"].lower() for d in tested_devices)

    recommendations: List[str] = []
    if has_nikon_webcam:
        nikon_dev = next(d for d in tested_devices if "nikon" in d["name"].lower())
        probe = nikon_dev["probe"]
        if probe["frame_readable"]:
            recommendations.append(
                f"✅ Tìm thấy nguồn 'Nikon Webcam Utility' tại DirectShow #{nikon_dev['index']}. "
                f"Khung hình đạt {probe['actual_width']}x{probe['actual_height']}. "
                "Khuyến nghị chọn nguồn này trong Cài đặt Máy Ảnh để xem hình trực tiếp từ Nikon D780."
            )
        else:
            recommendations.append(
                f"⚠️ Tìm thấy 'Nikon Webcam Utility' tại DirectShow #{nikon_dev['index']} nhưng chưa đọc được khung hình. "
                "Nguyên nhân: Máy ảnh Nikon D780 có thể chưa gạt cần bật Live View, cáp USB lỏng, hoặc Discord/OBS đang chiếm giữ nguồn này."
            )

    if has_logitech:
        logi_dev = next(d for d in tested_devices if "logi" in d["name"].lower() or "c270" in d["name"].lower())
        recommendations.append(
            f"ℹ️ Webcam phần cứng 'Logitech C270' sẵn sàng tại DirectShow #{logi_dev['index']}. "
            "Có thể dùng làm camera phụ hoặc camera dự phòng khi không gắn máy ảnh lớn."
        )

    digicam = report["digicam_status"]
    if digicam["cli_installed"] or digicam["rest_api_online"]:
        recommendations.append(
            "📷 DIGICAM (digiCamControl) được cấu hình cho việc điều khiển chụp ảnh RAW/JPEG 24MP từ Nikon. "
            "Để hiển thị Live View trên màn hình khách, hãy dùng nguồn DirectShow 'Nikon Webcam Utility' song song."
        )

    report["summary"]["recommendations"] = recommendations
    return report


def format_diagnostic_report_text(report: Dict[str, Any]) -> str:
    """Định dạng báo cáo chẩn đoán thành chuỗi văn bản chi tiết, dễ đọc."""
    lines: List[str] = []
    lines.append("=" * 76)
    lines.append("       1998 TEAM PHOTOBOOTH — BÁO CÁO CHẨN ĐOÁN HỆ THỐNG MÁY ẢNH")
    lines.append("=" * 76)
    lines.append(f"• Thời gian kiểm tra:  {report['timestamp']}")
    lines.append(f"• Hệ điều hành:        {report['platform']}")
    lines.append(f"• Phiên bản Python:    {report['python_version']}")
    lines.append(f"• Phiên bản OpenCV:    {report['opencv_version']}")
    lines.append("-" * 76)

    lines.append("\n[1] DANH SÁCH THIẾT BỊ VIDEO WEBCAM / DIRECTSHOW:")
    devs = report.get("directshow_devices", [])
    if not devs:
        lines.append("  ⚠️ Không tìm thấy thiết bị video DirectShow nào trên hệ thống.")
    else:
        for d in devs:
            idx = d["index"]
            name = d["name"]
            probe = d.get("probe", {})
            openable = "CÓ" if probe.get("openable") else "KHÔNG"
            readable = "CÓ" if probe.get("frame_readable") else "KHÔNG"
            w = probe.get("actual_width", 0)
            h = probe.get("actual_height", 0)
            fps = probe.get("measured_fps", 0.0)
            bright = probe.get("mean_brightness", 0.0)
            status = probe.get("status", "N/A")

            lines.append(f"\n  • Thiết bị DirectShow #{idx}: \"{name}\"")
            lines.append(f"    - Loại:              {'Virtual Camera (Driver phần mềm)' if d.get('is_virtual') else 'Hardware UVC Webcam (Phần cứng USB)'}")
            lines.append(f"    - Device Path:       {d.get('path') or '(Trống / COM Filter)'}")
            lines.append(f"    - Mở được nguồn:     {openable}")
            lines.append(f"    - Đọc frame hợp lệ:  {readable}")
            lines.append(f"    - Độ phân giải thực: {w} × {h}")
            lines.append(f"    - Tốc độ FPS đo:     {fps} FPS")
            lines.append(f"    - Độ sáng trung bình:{bright} / 255")
            lines.append(f"    - Đánh giá:          {status}")

    lines.append("\n" + "-" * 76)
    lines.append("[2] HỆ THỐNG ĐIỀU KHIỂN CHỤP ẢNH DSLR (digiCamControl):")
    dc = report.get("digicam_status", {})
    lines.append(f"  • Trạng thái cài đặt:  {'ĐÃ CÀI ĐẶT' if dc.get('cli_installed') else 'CHƯA CÀI ĐẶT'}")
    lines.append(f"  • Đường dẫn CLI:       {dc.get('cli_path')}")
    lines.append(f"  • Web Server REST:     {'ĐANG CHẠY (Port 5513)' if dc.get('rest_api_online') else 'KHÔNG PHẢN HỒI'}")
    lines.append(f"  • Máy ảnh phát hiện:   {dc.get('detected_camera_name')}")
    lines.append(f"  • Live View Server:    {'HOẠT ĐỘNG' if dc.get('liveview_stream_active') else 'TẮT / CHƯA BẬT'}")
    lines.append(f"  • Tóm tắt:             {dc.get('status_summary')}")

    lines.append("\n" + "-" * 76)
    lines.append("[3] KẾT LUẬN & HƯỚNG DẪN XỬ LÝ CHO STUDIO:")
    recs = report.get("summary", {}).get("recommendations", [])
    if recs:
        for r in recs:
            lines.append(f"  • {r}")
    else:
        lines.append("  • Tất cả hệ thống ở trạng thái mặc định.")
    lines.append("=" * 76)

    return "\n".join(lines)


def export_diagnostic_report_file(target_path: Optional[str] = None) -> str:
    """Chạy chẩn đoán và xuất kết quả ra file văn bản."""
    rep = run_full_camera_diagnostics()
    text = format_diagnostic_report_text(rep)

    if not target_path:
        out_dir = os.path.join(get_user_data_dir(), "Diagnostics")
        os.makedirs(out_dir, exist_ok=True)
        fname = f"Camera_Diagnostics_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        target_path = os.path.join(out_dir, fname)

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(text)

    # Ghi thêm file json kèm theo
    json_path = target_path.replace(".txt", ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    return target_path


if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("Đang tiến hành chẩn đoán toàn bộ thiết bị máy ảnh và webcam...")
    r = run_full_camera_diagnostics()
    print(format_diagnostic_report_text(r))
