"""
1998 TEAM — Photobooth Frame Gallery Page (Thư Viện Chọn Khung Ảnh)
Thiết kế lại theo phong cách Modern Gallery Card Grid (Soft Taupe Studio):
- Grid card hiện đại, khoảng cách đồng đều, tối ưu diện tích hiển thị.
- Thumbnail kích thước lớn, bảo toàn tuyệt đối tỷ lệ khung (2x6 strip, 4x6 ngang/dọc) không biến dạng.
- Tên khung hiển thị đầy đủ tối đa 2 dòng, hỗ trợ tiếng Việt có dấu, không bị cắt chữ.
- Badge tỷ lệ (2x6, 4x6) đặt gọn gàng ở góc trên thumbnail.
- Dấu tick nhỏ và viền Muted Champagne mảnh khi chọn; hover state nhẹ nhàng.
- Thanh tìm kiếm và bộ lọc cân đối, thanh cuộn mỏng không đè lên thẻ nội dung.
- Tự động điều chỉnh số cột theo chiều rộng khả dụng (1366×768: 4 cột, 1600×900: 5 cột, 1920×1080: 6 cột).
"""

import os
from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QScrollArea, QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QColor, QFont, QCursor

from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.frames.frame_models import FrameTemplate
from vietphotobooth.desktop.icons import (
    get_svg_icon, get_svg_pixmap, COLOR_GOLD, COLOR_WHITE, COLOR_SLATE, COLOR_BLUE
)
from vietphotobooth.desktop.styles import (
    THEME_BG_MAIN, THEME_BG_SECONDARY, THEME_SURFACE, THEME_BORDER,
    THEME_INPUT_BG, THEME_TEXT_PRIMARY, THEME_TEXT_SECONDARY, THEME_TEXT_DISABLED,
    THEME_GOLD, THEME_GOLD_LIGHT, THEME_GOLD_DARK, THEME_GOLD_PALE
)
from vietphotobooth.core.logger import get_logger

logger = get_logger()


