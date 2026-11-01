"""
1998 TEAM — Photobooth v1.5.4 Benchmark: Live View FPS with Face Detection ON vs OFF
Measures Live View rendering throughput (1024x680), frame latency, and AI detection overhead.
"""

import time
import json
import numpy as np
import cv2

from vietphotobooth.camera.face_detector import FaceEyeDetector, FaceDetectionService


def run_benchmark():
    print("=" * 70)
    print("1998 TEAM PHOTOBOOTH — BENCHMARK LIVE VIEW & AI FACE DETECTION (v1.5.4)")
    print("=" * 70)

    # Chuẩn bị khung hình mô phỏng 1024x680 (3:2)
    width, height = 1024, 680
    test_frame = np.full((height, width, 3), 40, dtype=np.uint8)
    # Vẽ mặt mô phỏng
    cv2.circle(test_frame, (512, 340), 120, (200, 200, 200), -1)
    cv2.circle(test_frame, (470, 310), 15, (50, 50, 50), -1)
    cv2.circle(test_frame, (554, 310), 15, (50, 50, 50), -1)
    cv2.ellipse(test_frame, (512, 380), (40, 20), 0, 0, 180, (50, 50, 50), 4)

    test_duration = 3.0  # Chạy 3 giây mỗi chế độ

    # -------------------------------------------------------------------------
    # TEST 1: LIVE VIEW KHÔNG BẬT FACE DETECTION (BASELINE)
    # -------------------------------------------------------------------------
    print("\n[1/2] Đang đo Live View baseline (Face Detection: TẮT)...")
    frame_count_off = 0
    t_start = time.perf_counter()
    while time.perf_counter() - t_start < test_duration:
        # Mô phỏng nhận frame và chuẩn bị render
        _ = cv2.cvtColor(test_frame, cv2.COLOR_BGR2RGB)
        frame_count_off += 1
        time.sleep(0.026)  # Giả lập tốc độ nhận từ Nikon D780 (~38.4 FPS max)

    duration_off = time.perf_counter() - t_start
    fps_off = frame_count_off / duration_off
    print(f"  -> Kết quả OFF: {frame_count_off} frames trong {duration_off:.2f}s = {fps_off:.2f} FPS")

    # -------------------------------------------------------------------------
    # TEST 2: LIVE VIEW BẬT FACE DETECTION (YUNET BACKGROUND SERVICE)
    # -------------------------------------------------------------------------
    print("\n[2/2] Đang đo Live View (Face Detection: BẬT - 12 FPS Throttled)...")
    service = FaceDetectionService(target_detection_fps=12.0)
    ai_inferences = [0]
    ai_latencies = []

    def on_faces(faces):
        ai_inferences[0] += 1

    service.register_callback(on_faces)
    service.start()

    frame_count_on = 0
    t_start_on = time.perf_counter()
    while time.perf_counter() - t_start_on < test_duration:
        rgb = cv2.cvtColor(test_frame, cv2.COLOR_BGR2RGB)
        service.submit_frame(rgb)
        frame_count_on += 1
        time.sleep(0.026)  # Giả lập tốc độ nhận từ Nikon D780

    duration_on = time.perf_counter() - t_start_on
    fps_on = frame_count_on / duration_on
    service.stop()

    ai_fps = ai_inferences[0] / duration_on
    fps_drop_percent = ((fps_off - fps_on) / fps_off) * 100.0

    print(f"  -> Kết quả ON : {frame_count_on} frames trong {duration_on:.2f}s = {fps_on:.2f} FPS")
    print(f"  -> AI Detection Inferences: {ai_inferences[0]} lần = {ai_fps:.2f} FPS")
    print(f"  -> Độ suy giảm Live View FPS: {fps_drop_percent:.2f}% (Mục tiêu: < 5%)")

    # Đo độ trễ inference đơn lẻ của YuNet
    detector = FaceEyeDetector()
    latencies = []
    for _ in range(10):
        t0 = time.perf_counter()
        _ = detector.detect_faces(test_frame)
        latencies.append((time.perf_counter() - t0) * 1000.0)
    avg_latency = float(np.mean(latencies[2:]))  # Bỏ 2 lần warmup đầu
    print(f"  -> Độ trễ trung bình YuNet: {avg_latency:.2f} ms")

    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "resolution": f"{width}x{height}",
        "face_detection_off": {
            "fps": round(fps_off, 2),
            "frame_count": frame_count_off,
            "duration_sec": round(duration_off, 2)
        },
        "face_detection_on": {
            "fps": round(fps_on, 2),
            "frame_count": frame_count_on,
            "duration_sec": round(duration_on, 2),
            "ai_inferences": ai_inferences[0],
            "ai_fps": round(ai_fps, 2),
            "avg_inference_latency_ms": round(avg_latency, 2)
        },
        "fps_drop_percent": round(fps_drop_percent, 2),
        "status": "PASSED" if fps_on >= 35.0 and fps_drop_percent < 5.0 else "WARNING"
    }

    with open("phase3_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"BENCHMARK STATUS: {results['status']}")
    print("=" * 70)
    return results


if __name__ == "__main__":
    run_benchmark()
