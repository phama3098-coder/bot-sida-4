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

# =========================================================================
# 1.2 MINIMAL LUXURY STUDIO DESIGN TOKENS (V1.1 DESIGN SYSTEM)
# =========================================================================
COLOR_BG = "#F8F7F3"               # Background (warm alabaster eggshell)
COLOR_SURFACE = "#FFFFFF"          # Surface card (pure crisp white)
COLOR_SURFACE_SECONDARY = "#F1F0EC"# Secondary surface / card fill
COLOR_TEXT_PRIMARY = "#292B29"     # High-contrast charcoal graphite
COLOR_TEXT_SECONDARY = "#6E6D67"   # Sophisticated warm slate
COLOR_BORDER = "#E8E6E0"           # Hairline border divider
COLOR_BORDER_LIGHT = "#F1F0EC"     # Subtle border tint
COLOR_CHAMPAGNE = "#B99A63"        # Refined champagne gold accent
COLOR_CHAMPAGNE_LIGHT = "#C8A870"  # Champagne gradient highlight
COLOR_PALE_GOLD = "#E9DFC9"        # Soft gold badge tint
COLOR_SUCCESS = "#54836A"          # Sage green
COLOR_WARNING = "#C18A42"          # Warm amber
COLOR_ERROR = "#C65D58"            # Terracotta red
COLOR_LIVEVIEW = "#151719"         # Viewfinder obsidian deep black

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
# 1.1 CENTRALIZED TYPOGRAPHY SYSTEM (BE VIETNAM PRO & SOFT TAUPE HIERARCHY)
# =========================================================================
FONT_FAMILY_PRIMARY = '"Be Vietnam Pro", "Segoe UI", Arial, sans-serif'
FONT_FAMILY_SERIF = '"Playfair Display", "Lora", "Times New Roman", serif'
FONT_FAMILY_SCRIPT = '"Great Vibes", "Dancing Script", cursive'

# Phân cấp kích thước font chuẩn hóa (Scale)
FONT_SIZE_DISPLAY = "20px"       # Tiêu đề trang / Màn hình chính
FONT_SIZE_TITLE_LG = "16px"      # Tiêu đề khu vực lớn / Dialog
FONT_SIZE_TITLE = "14px"         # Tiêu đề Card / GroupBox
FONT_SIZE_BODY = "13px"          # Nội dung chính, danh sách, bảng
FONT_SIZE_SECONDARY = "12px"     # Mô tả phụ, hướng dẫn thao tác
FONT_SIZE_CAPTION = "11px"       # Thông số kỹ thuật, huy hiệu, badge

# Độ đậm (Font Weights - chuẩn hóa tương thích Be Vietnam Pro Regular & Bold)
FONT_WEIGHT_NORMAL = "normal"
FONT_WEIGHT_BOLD = "bold"

# Các chuỗi định dạng Typography tái sử dụng
TYPO_DISPLAY = f"font-size: {FONT_SIZE_DISPLAY}; font-weight: {FONT_WEIGHT_BOLD}; color: {THEME_TEXT_PRIMARY}; letter-spacing: 0.5px;"
TYPO_SECTION_TITLE = f"font-size: {FONT_SIZE_TITLE_LG}; font-weight: {FONT_WEIGHT_BOLD}; color: {THEME_TEXT_PRIMARY};"
TYPO_CARD_TITLE = f"font-size: {FONT_SIZE_TITLE}; font-weight: {FONT_WEIGHT_BOLD}; color: {THEME_TEXT_PRIMARY};"
TYPO_BODY = f"font-size: {FONT_SIZE_BODY}; font-weight: {FONT_WEIGHT_NORMAL}; color: {THEME_TEXT_PRIMARY};"
TYPO_SECONDARY = f"font-size: {FONT_SIZE_SECONDARY}; font-weight: {FONT_WEIGHT_NORMAL}; color: {THEME_TEXT_SECONDARY};"
TYPO_CAPTION = f"font-size: {FONT_SIZE_CAPTION}; font-weight: {FONT_WEIGHT_NORMAL}; color: {THEME_TEXT_SECONDARY};"
TYPO_BADGE = f"font-size: {FONT_SIZE_CAPTION}; font-weight: {FONT_WEIGHT_BOLD};"

# Minimal Luxury Component Stylesheet Helpers
STYLE_BTN_CHAMPAGNE = f"""
QPushButton#btn_champagne {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT});
    color: #1C1D1C;
    font-weight: 800;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 10px 22px;
}}
QPushButton#btn_champagne:hover {{
    background: #A88952;
    color: #FFFFFF;
}}
QPushButton#btn_champagne:pressed {{
    background: #8F7240;
    color: #FFFFFF;
}}
QPushButton#btn_champagne:disabled {{
    background: #D9D5CC;
    color: {COLOR_TEXT_SECONDARY};
}}
"""

STYLE_BTN_SECONDARY = f"""
QPushButton#btn_secondary {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 600;
    font-size: 12px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 8px 18px;
}}
QPushButton#btn_secondary:hover {{
    background-color: {COLOR_SURFACE_SECONDARY};
    border-color: {COLOR_CHAMPAGNE};
}}
QPushButton#btn_secondary:pressed {{
    background-color: #E2DED5;
}}
"""

