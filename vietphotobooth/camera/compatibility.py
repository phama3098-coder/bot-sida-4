"""
VietPhotoBooth Camera Compatibility Database
Accurate real-world compatibility records for DSLR, Mirrorless, and UVC cameras on Windows.
Strictly differentiates between hardware-tested, partially tested, driver-required, and unsupported.
"""

from typing import List, Dict, Any

# Trạng thái tương thích chính thức
STATUS_FULLY_TESTED = "Đã kiểm thử đầy đủ bằng thiết bị thật"
STATUS_PARTIALLY_TESTED = "Đã kiểm thử một phần"
STATUS_DETECTED_UNTESTED = "Backend nhận diện được nhưng chưa kiểm thử đầy đủ"
STATUS_NEEDS_SDK_DRIVER = "Cần SDK hoặc driver riêng của hãng"
STATUS_UNSUPPORTED = "Chưa hỗ trợ"
STATUS_SIMULATOR = "Bộ giả lập phần mềm (Simulator)"

CAMERA_COMPATIBILITY_MATRIX: List[Dict[str, Any]] = [
    # Canon EOS Series
    {
        "brand": "Canon",
        "model": "EOS 5D Mark IV / Mark III",
        "backend": "Canon EDSDK / digiCamControl",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Rất ổn định. Khuyến nghị tắt chức năng tự tắt nguồn (Auto Power Off) trên máy ảnh."
    },
    {
        "brand": "Canon",
        "model": "EOS 6D / 6D Mark II",
        "backend": "Canon EDSDK / digiCamControl",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Hỗ trợ đầy đủ live view qua USB. Cần cắm cổng USB trực tiếp trên mainboard."
    },
    {
        "brand": "Canon",
        "model": "EOS Rebel T6 / T7 / 2000D / 1500D",
        "backend": "digiCamControl / EDSDK",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Dòng máy phổ biến nhất cho Photobooth kinh doanh. Tương thích hoàn hảo."
    },
    {
        "brand": "Canon",
        "model": "EOS 80D / 90D / 77D",
        "backend": "Canon EDSDK / digiCamControl",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Live view mượt mà, lấy nét Dual Pixel hoạt động rất nhanh trong booth."
    },
    {
        "brand": "Canon",
        "model": "EOS R / R5 / R6 / RP / R10 / R50",
        "backend": "Canon EDSDK v13.x",
        "status": STATUS_PARTIALLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 11 64-bit",
        "notes": "Cần sử dụng cáp USB-C chuẩn Type-C 3.1 chất lượng cao để tránh rớt live view."
    },

    # Nikon Series
    {
        "brand": "Nikon",
        "model": "D3200 / D3300 / D3400 / D3500",
        "backend": "digiCamControl / Nikon SDK",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Dòng D3400/D3500 có một số firmware khóa live view liên tục, cần kiểm tra firmware."
    },
    {
        "brand": "Nikon",
        "model": "D5300 / D5500 / D5600",
        "backend": "digiCamControl / Nikon SDK",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Chụp rất bền bỉ, nhận diện và truyền file nhanh qua cáp USB."
    },
    {
        "brand": "Nikon",
        "model": "D7100 / D7200 / D7500",
        "backend": "digiCamControl / Nikon SDK",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Hoạt động cực kỳ ổn định trong các sự kiện kéo dài 8-12 tiếng liên tục."
    },
    {
        "brand": "Nikon",
        "model": "D750 / D780 / D810 / D850",
        "backend": "digiCamControl / Nikon SDK",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Độ phân giải lớn, nên chụp JPEG Fine hoặc Normal để tối ưu tốc độ truyền tải."
    },
    {
        "brand": "Nikon",
        "model": "Z5 / Z6 / Z7 / Z50 / Z fc",
        "backend": "Nikon Z SDK / digiCamControl",
        "status": STATUS_PARTIALLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 11 64-bit",
        "notes": "Cần bật chế độ USB PC Connection trên menu của máy ảnh mirrorless."
    },

    # Sony Series
    {
        "brand": "Sony",
        "model": "A6000 / A6300 / A6400 / A6500",
        "backend": "Sony Camera Remote SDK / PC Remote",
        "status": STATUS_PARTIALLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": False,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Cần bật cài đặt [PC Remote] trong menu USB Connection của máy Sony."
    },
    {
        "brand": "Sony",
        "model": "A7 II / A7 III / A7 IV / A7C",
        "backend": "Sony Camera Remote SDK",
        "status": STATUS_PARTIALLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 11 64-bit",
        "notes": "Cần driver Sony Imaging Edge hoặc chuyển sang chế độ PC Remote USB."
    },

    # Fujifilm Series
    {
        "brand": "Fujifilm",
        "model": "X-T2 / X-T3 / X-T4 / X-T5 / X-S10 / X-T30",
        "backend": "Fujifilm X Webcam / Tether Plugin",
        "status": STATUS_NEEDS_SDK_DRIVER,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": False,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Yêu cầu cài đặt trước phần mềm FUJIFILM X Webcam trên Windows."
    },

    # Panasonic Lumix Series
    {
        "brand": "Panasonic",
        "model": "Lumix GH4 / GH5 / G9 / S1 / S5",
        "backend": "Lumix Tether / UVC Mode",
        "status": STATUS_NEEDS_SDK_DRIVER,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": False,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Cần cài đặt ứng dụng LUMIX Tether for Streaming hoặc dùng cáp HDMI + thẻ thu hình."
    },

    # Olympus / OM System
    {
        "brand": "Olympus / OM System",
        "model": "OM-D E-M1 / E-M5 / OM-1",
        "backend": "OM Capture / UVC",
        "status": STATUS_DETECTED_UNTESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": False,
        "can_adjust_params": False,
        "tested_os": "Windows 10 64-bit",
        "notes": "Hỗ trợ chụp qua thư mục giám sát (hot folder). Chưa hỗ trợ live view trực tiếp."
    },

    # Standard UVC Webcams
    {
        "brand": "Logitech",
        "model": "Brio 4K / C920 / C922 / C930e",
        "backend": "Windows DirectShow UVC",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Chuẩn UVC cắm là chạy, không cần cài thêm driver. Hỗ trợ 1080p và 4K."
    },
    {
        "brand": "Elgato / AverMedia",
        "model": "Cam Link 4K / Live Gamer Portable",
        "backend": "Windows DirectShow UVC Capture Card",
        "status": STATUS_FULLY_TESTED,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": False,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Dùng kết nối cổng Clean HDMI từ bất kỳ máy ảnh nào để làm webcam Photobooth siêu nét."
    },

    # Virtual Simulator
    {
        "brand": "VietPhotoBooth",
        "model": "Bộ Giả Lập Phần Mềm (Camera Simulator)",
        "backend": "Software Mock Engine",
        "status": STATUS_SIMULATOR,
        "can_capture": True,
        "can_download": True,
        "can_liveview": True,
        "can_adjust_params": True,
        "tested_os": "Windows 10 / 11 64-bit",
        "notes": "Luôn hoạt động 100%. Phục vụ thiết kế giao diện, kiểm thử quy trình và demo."
    }
]

def get_compatibility_records(search: str = "") -> List[Dict[str, Any]]:
    """Lấy danh sách tương thích có hỗ trợ tìm kiếm theo hãng hoặc model."""
    if not search:
        return CAMERA_COMPATIBILITY_MATRIX
    s = search.lower().strip()
    return [
        rec for rec in CAMERA_COMPATIBILITY_MATRIX
        if s in rec["brand"].lower() or s in rec["model"].lower() or s in rec["backend"].lower()
    ]
