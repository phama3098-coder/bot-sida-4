"""
1998 TEAM — MediaPipe Face Landmarker (478 Points) & Regional Beauty Integration Tests
Kiểm thử:
1. Giai đoạn 1: Khởi tạo offline model `Assets/Models/face_landmarker.task` (không cần Internet).
2. Giai đoạn 2–3: Tọa độ 478 landmarks, HeadPose 3D (Yaw/Pitch/Roll), và 7 vùng Face Mesh.
3. Giai đoạn 4–5: Tách biệt Face Analysis và Beauty Processing, bật/tắt từng hiệu ứng, nút Lưới 478 Điểm, giữ thiết lập giữa các ảnh.
4. Giai đoạn 6: Đa khuôn mặt, góc nghiêng, điều kiện ánh sáng tối/sáng, cơ chế fallback và bảo toàn ảnh gốc.
"""

import os
import math
from typing import Tuple
import numpy as np
import cv2
import pytest
from PIL import Image

from vietphotobooth.filters.face_analysis import (
    MediaPipeFaceAnalyzer,
    AnalyzedFace,
    FaceMeshRegions,
    FaceAnalysisResult,
    MEDIAPIPE_LANDMARK_COUNT,
    build_face_regions,
    draw_face_mesh_overlay,
    _compute_head_pose_from_matrix,
)
from vietphotobooth.filters.beauty_engine import SmartBeautyEngine, DEFAULT_ENABLED_EFFECTS
from vietphotobooth.desktop.widgets.smart_beauty_panel import SmartBeautyDialog


def _make_synthetic_478_landmarks(cx: float = 320.0, cy: float = 280.0, scale: float = 120.0, angle_deg: float = 0.0) -> np.ndarray:
    """Tạo bộ 478 điểm landmarks giả lập theo hình học khuôn mặt phục vụ kiểm thử cấu trúc vùng & góc nghiêng."""
    pts = np.zeros((MEDIAPIPE_LANDMARK_COUNT, 3), dtype=np.float32)
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    # Khởi tạo các điểm nằm trong hộp khuôn mặt cơ sở xoay quanh (cx, cy)
    from vietphotobooth.filters.face_analysis import (
        FACE_OVAL_INDICES, FOREHEAD_INDICES, RIGHT_EYE_INDICES, LEFT_EYE_INDICES,
        RIGHT_EYEBROW_INDICES, LEFT_EYEBROW_INDICES, RIGHT_UNDER_EYE_INDICES,
        LEFT_UNDER_EYE_INDICES, RIGHT_CHEEK_INDICES, LEFT_CHEEK_INDICES,
        NOSE_BRIDGE_INDICES, LIPS_OUTER_INDICES, LIPS_INNER_INDICES,
    )

    def _rot(dx: float, dy: float) -> Tuple[float, float]:
        rx = cx + (dx * cos_a - dy * sin_a)
        ry = cy + (dx * sin_a + dy * cos_a)
        return rx, ry

    # Phân bổ đều các điểm mẫu quanh elip chuẩn cho tất cả index 0..477 trước
    for i in range(MEDIAPIPE_LANDMARK_COUNT):
        ang = (i / float(MEDIAPIPE_LANDMARK_COUNT)) * 2.0 * math.pi
        pts[i, 0], pts[i, 1] = _rot(0.55 * scale * math.cos(ang), 0.72 * scale * math.sin(ang))

    # Gán vòng oval mượt
    for k, idx in enumerate(FACE_OVAL_INDICES):
        ang = -math.pi / 2.0 + (k / len(FACE_OVAL_INDICES)) * 2.0 * math.pi
        pts[idx, 0], pts[idx, 1] = _rot(0.75 * scale * math.cos(ang), 0.95 * scale * math.sin(ang))

    # Vùng trán
    for k, idx in enumerate(FOREHEAD_INDICES):
        t = (k / max(1, len(FOREHEAD_INDICES) - 1)) * 2.0 - 1.0
        dy = -0.78 * scale if k < len(FOREHEAD_INDICES) // 2 else -0.45 * scale
        dx = 0.55 * scale * (1.0 - abs(t) * 0.2) * (1 if k % 2 == 0 else -1)
        pts[idx, 0], pts[idx, 1] = _rot(dx * 0.6, dy)

    # Mắt, dưới mắt, lông mày
    for ring, ex, ey, erx, ery in [
        (RIGHT_EYE_INDICES, -0.28 * scale, -0.18 * scale, 0.14 * scale, 0.06 * scale),
        (LEFT_EYE_INDICES, 0.28 * scale, -0.18 * scale, 0.14 * scale, 0.06 * scale),
        (RIGHT_UNDER_EYE_INDICES, -0.28 * scale, -0.06 * scale, 0.16 * scale, 0.07 * scale),
        (LEFT_UNDER_EYE_INDICES, 0.28 * scale, -0.06 * scale, 0.16 * scale, 0.07 * scale),
        (RIGHT_EYEBROW_INDICES, -0.28 * scale, -0.32 * scale, 0.18 * scale, 0.04 * scale),
        (LEFT_EYEBROW_INDICES, 0.28 * scale, -0.32 * scale, 0.18 * scale, 0.04 * scale),
        (RIGHT_CHEEK_INDICES, -0.36 * scale, 0.18 * scale, 0.20 * scale, 0.18 * scale),
        (LEFT_CHEEK_INDICES, 0.36 * scale, 0.18 * scale, 0.20 * scale, 0.18 * scale),
        (NOSE_BRIDGE_INDICES, 0.0, 0.02 * scale, 0.09 * scale, 0.24 * scale),
        (LIPS_OUTER_INDICES, 0.0, 0.45 * scale, 0.25 * scale, 0.10 * scale),
        (LIPS_INNER_INDICES, 0.0, 0.45 * scale, 0.16 * scale, 0.05 * scale),
    ]:
        for k, idx in enumerate(ring):
            ang = (k / float(len(ring))) * 2.0 * math.pi
            pts[idx, 0], pts[idx, 1] = _rot(ex + erx * math.cos(ang), ey + ery * math.sin(ang))

    pts[468, 0], pts[468, 1] = _rot(-0.28 * scale, -0.18 * scale)
    pts[473, 0], pts[473, 1] = _rot(0.28 * scale, -0.18 * scale)
    pts[1, 0], pts[1, 1] = _rot(0.0, 0.12 * scale)
    pts[152, 0], pts[152, 1] = _rot(0.0, 0.95 * scale)
    return pts


