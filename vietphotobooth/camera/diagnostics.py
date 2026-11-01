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
    """Kiểm tra trạng thái hệ thống điều khiển máy ảnh digiCamControl theo quy chuẩn các trạng thái độc lập."""
    from vietphotobooth.camera.backends.digicam_control import (
        is_digicam_process_running, is_port_listening, is_valid_camera_name
    )
    import urllib.request

    cli_path = r"C:\Program Files (x86)\digiCamControl\CameraControlCmd.exe"
    rest_url = "http://127.0.0.1:5513"

    installed = os.path.exists(cli_path)
    proc_running = is_digicam_process_running("CameraControl.exe")
    port_open = is_port_listening("127.0.0.1", 5513, timeout=0.3)

    res = {
        "backend": "digiCamControl (DIGICAM)",
        "cli_installed": installed,
        "cli_path": cli_path,
        "process_running": proc_running,
        "rest_api_url": rest_url,
        "rest_port_open": port_open,
        "rest_api_online": False,
        "detected_camera_name": "Không phát hiện",
        "camera_detected": False,
        "liveview_stream_active": False,
        "error_code": "",
        "status_summary": ""
    }

    if not installed:
        res["error_code"] = "DIGICAM_NOT_INSTALLED"
        res["status_summary"] = "Chưa cài đặt digiCamControl trên máy tính."
        return res

    if not proc_running:
        res["error_code"] = "DIGICAM_NOT_RUNNING"
        res["status_summary"] = "digiCamControl (CameraControl.exe) chưa được khởi động trên Windows."
        return res

    if not port_open:
        res["error_code"] = "HTTP_SERVER_DISABLED"
        res["status_summary"] = "Web Server digiCamControl (cổng 5513) chưa bật trong Settings."
        return res

    # Kiểm tra REST API endpoint camera.name
    try:
        req = urllib.request.urlopen(f"{rest_url}/?sl=get&param=camera.name", timeout=1.2)
        if req.status == 200:
            res["rest_api_online"] = True
            raw_name = req.read().decode("utf-8", errors="ignore").strip()
            if is_valid_camera_name(raw_name):
                res["detected_camera_name"] = raw_name
                res["camera_detected"] = True

        # Kiểm tra Live View stream
        if res["camera_detected"]:
            lv_req = urllib.request.urlopen(f"{rest_url}/liveview.jpg", timeout=1.0)
            if lv_req.status == 200:
                data = lv_req.read()
                if len(data) > 1000 and data.startswith(b"\xff\xd8"):
                    res["liveview_stream_active"] = True
    except Exception as e:
        logger.debug(f"Diagnostics digicam HTTP check error: {e}")

    # Đưa ra kết luận tóm tắt chính xác
    if not res["camera_detected"]:
        res["error_code"] = "CAMERA_NOT_DETECTED"
        res["status_summary"] = "digiCamControl đang chạy nhưng không phát hiện máy ảnh USB nào cắm vào máy tính."
    elif res["liveview_stream_active"]:
        res["status_summary"] = f"Hoạt động đầy đủ (Máy ảnh: {res['detected_camera_name']}, Live View: BẬT)"
    else:
        res["error_code"] = "LIVEVIEW_UNAVAILABLE"
        res["status_summary"] = f"Đã kết nối {res['detected_camera_name']} sẵn sàng chụp tĩnh (Tethered 6000×4000). Luồng Live View HTTP chưa bật."

    return res