class FrameCard(QFrame):
    """
    Thẻ hiển thị khung ảnh trong Gallery Card Grid hiện đại:
    - Thumbnail kích thước lớn, bảo toàn tuyệt đối tỷ lệ khung, không méo hình.
    - Badge tỷ lệ (2x6, 4x6) và dấu tick chọn được gắn gọn gàng ở góc trên thumbnail.
    - Tên khung hiển thị đầy đủ tối đa 2 dòng với word wrap, chiều cao đồng bộ.
    - Trạng thái chọn với viền Muted Champagne mảnh và tick nhỏ.
    """
    clicked = Signal(str)  # frame_id

    def __init__(self, template: FrameTemplate, thumb_path: str, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.template = template
        self.thumb_path = thumb_path
        self._is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(180)
        self.setMaximumWidth(280)
        self.setFixedHeight(340)

        self._init_ui()
        self._update_style()

    def _init_ui(self):
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        # 1. KHU VỰC THUMBNAIL (Viewport chứa ảnh và badges)
        self.thumb_box = QFrame()
        self.thumb_box.setFixedHeight(260)
        self.thumb_box.setStyleSheet(f"""
            QFrame {{
                background-color: #CFCCC4;
                border-radius: 8px;
                border: none;
            }}
        """)
        box_layout = QVBoxLayout(self.thumb_box)
        box_layout.setContentsMargins(8, 8, 8, 8)
        box_layout.setSpacing(0)

        # Thanh overlay trên cùng bên trong thumbnail: Badge tỷ lệ (trái) & Dấu tick (phải)
        overlay_bar = QHBoxLayout()
        overlay_bar.setContentsMargins(0, 0, 0, 0)

        type_text = "2x6" if "2x6" in self.template.type else "4x6"
        lbl_type = QLabel(type_text)
        lbl_type.setAlignment(Qt.AlignCenter)
        lbl_type.setFixedSize(38, 20)
        lbl_type.setStyleSheet("""
            background-color: rgba(53, 54, 49, 0.78);
            color: #FFFFFF;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 800;
        """)
        overlay_bar.addWidget(lbl_type)

        overlay_bar.addStretch()

        self.lbl_check = QLabel()
        self.lbl_check.setPixmap(get_svg_pixmap("check", 12, "#FFFFFF"))
        self.lbl_check.setFixedSize(22, 22)
        self.lbl_check.setAlignment(Qt.AlignCenter)
        self.lbl_check.setStyleSheet(f"""
            background-color: {THEME_GOLD};
            border-radius: 11px;
        """)
        self.lbl_check.setVisible(self._is_selected)
        overlay_bar.addWidget(self.lbl_check)

        box_layout.addLayout(overlay_bar)

        # Thumbnail thực tế - Giữ đúng tỷ lệ ảnh gốc, căn giữa tuyệt đối
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setStyleSheet("background-color: transparent;")

        if self.thumb_path and os.path.exists(self.thumb_path):
            pix = QPixmap(self.thumb_path)
            # Tăng kích thước thumbnail để tận dụng tối đa không gian (max width 200, max height 230)
            self.lbl_thumb.setPixmap(pix.scaled(200, 230, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.lbl_thumb.setText(self.template.name)
            self.lbl_thumb.setStyleSheet(f"color: {THEME_TEXT_SECONDARY}; font-size: 12px;")

        box_layout.addWidget(self.lbl_thumb, 1, Qt.AlignCenter)
        card_layout.addWidget(self.thumb_box)

        # 2. TÊN KHUNG ẢNH (Hiển thị đầy đủ tối đa 2 dòng, word-wrap)
        self.lbl_name = QLabel(self.template.name)
        self.lbl_name.setAlignment(Qt.AlignCenter)
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setFixedHeight(38)
        self.lbl_name.setStyleSheet(f"""
            color: {THEME_TEXT_PRIMARY};
            font-weight: 700;
            font-size: 12px;
            line-height: 1.2;
            background: transparent;
        """)
        self.lbl_name.setToolTip(self.template.name)
        card_layout.addWidget(self.lbl_name)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.lbl_check.setVisible(selected)
        self._update_style()

    def _update_style(self):
        if self._is_selected:
            self.setStyleSheet(f"""
                FrameCard {{
                    background-color: #E3DFD6;
                    border: 2px solid {THEME_GOLD};
                    border-radius: 12px;
                }}
                FrameCard:hover {{
                    background-color: #E9E6DE;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                FrameCard {{
                    background-color: {THEME_SURFACE};
                    border: 1px solid {THEME_BORDER};
                    border-radius: 12px;
                }}
                FrameCard:hover {{
                    background-color: {THEME_INPUT_BG};
                    border: 1.5px solid {THEME_GOLD};
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.template.id)
        super().mousePressEvent(event)


class FrameGalleryPage(QWidget):
    """Trang Thư Viện Chọn Khung Ảnh chuẩn Soft Taupe Studio."""
    frame_selected = Signal(str)            # frame_id được chọn
    request_designer = Signal()            # Mở trình thiết kế khung

    CATEGORIES = [
        "Tất cả",
        "Sinh nhật",
        "Đám cưới",
        "Sự kiện",
        "Dễ thương",
        "Vintage",
        "Minimal",
        "Khác"
    ]

    def __init__(self, frame_mgr: FrameManager, config_mgr=None, auth_mgr=None, parent=None):
        super().__init__(parent)
        self.frame_mgr = frame_mgr
        self.config_mgr = config_mgr
        self.auth_mgr = auth_mgr

        self.current_category = "Tất cả"
        self.current_ratio = "Tất cả"
        self.selected_frame_id = ""
        if self.config_mgr:
            self.selected_frame_id = self.config_mgr.get("template_id", "wedding_2x6_strip3")

        self.cards: Dict[str, FrameCard] = {}
        self._current_cols = 4

        self._init_ui()
        self.refresh_gallery()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # 1. HEADER KHU VỰC CHỌN KHUNG ẢNH
        h_head = QHBoxLayout()
        h_head.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_pixmap("frame", 28, THEME_GOLD))
        h_head.addWidget(icon_lbl)

        v_titles = QVBoxLayout()
        v_titles.setSpacing(2)
        lbl_title = QLabel("CHỌN KHUNG ẢNH")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {THEME_TEXT_PRIMARY}; letter-spacing: 0.5px;")
        lbl_sub = QLabel("Nhấn vào khung bất kỳ để chọn và bắt đầu lượt chụp mới")
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {THEME_TEXT_SECONDARY};")
        v_titles.addWidget(lbl_title)
        v_titles.addWidget(lbl_sub)
        h_head.addLayout(v_titles)

        h_head.addStretch()

        # Nút chuyển sang trình thiết kế khung dành cho Quản trị viên
        self.btn_designer = QPushButton("Thiết Kế Khung Ảnh")
        self.btn_designer.setIcon(get_svg_icon("edit", 16, THEME_GOLD))
        self.btn_designer.setFixedHeight(38)
        self.btn_designer.setCursor(Qt.PointingHandCursor)
        self.btn_designer.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME_SURFACE};
                color: {THEME_TEXT_PRIMARY};
                border: 1.5px solid {THEME_BORDER};
                border-radius: 8px;
                padding: 4px 16px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {THEME_BG_SECONDARY};
                border: 1.5px solid {THEME_GOLD};
            }}
        """)
        self.btn_designer.setToolTip("Mở trình thiết kế kéo thả khung ảnh chuyên sâu (Cần mã PIN)")
        self.btn_designer.clicked.connect(self._on_open_designer_clicked)
        h_head.addWidget(self.btn_designer)

        main_layout.addLayout(h_head)

        # 2. THANH TÌM KIẾM & BỘ LỌC TỶ LỆ (TOP FILTER BAR CÂN ĐỐI)
        h_filter = QHBoxLayout()
        h_filter.setSpacing(12)

        # Ô tìm kiếm (Chiều rộng cân đối 280px)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Tìm tên khung ảnh...")
        self.txt_search.addAction(get_svg_icon("search", 16, THEME_TEXT_SECONDARY), QLineEdit.LeadingPosition)
        self.txt_search.setFixedHeight(38)
        self.txt_search.setFixedWidth(280)
        self.txt_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME_INPUT_BG};
                color: {THEME_TEXT_PRIMARY};
                border: 1.5px solid {THEME_BORDER};
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {THEME_GOLD};
                background-color: #FFFFFF;
            }}
        """)
        self.txt_search.textChanged.connect(lambda _: self.refresh_gallery())
        h_filter.addWidget(self.txt_search)

        # Pills chọn tỷ lệ (Tất cả, 2x6, 4x6)
        self.btn_ratio_all = QPushButton("Tất cả tỷ lệ")
        self.btn_ratio_2x6 = QPushButton("2x6 (Dải)")
        self.btn_ratio_4x6 = QPushButton("4x6 (Khổ chuẩn)")

        for b, r in [(self.btn_ratio_all, "Tất cả"), (self.btn_ratio_2x6, "2x6"), (self.btn_ratio_4x6, "4x6")]:
            b.setFixedHeight(38)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, ratio=r: self._on_ratio_clicked(ratio))
            h_filter.addWidget(b)

        h_filter.addStretch()

        # Nhãn đếm số lượng khung ảnh
        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet(f"color: {THEME_TEXT_SECONDARY}; font-size: 13px; font-weight: 600;")
        h_filter.addWidget(self.lbl_count)

        # Dropdown danh mục ẩn/dự phòng để tương thích backward compatibility nếu cần
        self.combo_cat = QComboBox()
        self.combo_cat.setVisible(False)
        self.combo_cat.addItems(["Tất cả danh mục"] + self.CATEGORIES[1:])
        self.combo_cat.currentIndexChanged.connect(self._on_combo_cat_changed)
        h_filter.addWidget(self.combo_cat)

        main_layout.addLayout(h_filter)

        # 3. NỘI DUNG CHÍNH (SIDEBAR DANH MỤC TRÁI + GRID KHUNG PHẢI)
        h_content = QHBoxLayout()
        h_content.setSpacing(18)

        # Sidebar danh mục bên trái (160px)
        sidebar = QFrame()
        sidebar.setFixedWidth(160)
        sidebar.setStyleSheet("background-color: transparent; border: none;")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(6)

        lbl_side_title = QLabel("DANH MỤC")
        lbl_side_title.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {THEME_TEXT_SECONDARY}; letter-spacing: 1px; padding-left: 4px; margin-bottom: 4px;")
        side_layout.addWidget(lbl_side_title)

        self.cat_buttons: Dict[str, QPushButton] = {}
        for cat in self.CATEGORIES:
            btn = QPushButton(cat)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, c=cat: self._on_category_clicked(c))
            self.cat_buttons[cat] = btn
            side_layout.addWidget(btn)

        side_layout.addStretch()
        h_content.addWidget(sidebar)

        # Grid khung ảnh bên phải (Scrollable với thanh cuộn tinh tế không che nội dung)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: transparent;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {THEME_BORDER};
                border-radius: 4px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {THEME_GOLD};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.grid_content = QWidget()
        self.grid_content.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_content)
        # Margin bên phải 16px để thanh cuộn 8px hoàn toàn không đè lên thẻ ngoài cùng
        self.grid_layout.setContentsMargins(4, 4, 16, 16)
        self.grid_layout.setSpacing(14)

        self.scroll.setWidget(self.grid_content)
        h_content.addWidget(self.scroll, 1)

        main_layout.addLayout(h_content, 1)

        self._update_filter_ui()

    def _recalculate_columns(self) -> int:
        """Tự động tính toán số cột thẻ tối ưu theo chiều rộng thực tế của vùng cuộn."""
        viewport_w = 0
        if hasattr(self, "scroll") and self.scroll.viewport():
            viewport_w = self.scroll.viewport().width()
        if viewport_w <= 0:
            viewport_w = max(400, self.width() - 220)

        # Responsive: 4 cột ở 1366, 5 cột ở 1600, 6 cột ở 1920
        if viewport_w < 700:
            return 3
        elif viewport_w < 1050:
            return 4
        elif viewport_w < 1400:
            return 5
        else:
            return 6

    def showEvent(self, event):
        """Khi hiển thị tab, cập nhật số cột thẻ chính xác theo chiều rộng thực tế."""
        super().showEvent(event)
        cols = self._recalculate_columns()
        if cols != self._current_cols and self.cards:
            self._relayout_cards(cols)

    def resizeEvent(self, event):
        """Khi thay đổi kích thước cửa sổ, tự động bố trí lại số cột thẻ nếu cần."""
        super().resizeEvent(event)
        new_cols = self._recalculate_columns()
        if new_cols != self._current_cols and self.cards:
            self._relayout_cards(new_cols)

    def _relayout_cards(self, cols: int):
        """Bố trí lại vị trí các card hiện có theo số cột mới mà không tạo lại widget."""
        self._current_cols = cols
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)
        for idx, (fid, card) in enumerate(self.cards.items()):
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def _on_category_clicked(self, category: str):
        self.current_category = category
        idx = self.combo_cat.findText(category if category != "Tất cả" else "Tất cả danh mục")
        if idx >= 0:
            self.combo_cat.blockSignals(True)
            self.combo_cat.setCurrentIndex(idx)
            self.combo_cat.blockSignals(False)
        self._update_filter_ui()
        self.refresh_gallery()

    def _on_combo_cat_changed(self, idx: int):
        text = self.combo_cat.currentText()
        self.current_category = "Tất cả" if text == "Tất cả danh mục" else text
        self._update_filter_ui()
        self.refresh_gallery()

    def _on_ratio_clicked(self, ratio: str):
        self.current_ratio = ratio
        self._update_filter_ui()
        self.refresh_gallery()

    def _update_filter_ui(self):
        # Cập nhật style nút danh mục bên sidebar
        for cat, btn in self.cat_buttons.items():
            if cat == self.current_category:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {THEME_GOLD};
                        color: #FFFFFF;
                        font-weight: bold;
                        border: none;
                        border-radius: 8px;
                        text-align: left;
                        padding-left: 14px;
                        font-size: 13px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {THEME_SURFACE};
                        color: {THEME_TEXT_PRIMARY};
                        border: 1px solid {THEME_BORDER};
                        border-radius: 8px;
                        text-align: left;
                        padding-left: 14px;
                        font-size: 13px;
                    }}
                    QPushButton:hover {{
                        background-color: {THEME_INPUT_BG};
                        border: 1px solid {THEME_GOLD};
                    }}
                """)

        # Cập nhật style nút lọc tỷ lệ
        active_ratio_style = f"""
            QPushButton {{
                background-color: {THEME_GOLD};
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 8px;
                padding: 4px 16px;
                border: none;
                font-size: 13px;
            }}
        """
        normal_ratio_style = f"""
            QPushButton {{
                background-color: {THEME_SURFACE};
                color: {THEME_TEXT_PRIMARY};
                border: 1.5px solid {THEME_BORDER};
                border-radius: 8px;
                padding: 4px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {THEME_INPUT_BG};
                border: 1.5px solid {THEME_GOLD};
            }}
        """

        self.btn_ratio_all.setStyleSheet(active_ratio_style if self.current_ratio == "Tất cả" else normal_ratio_style)
        self.btn_ratio_2x6.setStyleSheet(active_ratio_style if self.current_ratio == "2x6" else normal_ratio_style)
        self.btn_ratio_4x6.setStyleSheet(active_ratio_style if self.current_ratio == "4x6" else normal_ratio_style)

    def _reload_frames(self):
        """Hàm dự phòng gọi từ frame_tab_container."""
        self.refresh_gallery()

    def refresh_gallery(self):
        """Quét và bố trí lại toàn bộ danh sách card khung theo bộ lọc hiện tại."""
        # Xóa các card cũ khỏi grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.cards.clear()

        search_q = self.txt_search.text().strip()
        templates = self.frame_mgr.list_frames(
            category=self.current_category,
            ratio=self.current_ratio,
            search_query=search_q
        )

        total_all = len(self.frame_mgr.list_frames())
        shown = len(templates)
        self.lbl_count.setText(f"Hiển thị {shown}/{total_all} mẫu khung")

        # Mặc định chọn khung đầu tiên nếu chưa chọn khung nào
        if not self.selected_frame_id and templates:
            self.selected_frame_id = templates[0].id

        cols = self._recalculate_columns()
        self._current_cols = cols

        for idx, tmpl in enumerate(templates):
            thumb_path = self.frame_mgr.get_or_create_thumbnail(tmpl, max_width=240, max_height=360)
            is_sel = (tmpl.id == self.selected_frame_id)
            card = FrameCard(tmpl, thumb_path, is_selected=is_sel, parent=self.grid_content)
            card.clicked.connect(self._on_card_clicked)
            self.cards[tmpl.id] = card

            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def _on_card_clicked(self, frame_id: str):
        """Xử lý khi người dùng chọn khung ảnh: cập nhật trạng thái và chuyển sang luồng chụp."""
        self.selected_frame_id = frame_id
        for fid, c in self.cards.items():
            c.set_selected(fid == frame_id)

        if self.config_mgr:
            self.config_mgr.set("template_id", frame_id)
            self.config_mgr.save()

        logger.info(f"Đã chọn khung ảnh: {frame_id}")
        self.frame_selected.emit(frame_id)

    def _on_open_designer_clicked(self):
        """Mở trình thiết kế khung ảnh (Yêu cầu xác thực PIN nếu chưa mở khóa)."""
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Xác Thực Trình Thiết Kế Khung"):
                return
        self.request_designer.emit()