def _make_analyzed_face(cx: float = 320.0, cy: float = 280.0, scale: float = 120.0, angle_deg: float = 0.0) -> AnalyzedFace:
    lm = _make_synthetic_478_landmarks(cx=cx, cy=cy, scale=scale, angle_deg=angle_deg)
    regions = build_face_regions(lm)
    return AnalyzedFace(
        x=cx - scale,
        y=cy - scale,
        w=scale * 2.0,
        h=scale * 2.1,
        confidence=0.96,
        right_eye=(float(lm[468, 0]), float(lm[468, 1])),
        left_eye=(float(lm[473, 0]), float(lm[473, 1])),
        nose=(float(lm[1, 0]), float(lm[1, 1])),
        mouth_right=(float(lm[61, 0]), float(lm[61, 1])),
        mouth_left=(float(lm[291, 0]), float(lm[291, 1])),
        landmarks_px=lm,
        regions=regions,
        analysis_source="mediapipe_478",
    )


def test_offline_landmarker_model_exists_and_initializes():
    """Stage 1: Model face_landmarker.task phải tồn tại offline cục bộ và khởi tạo không cần Internet."""
    analyzer = MediaPipeFaceAnalyzer()
    try:
        assert analyzer.is_mediapipe_available is True
        assert analyzer.is_available is True
        assert os.path.exists(analyzer.model_path)
        assert analyzer.model_path.endswith("face_landmarker.task")
        assert os.path.getsize(analyzer.model_path) > 1_000_000
    finally:
        analyzer.close()