def check_nikon_maid_status() -> Dict[str, Any]:
    """Kiểm tra trạng thái hỗ trợ và kết nối của Nikon MAID Native USB SDK."""
    try:
        from vietphotobooth.camera.backends.nikon_maid.maid_loader import get_loader
        loader = get_loader()
        sdk_dir = loader.find_sdk_directory()
        installed = sdk_dir is not None

        res = {
            "backend": "Nikon MAID Native USB",
            "sdk_installed": installed,
            "sdk_path": sdk_dir or "Chưa tìm thấy thư mục bin/x64",
            "camera_detected": False,
            "detected_camera_name": "Không phát hiện",
            "status_summary": ""
        }

        if not installed:
            res["status_summary"] = "Chưa tìm thấy bộ runtime Nikon MAID SDK (Type0026.md3)."
            return res

        # Nhanh chóng kiểm tra PnP USB để xem Nikon D780 có đang cắm không mà không làm gián đoạn session
        # VID 04B0 (Nikon), PID 0446 (D780)
        import subprocess
        pnp_found = False
        try:
            out = subprocess.check_output("pnputil /enum-devices /class WPD", text=True, timeout=1.5, stderr=subprocess.DEVNULL)
            if "04B0&PID_0446" in out or "D780" in out:
                pnp_found = True
        except Exception:
            pass

        if pnp_found:
            res["camera_detected"] = True
            res["detected_camera_name"] = "Nikon D780 (USB MTP/MAID)"
            res["status_summary"] = "Phát hiện Nikon D780 qua USB. SDK MAID Type0026 sẵn sàng kết nối trực tiếp."
            return res

        # Fallback thử enumerate qua session nếu chưa phát hiện qua PnP
        try:
            from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
            session = NikonSession()
            cams = session.enumerate_cameras(timeout_sec=1.2)
            if cams:
                res["camera_detected"] = True
                res["detected_camera_name"] = "Nikon D780"
                res["status_summary"] = "Nikon D780 sẵn sàng kết nối trực tiếp qua USB (Native MAID)."
            else:
                res["status_summary"] = "SDK sẵn sàng nhưng chưa phát hiện Nikon D780 cắm cáp USB."
            session.close_module()
        except Exception as e:
            res["status_summary"] = f"SDK sẵn sàng nhưng chưa phát hiện D780: {e}"

        return res
    except Exception as ex:
        return {
            "backend": "Nikon MAID Native USB",
            "sdk_installed": False,
            "sdk_path": "",
            "camera_detected": False,
            "detected_camera_name": "Không phát hiện",
            "status_summary": f"Lỗi kiểm tra Nikon MAID: {ex}"
        }


def run_full_camera_diagnostics() -> Dict[str, Any]:
    """Chạy toàn bộ quy trình chẩn đoán các nguồn video và camera trên máy tính."""
    report: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": sys.platform,
        "python_version": sys.version.split()[0],
        "opencv_version": cv2.__version__,
        "directshow_devices": [],
        "digicam_status": {},
        "nikon_maid_status": {},
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

    # 3. Kiểm tra Nikon MAID Native USB
    report["nikon_maid_status"] = check_nikon_maid_status()

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
    lines.append(f"• Thời gian kiểm tra:  {report.get('timestamp', 'N/A')}")
    lines.append(f"• Hệ điều hành:        {report.get('platform', 'N/A')}")
    lines.append(f"• Phiên bản Python:    {report.get('python_version', 'N/A')}")
    lines.append(f"• Phiên bản OpenCV:    {report.get('opencv_version', 'N/A')}")
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
    lines.append("[2] HỆ THỐNG GIAO TIẾP NATIVE USB NIKON (MAID3 TYPE0026 SDK):")
    nm = report.get("nikon_maid_status", {})
    lines.append(f"  • Trạng thái SDK:      {'ĐÃ SẴN SÀNG' if nm.get('sdk_installed') else 'CHƯA TÌM THẤY'}")
    lines.append(f"  • Thư mục SDK:         {nm.get('sdk_path')}")
    lines.append(f"  • Máy ảnh phát hiện:   {nm.get('detected_camera_name')}")
    lines.append(f"  • Tóm tắt:             {nm.get('status_summary')}")

    lines.append("\n" + "-" * 76)
    lines.append("[3] HỆ THỐNG ĐIỀU KHIỂN CHỤP ẢNH DSLR (digiCamControl):")
    dc = report.get("digicam_status", {})
    lines.append(f"  • Trạng thái cài đặt:  {'ĐÃ CÀI ĐẶT' if dc.get('cli_installed') else 'CHƯA CÀI ĐẶT'}")
    lines.append(f"  • Đường dẫn CLI:       {dc.get('cli_path')}")
    lines.append(f"  • Web Server REST:     {'ĐANG CHẠY (Port 5513)' if dc.get('rest_api_online') else 'KHÔNG PHẢN HỒI'}")
    lines.append(f"  • Máy ảnh phát hiện:   {dc.get('detected_camera_name')}")
    lines.append(f"  • Live View Server:    {'HOẠT ĐỘNG' if dc.get('liveview_stream_active') else 'TẮT / CHƯA BẬT'}")
    lines.append(f"  • Tóm tắt:             {dc.get('status_summary')}")

    lines.append("\n" + "-" * 76)
    lines.append("[4] KẾT LUẬN & HƯỚNG DẪN XỬ LÝ CHO STUDIO:")
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
