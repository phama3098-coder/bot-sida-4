"""
1998 TEAM — Photobooth QSS Stylesheet
Phong cách Studio Cưới chuyên nghiệp, hiện đại, tinh tế.
Màu chủ đạo: Xanh than đậm (#0D1527, #070A12), Đen (#050811), Vàng Champagne (#D4AF37, #C5A059).
Hạn chế gradient sặc sỡ, tối ưu cho màn hình cảm ứng Kiosk.
"""

KIOSK_STYLE = """
/* === Giao Diện Nền Tảng 1998 TEAM Photobooth === */
QWidget {
    background-color: #070A12;
    color: #F8FAFC;
    font-family: "Segoe UI", "Arial", "Tahoma", sans-serif;
    font-size: 15px;
}

QMainWindow {
    background-color: #070A12;
}

/* === Thanh Tiêu Đề & Navigation Bar === */
QTabBar {
    background: transparent;
    qproperty-drawBase: 0;
}

QTabBar::tab {
    background: #10192C;
    color: #E2E8F0;
    padding: 8px 12px;
    font-size: 14px;
    font-weight: 600;
    border-radius: 8px;
    border: 1px solid #223354;
    margin: 3px 2px;
    min-width: 80px;
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F5DE88, stop:0.35 #E5C158, stop:1 #C59B27);
    color: #070A12;
    border: 1.5px solid #FDF4DC;
    font-weight: 800;
}

QTabBar::tab:hover:!selected {
    background: #17243E;
    color: #F7E7CE;
    border: 1px solid #D4AF37;
}

QTabWidget::pane {
    border: none;
    background: #070A12;
}

/* === Nút Bấm Cảm Ứng (Touch Buttons) === */
QPushButton {
    background-color: #15223D;
    color: #F8FAFC;
    font-size: 15px;
    font-weight: 600;
    border: 1px solid #28395E;
    border-radius: 10px;
    padding: 12px 24px;
    min-height: 28px;
}

QPushButton:hover {
    background-color: #1C2D52;
    border: 1px solid #D4AF37;
    color: #F7E7CE;
}

QPushButton:pressed {
    background-color: #121D36;
}

QPushButton:disabled {
    background-color: #131A2B;
    color: #64748B;
    border: 1px solid #1E273D;
}

/* NÚT BẮT ĐẦU CHỤP KHỔNG LỒ - VÀNG CHAMPAGNE QUÝ PHÁI */
QPushButton#btn_big_capture {
    background-color: #D4AF37;
    color: #070A12;
    font-size: 24px;
    font-weight: 900;
    letter-spacing: 1px;
    border: 2px solid #F7E7CE;
    border-radius: 16px;
    min-height: 72px;
    padding: 12px 36px;
}

QPushButton#btn_big_capture:hover {
    background-color: #E5C158;
    color: #050811;
    border: 2px solid #FFFFFF;
}

QPushButton#btn_big_capture:pressed {
    background-color: #C5A059;
}

QPushButton#btn_big_capture:disabled {
    background-color: #2D3748;
    color: #718096;
    border: 1px solid #4A5568;
}

/* Nút Vàng Champagne Hành Động Chính */
QPushButton#btn_champagne {
    background-color: #D4AF37;
    color: #070A12;
    font-weight: bold;
    border: 1px solid #E5C158;
}

QPushButton#btn_champagne:hover {
    background-color: #E5C158;
}

QPushButton#btn_secondary {
    background-color: #15223D;
    color: #E2E8F0;
    border: 1px solid #28395E;
}

QPushButton#btn_secondary:hover {
    background-color: #1E2D4E;
    border: 1px solid #D4AF37;
}

QPushButton#btn_danger {
    background-color: #7F1D1D;
    color: #FEE2E2;
    border: 1px solid #B91C1C;
}

QPushButton#btn_danger:hover {
    background-color: #991B1B;
}

QPushButton#btn_success {
    background-color: #D4AF37;
    color: #070A12;
    font-weight: bold;
    border: 1px solid #E5C158;
}

QPushButton#btn_success:hover {
    background-color: #E5C158;
}

/* === Khung Chứa & Thẻ (Cards / Panels) === */
QFrame#card_panel {
    background-color: #0E1629;
    border: 1px solid #1E2D4A;
    border-radius: 12px;
    padding: 14px;
}

QGroupBox {
    border: 1px solid #1E2D4A;
    border-radius: 10px;
    margin-top: 24px;
    font-weight: 600;
    font-size: 15px;
    color: #D4AF37; /* Tiêu đề nhóm màu vàng champagne */
    padding-top: 18px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    background-color: #0E1629;
}

/* === Ô Nhập Liệu & Danh Sách Lựa Chọn === */
QLineEdit, QSpinBox, QComboBox {
    background-color: #0A1020;
    color: #F8FAFC;
    border: 1px solid #28395E;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 15px;
    min-height: 26px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 2px solid #D4AF37;
}

QComboBox QAbstractItemView {
    background-color: #0E1629;
    color: #F8FAFC;
    selection-background-color: #1A284A;
    selection-color: #D4AF37;
    border: 1px solid #28395E;
}

/* === Hộp Kiểm (QCheckBox) === */
QCheckBox {
    color: #E2E8F0;
    font-size: 14px;
    font-weight: 500;
    spacing: 8px;
    background: transparent;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1.5px solid #28395E;
    border-radius: 4px;
    background-color: #0B1322;
}

QCheckBox::indicator:hover {
    border-color: #D4AF37;
}

QCheckBox::indicator:checked {
    background-color: #D4AF37;
    border-color: #F7E7CE;
}

/* === Thanh Trượt Tham Số Bộ Lọc (Sliders) === */
QSlider::groove:horizontal {
    border: none;
    height: 8px;
    background: #1A284A;
    border-radius: 4px;
}

QSlider::sub-page:horizontal {
    background: #D4AF37;
    border-radius: 4px;
}

QSlider::handle:horizontal {
    background: #F7E7CE;
    border: 2px solid #D4AF37;
    width: 22px;
    margin-top: -7px;
    margin-bottom: -7px;
    border-radius: 11px;
}

QSlider::handle:horizontal:hover {
    background: #FFFFFF;
}

/* === Bảng Dữ Liệu (Tables) === */
QTableWidget {
    background-color: #0A1020;
    alternate-background-color: #0E1629;
    gridline-color: #1E2D4A;
    border: 1px solid #1E2D4A;
    border-radius: 8px;
    color: #F8FAFC;
}

QTableWidget::item:selected {
    background-color: #1A284A;
    color: #D4AF37;
}

QHeaderView::section {
    background-color: #0E1629;
    color: #D4AF37;
    font-weight: bold;
    border: none;
    border-bottom: 2px solid #28395E;
    padding: 10px;
}

/* === Thanh Cuộn Mượt (Scrollbar) === */
QScrollBar:vertical {
    border: none;
    background: #070A12;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #28395E;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #D4AF37;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #070A12;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #28395E;
    min-width: 30px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #D4AF37;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""
