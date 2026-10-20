"""
VietPhotoBooth Desktop QSS Stylesheet
Modern, touch-friendly dark theme optimized for Windows 10/11 high-DPI kiosks.
"""

KIOSK_STYLE = """
/* === Giao Diện Nền Tảng VietPhotoBooth === */
QWidget {
    background-color: #0F172A;
    color: #F8FAFC;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 14px;
}

QMainWindow {
    background-color: #0F172A;
}

/* === Thanh Tiêu Đề & Navigation Bar === */
QTabBar::tab {
    background: #1E293B;
    color: #94A3B8;
    padding: 14px 24px;
    font-size: 15px;
    font-weight: 600;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    min-width: 130px;
}

QTabBar::tab:selected {
    background: #3B82F6;
    color: #FFFFFF;
}

QTabBar::tab:hover:!selected {
    background: #334155;
    color: #F1F5F9;
}

QTabWidget::pane {
    border: 1px solid #334155;
    background: #1E293B;
    border-radius: 8px;
}

/* === Nút Bấm Cảm Ứng (Touch Buttons) === */
QPushButton {
    background-color: #3B82F6;
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #2563EB;
}

QPushButton:pressed {
    background-color: #1D4ED8;
}

QPushButton:disabled {
    background-color: #475569;
    color: #94A3B8;
}

/* Nút Chụp Ảnh To Đặc Biệt Cho Kiosk */
QPushButton#btn_big_capture {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EC4899, stop:1 #8B5CF6);
    color: #FFFFFF;
    font-size: 24px;
    font-weight: bold;
    border-radius: 35px;
    min-height: 70px;
    min-width: 220px;
}

QPushButton#btn_big_capture:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DB2777, stop:1 #7C3AED);
}

QPushButton#btn_big_capture:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #BE185D, stop:1 #6D28D9);
}

QPushButton#btn_secondary {
    background-color: #334155;
    color: #F8FAFC;
    font-size: 15px;
}

QPushButton#btn_secondary:hover {
    background-color: #475569;
}

QPushButton#btn_danger {
    background-color: #EF4444;
    color: #FFFFFF;
}

QPushButton#btn_danger:hover {
    background-color: #DC2626;
}

QPushButton#btn_success {
    background-color: #10B981;
    color: #FFFFFF;
}

QPushButton#btn_success:hover {
    background-color: #059669;
}

/* === Khung Chứa & Thẻ (Cards / Panels) === */
QFrame#card_panel {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
}

QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 24px;
    font-weight: 600;
    font-size: 15px;
    color: #38BDF8;
    padding-top: 16px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
}

/* === Ô Nhập Liệu & Danh Sách Lựa Chọn === */
QLineEdit, QSpinBox, QComboBox {
    background-color: #0F172A;
    color: #FFFFFF;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 14px;
    min-height: 22px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 2px solid #3B82F6;
}

QComboBox QAbstractItemView {
    background-color: #1E293B;
    color: #FFFFFF;
    selection-background-color: #3B82F6;
    selection-color: #FFFFFF;
    border: 1px solid #334155;
}

/* === Thanh Trượt Tham Số Bộ Lọc (Sliders) === */
QSlider::groove:horizontal {
    border: none;
    height: 8px;
    background: #334155;
    border-radius: 4px;
}

QSlider::sub-page:horizontal {
    background: #3B82F6;
    border-radius: 4px;
}

QSlider::handle:horizontal {
    background: #60A5FA;
    border: 2px solid #FFFFFF;
    width: 20px;
    margin-top: -6px;
    margin-bottom: -6px;
    border-radius: 10px;
}

QSlider::handle:horizontal:hover {
    background: #93C5FD;
}

/* === Bảng Dữ Liệu (Tables) === */
QTableWidget {
    background-color: #0F172A;
    alternate-background-color: #1E293B;
    gridline-color: #334155;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #F8FAFC;
}

QTableWidget::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}

QHeaderView::section {
    background-color: #1E293B;
    color: #94A3B8;
    font-weight: 600;
    border: none;
    border-bottom: 2px solid #334155;
    padding: 8px;
}

/* === Thanh Cuộn Mượt (Scrollbar) === */
QScrollBar:vertical {
    border: none;
    background: #0F172A;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #475569;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #64748B;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #0F172A;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #475569;
    min-width: 30px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #64748B;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""
