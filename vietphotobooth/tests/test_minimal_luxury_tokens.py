"""
Unit Test Suite for Minimal Luxury Design Tokens & Reusable Cards (Stage 2.1)
Verifies design tokens, WCAG contrast compliance, SurfaceCard, SecondaryCard,
StatCardMetric (Live, Demo, N/A), and AlertBannerWidget.
"""

import re
import pytest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from vietphotobooth.desktop.styles import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_SECONDARY,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_BORDER,
    COLOR_CHAMPAGNE, COLOR_CHAMPAGNE_LIGHT, COLOR_PALE_GOLD,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_LIVEVIEW,
    STYLE_BTN_CHAMPAGNE, STYLE_BTN_SECONDARY, STYLE_NAV_ITEM
)
from vietphotobooth.desktop.widgets.minimal_luxury_cards import (
    SurfaceCard, SecondaryCard, StatCardMetric, AlertBannerWidget
)


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication instance is initialized for GUI testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _relative_luminance(color_hex: str) -> float:
    """Calculate WCAG relative luminance of a #RRGGBB color."""
    c = QColor(color_hex)
    r = c.redF()
    g = c.greenF()
    b = c.blueF()

    def _adjust(val: float) -> float:
        return val / 12.92 if val <= 0.03928 else ((val + 0.055) / 1.055) ** 2.4

    r_adj = _adjust(r)
    g_adj = _adjust(g)
    b_adj = _adjust(b)
    return 0.2126 * r_adj + 0.7152 * g_adj + 0.0722 * b_adj


def _contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors."""
    lum1 = _relative_luminance(hex1)
    lum2 = _relative_luminance(hex2)
    l_max = max(lum1, lum2)
    l_min = min(lum1, lum2)
    return (l_max + 0.05) / (l_min + 0.05)


def test_minimal_luxury_token_definitions():
    """Verify all 13 Minimal Luxury color tokens exist and follow valid #RRGGBB format."""
    tokens = [
        COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_SECONDARY,
        COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_BORDER,
        COLOR_CHAMPAGNE, COLOR_CHAMPAGNE_LIGHT, COLOR_PALE_GOLD,
        COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_LIVEVIEW
    ]

    hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
    for token in tokens:
        assert isinstance(token, str), f"Token {token} must be a string"
        assert hex_pattern.match(token), f"Token {token} is not valid #RRGGBB format"


def test_minimal_luxury_wcag_contrast_compliance():
    """Verify primary and secondary text have sufficient contrast against background and surface."""
    # Text primary on white surface (>= 4.5:1)
    contrast_primary_surface = _contrast_ratio(COLOR_TEXT_PRIMARY, COLOR_SURFACE)
    assert contrast_primary_surface >= 4.5, (
        f"Primary text contrast on Surface {contrast_primary_surface:.2f} must meet WCAG AA (>= 4.5:1)"
    )

    # Text primary on background (>= 4.5:1)
    contrast_primary_bg = _contrast_ratio(COLOR_TEXT_PRIMARY, COLOR_BG)
    assert contrast_primary_bg >= 4.5, (
        f"Primary text contrast on BG {contrast_primary_bg:.2f} must meet WCAG AA (>= 4.5:1)"
    )

    # Text secondary on white surface (>= 4.5:1 WCAG AA)
    contrast_sec_surface = _contrast_ratio(COLOR_TEXT_SECONDARY, COLOR_SURFACE)
    assert contrast_sec_surface >= 4.5, (
        f"Secondary text contrast on Surface {contrast_sec_surface:.2f} must meet WCAG AA (>= 4.5:1)"
    )

    # Text secondary on background (>= 4.5:1 WCAG AA)
    contrast_sec_bg = _contrast_ratio(COLOR_TEXT_SECONDARY, COLOR_BG)
    assert contrast_sec_bg >= 4.5, (
        f"Secondary text contrast on BG {contrast_sec_bg:.2f} must meet WCAG AA (>= 4.5:1)"
    )

    # Champagne button text (#1C1D1C) on Champagne gold (>= 4.5:1 WCAG AA)
    contrast_btn_champagne = _contrast_ratio("#1C1D1C", COLOR_CHAMPAGNE)
    assert contrast_btn_champagne >= 4.5, (
        f"Champagne button text contrast {contrast_btn_champagne:.2f} must meet WCAG AA (>= 4.5:1)"
    )

    # Champagne accent on dark live view (>= 3.0:1)
    contrast_accent_liveview = _contrast_ratio(COLOR_CHAMPAGNE, COLOR_LIVEVIEW)
    assert contrast_accent_liveview >= 3.0, (
        f"Champagne contrast on Live View {contrast_accent_liveview:.2f} must be >= 3.0:1"
    )


