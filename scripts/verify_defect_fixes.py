"""
1998 TEAM PHOTOBOOTH v2.0.0 RC2 — DEFECT FIX VISUAL VERIFICATION SCRIPT
Captures visual screenshots for:
1. DEF-UI-01: Dashboard Disclaimer Banner at 1366x768, 1600x900, 1920x1080.
2. DEF-UI-02: Capture Studio Photo Count Selector with 44x44px touch targets and centered value.
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap

# Ensure workspace root is in python path
sys.path.insert(0, os.path.abspath("."))

from vietphotobooth.core.events import EventManager
from vietphotobooth.core.config import ConfigManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.filters.filter_engine import FilterEngine
from vietphotobooth.desktop.main_window import MainWindow
from vietphotobooth.desktop.widgets.kiosk_page import KioskPage

def main():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    out_dir = r"C:\Users\Admin\.gemini\antigravity\brain\676858c6-2a30-4e77-a479-d21f91264a09"
    os.makedirs(out_dir, exist_ok=True)

    print("=== 1. VERIFYING DEF-UI-01: DASHBOARD DISCLAIMER BANNER ===")
    resolutions = [
        ("1366x768", 1366, 768),
        ("1600x900", 1600, 900),
        ("1920x1080", 1920, 1080),
    ]

    for label, w, h in resolutions:
        win = MainWindow(start_in_kiosk=False)
        win.resize(w, h)
        win.show_dashboard()
        win.show()
        app.processEvents()
        
        # Verify disclaimer banner properties
        db = win.dashboard_page.disclaimer_banner
        lbl_text = win.dashboard_page.lbl_disclaimer_text
        print(f"[{label}] Disclaimer Banner geometry: {db.geometry()}, Text size: {lbl_text.size()}, WordWrap: {lbl_text.wordWrap()}")
        assert db.height() >= 40, f"Banner too short on {label}!"
        assert lbl_text.wordWrap() is True, f"WordWrap disabled on {label}!"

        # Capture entire window
        pix = win.grab()
        screenshot_path = os.path.join(out_dir, f"dashboard_fixed_{label}.png")
        pix.save(screenshot_path, "PNG")
        print(f"Saved: {screenshot_path}")

        # Also capture close-up of header + disclaimer
        banner_pix = db.grab()
        banner_path = os.path.join(out_dir, f"disclaimer_banner_fixed_{label}.png")
        banner_pix.save(banner_path, "PNG")
        print(f"Saved banner close-up: {banner_path}")
        win.close()

    print("\n=== 2. VERIFYING DEF-UI-02: CAPTURE STUDIO PHOTO COUNT CONTROL ===")
    win = MainWindow(start_in_kiosk=True)
    win.resize(1920, 1080)
    win.show()
    app.processEvents()
    kiosk = win.kiosk_page

    # Verify buttons hit size >= 44x44
    bm_size = kiosk.btn_shots_minus.size()
    bp_size = kiosk.btn_shots_plus.size()
    txt_size = kiosk.txt_shots_input.size()
    print(f"Minus button size: {bm_size.width()}x{bm_size.height()} (Expected >= 44x44)")
    print(f"Plus button size: {bp_size.width()}x{bp_size.height()} (Expected >= 44x44)")
    print(f"Input box size: {txt_size.width()}x{txt_size.height()}")
    assert bm_size.width() >= 44 and bm_size.height() >= 44, "Minus button smaller than 44x44!"
    assert bp_size.width() >= 44 and bp_size.height() >= 44, "Plus button smaller than 44x44!"

    # Test values 1, 3, 9, 16 and capture the card_shots close-up
    test_values = [1, 3, 9, 16]
    for val in test_values:
        kiosk.txt_shots_input.setText(str(val))
        kiosk._on_shots_input_finished()
        app.processEvents()
        
        card_pix = kiosk.card_shots.grab()
        card_path = os.path.join(out_dir, f"photo_count_selector_{val}shots.png")
        card_pix.save(card_path, "PNG")
        print(f"Saved photo count card for {val} shots: {card_path}")

    # Capture whole Capture Studio bottom control row
    row_pix = kiosk.card_shots.parentWidget().grab() if kiosk.card_shots.parentWidget() else kiosk.card_shots.grab()
    ctrl_path = os.path.join(out_dir, "capture_studio_controls_row_fixed.png")
    row_pix.save(ctrl_path, "PNG")
    print(f"Saved controls row: {ctrl_path}")

    # Capture entire Kiosk page at 1920x1080
    kiosk_pix = kiosk.grab()
    kiosk_path = os.path.join(out_dir, "capture_studio_fixed_1920x1080.png")
    kiosk_pix.save(kiosk_path, "PNG")
    print(f"Saved full Kiosk page: {kiosk_path}")

    win.close()
    print("\nALL VISUAL VERIFICATIONS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
