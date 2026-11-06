"""
1998 TEAM — Photobooth Global Design System & Soft Taupe Stylesheet
Phong cách thiết kế chính thức: SOFT TAUPE STUDIO – LUXURY WEDDING PHOTOBOOTH
Design Tokens:
- Main Background: #C8C5BD
- Surface (Panel / Card): #D9D5CC
- Secondary Surface: #B9B5AB
- Input Background: #E2DED5
- Border: #AAA69D
- Primary Text: #353631
- Secondary Text: #716F68
- Muted Champagne (CTA & Accents): #AD905B
- Gold Light (Highlights): #D0BC94
- Live View Canvas: #17191C
"""

# =========================================================================
# 1. CENTRALIZED DESIGN TOKENS (SOFT TAUPE STUDIO)
# =========================================================================
THEME_BG_MAIN = "#C8C5BD"
THEME_SURFACE = "#D9D5CC"
THEME_BG_SECONDARY = "#B9B5AB"
THEME_INPUT_BG = "#E2DED5"
THEME_BORDER = "#AAA69D"
THEME_BORDER_LIGHT = "#B9B5AB"
THEME_TEXT_PRIMARY = "#353631"
THEME_TEXT_SECONDARY = "#716F68"
THEME_TEXT_DISABLED = "#97948D"

# Brand Identity Colors (1998 TEAM & 1998 Studio Phóng Sự Cưới)
THEME_GOLD = "#AD905B"
THEME_GOLD_LIGHT = "#D0BC94"
THEME_GOLD_PALE = "#EBE5D8"
THEME_GOLD_DARK = "#8A703F"

# Warm Studio Accents (Replacing harsh cold blues with deep studio taupe)
THEME_BRAND_BLUE = "#353631"
THEME_BRAND_BLUE_LIGHT = "#55534D"
THEME_BRAND_BLUE_PALE = "#D9D5CC"

# Live View Contrast Background
LIVE_VIEW_BG = "#17191C"

# Semantic Colors
THEME_SUCCESS = "#2E7D32"
THEME_SUCCESS_BG = "#E2EFE2"
THEME_SUCCESS_BORDER = "#A5D6A7"
THEME_WARNING = "#B45309"
THEME_WARNING_BG = "#FEF3C7"
THEME_WARNING_BORDER = "#FCD34D"
THEME_DANGER = "#C53030"
THEME_DANGER_BG = "#FDE8E8"
THEME_DANGER_BORDER = "#FCA5A5"

