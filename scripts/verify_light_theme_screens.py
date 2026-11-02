"""
1998 TEAM PHOTOBOOTH v2.0.0 — GLOBAL LIGHT THEME VISUAL VERIFICATION SCRIPT
Captures visual screenshots across all screens and key resolutions:
- Dashboard: 1366x768, 1600x900, 1920x1080
- Capture Studio (KioskPage): 1366x768, 1600x900, 1920x1080
- Guest Idle Screen: 1366x768, 1600x900, 1920x1080
- Events & Gallery: 1920x1080
- Printing Settings: 1920x1080
- Frame Gallery: 1920x1080
- Devices Page: 1920x1080
- QR Sharing Page: 1920x1080
"""

import sys
import os
import time

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap

sys.path.insert(0, os.path.abspath("."))

from vietphotobooth.desktop.main_window import MainWindow

def main():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    out_dir = r"C:\Users\Admin\.gemini\antigravity\brain\676858c6-2a30-4e77-a479-d21f91264a09"
    os.makedirs(out_dir, exist_ok=True)

    resolutions = [
        ("1366x768", 1366, 768),
        ("1600x900", 1600, 900),
        ("1920x1080", 1920, 1080),
    ]

    print("=== CAPTURING LIGHT THEME SCREENSHOTS ===")

    for label, w, h in resolutions:
        print(f"\n--- Testing Resolution: {label} ---")
        win = MainWindow(start_in_kiosk=False)
        win.resize(w, h)
        win.show()
        app.processEvents()

        # 1. Dashboard
        win.show_dashboard()
        app.processEvents()
        time.sleep(0.15)
        pix = win.grab()
        p = os.path.join(out_dir, f"dashboard_light_{label}.png")
        pix.save(p, "PNG")
        print(f"Captured: {p}")

        # 2. Capture Studio (KioskPage)
        win.switch_to_tab(0)
        app.processEvents()
        time.sleep(0.15)
        pix = win.grab()
        p = os.path.join(out_dir, f"capture_studio_light_{label}.png")
        pix.save(p, "PNG")
        print(f"Captured: {p}")

        # 3. Guest Idle Screen
        win.show_idle_screen()
        app.processEvents()
        time.sleep(0.15)
        pix = win.grab()
        p = os.path.join(out_dir, f"guest_idle_light_{label}.png")
        pix.save(p, "PNG")
        print(f"Captured: {p}")

        win.cleanup()
        win.close()
        app.processEvents()

    # Capture remaining screens at 1920x1080
    print("\n--- Testing Dedicated Screens at 1920x1080 ---")
    win = MainWindow(start_in_kiosk=False)
    win.resize(1920, 1080)
    win.show()
    app.processEvents()

    # Authenticate admin so tabs can switch without blocking dialogs
    win.auth_mgr.authenticate("1234")

    # Events & Gallery (Tab index 4)
    win.switch_to_tab(4)
    app.processEvents()
    time.sleep(0.15)
    p = os.path.join(out_dir, "events_gallery_light_1920x1080.png")
    win.grab().save(p, "PNG")
    print(f"Captured: {p}")

    # Printing Page (Tab index 3)
    win.switch_to_tab(3)
    app.processEvents()
    time.sleep(0.15)
    p = os.path.join(out_dir, "printing_page_light_1920x1080.png")
    win.grab().save(p, "PNG")
    print(f"Captured: {p}")

    # Frame Gallery (Tab index 1)
    win.switch_to_tab(1)
    app.processEvents()
    time.sleep(0.15)
    p = os.path.join(out_dir, "frame_gallery_light_1920x1080.png")
    win.grab().save(p, "PNG")
    print(f"Captured: {p}")

    # Devices Page
    win.show_devices()
    app.processEvents()
    time.sleep(0.15)
    p = os.path.join(out_dir, "devices_page_light_1920x1080.png")
    win.grab().save(p, "PNG")
    print(f"Captured: {p}")

    # QR Sharing Page
    win.show_qr_sharing()
    app.processEvents()
    time.sleep(0.15)
    p = os.path.join(out_dir, "qr_sharing_light_1920x1080.png")
    win.grab().save(p, "PNG")
    print(f"Captured: {p}")

    win.cleanup()
    win.close()
    app.processEvents()
    print("\n=== ALL SCREENSHOTS SUCCESSFULLY CAPTURED ===")

if __name__ == "__main__":
    main()
