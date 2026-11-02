"""
1998 TEAM PHOTOBOOTH v2.0.0 — SESSION PHOTO LIGHTBOX DIALOG
Cung cấp cửa sổ xem trước ảnh thành phẩm và toàn bộ ảnh gốc của từng lượt chụp (Session Preview & Lightbox).
Tích hợp:
- Hiển thị ảnh thành phẩm độ phân giải cao, hỗ trợ chuyển đổi xem từng ảnh gốc.
- Dải thumbnail trực quan cho từng shot chụp (photo_1, photo_2, photo_3, ...).
- Thông tin metadata chi tiết: Mã lượt, độ phân giải, dung lượng, thời gian, trạng thái đồng bộ Google Drive.
- Thao tác nhanh: In lại ngay, mở mã QR, mở thư mục trên đĩa, xuất tệp lượt chụp.
"""

import os
import shutil
from typing import Optional, List, Dict
from datetime import datetime
from PIL import Image

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QImage, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QFileDialog, QMessageBox, QWidget, QSizePolicy
)

from vietphotobooth.core.events import EventManager
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.cloud import SyncManager, SyncStatus
from vietphotobooth.desktop.icons import (
    get_svg_icon, COLOR_GOLD, COLOR_GOLD_LIGHT, COLOR_WHITE,
    COLOR_NAVY, COLOR_SLATE, COLOR_GREEN
)


