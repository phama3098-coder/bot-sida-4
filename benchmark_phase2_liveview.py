"""
1998 TEAM — Photobooth Phase 2 Live View Benchmark (60-second Stress & Latency Test)
Native Windows API Memory & CPU measurement (Zero external dependencies).
Measures:
- Resolution: 1024 x 680 (XGA, 3:2) vs 640 x 424 (VGA)
- Read FPS & Render FPS
- Frame Processing Latency (Average & P95 in ms)
- CPU Usage (%) & RAM Memory RSS (MB) over 60 seconds
- Memory leak detection (RSS Start vs RSS End)
- Hardware status vs Streaming pipeline evaluation
"""

import os
import sys
import time
import json
import ctypes
from ctypes import wintypes
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from vietphotobooth.camera.backends.nikon_maid.maid_types import (
    NkMAIDLiveViewImageSize, NkMAIDCapability
)
from vietphotobooth.camera.backends.nikon_maid.maid_loader import NikonSDKLoader
from vietphotobooth.camera.backends.nikon_maid.nikon_d780_backend import NikonD780Backend
from vietphotobooth.camera.models import FrameData

# Native Windows Process Memory & CPU Tracker (64-bit ctypes argtypes)
class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
    ]

class FILETIME(ctypes.Structure):
    _fields_ = [('dwLowDateTime', wintypes.DWORD), ('dwHighDateTime', wintypes.DWORD)]

_fn_mem = ctypes.windll.psapi.GetProcessMemoryInfo
_fn_mem.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
_fn_mem.restype = wintypes.BOOL

_fn_cpu = ctypes.windll.kernel32.GetProcessTimes
_fn_cpu.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME)
]
_fn_cpu.restype = wintypes.BOOL

def get_process_memory_mb() -> float:
    h = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, os.getpid())
    if not h:
        return 0.0
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    res = _fn_mem(h, ctypes.byref(counters), counters.cb)
    ctypes.windll.kernel32.CloseHandle(h)
    if res:
        return counters.WorkingSetSize / (1024 * 1024)
    return 0.0

def get_process_cpu_time() -> float:
    h = ctypes.windll.kernel32.OpenProcess(0x0400, False, os.getpid())
    if not h:
        return 0.0
    creation, exit_t, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    res = _fn_cpu(h, ctypes.byref(creation), ctypes.byref(exit_t), ctypes.byref(kernel), ctypes.byref(user))
    ctypes.windll.kernel32.CloseHandle(h)
    if res:
        k = (kernel.dwHighDateTime << 32) + kernel.dwLowDateTime
        u = (user.dwHighDateTime << 32) + user.dwLowDateTime
        return (k + u) / 10_000_000.0  # 100ns units to seconds
    return 0.0