STYLE_NAV_ITEM = f"""
QPushButton#nav_item {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-weight: 600;
    font-size: 12px;
    border: none;
    padding: 7px 12px;
    border-radius: 6px;
}}
QPushButton#nav_item:hover {{
    color: {COLOR_TEXT_PRIMARY};
    background-color: {COLOR_SURFACE_SECONDARY};
}}
QPushButton#nav_item_active {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_CHAMPAGNE};
    font-weight: 700;
    font-size: 12px;
    border: 1px solid {COLOR_BORDER};
    border-bottom: 2px solid {COLOR_CHAMPAGNE};
    border-radius: 6px;
    padding: 7px 12px;
}}
"""

# =========================================================================
# 2. GLOBAL MINIMAL LUXURY STYLESHEET (KIOSK_STYLE)
# =========================================================================
KIOSK_STYLE = f"""
/* === Giao Diện Toàn Cục 1998 TEAM Photobooth (Minimal Luxury Studio) === */
QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT_PRIMARY};
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 13px;
}}

QMainWindow {{
    background-color: {COLOR_BG};
}}

/* Triệt tiêu triệt để viền chữ nhật thừa trên tất cả QLabel */
QLabel {{
    border: none;
    background: transparent;
}}

/* === Thanh Tiêu Đề & Navigation Bar === */
QTabBar {{
    background: transparent;
    qproperty-drawBase: 0;
}}

QTabBar::tab {{
    background: {COLOR_SURFACE};
    color: {COLOR_TEXT_SECONDARY};
    padding: 7px 18px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    border: 1px solid {COLOR_BORDER};
    margin: 2px 3px;
    min-width: 60px;
}}

QTabBar::tab:selected {{
    background: {COLOR_SURFACE};
    color: {COLOR_CHAMPAGNE};
    border: 1px solid {COLOR_BORDER};
    border-bottom: 2px solid {COLOR_CHAMPAGNE};
    font-weight: 700;
}}

QTabBar::tab:hover:!selected {{
    background: {COLOR_SURFACE_SECONDARY};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_CHAMPAGNE};
}}

QTabBar QToolButton {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    color: {COLOR_CHAMPAGNE};
    margin: 1px;
}}

QTabBar QToolButton:hover {{
    background: {COLOR_CHAMPAGNE};
    color: #FFFFFF;
}}

QTabWidget::pane {{
    border: none;
    background: {COLOR_BG};
}}

/* === Nút Bấm Thao Tác (Buttons) === */
QPushButton {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 600;
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    min-height: 26px;
}}

QPushButton:hover {{
    background-color: {COLOR_SURFACE_SECONDARY};
    border: 1px solid {COLOR_CHAMPAGNE};
    color: {COLOR_TEXT_PRIMARY};
}}

QPushButton:pressed {{
    background-color: #E2DED5;
}}

QPushButton:disabled {{
    background-color: {COLOR_SURFACE_SECONDARY};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER};
}}

/* NÚT BẮT ĐẦU CHỤP KHỔNG LỒ - VÀNG CHAMPAGNE QUÝ PHÁI */
QPushButton#btn_big_capture {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT});
    color: #1C1D1C;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 0.5px;
    border: none;
    border-radius: 28px;
    min-height: 56px;
    padding: 10px 36px;
}}

QPushButton#btn_big_capture:hover {{
    background: #A88952;
    color: #FFFFFF;
}}

QPushButton#btn_big_capture:pressed {{
    background: #8F7240;
    color: #FFFFFF;
}}

QPushButton#btn_big_capture:disabled {{
    background: {COLOR_SURFACE_SECONDARY};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER};
}}

/* Nút Vàng Champagne Hành Động Chính */
QPushButton#btn_champagne {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT});
    color: #1C1D1C;
    font-weight: 800;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
}}

QPushButton#btn_champagne:hover {{
    background: #A88952;
    color: #FFFFFF;
}}

QPushButton#btn_secondary {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 8px 18px;
}}

QPushButton#btn_secondary:hover {{
    background-color: {COLOR_SURFACE_SECONDARY};
    border: 1px solid {COLOR_CHAMPAGNE};
}}

QPushButton#btn_danger {{
    background-color: #FDE8E8;
    color: {COLOR_ERROR};
    border: 1px solid #FCA5A5;
    font-weight: 700;
    border-radius: 8px;
}}

QPushButton#btn_danger:hover {{
    background-color: #FCDCDC;
    border: 1px solid {COLOR_ERROR};
}}

QPushButton#btn_success {{
    background-color: #E2EFE2;
    color: {COLOR_SUCCESS};
    border: 1px solid #A5D6A7;
    font-weight: 700;
    border-radius: 8px;
}}

QPushButton#btn_success:hover {{
    background-color: #C8E6C9;
    border: 1px solid {COLOR_SUCCESS};
}}

/* === Khung Chứa & Thẻ (Cards / Panels) === */
QFrame#card_panel, QFrame.card {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    padding: 16px;
}}

QGroupBox {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    margin-top: 24px;
    font-weight: 700;
    font-size: 14px;
    color: {COLOR_TEXT_PRIMARY};
    padding: 18px 14px 14px 14px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
}}

/* === Ô Nhập Liệu & Danh Sách Lựa Chọn (Inputs & Selects) === */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
    min-height: 28px;
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1.5px solid {COLOR_CHAMPAGNE};
    background-color: {COLOR_SURFACE};
}}

QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background-color: {COLOR_SURFACE_SECONDARY};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    selection-background-color: {COLOR_SURFACE_SECONDARY};
    selection-color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    outline: none;
    padding: 4px;
}}

/* === Hộp Kiểm (QCheckBox) & Radio Buttons === */
QCheckBox, QRadioButton {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 500;
    spacing: 8px;
    background: transparent;
    border: none;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    background-color: {COLOR_SURFACE};
}}

QCheckBox::indicator:hover {{
    border-color: {COLOR_CHAMPAGNE};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_CHAMPAGNE};
    border-color: {COLOR_CHAMPAGNE};
}}

/* === Thanh Trượt Tham Số Bộ Lọc (Sliders) === */
QSlider::groove:horizontal {{
    border: none;
    height: 6px;
    background: {COLOR_BORDER};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {COLOR_CHAMPAGNE};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {COLOR_SURFACE};
    border: 2px solid {COLOR_CHAMPAGNE};
    width: 18px;
    margin-top: -6px;
    margin-bottom: -6px;
    border-radius: 9px;
}}

QSlider::handle:horizontal:hover {{
    background: {COLOR_PALE_GOLD};
}}

/* === Bảng Dữ Liệu (Tables) === */
QTableWidget {{
    background-color: {COLOR_SURFACE};
    alternate-background-color: #FAF9F6;
    gridline-color: {COLOR_BORDER_LIGHT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    color: {COLOR_TEXT_PRIMARY};
}}

QTableWidget::item:selected {{
    background-color: {COLOR_PALE_GOLD};
    color: {COLOR_TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {COLOR_SURFACE_SECONDARY};
    color: {COLOR_TEXT_PRIMARY};
    font-weight: bold;
    border: none;
    border-bottom: 1.5px solid {COLOR_BORDER};
    padding: 8px;
    font-size: 12px;
}}

/* === Thanh Cuộn Mượt (Scrollbars) === */
QScrollBar:vertical {{
    border: none;
    background: {COLOR_BG};
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_CHAMPAGNE};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: {COLOR_BG};
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER};
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {COLOR_CHAMPAGNE};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* === Hộp Thoại, Menu ngữ cảnh & Tooltip (Dialogs, Menus, Tooltips) === */
QDialog {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT_PRIMARY};
}}

QMenu {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {COLOR_SURFACE_SECONDARY};
    color: {COLOR_CHAMPAGNE};
}}

QToolTip {{
    background-color: {COLOR_TEXT_PRIMARY};
    color: #FFFFFF;
    border: 1px solid {COLOR_TEXT_SECONDARY};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}}

QProgressBar {{
    background-color: {COLOR_SURFACE_SECONDARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    text-align: center;
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 700;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_CHAMPAGNE}, stop:1 {COLOR_CHAMPAGNE_LIGHT});
    border-radius: 7px;
}}

/* === Tối Ưu Bố Cục Co Giãn Frame Designer (Responsive Designer Styles) === */
FrameDesignerPage QPushButton {{
    padding: 5px 10px;
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

/* === Minimal Luxury Studio Global Helpers === */
QPushButton#btn_champagne {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B99A63, stop:1 #C8A870);
    color: #1C1D1C;
    font-weight: 800;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 10px 22px;
}}
QPushButton#btn_champagne:hover {{
    background: #A88952;
    color: #FFFFFF;
}}
QPushButton#btn_champagne:pressed {{
    background: #8F7240;
    color: #FFFFFF;
}}
QPushButton#btn_champagne:disabled {{
    background: #D9D5CC;
    color: #6E6D67;
}}

QPushButton#btn_secondary {{
    background-color: #FFFFFF;
    color: #292B29;
    font-weight: 600;
    font-size: 12px;
    border: 1px solid #E8E6E0;
    border-radius: 8px;
    padding: 8px 18px;
}}
QPushButton#btn_secondary:hover {{
    background-color: #F1F0EC;
    border-color: #B99A63;
}}
QPushButton#btn_secondary:pressed {{
    background-color: #E2DED5;
}}

QPushButton#nav_item {{
    background: transparent;
    color: #85847D;
    font-weight: 600;
    font-size: 12px;
    border: none;
    padding: 7px 12px;
    border-radius: 6px;
}}
QPushButton#nav_item:hover {{
    color: #292B29;
    background-color: #F1F0EC;
}}

QPushButton#nav_item_active {{
    background-color: #FFFFFF;
    color: #B99A63;
    font-weight: 700;
    font-size: 12px;
    border: 1px solid #E8E6E0;
    border-bottom: 2px solid #B99A63;
    border-radius: 6px;
    padding: 7px 12px;
}}
"""
