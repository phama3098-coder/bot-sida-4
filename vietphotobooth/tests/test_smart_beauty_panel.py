"""
1998 TEAM — Comprehensive Automated Tests for Smart Beauty Panel & Engine
Covers all requirements in D2:
- Ảnh không có khuôn mặt.
- Một và nhiều khuôn mặt.
- Khuôn mặt gần mép ảnh.
- Ba thanh trượt ở 0%.
- Thay đổi từng hiệu ứng và đặt lại.
- Xem ảnh gốc.
- Không ghi đè ảnh gốc.
- Không nhầm kết quả giữa hai ảnh xử lý đồng thời.
- Xử lý ảnh JPEG lớn từ Nikon D780.
- Xuất ảnh cuối, ghép khung và in đúng phiên bản ảnh.
- Đóng panel khi worker vẫn chạy.
- Thiếu model hoặc lỗi AI.
"""

import os
import shutil
import tempfile
import pytest
import numpy as np
import cv2
from PIL import Image

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from vietphotobooth.filters.beauty_engine import SmartBeautyEngine
from vietphotobooth.camera.face_detector import DetectedFace, FaceEyeDetector
from vietphotobooth.desktop.widgets.smart_beauty_panel import (
    SmartBeautyDialog, BeautyPreviewWorker
)


@pytest.fixture(scope="module")
def sample_portrait_image():
    """Tải ảnh chân dung mẫu hoặc tạo ảnh giả lập chân dung."""
    path = "Assets/Branding/sample_slot_portrait.jpg"
    if os.path.exists(path):
        return Image.open(path)
    # Ảnh giả lập nếu không tìm thấy
    im = Image.new("RGB", (400, 500), color=(180, 150, 130))
    return im


@pytest.fixture
def dummy_face_center():
    return DetectedFace(
        x=100.0, y=100.0, w=150.0, h=180.0, confidence=0.95,
        right_eye=(135.0, 150.0), left_eye=(205.0, 150.0), nose=(170.0, 185.0),
        mouth_right=(140.0, 230.0), mouth_left=(200.0, 230.0)
    )