class SessionLightboxDialog(QDialog):
    """
    Cửa sổ xem trước chuyên nghiệp (Photo Lightbox) cho từng lượt chụp của sự kiện.
    """
    def __init__(
        self,
        session_id: str,
        event_name: str,
        event_mgr: EventManager,
        print_mgr: Optional[PrintManager] = None,
        token_mgr: Optional[TokenManager] = None,
        sync_mgr: Optional[SyncManager] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.session_id = session_id
        self.event_name = event_name
        self.event_mgr = event_mgr
        self.print_mgr = print_mgr
        self.token_mgr = token_mgr
        self.sync_mgr = sync_mgr

        self.setWindowTitle(f"1998 TEAM — Chi Tiết Lượt Chụp [{session_id}]")
        self.resize(960, 680)
        self.setMinimumSize(800, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #D8D0C3;
                color: #34312E;
            }
        """)

        self.dirs = self.event_mgr.get_event_dirs(self.event_name)
        self.final_path = self._find_final_photo_path()
        self.original_photos: List[str] = self._find_original_photos()
        self.current_preview_path: Optional[str] = self.final_path

        self._init_ui()
        self._load_active_preview()

    def _find_final_photo_path(self) -> Optional[str]:
        final_dir = self.dirs["final"]
        if not os.path.exists(final_dir):
            return None
        for ext in (".jpg", ".jpeg", ".png"):
            p = os.path.join(final_dir, f"{self.session_id}_final{ext}")
            if os.path.exists(p):
                return p
            p2 = os.path.join(final_dir, f"{self.session_id}{ext}")
            if os.path.exists(p2):
                return p2
        return None

    def _find_original_photos(self) -> List[str]:
        orig_dir = os.path.join(self.dirs["originals"], self.session_id)
        if not os.path.exists(orig_dir):
            return []
        photos = []
        for f in sorted(os.listdir(orig_dir)):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                photos.append(os.path.join(orig_dir, f))
        return photos

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # 1. HEADER BAR
        h_head = QHBoxLayout()
        h_head.setSpacing(10)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(get_svg_icon("camera", 24, COLOR_GOLD).pixmap(24, 24))
        h_head.addWidget(lbl_icon)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel(f"LƯỢT CHỤP: <span style='color: #B89555;'>{self.session_id}</span>")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #34312E;")
        v_head.addWidget(lbl_title)

        lbl_sub = QLabel(f"Sự kiện: <b>{self.event_name}</b> • 1998 TEAM Photobooth Studio")
        lbl_sub.setStyleSheet("font-size: 11px; color: #777067;")
        v_head.addWidget(lbl_sub)
        h_head.addLayout(v_head)

        h_head.addStretch(1)

        btn_export = QPushButton(" Xuất Thư Mục Lượt")
        btn_export.setIcon(get_svg_icon("paper", 14, COLOR_SLATE))
        btn_export.setObjectName("btn_secondary")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                color: #34312E;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                border-color: #B89555;
                background-color: #C9BDAA;
            }
        """)
        btn_export.clicked.connect(self._export_session)
        h_head.addWidget(btn_export)

        btn_open_folder = QPushButton(" Mở Thư Mục")
        btn_open_folder.setIcon(get_svg_icon("folder", 14, COLOR_GOLD))
        btn_open_folder.setCursor(Qt.PointingHandCursor)
        btn_open_folder.setStyleSheet("""
            QPushButton {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                color: #34312E;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                border-color: #B89555;
                background-color: #C9BDAA;
            }
        """)
        btn_open_folder.clicked.connect(self._open_session_folder)
        h_head.addWidget(btn_open_folder)

        main_layout.addLayout(h_head)

        # 2. BODY KHU VỰC CHÍNH (Split: Cột ảnh lớn + Cột thông tin & thao tác)
        h_body = QHBoxLayout()
        h_body.setSpacing(14)

        # Left / Center: Khung hiển thị ảnh lớn (Interactive Viewport)
        self.frame_viewer = QFrame()
        self.frame_viewer.setStyleSheet("""
            QFrame {
                background-color: #17191C;
                border: 1.5px solid #2A2D33;
                border-radius: 8px;
            }
        """)
        l_viewer = QVBoxLayout(self.frame_viewer)
        l_viewer.setContentsMargins(10, 10, 10, 10)
        l_viewer.setAlignment(Qt.AlignCenter)

        self.lbl_image_display = QLabel()
        self.lbl_image_display.setAlignment(Qt.AlignCenter)
        self.lbl_image_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_image_display.setStyleSheet("border: none; background: transparent;")
        l_viewer.addWidget(self.lbl_image_display)

        self.lbl_current_label = QLabel("Đang xem: Ảnh Thành Phẩm Ghép In")
        self.lbl_current_label.setAlignment(Qt.AlignCenter)
        self.lbl_current_label.setStyleSheet("color: #B89555; font-size: 11px; font-weight: 700; padding: 4px;")
        l_viewer.addWidget(self.lbl_current_label)

        h_body.addWidget(self.frame_viewer, 3)

        # Right: Thông tin chi tiết & Bảng điều khiển
        v_info = QVBoxLayout()
        v_info.setSpacing(12)

        # Metadata Card
        card_meta = QFrame()
        card_meta.setStyleSheet("""
            QFrame {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                border-radius: 8px;
            }
        """)
        l_meta = QVBoxLayout(card_meta)
        l_meta.setContentsMargins(14, 12, 14, 12)
        l_meta.setSpacing(8)

        lbl_meta_h = QLabel("THÔNG TIN LƯỢT CHỤP")
        lbl_meta_h.setStyleSheet("color: #34312E; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        l_meta.addWidget(lbl_meta_h)

        self.lbl_res = QLabel("Độ phân giải: Đang tải...")
        self.lbl_res.setStyleSheet("color: #34312E; font-size: 12px; font-weight: 600;")
        l_meta.addWidget(self.lbl_res)

        self.lbl_size = QLabel("Dung lượng tệp: --")
        self.lbl_size.setStyleSheet("color: #34312E; font-size: 12px; font-weight: 600;")
        l_meta.addWidget(self.lbl_size)

        self.lbl_time = QLabel("Thời gian tạo: --")
        self.lbl_time.setStyleSheet("color: #777067; font-size: 12px;")
        l_meta.addWidget(self.lbl_time)

        self.lbl_shots_count = QLabel(f"Số ảnh gốc chụp: {len(self.original_photos)} ảnh")
        self.lbl_shots_count.setStyleSheet("color: #777067; font-size: 12px;")
        l_meta.addWidget(self.lbl_shots_count)

        self.lbl_sync_badge = QLabel("Đồng bộ Cloud: Kiểm tra...")
        self.lbl_sync_badge.setStyleSheet("color: #B89555; font-size: 12px; font-weight: bold;")
        l_meta.addWidget(self.lbl_sync_badge)

        v_info.addWidget(card_meta)

        # Quick Actions Card
        card_actions = QFrame()
        card_actions.setStyleSheet("""
            QFrame {
                background-color: #E7DFD2;
                border: 1.5px solid #BEB3A3;
                border-radius: 8px;
            }
        """)
        l_act = QVBoxLayout(card_actions)
        l_act.setContentsMargins(14, 12, 14, 12)
        l_act.setSpacing(8)

        lbl_act_h = QLabel("THAO TÁC NHANH")
        lbl_act_h.setStyleSheet("color: #34312E; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        l_act.addWidget(lbl_act_h)

        self.btn_print_now = QPushButton(" In Ngay Lượt Này")
        self.btn_print_now.setIcon(get_svg_icon("printer", 16, COLOR_NAVY))
        self.btn_print_now.setFixedHeight(38)
        self.btn_print_now.setCursor(Qt.PointingHandCursor)
        self.btn_print_now.setStyleSheet("""
            QPushButton {
                background: #B89555;
                color: #FFFFFF;
                font-weight: 800;
                font-size: 12px;
                border-radius: 6px;
                border: 1px solid #8F7038;
            }
            QPushButton:hover {
                background: #CDB07B;
            }
            QPushButton:pressed {
                background: #8F7038;
            }
        """)
        self.btn_print_now.clicked.connect(self._print_current_session)
        l_act.addWidget(self.btn_print_now)

        self.btn_open_qr = QPushButton(" Quét Mã QR Nhận Ảnh")
        self.btn_open_qr.setIcon(get_svg_icon("camera", 16, COLOR_GOLD))
        self.btn_open_qr.setFixedHeight(36)
        self.btn_open_qr.setCursor(Qt.PointingHandCursor)
        self.btn_open_qr.setStyleSheet("""
            QPushButton {
                background-color: #EFE8DC;
                border: 1.5px solid #BEB3A3;
                color: #34312E;
                font-size: 12px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                border-color: #B89555;
                color: #34312E;
                background-color: #C9BDAA;
            }
        """)
        self.btn_open_qr.clicked.connect(self._show_qr_code)
        l_act.addWidget(self.btn_open_qr)

        v_info.addWidget(card_actions)
        v_info.addStretch(1)

        btn_close = QPushButton("Đóng")
        btn_close.setFixedHeight(34)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #EFE8DC;
                border: 1.5px solid #BEB3A3;
                color: #777067;
                font-size: 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #C9BDAA;
                color: #34312E;
            }
        """)
        btn_close.clicked.connect(self.accept)
        v_info.addWidget(btn_close)

        h_body.addLayout(v_info, 1)
        main_layout.addLayout(h_body, 1)

        # 3. THUMBNAIL STRIP DƯỚI ĐÁY (Hiển thị tất cả ảnh thuộc lượt: Final + Originals)
        lbl_strip_h = QLabel("<b>DANH SÁCH ẢNH TRONG LƯỢT:</b> Nhấp để chuyển ảnh xem chi tiết")
        lbl_strip_h.setStyleSheet("color: #777067; font-size: 11px;")
        main_layout.addWidget(lbl_strip_h)

        scroll_strip = QScrollArea()
        scroll_strip.setFixedHeight(95)
        scroll_strip.setWidgetResizable(True)
        scroll_strip.setStyleSheet("""
            QScrollArea {
                background-color: #17191C;
                border: 1px solid #2A2D33;
                border-radius: 6px;
            }
        """)
        strip_content = QWidget()
        strip_content.setStyleSheet("background-color: transparent;")
        h_strip = QHBoxLayout(strip_content)
        h_strip.setContentsMargins(8, 6, 8, 6)
        h_strip.setSpacing(10)
        h_strip.setAlignment(Qt.AlignLeft)

        # Thumbnail 1: Final
        if self.final_path and os.path.exists(self.final_path):
            btn_th_final = self._create_thumbnail_btn(self.final_path, "Thành phẩm", is_final=True)
            h_strip.addWidget(btn_th_final)

        # Thumbnails 2..N: Originals
        for idx, orig_p in enumerate(self.original_photos):
            base_n = os.path.basename(orig_p)
            btn_th = self._create_thumbnail_btn(orig_p, f"Shot #{idx+1}", is_final=False)
            h_strip.addWidget(btn_th)

        if not self.final_path and not self.original_photos:
            lbl_empty = QLabel("Không tìm thấy tệp ảnh nào thuộc lượt chụp này.")
            lbl_empty.setStyleSheet("color: #777067; font-size: 12px;")
            h_strip.addWidget(lbl_empty)

        h_strip.addStretch(1)
        scroll_strip.setWidget(strip_content)
        main_layout.addWidget(scroll_strip)

    def _create_thumbnail_btn(self, path: str, label: str, is_final: bool = False) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(65, 75)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(f"{label}: {os.path.basename(path)}")

        # Tạo thumbnail icon nhanh
        pix = QPixmap(path)
        if not pix.isNull():
            btn.setIcon(QIcon(pix.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            btn.setIconSize(QSize(50, 50))
        btn.setText(label)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #E7DFD2;
                border: 1.5px solid {"#B89555" if is_final else "#BEB3A3"};
                border-radius: 6px;
                color: #34312E;
                font-size: 9px;
                font-weight: bold;
                padding-top: 2px;
            }}
            QPushButton:hover {{
                border-color: #B89555;
                background-color: #C9BDAA;
            }}
        """)
        btn.clicked.connect(lambda: self._select_preview(path, label))
        return btn

    def _select_preview(self, path: str, label: str):
        self.current_preview_path = path
        self.lbl_current_label.setText(f"Đang xem: {label} ({os.path.basename(path)})")
        self._load_active_preview()

    def _load_active_preview(self):
        if not self.current_preview_path or not os.path.exists(self.current_preview_path):
            self.lbl_image_display.setText("Không có ảnh hiển thị")
            return

        pix = QPixmap(self.current_preview_path)
        if not pix.isNull():
            scaled = pix.scaled(
                self.frame_viewer.width() - 30,
                self.frame_viewer.height() - 60,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.lbl_image_display.setPixmap(scaled)

            # Đọc metadata bằng PIL
            try:
                with Image.open(self.current_preview_path) as im:
                    w, h = im.size
                    self.lbl_res.setText(f"Độ phân giải: <b>{w} × {h} px</b>")
            except Exception:
                self.lbl_res.setText(f"Độ phân giải: <b>{pix.width()} × {pix.height()} px</b>")

            sz_bytes = os.path.getsize(self.current_preview_path)
            sz_mb = round(sz_bytes / (1024 * 1024), 2)
            self.lbl_size.setText(f"Dung lượng tệp: <b>{sz_mb} MB</b> ({sz_bytes:,} B)")

            mtime = os.path.getmtime(self.current_preview_path)
            dt_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S")
            self.lbl_time.setText(f"Thời gian tạo: <b>{dt_str}</b>")

        # Cập nhật Cloud status
        if self.sync_mgr and self.final_path:
            info = self.sync_mgr.get_file_info(self.final_path)
            if info:
                st = info.get("status")
                if st == SyncStatus.SYNCED:
                    self.lbl_sync_badge.setText("● Đã tải lên Google Drive")
                    self.lbl_sync_badge.setStyleSheet("color: #10B981; font-size: 12px; font-weight: bold;")
                elif st == SyncStatus.UPLOADING:
                    self.lbl_sync_badge.setText("● Đang đồng bộ lên Cloud...")
                    self.lbl_sync_badge.setStyleSheet("color: #F59E0B; font-size: 12px; font-weight: bold;")
                else:
                    self.lbl_sync_badge.setText("● Tải thất bại (Thử lại)")
                    self.lbl_sync_badge.setStyleSheet("color: #EF4444; font-size: 12px; font-weight: bold;")
            elif self.sync_mgr.is_ready():
                self.lbl_sync_badge.setText("● Sẵn sàng đồng bộ")
                self.lbl_sync_badge.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: bold;")
            else:
                self.lbl_sync_badge.setText("● Chưa kết nối Cloud")
                self.lbl_sync_badge.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold;")
        else:
            self.lbl_sync_badge.setText("● Lưu trữ cục bộ (Offline)")
            self.lbl_sync_badge.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._load_active_preview()

    def _print_current_session(self):
        if not self.final_path or not os.path.exists(self.final_path):
            QMessageBox.warning(self, "Thông Báo", "Không tìm thấy file ảnh thành phẩm để in lại.")
            return
        if self.print_mgr:
            self.print_mgr.print_image(self.final_path, copies=1)
            QMessageBox.information(self, "In Lại Thành Công", f"Đã gửi lệnh in cho lượt:\n{self.session_id}")
        else:
            QMessageBox.information(self, "In Lại", f"Đã mô phỏng lệnh in cho:\n{self.final_path}")

    def _show_qr_code(self):
        # Mở dialog QR chuẩn
        parent_widget = self.parent()
        if parent_widget and hasattr(parent_widget, "_show_qr_selected"):
            self.accept()
            parent_widget._show_qr_selected()
        else:
            QMessageBox.information(self, "QR Code", f"Mã lượt: {self.session_id}\nBạn có thể quét tải ảnh qua mạng LAN hoặc Google Drive.")

    def _open_session_folder(self):
        orig_dir = os.path.join(self.dirs["originals"], self.session_id)
        if os.path.exists(orig_dir):
            os.startfile(orig_dir)
        elif os.path.exists(self.dirs["final"]):
            os.startfile(self.dirs["final"])

    def _export_session(self):
        save_zip, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất File Lượt Chụp",
            f"{self.session_id}_package.zip",
            "ZIP Files (*.zip)"
        )
        if not save_zip:
            return

        import zipfile
        try:
            with zipfile.ZipFile(save_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                if self.final_path and os.path.exists(self.final_path):
                    zf.write(self.final_path, f"final/{os.path.basename(self.final_path)}")
                for orig_p in self.original_photos:
                    zf.write(orig_p, f"originals/{os.path.basename(orig_p)}")
            QMessageBox.information(
                self,
                "Xuất Hoàn Tất",
                f"Đã đóng gói toàn bộ ảnh lượt {self.session_id} vào:\n{save_zip}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Xuất File", f"Không thể xuất file ZIP: {e}")