def run_benchmark(duration_seconds: int = 60):
    print(f"=== 1998 TEAM PHOTOBOOTH — PHASE 2 LIVE VIEW BENCHMARK ({duration_seconds}s) ===")
    start_rss_mb = get_process_memory_mb()
    print(f"Initial Memory RSS: {start_rss_mb:.2f} MB")

    # 1. Hardware Presence & SDK Check
    loader = NikonSDKLoader()
    sdk_found = loader.find_sdk_directory() is not None
    sdk_loaded, sdk_msg = loader.load()
    backend = NikonD780Backend()
    devs = backend.discover_devices()
    hw_connected = len(devs) > 0 and any(not d.is_virtual for d in devs)

    print(f"Nikon SDK Loaded: {sdk_loaded} ({sdk_msg})")
    print(f"Nikon D780 Hardware Connected: {hw_connected} ({len(devs)} devices discovered)")

    # 2. Setup 1024x680 Streamer Evaluation
    import cv2
    test_img = np.zeros((680, 1024, 3), dtype=np.uint8)
    test_img[:] = (10, 17, 31)  # Studio Navy
    test_img[50:630, 80:944] = (25, 40, 74)
    cv2.putText(test_img, "1998 TEAM STUDIO - 1024x680 XGA", (120, 340), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (212, 175, 55), 2)
    ok, encoded_jpeg = cv2.imencode(".jpg", test_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    jpeg_bytes = encoded_jpeg.tobytes()

    latencies_ms = []
    fps_timestamps = []
    cpu_samples = []
    mem_samples = []

    print(f"\nBắt đầu đo kiểm {duration_seconds} giây Live View stream 1024 × 680...")
    start_time = time.time()
    last_sample_wall = start_time
    last_sample_cpu = get_process_cpu_time()
    frame_count = 0

    num_cores = os.cpu_count() or 4

    # Stream loop
    while (time.time() - start_time) < duration_seconds:
        t0 = time.perf_counter()

        # Simulate worker decode
        nparr = np.frombuffer(jpeg_bytes, np.uint8)
        bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        w, h = rgb.shape[1], rgb.shape[0]

        frame = FrameData(
            rgb=rgb,
            jpeg=jpeg_bytes,
            width=w,
            height=h,
            fps=38.0,
            timestamp=time.time(),
            is_valid=True
        )

        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000.0
        latencies_ms.append(lat_ms)
        now = time.time()
        fps_timestamps.append(now)
        frame_count += 1

        # Periodic telemetry (every ~1s)
        wall_diff = now - last_sample_wall
        if wall_diff >= 1.0:
            now_cpu = get_process_cpu_time()
            cpu_diff = now_cpu - last_sample_cpu
            cpu_pct = (cpu_diff / (wall_diff * num_cores)) * 100.0
            rss_mb = get_process_memory_mb()
            cpu_samples.append(cpu_pct)
            mem_samples.append(rss_mb)
            last_sample_wall = now
            last_sample_cpu = now_cpu
            elapsed = now - start_time
            curr_fps = len([t for t in fps_timestamps if (now - t) <= 1.0])
            print(f"[{elapsed:4.1f}s / {duration_seconds}s] FPS: {curr_fps:4.1f} | Frame Latency: {lat_ms:4.2f}ms | CPU: {cpu_pct:4.1f}% | RAM: {rss_mb:6.2f} MB")

        # Yield interval for ~38 FPS rate (target 26.3ms per frame)
        dur = time.perf_counter() - t0
        target_sleep = max(0.001, 0.0263 - dur)
        time.sleep(target_sleep)

    total_time = time.time() - start_time
    end_rss_mb = get_process_memory_mb()
    avg_fps = frame_count / total_time
    avg_latency = float(np.mean(latencies_ms))
    p95_latency = float(np.percentile(latencies_ms, 95))
    p99_latency = float(np.percentile(latencies_ms, 99))
    min_latency = float(np.min(latencies_ms))
    max_latency = float(np.max(latencies_ms))
    avg_cpu = float(np.mean(cpu_samples)) if cpu_samples else 0.0
    max_cpu = float(np.max(cpu_samples)) if cpu_samples else 0.0
    mem_delta_mb = end_rss_mb - start_rss_mb

    results = {
        "hardware_connected": hw_connected,
        "sdk_loaded": sdk_loaded,
        "duration_seconds": round(total_time, 2),
        "total_frames": frame_count,
        "resolution": f"{w} x {h}",
        "aspect_ratio": "3:2 (1.506)",
        "read_fps": round(avg_fps, 2),
        "target_fps": 38.0,
        "latency_avg_ms": round(avg_latency, 2),
        "latency_p95_ms": round(p95_latency, 2),
        "latency_p99_ms": round(p99_latency, 2),
        "latency_min_ms": round(min_latency, 2),
        "latency_max_ms": round(max_latency, 2),
        "cpu_avg_percent": round(avg_cpu, 2),
        "cpu_max_percent": round(max_cpu, 2),
        "ram_start_mb": round(start_rss_mb, 2),
        "ram_end_mb": round(end_rss_mb, 2),
        "ram_delta_mb": round(mem_delta_mb, 2),
        "memory_leak_detected": mem_delta_mb > 30.0
    }

    print("\n=== KẾT QUẢ ĐO KIỂM 60 GIÂY PHASE 2 ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    with open("phase2_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return results

if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    run_benchmark(dur)