def test_478_landmarks_regions_and_head_pose_angles():
    """Stage 2 & 3: Xác minh 478 landmarks, đủ các vùng giải phẫu và góc nghiêng đầu Yaw/Pitch/Roll."""
    face = _make_analyzed_face(300.0, 260.0, scale=110.0, angle_deg=20.0)
    assert face.landmark_count == MEDIAPIPE_LANDMARK_COUNT
    assert face.has_mesh is True

    reg = face.regions
    assert isinstance(reg, FaceMeshRegions)
    for attr in [
        "face_oval", "forehead", "left_cheek", "right_cheek",
        "left_eye", "right_eye", "left_eyebrow", "right_eyebrow",
        "left_under_eye", "right_under_eye", "nose_bridge",
        "lips_outer", "lips_inner", "jawline_left", "jawline_right",
    ]:
        poly = getattr(reg, attr)
        assert poly is not None and len(poly) >= 3, f"Thiếu vùng {attr}"
    assert reg.chin_point is not None

    # Kiểm tra ma trận 4x4 cho góc quay Yaw = +25 độ
    rad = math.radians(25.0)
    rot_y = np.eye(4, dtype=np.float32)
    rot_y[0, 0] = math.cos(rad)
    rot_y[0, 2] = math.sin(rad)
    rot_y[2, 0] = -math.sin(rad)
    rot_y[2, 2] = math.cos(rad)
    pose_yaw = _compute_head_pose_from_matrix(rot_y, face.landmarks_px)
    assert pose_yaw.yaw > 18.0
    assert pose_yaw.pose_label == "Nghiêng trái"

    # Kiểm tra ma trận đơn vị cho thẳng diện
    pose_front = _compute_head_pose_from_matrix(np.eye(4, dtype=np.float32), face.landmarks_px)
    assert abs(pose_front.yaw) < 1.0 and abs(pose_front.pitch) < 1.0 and abs(pose_front.roll) < 1.0
    assert pose_front.pose_label == "Thẳng diện"


