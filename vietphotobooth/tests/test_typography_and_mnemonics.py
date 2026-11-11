"""
Test Suite: Typography Standardization, Vietnamese Glyphs & Mnemonic Audit (Phân Hệ 4)
1998 TEAM Photobooth — Machine 2 (UI/UX Developer)
"""

import os
import sys
import pytest
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QGroupBox, QCheckBox, QTabBar
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QRawFont, QFontMetrics, QFontDatabase

from vietphotobooth.core.font_registry import FontRegistry
from vietphotobooth.desktop.styles import (
    FONT_FAMILY_PRIMARY, FONT_SIZE_DISPLAY, FONT_SIZE_BODY, FONT_WEIGHT_BOLD, KIOSK_STYLE
)
from vietphotobooth.desktop.main_window import MainWindow


# =========================================================================
# 1. VIETNAMESE GLYPH VALIDATION (ĐẦY ĐỦ 146 KÝ TỰ CÓ DẤU & NGUYÊN ÂM)
# =========================================================================

VIETNAMESE_ALL_CHARS = (
    # Nguyên âm thường kèm 5 dấu thanh (huyền, sắc, hỏi, ngã, nặng)
    "aáàảãạ"
    "ăắằẳẵặ"
    "âấầẩẫậ"
    "eéèẻẽẹ"
    "êếềểễệ"
    "iíìỉĩị"
    "oóòỏõọ"
    "ôốồổỗộ"
    "ơớờởỡợ"
    "uúùủũụ"
    "ưứừửữự"
    "yýỳỷỹỵ"
    "đ"
    # Nguyên âm hoa kèm 5 dấu thanh
    "AÁÀẢÃẠ"
    "ĂẮẰẲẴẶ"
    "ÂẤẦẨẪẬ"
    "EÉÈẺẼẸ"
    "ÊẾỀỂỄỆ"
    "IÍÌỈĨỊ"
    "OÓÒỎÕỌ"
    "ÔỐỒỔỖỘ"
    "ƠỚỜỞỠỢ"
    "UÚÙỦŨỤ"
    "ƯỨỪỬỮỰ"
    "YÝỲỶỸỴ"
    "Đ"
)


def test_vietnamese_glyph_coverage_in_be_vietnam_pro(qapp):
    """Xác minh 100% bộ 146 ký tự tiếng Việt có glyph index hợp lệ trong Be Vietnam Pro."""
    FontRegistry.initialize()
    font_path_regular = FontRegistry.resolve_font_path("BeVietnamPro-Regular.ttf")
    font_path_bold = FontRegistry.resolve_font_path("BeVietnamPro-Bold.ttf")

    assert font_path_regular and os.path.exists(font_path_regular), "Thiếu tệp BeVietnamPro-Regular.ttf"
    assert font_path_bold and os.path.exists(font_path_bold), "Thiếu tệp BeVietnamPro-Bold.ttf"

    raw_regular = QRawFont(font_path_regular, 12)
    raw_bold = QRawFont(font_path_bold, 12)

    assert raw_regular.isValid(), "QRawFont BeVietnamPro-Regular không hợp lệ"
    assert raw_bold.isValid(), "QRawFont BeVietnamPro-Bold không hợp lệ"

    missing_regular = []
    missing_bold = []

    for char in VIETNAMESE_ALL_CHARS:
        code = ord(char)
        # 1. Kiểm tra regular
        if not raw_regular.supportsCharacter(code):
            missing_regular.append((char, f"U+{code:04X}", "not_supported"))
        else:
            glyphs = raw_regular.glyphIndexesForString(char)
            if not glyphs or glyphs[0] == 0:
                missing_regular.append((char, f"U+{code:04X}", "glyph_index_0"))

        # 2. Kiểm tra bold
        if not raw_bold.supportsCharacter(code):
            missing_bold.append((char, f"U+{code:04X}", "not_supported"))
        else:
            glyphs = raw_bold.glyphIndexesForString(char)
            if not glyphs or glyphs[0] == 0:
                missing_bold.append((char, f"U+{code:04X}", "glyph_index_0"))

    assert len(missing_regular) == 0, f"BeVietnamPro-Regular thiếu {len(missing_regular)} ký tự: {missing_regular}"
    assert len(missing_bold) == 0, f"BeVietnamPro-Bold thiếu {len(missing_bold)} ký tự: {missing_bold}"