# =========================================================================
# 2. GLOBAL SOFT TAUPE STYLESHEET (KIOSK_STYLE)
# =========================================================================
KIOSK_STYLE = f"""
/* === Giao Diện Toàn Cục 1998 TEAM Photobooth (Soft Taupe Studio) === */
QWidget {{
    background-color: {THEME_BG_MAIN};
    color: {THEME_TEXT_PRIMARY};
    font-family: "Segoe UI", "Arial", "Tahoma", sans-serif;
    font-size: 14px;
}}

QMainWindow {{
    background-color: {THEME_BG_MAIN};
}}

/* === Thanh Tiêu Đề & Navigation Bar === */
QTabBar {{
    background: transparent;
    qproperty-drawBase: 0;
}}

QTabBar::tab {{
    background: {THEME_SURFACE};
    color: {THEME_TEXT_PRIMARY};
    padding: 6px 16px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    border: 1.5px solid {THEME_BORDER};
    margin: 2px 3px;
    min-width: 60px;
}}

QTabBar::tab:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {THEME_GOLD_LIGHT}, stop:1 {THEME_GOLD});
    color: #FFFFFF;
    border: 1.5px solid {THEME_GOLD_DARK};
    font-weight: 800;
}}

QTabBar::tab:hover:!selected {{
    background: {THEME_BG_SECONDARY};
    color: {THEME_TEXT_PRIMARY};
    border: 1.5px solid {THEME_GOLD};
}}

QTabBar QToolButton {{
    background: {THEME_SURFACE};
    border: 1.5px solid {THEME_BORDER};
    border-radius: 6px;
    color: {THEME_GOLD_DARK};
    margin: 1px;
}}

QTabBar QToolButton:hover {{
    background: {THEME_GOLD};
    color: #FFFFFF;
}}

QTabWidget::pane {{
    border: none;
    background: {THEME_BG_MAIN};
}}

/* === Nút Bấm Thao Tác (Buttons) === */
QPushButton {{
    background-color: {THEME_SURFACE};
    color: {THEME_TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 600;
    border: 1.5px solid {THEME_BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    min-height: 26px;
}}

QPushButton:hover {{
    background-color: {THEME_BG_SECONDARY};
    border: 1.5px solid {THEME_GOLD};
    color: {THEME_TEXT_PRIMARY};
}}

QPushButton:pressed {{
    background-color: #BAAEA0;
}}

QPushButton:disabled {{
    background-color: #D5CDC0;
    color: {THEME_TEXT_DISABLED};
    border: 1px solid #C4B9AA;
}}

/* NÚT BẮT ĐẦU CHỤP KHỔNG LỒ - VÀNG CHAMPAGNE QUÝ PHÁI */
QPushButton#btn_big_capture {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {THEME_GOLD_LIGHT}, stop:0.45 {THEME_GOLD}, stop:1 {THEME_GOLD_DARK});
    color: #FFFFFF;
    font-size: 22px;
    font-weight: 900;
    letter-spacing: 1px;
    border: 2px solid {THEME_GOLD_PALE};
    border-radius: 31px;
    min-height: 60px;
    padding: 10px 36px;
}}

QPushButton#btn_big_capture:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #D9C293, stop:0.45 #C4A364, stop:1 #AF8E4E);
    border: 2px solid #FFFFFF;
}}

QPushButton#btn_big_capture:pressed {{
    background: {THEME_GOLD_DARK};
}}

QPushButton#btn_big_capture:disabled {{
    background: {THEME_BG_SECONDARY};
    color: {THEME_TEXT_SECONDARY};
    border: 1px solid {THEME_BORDER};
}}

/* Nút Vàng Champagne Hành Động Chính */
QPushButton#btn_champagne {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {THEME_GOLD_LIGHT}, stop:1 {THEME_GOLD});
    color: #FFFFFF;
    font-weight: 800;
    border: 1px solid {THEME_GOLD_DARK};
}}

QPushButton#btn_champagne:hover {{
    background: {THEME_GOLD_LIGHT};
    color: {THEME_TEXT_PRIMARY};
}}

QPushButton#btn_secondary {{
    background-color: {THEME_SURFACE};
    color: {THEME_TEXT_PRIMARY};
    border: 1.5px solid {THEME_BORDER};
}}

QPushButton#btn_secondary:hover {{
    background-color: {THEME_BG_SECONDARY};
    border: 1.5px solid {THEME_GOLD};
}}

QPushButton#btn_danger {{
    background-color: {THEME_DANGER_BG};
    color: {THEME_DANGER};
    border: 1.5px solid {THEME_DANGER_BORDER};
    font-weight: 700;
}}

QPushButton#btn_danger:hover {{
    background-color: #FCDCDC;
    border: 1.5px solid {THEME_DANGER};
}}

QPushButton#btn_success {{
    background-color: {THEME_SUCCESS_BG};
    color: {THEME_SUCCESS};
    border: 1.5px solid {THEME_SUCCESS_BORDER};
    font-weight: 700;
}}

QPushButton#btn_success:hover {{
    background-color: #C8E6C9;
    border: 1.5px solid {THEME_SUCCESS};
}}

/* === Khung Chứa & Thẻ (Cards / Panels) === */
QFrame#card_panel, QFrame.card {{
    background-color: {THEME_SURFACE};
    border: 1.5px solid {THEME_BORDER};
    border-radius: 12px;
    padding: 14px;
}}

QGroupBox {{
    background-color: {THEME_SURFACE};
    border: 1.5px solid {THEME_BORDER};
    border-radius: 10px;
    margin-top: 24px;
    font-weight: 700;
    font-size: 14px;
    color: {THEME_TEXT_PRIMARY};
    padding-top: 18px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    background-color: {THEME_SURFACE};
    color: {THEME_TEXT_PRIMARY};
}}

/* === Ô Nhập Liệu & Danh Sách Lựa Chọn (Inputs & Selects) === */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {THEME_INPUT_BG};
    color: {THEME_TEXT_PRIMARY};
    border: 1.5px solid {THEME_BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 14px;
    min-height: 26px;
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 2px solid {THEME_GOLD};
    background-color: #F8F3EB;
}}

QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background-color: #D5CDC0;
    color: {THEME_TEXT_DISABLED};
    border: 1px solid #C4B9AA;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {THEME_SURFACE};
    color: {THEME_TEXT_PRIMARY};
    selection-background-color: {THEME_BG_SECONDARY};
    selection-color: {THEME_TEXT_PRIMARY};
    border: 1.5px solid {THEME_BORDER};
    outline: none;
    padding: 4px;
}}

/* === Hộp Kiểm (QCheckBox) & Radio Buttons === */
QCheckBox, QRadioButton {{
    color: {THEME_TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 500;
    spacing: 8px;
    background: transparent;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1.5px solid {THEME_BORDER};
    border-radius: 4px;
    background-color: {THEME_SURFACE};
}}

QCheckBox::indicator:hover {{
    border-color: {THEME_GOLD};
}}

QCheckBox::indicator:checked {{
    background-color: {THEME_GOLD};
    border-color: {THEME_GOLD_DARK};
}}

/* === Thanh Trượt Tham Số Bộ Lọc (Sliders) === */
QSlider::groove:horizontal {{
    border: none;
    height: 6px;
    background: {THEME_BORDER};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {THEME_GOLD};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {THEME_SURFACE};
    border: 2px solid {THEME_GOLD};
    width: 20px;
    margin-top: -7px;
    margin-bottom: -7px;
    border-radius: 10px;
}}

QSlider::handle:horizontal:hover {{
    background: {THEME_GOLD_PALE};
}}

/* === Bảng Dữ Liệu (Tables) === */
QTableWidget {{
    background-color: {THEME_SURFACE};
    alternate-background-color: {THEME_BG_SECONDARY};
    gridline-color: {THEME_BORDER_LIGHT};
    border: 1.5px solid {THEME_BORDER};
    border-radius: 8px;
    color: {THEME_TEXT_PRIMARY};
}}

QTableWidget::item:selected {{
    background-color: {THEME_GOLD_PALE};
    color: {THEME_TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {THEME_BG_SECONDARY};
    color: {THEME_TEXT_PRIMARY};
    font-weight: bold;
    border: none;
    border-bottom: 2px solid {THEME_BORDER};
    padding: 8px;
    font-size: 13px;
}}

/* === Thanh Cuộn Mượt (Scrollbars) === */
QScrollBar:vertical {{
    border: none;
    background: {THEME_BG_MAIN};
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {THEME_BORDER};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {THEME_GOLD};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: {THEME_BG_MAIN};
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {THEME_BORDER};
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {THEME_GOLD};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* === Hộp Thoại, Menu ngữ cảnh & Tooltip (Dialogs, Menus, Tooltips) === */
QDialog {{
    background-color: {THEME_BG_MAIN};
    color: {THEME_TEXT_PRIMARY};
}}

QMenu {{
    background-color: {THEME_SURFACE};
    color: {THEME_TEXT_PRIMARY};
    border: 1.5px solid {THEME_BORDER};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {THEME_GOLD_PALE};
    color: {THEME_TEXT_PRIMARY};
}}

QToolTip {{
    background-color: {THEME_TEXT_PRIMARY};
    color: {THEME_GOLD_PALE};
    border: 1px solid {THEME_TEXT_SECONDARY};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}}

QProgressBar {{
    background-color: {THEME_BG_SECONDARY};
    border: 1px solid {THEME_BORDER};
    border-radius: 8px;
    text-align: center;
    color: {THEME_TEXT_PRIMARY};
    font-weight: 700;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {THEME_GOLD}, stop:1 {THEME_GOLD_LIGHT});
    border-radius: 7px;
}}

/* === Tối Ưu Bố Cục Co Giãn Frame Designer (Responsive Designer Styles) === */
FrameDesignerPage QPushButton {{
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 600;
    min-height: 24px;
}}

FrameDesignerPage QHeaderView::section {{
    padding: 4px 6px;
    font-size: 12px;
}}

FrameDesignerPage QComboBox {{
    padding: 4px 8px;
    font-size: 13px;
    min-height: 24px;
}}
"""
