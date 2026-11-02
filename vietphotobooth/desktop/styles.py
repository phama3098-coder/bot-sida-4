"""
1998 TEAM — Photobooth Global Design System & Light Theme Stylesheet
Chuyển đổi toàn diện sang phong cách Premium Light Theme sang trọng, tinh tế.
Design Tokens:
- Main Background: #F3F4F6
- Secondary Background: #F8FAFC
- Card / Surface: #FFFFFF
- Input Background: #FFFFFF
- Border: #D9DEE7
- Primary Text: #303746
- Secondary Text: #64748B
- Disabled Text: #94A3B8
- Brand Accents: Champagne Gold (#D4AF37) & Brand Blue (#1E40AF)
"""

# =========================================================================
# 1. CENTRALIZED DESIGN TOKENS
# =========================================================================
THEME_BG_MAIN = "#F3F4F6"
THEME_BG_SECONDARY = "#F8FAFC"
THEME_SURFACE = "#FFFFFF"
THEME_INPUT_BG = "#FFFFFF"
THEME_BORDER = "#D9DEE7"
THEME_BORDER_LIGHT = "#E2E8F0"
THEME_TEXT_PRIMARY = "#303746"
THEME_TEXT_SECONDARY = "#64748B"
THEME_TEXT_DISABLED = "#94A3B8"

# Brand Identity Colors (1998 TEAM & 1998 Studio Phóng Sự Cưới)
THEME_GOLD = "#D4AF37"
THEME_GOLD_LIGHT = "#F5DE88"
THEME_GOLD_PALE = "#FDF4DC"
THEME_GOLD_DARK = "#997A15"
THEME_BRAND_BLUE = "#1E40AF"
THEME_BRAND_BLUE_LIGHT = "#3B82F6"
THEME_BRAND_BLUE_PALE = "#EFF6FF"

# Semantic Colors
THEME_SUCCESS = "#10B981"
THEME_SUCCESS_BG = "#ECFDF5"
THEME_SUCCESS_BORDER = "#A7F3D0"
THEME_WARNING = "#D97706"
THEME_WARNING_BG = "#FFFBEB"
THEME_WARNING_BORDER = "#FDE68A"
THEME_DANGER = "#DC2626"
THEME_DANGER_BG = "#FEF2F2"
THEME_DANGER_BORDER = "#FECACA"

# =========================================================================
# 2. GLOBAL LIGHT THEME STYLESHEET (KIOSK_STYLE)
# =========================================================================
KIOSK_STYLE = f"""
/* === Giao Diện Toàn Cục 1998 TEAM Photobooth (Premium Light Theme) === */
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
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    border: 1.5px solid {THEME_BORDER};
    margin: 2px 2px;
    min-width: 52px;
}}

QTabBar::tab:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F5DE88, stop:0.4 #E5C158, stop:1 #C59B27);
    color: #070A12;
    border: 1.5px solid {THEME_GOLD_PALE};
    font-weight: 800;
}}

QTabBar::tab:hover:!selected {{
    background: {THEME_BG_SECONDARY};
    color: {THEME_BRAND_BLUE};
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
    color: {THEME_GOLD_DARK};
}}

QPushButton:pressed {{
    background-color: #E2E8F0;
}}

QPushButton:disabled {{
    background-color: #F1F5F9;
    color: {THEME_TEXT_DISABLED};
    border: 1px solid #E2E8F0;
}}

/* NÚT BẮT ĐẦU CHỤP KHỔNG LỒ - VÀNG CHAMPAGNE QUÝ PHÁI */
QPushButton#btn_big_capture {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F7E7CE, stop:0.35 #E5C158, stop:1 #C59B27);
    color: #070A12;
    font-size: 22px;
    font-weight: 900;
    letter-spacing: 1px;
    border: 2px solid #FFF8E7;
    border-radius: 31px;
    min-height: 60px;
    padding: 10px 36px;
}}

QPushButton#btn_big_capture:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFFFFF, stop:0.35 #F0D278, stop:1 #D4AF37);
    border: 2px solid #FFFFFF;
}}

QPushButton#btn_big_capture:pressed {{
    background: #C59B27;
}}

QPushButton#btn_big_capture:disabled {{
    background: #CBD5E1;
    color: #64748B;
    border: 1px solid #94A3B8;
}}

/* Nút Vàng Champagne Hành Động Chính */
QPushButton#btn_champagne {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F5DE88, stop:0.4 #E5C158, stop:1 #C59B27);
    color: #070A12;
    font-weight: 800;
    border: 1px solid #FFF8E7;
}}

QPushButton#btn_champagne:hover {{
    background: #E5C158;
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
    background-color: #FEE2E2;
    border: 1.5px solid {THEME_DANGER};
}}

QPushButton#btn_success {{
    background-color: {THEME_SUCCESS_BG};
    color: #047857;
    border: 1.5px solid {THEME_SUCCESS_BORDER};
    font-weight: 700;
}}

QPushButton#btn_success:hover {{
    background-color: #D1FAE5;
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
    color: {THEME_BRAND_BLUE};
    padding-top: 18px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    background-color: {THEME_SURFACE};
    color: {THEME_BRAND_BLUE};
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
    background-color: #FFFFFF;
}}

QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background-color: #F1F5F9;
    color: {THEME_TEXT_DISABLED};
    border: 1px solid #E2E8F0;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {THEME_SURFACE};
    color: {THEME_TEXT_PRIMARY};
    selection-background-color: #FEF3C7;
    selection-color: #92400E;
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
    background: #E2E8F0;
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {THEME_GOLD};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: #FFFFFF;
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
    background-color: #FEF3C7;
    color: #92400E;
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
    background: #CBD5E1;
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
    background: #CBD5E1;
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
    background-color: #FEF3C7;
    color: #92400E;
}}

QToolTip {{
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}}

QProgressBar {{
    background-color: #E2E8F0;
    border: 1px solid {THEME_BORDER};
    border-radius: 8px;
    text-align: center;
    color: {THEME_TEXT_PRIMARY};
    font-weight: 700;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #34D399);
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