def test_vietnamese_sentence_rendering_metrics(qapp):
    """Kiểm tra đo đạc kích thước và tính liên tục khi render các câu tiếng Việt thực tế."""
    FontRegistry.initialize()
    font = FontRegistry.get_default_application_font(point_size=12)
    fm = QFontMetrics(font)

    test_sentences = [
        "1998 TEAM — Photobooth Chuyên Nghiệp Dành Cho Windows 10 & 11",
        "Hệ thống chụp ảnh phóng sự cưới & tiệc sự kiện cao cấp",
        "CÀI ĐẶT MÁY IN — BỘ ĐẾM GIẤY & GIÁM SÁT VẬT TƯ IN NHIỆT DYE-SUB",
        "Điều chỉnh tọa độ bù cơ khí (Offset X/Y) và tỷ lệ ảnh để vừa khít vùng in",
        "Lề an toàn chống xén mép (98%) • Tự động xoay khớp hướng giấy",
        "Thư Viện Lượt Chụp & In Lại • Quản Lý Sự Kiện & Khách Hàng",
        "Cho phép khách chọn khung và chỉnh sửa: Lời chúc & Sticker",
    ]

    for sentence in test_sentences:
        width = fm.horizontalAdvance(sentence)
        height = fm.height()
        assert width > 0, f"Độ rộng của chuỗi '{sentence[:20]}' phải > 0"
        assert height > 0, f"Chiều cao của chuỗi '{sentence[:20]}' phải > 0"
        # Đảm bảo không bị ký tự rỗng đè lên nhau
        assert width >= len(sentence) * 4, f"Độ rộng quá nhỏ bất thường ({width}px) cho chuỗi {len(sentence)} ký tự"


# =========================================================================
# 2. MNEMONIC AMPERSAND AUDIT (TRIỆT TIÊU GẠCH CHÂN VÔ Ý TRÊN WIDGETS)
# =========================================================================

def test_mnemonic_tab_text_clean(qapp):
    """Kiểm tra thanh TabBar chính sử dụng escape '&&' để không bị biến dạng thành gạch chân _Thư Viện."""
    win = MainWindow()
    if hasattr(win, "update_mgr"):
        win.update_mgr.is_auto_check_enabled = False

    # Tab 4 được escape thành "Sự Kiện && Thư Viện" để Qt render visual "Sự Kiện & Thư Viện" không có gạch chân
    tab_text = win.tabs.tabText(4)
    assert tab_text == "Sự Kiện && Thư Viện", f"Tab 4 text chưa được escape đúng: '{tab_text}'"
    assert tab_text.replace("&&", "&") == "Sự Kiện & Thư Viện"

    # Chuyển kích thước nhỏ (tab label rút gọn) và phục hồi
    win._update_responsive_navigation(800)
    assert win.tabs.tabText(4) == "Sự Kiện"

    win._update_responsive_navigation(1200)
    assert win.tabs.tabText(4) == "Sự Kiện && Thư Viện"

    win.close()


def test_mnemonic_groupbox_and_buttons(qapp):
    """Kiểm tra các QGroupBox và QPushButton được escape '&&' để triệt tiêu phím tắt gạch chân sai lệch."""
    win = MainWindow()
    if hasattr(win, "update_mgr"):
        win.update_mgr.is_auto_check_enabled = False
    if hasattr(win, "auth_mgr"):
        win.auth_mgr.is_authenticated = lambda: True

    # 1. Events Page
    events_page = win.events_page
    assert events_page.btn_create_submit.text().strip() == "Tạo Sự Kiện && Chọn"
    assert events_page.btn_create_submit.shortcut().isEmpty() is True, "Nút không được có phím tắt vô ý từ dấu &"
    events_gb_titles = [gb.title() for gb in events_page.findChildren(QGroupBox)]
    assert "Thư Viện Lượt Chụp && In Lại" in events_gb_titles

    # 2. Settings Page
    settings_page = win.settings_page
    settings_gb_titles = [gb.title() for gb in settings_page.findChildren(QGroupBox)]
    assert "1. Bảo Mật && Mã PIN Quản Trị" in settings_gb_titles
    assert "Lời chúc && Sticker" in settings_page.chk_guest_review.text()
    assert settings_page.chk_guest_review.shortcut().isEmpty() is True
    assert "6. Lưu Trữ && Đồng Bộ Đám Mây (Google Drive Cloud Sync)" in settings_gb_titles
    assert "7. Thông Tin Ứng Dụng && Cập Nhật Phiên Bản" in settings_gb_titles

    # 3. Camera Page
    cam_page = win.camera_page
    cam_gb_titles = [gb.title() for gb in cam_page.findChildren(QGroupBox)]
    assert "HƯỚNG DẪN KỸ THUẬT && TƯƠNG THÍCH THIẾT BỊ STUDIO 1998" in cam_gb_titles

    # 4. Smart Beauty Dialog Button
    from PIL import Image
    from vietphotobooth.desktop.widgets.smart_beauty_panel import SmartBeautyDialog
    dummy_img = Image.new("RGB", (100, 100), (255, 255, 255))
    beauty_dialog = SmartBeautyDialog(dummy_img)
    assert beauty_dialog.btn_confirm.text().strip() == "✓ Xác Nhận && Tiếp Tục"
    assert beauty_dialog.btn_confirm.shortcut().isEmpty() is True
    beauty_dialog.close()

    win.close()


