"""
1998 TEAM — Nikon D780 Live View & Autofocus Hardware Diagnostic Tool
Deep hardware diagnostic verifying Native USB MAID Type0026, Live View stream,
Contrast AF (0x8240) and Contrast AF Area (0x824A) directly on physical hardware.
"""

import sys
import time
import logging

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("NikonD780Diag")


def run_diagnostics():
    print("=" * 70)
    print("  1998 TEAM — NIKON D780 NATIVE USB & AUTOFOCUS DIAGNOSTIC")
    print("=" * 70)

    from vietphotobooth.camera.backends.nikon_maid.maid_loader import get_loader
    from vietphotobooth.camera.backends.nikon_maid.maid_session import NikonSession
    from vietphotobooth.camera.backends.nikon_maid.maid_types import (
        NkMAIDCapability, NkMAIDContrastAF, NkMAIDLiveViewStatus
    )

    loader = get_loader()
    ok_load, msg_load = loader.load()
    print(f"\n[1] Kiểm tra MAID Driver Module Type0026:")
    print(f"    - SDK directory: {loader.sdk_directory}")
    print(f"    - Driver loaded: {loader.is_loaded} ({msg_load})")

    if not loader.is_loaded:
        print("    [X] Thất bại: Không thể tải Type0026.md3!")
        return False

    session = NikonSession()

    print(f"\n[2] Khởi tạo phiên làm việc MAID (Open Module):")
    if not session.open_module():
        print("    [X] Thất bại: Không thể mở module MAID!")
        return False
    print("    [✓] Mở module MAID thành công.")

    print(f"\n[3] Dò tìm máy ảnh (Enumerate Cameras):")
    cameras = session.enumerate_cameras()
    print(f"    - Tìm thấy {len(cameras)} thiết bị: {cameras}")

    if not cameras:
        print("    [!] Chưa phát hiện máy ảnh Nikon D780 cắm qua cáp USB.")
        print("        Vui lòng đảm bảo:")
        print("        1. Cáp USB Type-C cắm chắc chắn từ D780 vào cổng USB 3.0 máy tính.")
        print("        2. Công tắc nguồn D780 gạt sang ON.")
        print("        3. Không có ứng dụng khác (Nikon Camera Control Pro, digiCamControl) đang chiếm cổng USB.")
        session.close_module()
        return False

    src_id = cameras[0]
    print(f"\n[4] Kết nối với máy ảnh (Source ID: {src_id}):")
    ok_open, msg_open = session.open_camera(src_id)
    if not ok_open:
        print(f"    [X] Thất bại: Không thể mở camera: {msg_open}")
        session.close_module()
        return False
    print(f"    [✓] Kết nối Nikon D780 thành công ({msg_open})!")

    # Query info
    battery = session.get_unsigned_capability(NkMAIDCapability.BATTERY_LEVEL)
    print(f"    - Mức pin máy ảnh: {battery}%" if battery is not None else "    - Không đọc được pin")

    # Focus Mode
    fm = session.get_unsigned_capability(NkMAIDCapability.FOCUS_MODE)
    fm_str = "MF (Manual Focus)" if fm == 0 else f"AF (Mode {fm})" if fm is not None else "Unknown"
    print(f"    - Chế độ lấy nét phần cứng: {fm_str}")

    # Live View Status
    lv_status = session.get_unsigned_capability(NkMAIDCapability.LIVE_VIEW_STATUS)
    print(f"    - Trạng thái Live View hiện tại: {lv_status} (0=OFF, 3=ON_REMOTE_LV)")

    print(f"\n[5] Kích hoạt Live View:")
    if not session.start_live_view():
        print("    [X] Thất bại: Không thể bật Live View trên Nikon D780!")
        session.close_camera()
        session.close_module()
        return False
    print("    [✓] Live View đã BẬT thành công.")

    # Helper function đo độ nét quang học
    import cv2
    import numpy as np

    def calc_sharpness(raw_bytes):
        if not raw_bytes:
            return 0.0
        try:
            nparr = np.frombuffer(raw_bytes, np.uint8)
            bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if bgr is None:
                return 0.0
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            return float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception:
            return 0.0

    # Fetch a few frames to confirm video pipeline
    frames_read = 0
    start_fetch = time.time()
    last_frame_bytes = None
    while time.time() - start_fetch < 2.0:
        raw_jpeg = session.fetch_live_view_frame()
        if raw_jpeg:
            frames_read += 1
            last_frame_bytes = raw_jpeg
        time.sleep(0.02)
    print(f"    - Đã đọc thành công {frames_read} khung hình Live View (~{frames_read/2.0:.1f} FPS).")

    s_before = round(calc_sharpness(last_frame_bytes), 2)
    print(f"    - Độ nét quang học trước AF (Tenengrad Laplacian): {s_before}")

    print(f"\n[6] Kiểm tra phần cứng lấy nét tự động trong Live View:")
    print("    - Giao thức: Contrast AF (kNkMAIDCapability_ContrastAF = 0x8240)")
    print("    - Định vị điểm ngắm: Contrast AF Area (kNkMAIDCapability_ContrastAFArea = 0x824A)")

    test_center = (512, 340)
    print(f"    - Thiết lập điểm ngắm AF tại tâm khung hình: {test_center}...")
    area_ok = session.set_contrast_af_area(test_center[0], test_center[1])
    print(f"      ContrastAFArea result: {'[✓] Thành công' if area_ok else '[!] Bỏ qua'}")

    print("    - Phát lệnh bắt đầu lấy nét (ContrastAF = START)...")
    t0 = time.perf_counter()
    af_success, af_msg = session.trigger_autofocus(target_point=test_center, timeout_sec=4.0)
    t_af = (time.perf_counter() - t0) * 1000.0

    # Đọc frame mới sau khi lấy nét để đo độ nét
    time.sleep(0.15)
    post_frame_bytes = session.fetch_live_view_frame()
    s_after = round(calc_sharpness(post_frame_bytes or last_frame_bytes), 2)
    s_delta = round(s_after - s_before, 2)

    # Phân loại lỗi
    if af_success:
        if s_before > 0 and s_delta < 0 and s_after < 20:
            category = "MAID_COMPLETED_NO_OPTICAL_CHANGE"
        else:
            category = "SUCCESS_IN_FOCUS"
    elif "out of focus" in af_msg.lower() or "mất nét" in af_msg.lower():
        category = "MAID_COMPLETED_OUT_OF_FOCUS"
    elif "thời gian" in af_msg.lower() or "timeout" in af_msg.lower():
        category = "MAID_NOT_COMPLETED"
    elif fm == 0:
        category = "MAID_REJECTED (Ống kính/Thân máy đang ở chế độ MF)"
    else:
        category = "MAID_REJECTED"

    print(f"\n[7] KẾT QUẢ KIỂM THỬ AUTOFOCUS TRÊN PHẦN CỨNG THẬT:")
    print(f"    - Phân loại trạng thái: {category}")
    print(f"    - Thời gian phản hồi: {t_af:.1f} ms")
    print(f"    - Độ nét quang học: Trước={s_before}, Sau={s_after} (Δ={s_delta:+0.2f})")
    print(f"    - Kết quả: {'[✓] IN FOCUS (LẤY NÉT THÀNH CÔNG)' if af_success else '[X] THẤT BẠI'}")
    print(f"    - Chi tiết phản hồi từ D780: {af_msg}")

    print(f"\n[8] Dọn dẹp & Tắt Live View an toàn:")
    session.stop_live_view()
    session.close_camera()
    session.close_module()
    print("    [✓] Đã đóng phiên làm việc an toàn.")
    print("=" * 70)
    return af_success


if __name__ == "__main__":
    run_diagnostics()
