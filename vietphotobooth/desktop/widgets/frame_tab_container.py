"""
1998 TEAM — Frame Tab Container
Integrates the Luxury Frame Gallery (Panel 1) and the Visual Frame Designer.
Defaults to FrameGalleryPage for intuitive template selection and browsing.
Allows admins to switch to FrameDesignerPage for full slot/layer customization.
Maintains 100% attribute backward-compatibility with tests via delegation.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QSize

from vietphotobooth.frames.frame_manager import FrameManager
from vietphotobooth.desktop.widgets.frame_gallery_page import FrameGalleryPage
from vietphotobooth.desktop.widgets.frame_designer_page import FrameDesignerPage
from vietphotobooth.desktop.icons import get_svg_icon, COLOR_GOLD, COLOR_NAVY, COLOR_SLATE

class FrameTabContainer(QWidget):
    """Container tích hợp Thư Viện Chọn Khung Ảnh và Trình Thiết Kế Khung."""

    frame_changed = Signal(str)
    frame_selected = Signal(str)

    def minimumSizeHint(self) -> QSize:
        return QSize(720, 420)

    def __init__(self, frame_manager: FrameManager, auth_mgr=None, parent=None):
        super().__init__(parent)
        self.frame_manager = frame_manager
        self.auth_mgr = auth_mgr

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.stack = QStackedWidget(self)
        main_layout.addWidget(self.stack)

        # 1. Thư viện chọn khung ảnh (Panel 1 - Default View)
        self.gallery_page = FrameGalleryPage(self.frame_manager, auth_mgr=self.auth_mgr)
        self.stack.addWidget(self.gallery_page)  # Index 0

        # 2. Trình thiết kế khung in ảnh (Designer View)
        self.designer_page = FrameDesignerPage(self.frame_manager)
        self.stack.addWidget(self.designer_page) # Index 1

        # Nút quay lại thư viện trên thanh công cụ của Designer
        self._setup_designer_back_button()

        # Kết nối sự kiện
        self.gallery_page.request_designer.connect(self._open_designer)
        self.gallery_page.frame_selected.connect(self._on_gallery_frame_selected)
        self.designer_page.frame_changed.connect(self._on_designer_frame_saved)

    def _setup_designer_back_button(self):
        """Chèn nút Quay Lại Thư Viện lên thanh công cụ của designer_page."""
        try:
            # Tìm layout đầu tiên của cột trái designer_page
            left_col = self.designer_page.layout().itemAt(0).layout()
            top_bar = left_col.itemAt(0).layout()

            btn_back = QPushButton("⬅️ Thư Viện Khung")
            btn_back.setIcon(get_svg_icon("frame", size=15, color=COLOR_GOLD))
            btn_back.setObjectName("btn_secondary")
            btn_back.setCursor(Qt.PointingHandCursor)
            btn_back.setToolTip("Quay lại màn hình duyệt & chọn mẫu khung in ảnh")
            btn_back.clicked.connect(self.back_to_gallery)

            top_bar.insertWidget(0, btn_back)
        except Exception:
            pass

    def _open_designer(self):
        """Mở Trình thiết kế khung in ảnh sau khi xác thực mã PIN quản trị."""
        if self.auth_mgr and not self.auth_mgr.is_authenticated():
            if not self.auth_mgr.prompt_pin_dialog(self, "Mở Trình Thiết Kế Khung Ảnh"):
                return

        # Nạp lại khung hiện tại vào designer
        if hasattr(self.gallery_page, "selected_frame_id") and self.gallery_page.selected_frame_id:
            idx = self.designer_page.combo_frames.findData(self.gallery_page.selected_frame_id)
            if idx >= 0:
                self.designer_page.combo_frames.setCurrentIndex(idx)

        self.stack.setCurrentIndex(1)

    def back_to_gallery(self):
        """Quay lại giao diện Thư viện khung ảnh."""
        self.gallery_page._reload_frames()
        self.stack.setCurrentIndex(0)

    def _on_gallery_frame_selected(self, frame_id: str):
        """Chuyển tiếp tín hiệu khi khách hoặc người dùng chọn một khung từ Thư viện."""
        self.frame_selected.emit(frame_id)
        self.frame_changed.emit(frame_id)

    def _on_designer_frame_saved(self, frame_id: str):
        """Khi designer lưu hoặc cập nhật khung ảnh."""
        self.gallery_page._reload_frames()
        self.frame_changed.emit(frame_id)

    def __getattr__(self, name):
        """Ủy quyền mọi thuộc tính chưa có cho designer_page để tương thích hoàn toàn các test."""
        if "designer_page" in self.__dict__:
            return getattr(self.designer_page, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