# =========================================================================
# 3. TYPOGRAPHY SYSTEM CONSISTENCY & TOKEN DEFINITION
# =========================================================================

def test_typography_tokens_and_application_font(qapp):
    """Kiểm tra các token typography tập trung và phông mặc định của ứng dụng."""
    FontRegistry.initialize()
    default_family = FontRegistry.get_default_font_family()
    assert default_family == "Be Vietnam Pro", f"Phông mặc định phải là Be Vietnam Pro, nhận được: {default_family}"

    app_font = FontRegistry.get_default_application_font(point_size=10)
    assert app_font.family() == "Be Vietnam Pro"
    assert app_font.pointSize() == 10

    # Kiểm tra FONT_FAMILY_PRIMARY trong styles.py
    assert "Be Vietnam Pro" in FONT_FAMILY_PRIMARY
    assert "Segoe UI" in FONT_FAMILY_PRIMARY

    # Kiểm tra KIOSK_STYLE chứa đúng phông chữ
    assert "Be Vietnam Pro" in KIOSK_STYLE
    assert "font-size: 13px" in KIOSK_STYLE


# =========================================================================
# 4. PRESERVE SPECIAL ARTISTIC FONTS (WEDDING / LUXURY / SCRIPT)
# =========================================================================

def test_preserve_artistic_wedding_fonts(qapp):
    """Xác minh các phông cưới nghệ thuật không bị mất hoặc bị ghi đè."""
    from PySide6.QtGui import QFontInfo
    FontRegistry.initialize()

    artistic_fonts = [
        ("Great Vibes", "handwriting"),
        ("Dancing Script", "handwriting"),
        ("Playfair Display", "luxury"),
        ("Lora", "luxury"),
    ]

    for family, cat in artistic_fonts:
        item = FontRegistry.find_font(family)
        assert item is not None, f"Không tìm thấy phông {family} trong FontRegistry"
        assert item.category == cat
        assert item.file_path and os.path.exists(item.file_path), f"Thiếu tệp font {family}"

        # Kiểm tra đã được đăng ký thành công vào QFontDatabase
        assert family in QFontDatabase.families(), f"Hệ thống Qt chưa nạp family {family}"
        assert QFontDatabase.isSmoothlyScalable(family) is True

        # Kiểm tra QFontInfo resolve đúng family mong muốn
        qf = QFont(family, 14)
        fi = QFontInfo(qf)
        assert fi.family() == family, f"QFont không resolve đúng {family}, nhận được {fi.family()}"

        # Kiểm tra QRawFont trỏ đúng tệp TTF cục bộ
        raw_font = QRawFont(item.file_path, 14)
        assert raw_font.isValid() is True, f"QRawFont cho tệp {item.file_path} không hợp lệ"


# =========================================================================
# 5. RESPONSIVE REGRESSION ACROSS RESOLUTIONS (1920×1080, 1366×768, 1277×752)
# =========================================================================

@pytest.mark.parametrize("width,height", [
    (1920, 1080),
    (1366, 768),
    (1277, 752),
])
def test_typography_responsive_window_stability(qapp, width, height):
    """Kiểm tra toàn bộ cửa sổ chính tại 3 độ phân giải không bị vỡ layout sau khi đổi font."""
    win = MainWindow()
    if hasattr(win, "update_mgr"):
        win.update_mgr.is_auto_check_enabled = False
    if hasattr(win, "auth_mgr"):
        win.auth_mgr.is_authenticated = lambda: True

    win.resize(QSize(width, height))
    win.show()
    qapp.processEvents()

    # 1. Thanh TabBar không bị tràn và hiển thị đầy đủ các tab
    tab_bar = win.tabs.tabBar()
    assert tab_bar.count() == 6
    assert tab_bar.isVisible()

    # 2. Tiêu đề logo không bị clip
    assert win.lbl_title.isVisible()
    assert win.lbl_title.text() == "1998 TEAM"

    # 3. Nút Dashboard (Tổng Quan Hệ Thống) trong Cài Đặt hiển thị tốt
    win.show_dashboard()
    qapp.processEvents()
    assert win.btn_dashboard.isVisible()
    assert win.btn_dashboard.width() >= 100

    win.close()