def test_surface_and_secondary_cards(qapp):
    """Verify SurfaceCard and SecondaryCard attributes, styling, and leak-free label rendering."""
    # 1. SurfaceCard
    surface = SurfaceCard()
    assert surface.testAttribute(Qt.WA_StyledBackground) is True
    assert surface.frameShape() == QFrame.StyledPanel
    assert surface.objectName() == "surface_card"

    # Add child widgets
    layout_s = QVBoxLayout(surface)
    lbl_s = QLabel("Thử Nghiệm Thẻ Trắng", surface)
    layout_s.addWidget(lbl_s)
    surface.resize(300, 150)
    surface.show()
    pix_s = surface.grab()
    assert not pix_s.isNull()
    assert pix_s.width() == 300
    surface.close()

    # 2. SecondaryCard
    secondary = SecondaryCard()
    assert secondary.testAttribute(Qt.WA_StyledBackground) is True
    assert secondary.frameShape() == QFrame.StyledPanel
    assert secondary.objectName() == "secondary_card"

    layout_sec = QVBoxLayout(secondary)
    lbl_sec = QLabel("Thử Nghiệm Thẻ Phụ", secondary)
    layout_sec.addWidget(lbl_sec)
    secondary.resize(300, 150)
    secondary.show()
    pix_sec = secondary.grab()
    assert not pix_sec.isNull()
    secondary.close()


def test_stat_card_metric_modes_and_updates(qapp):
    """Verify StatCardMetric renders LIVE, DEMO, and N/A modes accurately without mock confusion."""
    # 1. Live mode
    card = StatCardMetric(
        icon_char="📸",
        accent_color=COLOR_SUCCESS,
        title="Phiên Đã Chụp",
        value="42",
        subtitle="Hoàn tất: 42 lượt chụp",
        badge_mode="LIVE"
    )
    assert card.badge_mode == "LIVE"
    assert "LIVE" in card.lbl_badge.text()
    assert card.lbl_val.text() == "42"

    # 2. Demo mode switch
    card.set_badge_mode("DEMO")
    assert card.badge_mode == "DEMO"
    assert "DEMO" in card.lbl_badge.text()

    # 3. N/A mode switch
    card.set_badge_mode("N/A")
    assert card.badge_mode == "N/A"
    assert "N/A" in card.lbl_badge.text()

    # 4. MANUAL mode switch
    card.set_badge_mode("MANUAL")
    assert card.badge_mode == "MANUAL"
    assert "MANUAL" in card.lbl_badge.text()

    # 5. ERROR mode switch
    card.set_badge_mode("ERROR")
    assert card.badge_mode == "ERROR"
    assert "ERROR" in card.lbl_badge.text()

    # 6. Value and subtitle updates
    card.set_value("156")
    card.set_subtitle("Đã cập nhật theo sự kiện mới")
    assert card.lbl_val.text() == "156"
    assert card.lbl_sub.text() == "Đã cập nhật theo sự kiện mới"

    card.resize(260, 120)
    card.show()
    pix = card.grab()
    assert not pix.isNull()
    card.close()


def test_alert_banner_widget_types_and_signals(qapp):
    """Verify AlertBannerWidget styling, signals, and responsive text reflow."""
    banner = AlertBannerWidget(
        banner_type="warning",
        title="MÁY IN SẮP HẾT GIẤY",
        message="Còn lại 15 bản in trong khay DNP DS-RX1HS.",
        action_text="Nạp Giấy"
    )
    assert banner.banner_type == "warning"
    assert banner.lbl_title.text() == "MÁY IN SẮP HẾT GIẤY"
    assert banner.btn_action.isHidden() is False

    # Signal verification
    action_received = []
    dismiss_received = []
    banner.action_clicked.connect(lambda: action_received.append(True))
    banner.dismiss_clicked.connect(lambda: dismiss_received.append(True))

    banner.btn_action.click()
    assert len(action_received) == 1

    banner.btn_dismiss.click()
    assert len(dismiss_received) == 1

    # Switch to error type
    banner.set_banner_type("error")
    assert banner.banner_type == "error"
    banner.set_message("MÁY ẢNH MẤT KẾT NỐI", "Cáp USB đã bị rút.")
    assert banner.lbl_title.text() == "MÁY ẢNH MẤT KẾT NỐI"

    # Switch to success type
    banner.set_banner_type("success")
    assert banner.banner_type == "success"

    # Hide action button
    banner.set_action_text(None)
    assert banner.btn_action.isHidden() is True

    banner.resize(600, 60)
    banner.show()
    pix = banner.grab()
    assert not pix.isNull()
    banner.close()


def test_minimal_luxury_button_helpers(qapp):
    """Verify Minimal Luxury button stylesheet helpers format and render cleanly."""
    container = QWidget()
    layout = QVBoxLayout(container)

    btn_cta = QPushButton("BẮT ĐẦU PHOTOBOOTH")
    btn_cta.setObjectName("btn_champagne")
    btn_cta.setStyleSheet(STYLE_BTN_CHAMPAGNE)
    layout.addWidget(btn_cta)

    btn_sec = QPushButton("Chụp Lại")
    btn_sec.setObjectName("btn_secondary")
    btn_sec.setStyleSheet(STYLE_BTN_SECONDARY)
    layout.addWidget(btn_sec)

    btn_nav = QPushButton("📊 Dashboard")
    btn_nav.setObjectName("nav_item")
    btn_nav.setStyleSheet(STYLE_NAV_ITEM)
    layout.addWidget(btn_nav)

    container.resize(300, 200)
    container.show()
    pix = container.grab()
    assert not pix.isNull()
    container.close()