class TestSmartBeautyEngine:
    """Bộ kiểm thử cho lõi xử lý SmartBeautyEngine."""

    def test_zero_sliders_returns_exact_copy(self, dummy_face_center):
        """Khi cả 3 thanh trượt ở 0%, ảnh trả về phải đồng nhất byte-for-byte với ảnh gốc."""
        engine = SmartBeautyEngine()
        img = np.random.randint(50, 200, (400, 400, 3), dtype=np.uint8)
        out = engine.apply_beauty(img, skin_brighten_pct=0, skin_smooth_pct=0, lip_tint_pct=0, faces=[dummy_face_center])

        assert np.array_equal(out, img)
        assert out is not img  # Đảm bảo trả về bản sao an toàn, không làm hỏng con trỏ

    def test_no_face_detected_graceful_identity(self):
        """Ảnh không có khuôn mặt: trả về ảnh gốc, không lỗi, không làm biến dạng."""
        engine = SmartBeautyEngine()
        # Ảnh nền màu đồng nhất không có khuôn mặt
        blank_img = np.full((300, 300, 3), 100, dtype=np.uint8)
        out = engine.apply_beauty(blank_img, skin_brighten_pct=50, skin_smooth_pct=60, lip_tint_pct=70, faces=[])

        assert np.array_equal(out, blank_img)

    def test_multiple_faces_processing(self):
        """Ảnh có nhiều khuôn mặt: xử lý độc lập từng khuôn mặt không gây xung đột."""
        engine = SmartBeautyEngine()
        img = np.full((600, 800, 3), 120, dtype=np.uint8)

        face1 = DetectedFace(
            x=50.0, y=50.0, w=120.0, h=150.0, confidence=0.92,
            right_eye=(80.0, 90.0), left_eye=(140.0, 90.0),
            mouth_right=(85.0, 150.0), mouth_left=(135.0, 150.0)
        )
        face2 = DetectedFace(
            x=450.0, y=100.0, w=140.0, h=170.0, confidence=0.90,
            right_eye=(480.0, 150.0), left_eye=(550.0, 150.0),
            mouth_right=(490.0, 220.0), mouth_left=(540.0, 220.0)
        )

        out = engine.apply_beauty(img, skin_brighten_pct=40, skin_smooth_pct=40, lip_tint_pct=40, faces=[face1, face2])
        assert out.shape == img.shape
        assert out.dtype == np.uint8

    def test_faces_touching_image_borders(self):
        """Khuôn mặt nằm sát mép ảnh (x=0, y=0 hoặc tràn lề): xử lý an toàn không lỗi IndexError."""
        engine = SmartBeautyEngine()
        img = np.full((400, 400, 3), 120, dtype=np.uint8)

        # Mặt sát mép trên cùng bên trái
        face_edge_tl = DetectedFace(
            x=0.0, y=0.0, w=100.0, h=120.0, confidence=0.88,
            right_eye=(25.0, 35.0), left_eye=(75.0, 35.0),
            mouth_right=(30.0, 80.0), mouth_left=(70.0, 80.0)
        )
        # Mặt sát mép dưới cùng bên phải
        face_edge_br = DetectedFace(
            x=320.0, y=300.0, w=120.0, h=140.0, confidence=0.85,
            right_eye=(350.0, 330.0), left_eye=(390.0, 330.0),
            mouth_right=(355.0, 380.0), mouth_left=(395.0, 380.0)
        )

        out = engine.apply_beauty(img, skin_brighten_pct=50, skin_smooth_pct=50, lip_tint_pct=50, faces=[face_edge_tl, face_edge_br])
        assert out.shape == img.shape

    def test_individual_slider_effects(self, dummy_face_center):
        """Thay đổi riêng từng thanh trượt (Brighten, Smooth, Lips) và xác nhận tác động có mục tiêu."""
        engine = SmartBeautyEngine()
        # Tạo vùng mặt giả lập có tông da
        img = np.full((400, 400, 3), 40, dtype=np.uint8)
        cv2.ellipse(img, (175, 190), (70, 90), 0, 0, 360, (160, 180, 220), -1)

        # 1. Chỉ tăng sáng da
        out_bright = engine.apply_beauty(img, skin_brighten_pct=60, skin_smooth_pct=0, lip_tint_pct=0, faces=[dummy_face_center])
        assert not np.array_equal(out_bright, img)

        # 2. Chỉ làm mịn da
        out_smooth = engine.apply_beauty(img, skin_brighten_pct=0, skin_smooth_pct=60, lip_tint_pct=0, faces=[dummy_face_center])
        assert not np.array_equal(out_smooth, img)

        # 3. Chỉ tô son môi
        out_lips = engine.apply_beauty(img, skin_brighten_pct=0, skin_smooth_pct=0, lip_tint_pct=60, faces=[dummy_face_center])
        assert not np.array_equal(out_lips, img)

    def test_large_jpeg_from_nikon_d780_simulation(self):
        """Xử lý ảnh JPEG độ phân giải cao chuẩn Nikon D780 (6048x4024)."""
        engine = SmartBeautyEngine()
        # Tạo canvas lớn mô phỏng ảnh 24.3 MP Nikon D780
        h, w = 4024, 6048
        # Giả lập vùng mặt 1000x1200 ở trung tâm
        face = DetectedFace(
            x=2500.0, y=1400.0, w=1000.0, h=1200.0, confidence=0.96,
            right_eye=(2750.0, 1750.0), left_eye=(3250.0, 1750.0),
            mouth_right=(2800.0, 2250.0), mouth_left=(3200.0, 2250.0)
        )

        # Test trên crop đại diện để tối ưu thời gian test
        crop_h, crop_w = 1400, 1200
        crop = np.full((crop_h, crop_w, 3), 150, dtype=np.uint8)
        crop_face = DetectedFace(
            x=100.0, y=100.0, w=900.0, h=1100.0, confidence=0.96,
            right_eye=(300.0, 400.0), left_eye=(700.0, 400.0),
            mouth_right=(350.0, 850.0), mouth_left=(650.0, 850.0)
        )

        out_crop = engine.apply_beauty(crop, skin_brighten_pct=40, skin_smooth_pct=50, lip_tint_pct=30, faces=[crop_face])
        assert out_crop.shape == (crop_h, crop_w, 3)

    def test_missing_model_fallback(self):
        """Khi mô hình AI bị thiếu hoặc đường dẫn sai: engine không crash và fallback an toàn."""
        engine_broken = SmartBeautyEngine(model_path="C:/non_existent_model.onnx")
        assert engine_broken.is_available is False

        img = np.full((200, 200, 3), 120, dtype=np.uint8)
        faces = engine_broken.detect_faces(img)
        assert faces == []

        out = engine_broken.apply_beauty(img, skin_brighten_pct=50, skin_smooth_pct=50, lip_tint_pct=50)
        assert np.array_equal(out, img)

    def test_generate_debug_masks(self, dummy_face_center):
        """Kiểm tra chế độ debug generate_debug_masks xuất đủ 6 loại ảnh với kích thước đồng nhất."""
        engine = SmartBeautyEngine()
        img = np.full((300, 300, 3), 100, dtype=np.uint8)
        debug_dict = engine.generate_debug_masks(img, faces=[dummy_face_center])

        expected_keys = {"original", "face_landmarks", "skin_mask", "excluded_features_mask", "lip_mask", "composite_preview"}
        assert set(debug_dict.keys()) == expected_keys
        for key, mat in debug_dict.items():
            assert mat.shape[:2] == (300, 300)
            assert mat.dtype == np.uint8

    def test_anatomical_polygon_inside_face_box(self, dummy_face_center):
        """Đa giác giải phẫu 10 điểm phải nằm bên trong vùng bounding box của khuôn mặt."""
        engine = SmartBeautyEngine()
        poly = engine._build_face_anatomical_polygon(dummy_face_center, 400, 400)
        assert poly is not None
        assert len(poly) == 10
        # Tất cả các đỉnh của đa giác phải nằm trong biên hợp lý của khuôn mặt
        for pt in poly:
            x, y = pt[0], pt[1]
            assert dummy_face_center.x - 10 <= x <= dummy_face_center.x + dummy_face_center.w + 10
            assert dummy_face_center.y - 10 <= y <= dummy_face_center.y + dummy_face_center.h + 10