def test_region_based_beauty_effects_toggles_and_lighting_conditions():
    """Stage 4 & 6: Kiểm thử làm đẹp đa vùng với bật/tắt từng hiệu ứng, đa khuôn mặt, góc nghiêng & ánh sáng tối/sáng."""
    engine = SmartBeautyEngine()

    # Ảnh có 2 khuôn mặt nghiêng trái/phải với vùng da có kết cấu chi tiết
    base_img = np.full((600, 900, 3), 45, dtype=np.uint8)
    f1 = _make_analyzed_face(240.0, 290.0, scale=110.0, angle_deg=-22.0)
    f2 = _make_analyzed_face(640.0, 300.0, scale=115.0, angle_deg=18.0)

    # Tô màu da giả lập có nhiễu vân da nhẹ bên trong oval hai khuôn mặt
    rng = np.random.default_rng(42)
    noise = rng.integers(-8, 9, size=base_img.shape, dtype=np.int16)
    for f in (f1, f2):
        cv2.fillPoly(base_img, [f.regions.face_oval], (155, 178, 215))
        cv2.fillPoly(base_img, [f.regions.lips_outer], (115, 110, 175))
    textured = np.clip(base_img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    original_snapshot = textured.copy()

    # 1. Tắt toàn bộ hiệu ứng qua enabled_effects -> phải trả về ảnh nguyên bản
    all_off = {k: False for k in DEFAULT_ENABLED_EFFECTS}
    out_off = engine.apply_beauty(
        textured,
        skin_brighten_pct=70, skin_smooth_pct=70, lip_tint_pct=70,
        eye_brighten_pct=70, cheek_rosy_pct=70, nose_highlight_pct=70, face_slim_pct=50,
        enabled_effects=all_off, faces=[f1, f2],
    )
    assert np.array_equal(out_off, textured)
    # Bảo toàn tuyệt đối mảng đầu vào không bị mutate tại chỗ
    assert np.array_equal(textured, original_snapshot)

    # 2. Thử nghiệm dưới cả điều kiện thiếu sáng (dark) và dư sáng (bright)
    dark_img = np.clip(textured.astype(np.float32) * 0.45, 0, 255).astype(np.uint8)
    bright_img = np.clip(textured.astype(np.float32) * 1.25, 0, 255).astype(np.uint8)
    for lighting_img in (textured, dark_img, bright_img):
        out_fx = engine.apply_beauty(
            lighting_img,
            skin_brighten_pct=40, skin_smooth_pct=50, lip_tint_pct=45,
            eye_brighten_pct=55, cheek_rosy_pct=40, nose_highlight_pct=35, face_slim_pct=30,
            enabled_effects={
                "smooth": True, "brighten": True, "lips": True,
                "eye_brighten": True, "cheek_rosy": True, "nose_highlight": True, "face_slim": True,
            },
            faces=[f1, f2],
        )
        assert out_fx.shape == lighting_img.shape
        assert out_fx.dtype == np.uint8
        assert not np.array_equal(out_fx, lighting_img)

    # 3. Kiểm tra hàm vẽ Face Mesh overlay không làm thay đổi ảnh gốc
    mesh_vis = draw_face_mesh_overlay(textured, [f1, f2])
    assert mesh_vis.shape == textured.shape
    assert not np.array_equal(mesh_vis, textured)
    assert np.array_equal(textured, original_snapshot)


def test_dialog_effect_toggles_mesh_toggle_and_multishot_persistence(qapp):
    """Stage 5: Kiểm tra công tắc Bật/Tắt từng hiệu ứng, Developer Mode Face Mesh và lưu thiết lập cho ảnh kế tiếp."""
    import time

    img = Image.new("RGB", (640, 480), color=(190, 165, 150))
    f1 = _make_analyzed_face(320.0, 240.0, scale=110.0)

    # 1. Ở chế độ khách hàng (mặc định developer_mode=False): ẩn lưới 478 điểm và nhãn kỹ thuật
    dlg_cust = SmartBeautyDialog(img, shot_index=1, total_shots=1)
    assert not hasattr(dlg_cust, "lbl_compare_badge")
    assert not hasattr(dlg_cust, "btn_toggle_mesh")
    status_txt = dlg_cust.lbl_face_status.text()
    for tech in ("MediaPipe", "478", "Fallback", "GFPGAN", "ONNX"):
        assert tech not in status_txt
    dlg_cust.close()

    # 2. Ở Developer Mode: cho phép bật/tắt Lưới 478 Điểm và kiểm tra cả 8 hiệu ứng
    dlg = SmartBeautyDialog(
        img,
        shot_index=1,
        total_shots=3,
        initial_settings={
            "brighten": 30.0, "smooth": 40.0, "lips": 25.0,
            "eye_brighten": 35.0, "cheek_rosy": 20.0, "nose_highlight": 15.0, "face_slim": 25.0,
            "ai_enhance": 45.0,
        },
        reuse_for_next=True,
        developer_mode=True,
    )
    dlg._preview_faces = [f1]
    dlg._full_faces = [f1]
    dlg.btn_toggle_mesh.setEnabled(True)
    dlg.show()
    qapp.processEvents()

    # Tắt riêng hiệu ứng thâm mắt và kiểm tra cập nhật trạng thái + giữ nguyên cường độ cũ
    dlg.btn_toggle_eye.setChecked(False)
    t0 = time.time()
    while time.time() - t0 < 0.25:
        qapp.processEvents()
        time.sleep(0.02)
    assert dlg.btn_toggle_eye.isChecked() is False
    assert dlg.get_enabled_effects()["eye_brighten"] is False
    assert dlg.slider_eye.value() == 35  # Giữ nguyên cường độ đã chọn

    # Bật lại phải khôi phục đúng 35%
    dlg.btn_toggle_eye.setChecked(True)
    t0 = time.time()
    while time.time() - t0 < 0.25:
        qapp.processEvents()
        time.sleep(0.02)
    assert dlg.get_enabled_effects()["eye_brighten"] is True
    assert dlg.slider_eye.value() == 35
    assert dlg.lbl_eye_val.text() == "35%"

    # Kiểm tra vừa vặn hoàn toàn trong 1382x725 kể cả khi mở cả 7 hiệu ứng (không cần thanh cuộn)
    dlg.resize(1382, 725)
    t0 = time.time()
    while time.time() - t0 < 0.25:
        qapp.processEvents()
        time.sleep(0.02)
    from PySide6.QtWidgets import QScrollArea
    scroll = dlg.findChild(QScrollArea, "beauty_sliders_scroll")
    assert scroll is not None
    assert scroll.verticalScrollBar().maximum() == 0, f"Không được tràn cuộn ở 1382x725 (max={scroll.verticalScrollBar().maximum()})"

    # Kiểm tra nút Lưới 478 Điểm
    dlg.btn_toggle_mesh.setChecked(True)
    qapp.processEvents()
    assert dlg._show_mesh_overlay is True

    # Kiểm tra nút Đặt Lại trả mọi thanh trượt (gồm cả AI Enhancement) về 0% và khôi phục mặc định
    dlg._on_reset_clicked()
    assert dlg.slider_eye.value() == 0
    assert dlg.slider_cheek.value() == 0
    assert dlg.slider_nose.value() == 0
    assert dlg.slider_slim.value() == 0
    assert dlg.slider_ai_enhance.value() == 0
    assert dlg.btn_toggle_slim.isChecked() is False
    assert dlg.btn_toggle_eye.isChecked() is False
    assert dlg.btn_toggle_ai.isChecked() is False

    # Kéo lại thông số mới và xác nhận giữ thiết lập sang ảnh thứ 2
    dlg.slider_eye.setValue(50)
    dlg.slider_slim.setValue(30)
    t0 = time.time()
    while time.time() - t0 < 0.25:
        qapp.processEvents()
        time.sleep(0.02)

    assert dlg.btn_toggle_slim.isChecked() is True  # Tự động bật khi kéo slider > 0%
    dlg._on_confirm_clicked()
    _, settings, reuse = dlg.get_result()
    enabled = dlg.get_enabled_effects()
    dlg.close()

    assert reuse is True
    assert settings["eye_brighten"] == 50.0
    assert settings["face_slim"] == 30.0

    # Mở ảnh kế tiếp #2 truyền tiếp thiết lập & trạng thái bật/tắt đã lưu
    dlg2 = SmartBeautyDialog(
        img,
        shot_index=2,
        total_shots=3,
        initial_settings=settings,
        initial_enabled_effects=enabled,
        reuse_for_next=reuse,
    )
    assert dlg2.slider_eye.value() == 50
    assert dlg2.slider_slim.value() == 30
    assert dlg2.btn_toggle_slim.isChecked() is True
    assert dlg2.chk_reuse.isChecked() is True
    dlg2.close()


def test_sliders_one_unit_fine_precision_step(qapp):
    """Kiểm tra cả 7 thanh slider có singleStep=1 và truyền chính xác từng giá trị 0, 1, 2, 3, ..., 99."""
    img = Image.new("RGB", (640, 480), color=(200, 175, 160))
    dlg = SmartBeautyDialog(img, shot_index=1, total_shots=1)
    dlg.show()
    qapp.processEvents()

    sliders_spec = [
        ("brighten", dlg.slider_brighten, dlg.lbl_s1_val, 1),
        ("smooth", dlg.slider_smooth, dlg.lbl_s2_val, 2),
        ("eye_brighten", dlg.slider_eye, dlg.lbl_eye_val, 3),
        ("cheek_rosy", dlg.slider_cheek, dlg.lbl_cheek_val, 17),
        ("nose_highlight", dlg.slider_nose, dlg.lbl_nose_val, 43),
        ("lips", dlg.slider_lips, dlg.lbl_s3_val, 68),
        ("face_slim", dlg.slider_slim, dlg.lbl_slim_val, 99),
    ]

    for key, slider, lbl_val, target_val in sliders_spec:
        assert slider.minimum() == 0
        assert slider.maximum() == 100
        assert slider.singleStep() == 1
        slider.setValue(target_val)
        qapp.processEvents()
        assert slider.value() == target_val
        assert lbl_val.text() == f"{target_val}%"

    _, settings, _ = dlg.get_result()
    for key, _, _, target_val in sliders_spec:
        assert settings[key] == float(target_val)

    # Kiểm tra tăng/giảm liên tiếp 0 -> 1 -> 2 -> 3 -> 4 không bị làm tròn về bội số của 5
    for step_v in (0, 1, 2, 3, 4):
        dlg.slider_brighten.setValue(step_v)
        qapp.processEvents()
        assert dlg.lbl_s1_val.text() == f"{step_v}%"
        assert dlg._brighten_val == float(step_v)

    dlg.close()
