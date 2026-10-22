"""
1998 TEAM — Photobooth Frame Gallery Page (Thư Viện Chọn Khung Ảnh)
Matches exact design of Panel 1:
- Search box & ratio filter pills (Tất cả, 2x6, 4x6).
- Category sidebar (Tất cả, Sinh nhật, Đám cưới, Sự kiện, Dễ thương, Vintage, Minimal, Khác).
- Responsive grid of actual rendered thumbnails with selection checkmark & format badge.
- Clicking any frame selects it and transitions into capture flow.
- Admin button to open Frame Designer.
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
from vietphotobooth.desktop.icons import get_svg_icon, get_svg_pixmap, COLOR_GOLD, COLOR_WHITE, COLOR_SLATE, COLOR_BLUE
from vietphotobooth.core.logger import get_logger

logger = get_logger()

class FrameCard(QFrame):
    """Thẻ hiển thị khung ảnh với thumbnail thực tế, badge tỷ lệ và dấu tích chọn."""
    clicked = Signal(str)  # frame_id

    def __init__(self, template: FrameTemplate, thumb_path: str, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.template = template
        self.thumb_path = thumb_path
        self._is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self._init_ui()
        self._update_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header card: Checkmark khi chọn (trái) & Badge khổ ảnh (phải)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        self.lbl_check = QLabel()
        self.lbl_check.setPixmap(get_svg_pixmap("check", 14, "#070A12"))
        self.lbl_check.setFixedSize(22, 22)
        self.lbl_check.setAlignment(Qt.AlignCenter)
        self.lbl_check.setStyleSheet(
            "background-color: #D4AF37; border-radius: 11px;"
        )
        self.lbl_check.setVisible(self._is_selected)
        top_bar.addWidget(self.lbl_check)
        top_bar.addStretch()

        type_text = "2x6" if "2x6" in self.template.type else "4x6"
        lbl_type = QLabel(type_text)
        lbl_type.setAlignment(Qt.AlignCenter)
        lbl_type.setFixedSize(36, 18)
        lbl_type.setStyleSheet(
            "background-color: #1E3A8A; color: #93C5FD; border-radius: 4px; font-size: 11px; font-weight: bold;"
        )
        top_bar.addWidget(lbl_type)
        layout.addLayout(top_bar)

        # Thumbnail thực tế
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setFixedHeight(230)
        self.lbl_thumb.setStyleSheet("background-color: transparent;")

        if self.thumb_path and os.path.exists(self.thumb_path):
            pix = QPixmap(self.thumb_path)
            self.lbl_thumb.setPixmap(pix.scaled(130, 230, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.lbl_thumb.setText(self.template.name)
            self.lbl_thumb.setStyleSheet("color: #94A3B8; font-size: 12px;")

        layout.addWidget(self.lbl_thumb, 1, Qt.AlignCenter)

        # Tên khung
        self.lbl_name = QLabel(self.template.name)
        self.lbl_name.setAlignment(Qt.AlignCenter)
        self.lbl_name.setStyleSheet("color: #F8FAFC; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.lbl_name)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.lbl_check.setVisible(selected)
        self._update_style()

    def _update_style(self):
        if self._is_selected:
            self.setStyleSheet(
                "FrameCard { background-color: #111C30; border: 2.5px solid #D4AF37; border-radius: 12px; }"
                "FrameCard:hover { background-color: #16243E; }"
            )
        else:
            self.setStyleSheet(
                "FrameCard { background-color: #0E1626; border: 1.5px solid #1E2D4A; border-radius: 12px; }"
                "FrameCard:hover { background-color: #142036; border: 1.5px solid #D4AF37; }"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.template.id)
        super().mousePressEvent(event)


class FrameGalleryPage(QWidget):
    """Trang Thư Viện Chọn Khung Ảnh chuẩn 1998 TEAM Photobooth."""
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

        self._init_ui()
        self.refresh_gallery()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(14)

        # 1. HEADER KHU VỰC CHỌN KHUNG ẢNH
        h_head = QHBoxLayout()
        h_head.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_pixmap("frame", 28, COLOR_GOLD))
        h_head.addWidget(icon_lbl)

        v_titles = QVBoxLayout()
        lbl_title = QLabel("CHỌN KHUNG ẢNH")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 900; color: #D4AF37; letter-spacing: 0.5px;")
        lbl_sub = QLabel("Nhấn vào khung bất kỳ để bắt đầu chụp")
        lbl_sub.setStyleSheet("font-size: 13px; color: #94A3B8;")
        v_titles.addWidget(lbl_title)
        v_titles.addWidget(lbl_sub)
        h_head.addLayout(v_titles)

        h_head.addStretch()

        # Nút chuyển sang trình thiết kế khung dành cho Quản trị viên
        self.btn_designer = QPushButton("Thiết Kế Khung Ảnh")
        self.btn_designer.setIcon(get_svg_icon("edit", 16, COLOR_GOLD))
        self.btn_designer.setFixedHeight(36)
        self.btn_designer.setCursor(Qt.PointingHandCursor)
        self.btn_designer.setObjectName("btn_secondary")
        self.btn_designer.setToolTip("Mở trình thiết kế kéo thả khung ảnh chuyên sâu")
        self.btn_designer.clicked.connect(self._on_open_designer_clicked)
        h_head.addWidget(self.btn_designer)

        main_layout.addLayout(h_head)

        # 2. THANH TÌM KIẾM & BỘ LỌC TỶ LỆ (TOP FILTER BAR)
        h_filter = QHBoxLayout()
        h_filter.setSpacing(10)

        # Ô tìm kiếm
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Tìm tên khung...")
        self.txt_search.addAction(get_svg_icon("search", 16, COLOR_SLATE), QLineEdit.LeadingPosition)
        self.txt_search.setFixedHeight(38)
        self.txt_search.setStyleSheet(
            "QLineEdit { background-color: #0E1626; color: #F8FAFC; border: 1px solid #1E2D4A; "
            "border-radius: 8px; padding: 4px 12px; font-size: 13px; }"
            "QLineEdit:focus { border: 1.5px solid #D4AF37; }"
        )
        self.txt_search.textChanged.connect(lambda _: self.refresh_gallery())
        h_filter.addWidget(self.txt_search, 1)

        # Pills chọn tỷ lệ (Tất cả, 2x6, 4x6)
        self.btn_ratio_all = QPushButton("Tất cả")
        self.btn_ratio_2x6 = QPushButton("2x6")
        self.btn_ratio_4x6 = QPushButton("4x6")

        for b, r in [(self.btn_ratio_all, "Tất cả"), (self.btn_ratio_2x6, "2x6"), (self.btn_ratio_4x6, "4x6")]:
            b.setFixedHeight(38)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, ratio=r: self._on_ratio_clicked(ratio))
            h_filter.addWidget(b)

        # Dropdown danh mục
        self.combo_cat = QComboBox()
        self.combo_cat.setFixedHeight(38)
        self.combo_cat.addItems(["Tất cả danh mục"] + self.CATEGORIES[1:])
        self.combo_cat.setStyleSheet(
            "QComboBox { background-color: #0E1626; color: #F8FAFC; border: 1px solid #1E2D4A; "
            "border-radius: 8px; padding: 4px 12px; min-width: 140px; font-size: 13px; }"
            "QComboBox:hover { border: 1px solid #D4AF37; }"
        )
        self.combo_cat.currentIndexChanged.connect(self._on_combo_cat_changed)
        h_filter.addWidget(self.combo_cat)

        main_layout.addLayout(h_filter)

        # 3. NỘI DUNG CHÍNH (SIDEBAR DANH MỤC TRÁI + GRID KHUNG PHẢI)
        h_content = QHBoxLayout()
        h_content.setSpacing(16)

        # Sidebar danh mục bên trái
        sidebar = QFrame()
        sidebar.setFixedWidth(160)
        sidebar.setStyleSheet("background-color: transparent;")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(6)

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

        # Grid khung ảnh bên phải (Scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent;")

        self.grid_content = QWidget()
        self.grid_content.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_content)
        self.grid_layout.setContentsMargins(0, 0, 8, 0)
        self.grid_layout.setSpacing(14)

        scroll.setWidget(self.grid_content)
        h_content.addWidget(scroll, 1)

        main_layout.addLayout(h_content, 1)

        self._update_filter_ui()

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
        # Update category sidebar pills
        for cat, btn in self.cat_buttons.items():
            if cat == self.current_category:
                btn.setStyleSheet(
                    "background-color: #D4AF37; color: #070A12; font-weight: bold; border: none; "
                    "border-radius: 8px; text-align: left; padding-left: 14px; font-size: 13px;"
                )
            else:
                btn.setStyleSheet(
                    "background-color: #0E1626; color: #CBD5E1; border: 1px solid #1E2D4A; "
                    "border-radius: 8px; text-align: left; padding-left: 14px; font-size: 13px;"
                )

        # Update ratio filter buttons
        active_ratio_style = "background-color: #D4AF37; color: #070A12; font-weight: bold; border-radius: 8px; padding: 4px 16px; border: none;"
        normal_ratio_style = "background-color: #0E1626; color: #94A3B8; border: 1px solid #1E2D4A; border-radius: 8px; padding: 4px 16px;"

        self.btn_ratio_all.setStyleSheet(active_ratio_style if self.current_ratio == "Tất cả" else normal_ratio_style)
        self.btn_ratio_2x6.setStyleSheet(active_ratio_style if self.current_ratio == "2x6" else normal_ratio_style)
        self.btn_ratio_4x6.setStyleSheet(active_ratio_style if self.current_ratio == "4x6" else normal_ratio_style)

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

        cols = 4  # 4 cột chuẩn như giao diện mẫu
        for idx, tmpl in enumerate(templates):
            thumb_path = self.frame_mgr.get_or_create_thumbnail(tmpl, max_width=180, max_height=360)
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