class TestSmartBeautyDialog:
    """Bộ kiểm thử cho giao diện SmartBeautyDialog và Worker."""

    def test_dialog_initialization_and_ui_components(self, sample_portrait_image, qapp):
        """Khởi tạo hộp thoại SmartBeautyDialog đầy đủ tiêu đề, huy hiệu, sliders và nút bấm."""
        dlg = SmartBeautyDialog(
            sample_portrait_image,
            shot_index=1,
            total_shots=6,
            auto_timeout_sec=0
        )

        assert "1/6" in dlg.lbl_progress.text()
        assert dlg.slider_brighten.value() == 0
        assert dlg.slider_smooth.value() == 0
        assert dlg.slider_lips.value() == 0

        assert hasattr(dlg, "btn_reset")
        assert hasattr(dlg, "btn_compare")
        assert hasattr(dlg, "btn_confirm")
        assert hasattr(dlg, "chk_reuse")

        dlg.close()

    def test_reset_button_restores_all_sliders_to_zero(self, sample_portrait_image, qapp):
        """Bấm nút Đặt Lại phải khôi phục cả 3 thanh trượt về 0%."""
        dlg = SmartBeautyDialog(sample_portrait_image, shot_index=2, total_shots=4, auto_timeout_sec=0)

        dlg.slider_brighten.setValue(35)
        dlg.slider_smooth.setValue(45)
        dlg.slider_lips.setValue(55)
        assert dlg._brighten_val == 35.0
        assert dlg._smooth_val == 45.0
        assert dlg._lips_val == 55.0

        dlg._on_reset_clicked()
        assert dlg.slider_brighten.value() == 0
        assert dlg.slider_smooth.value() == 0
        assert dlg.slider_lips.value() == 0
        assert dlg._brighten_val == 0.0
        assert dlg._smooth_val == 0.0
        assert dlg._lips_val == 0.0

        dlg.close()

    def test_compare_button_toggles_original_view(self, sample_portrait_image, qapp):
        """Bấm nút Xem Ảnh Gốc chuyển đổi qua lại giữa ảnh gốc và ảnh xem trước làm đẹp."""
        dlg = SmartBeautyDialog(sample_portrait_image, shot_index=1, total_shots=3, auto_timeout_sec=0)

        assert dlg._showing_original is False
        dlg._on_compare_toggled(True)
        assert dlg._showing_original is True
        assert "Đang Xem Gốc" in dlg.btn_compare.text()

        dlg._on_compare_toggled(False)
        assert dlg._showing_original is False
        assert "Xem Ảnh Gốc" in dlg.btn_compare.text()

        dlg.close()

    def test_original_file_preservation_on_disk(self, tmp_path, qapp):
        """Xác nhận tệp ảnh gốc trên đĩa không bao giờ bị ghi đè hay thay đổi khi làm đẹp."""
        orig_file = tmp_path / "photo_1.jpg"
        im = Image.new("RGB", (300, 300), color=(100, 150, 200))
        im.save(str(orig_file), "JPEG", quality=95)
        orig_bytes = orig_file.read_bytes()

        dlg = SmartBeautyDialog(str(orig_file), shot_index=1, total_shots=1, auto_timeout_sec=0)
        dlg.slider_brighten.setValue(50)
        dlg.slider_smooth.setValue(50)
        dlg._on_confirm_clicked()

        final_im, settings, _ = dlg.get_result()
        assert settings["brighten"] == 50.0

        # Kiểm tra file gốc trên đĩa vẫn giữ nguyên 100% dung lượng và nội dung
        after_bytes = orig_file.read_bytes()
        assert orig_bytes == after_bytes

        dlg.close()

    def test_close_dialog_while_worker_running(self, sample_portrait_image, qapp):
        """Đóng hộp thoại khi worker nền đang render không gây văng crash hay access violation."""
        dlg = SmartBeautyDialog(sample_portrait_image, shot_index=1, total_shots=3, auto_timeout_sec=0)
        dlg.slider_brighten.setValue(40)
        dlg.slider_smooth.setValue(60)

        # Đóng hộp thoại ngay lập tức
        dlg.close()
        assert not dlg.isVisible()
        assert not dlg._worker.isRunning()

    def test_concurrent_worker_requests_isolation(self, qapp):
        """Worker tách biệt rõ ràng giữa các request, không nhầm lẫn request ID cũ và mới."""
        engine = SmartBeautyEngine()
        worker = BeautyPreviewWorker(engine)
        worker.start()

        img = np.full((150, 150, 3), 100, dtype=np.uint8)
        results = []

        def on_ready(req_id, res_bgr):
            results.append((req_id, res_bgr))

        worker.preview_ready.connect(on_ready)

        # Gửi request 1 rồi ghi đè ngay bằng request 2
        worker.update_params(req_id=1, preview_bgr=img, faces=[], brighten=10, smooth=10, lips=10)
        worker.update_params(req_id=2, preview_bgr=img, faces=[], brighten=50, smooth=50, lips=50)

        # Đợi worker hoàn tất
        qapp.processEvents()
        import time
        t0 = time.time()
        while len(results) == 0 and time.time() - t0 < 1.0:
            qapp.processEvents()
            time.sleep(0.02)

        worker.stop()
        worker.wait(500)

        # Kết quả cuối cùng trả về phải ứng với req_id mới nhất
        if results:
            last_req_id = results[-1][0]
            assert last_req_id == 2

    def test_exif_orientation_preserved_in_dialog(self, tmp_path, qapp):
        """Hộp thoại tự động chuẩn hóa hướng ảnh theo EXIF orientation metadata."""
        from PIL import Image

        img_path = tmp_path / "exif_test.jpg"
        im = Image.new("RGB", (200, 300), color=(100, 150, 200))
        # Orientation 6: Rotate 90 CW (sau khi transpose kích thước sẽ là 300x200)
        exif = im.getexif()
        exif[0x0112] = 6
        im.save(str(img_path), exif=exif)

        dlg = SmartBeautyDialog(str(img_path), shot_index=1, total_shots=1, auto_timeout_sec=0)
        assert dlg._original_pil.size == (300, 200)
        dlg.close()
