"""
1998 TEAM — Hybrid AI Beauty Integration & Reliability Tests
Kiểm thử toàn diện cho hệ thống Hybrid AI Beauty:
1. Tồn tại mô hình AI cục bộ GFPGAN v1.4 FP16 ONNX, chạy 100% offline không cần Internet.
2. Kiến trúc adapter tách rời cho phép hoán đổi mô hình (registry & BasePortraitEnhancer).
3. Cơ chế cache kết quả AI trung gian: kéo slider cường độ AI không chạy lại suy luận neural.
4. Giới hạn mặt nạ MediaPipe 478 điểm bảo toàn vùng mắt / răng / tóc / kính mắt & ảnh gốc.
5. Fallback an toàn khi thiếu model AI hoặc lỗi khởi tạo GPU CUDA -> CPU.
6. Giao diện khách hàng sạch sẽ (không lộ thông tin kỹ thuật), nút AI Beauty điều chỉnh bước 1%.
"""

import os
from typing import List
from unittest.mock import patch
import numpy as np
import cv2
import pytest
from PIL import Image

from vietphotobooth.filters.ai_portrait_enhancer import (
    BasePortraitEnhancer,
    OnnxPortraitEnhancer,
    PortraitModelSpec,
    PORTRAIT_MODEL_REGISTRY,
    register_portrait_model,
    create_portrait_enhancer,
)
from vietphotobooth.filters.beauty_engine import SmartBeautyEngine
from vietphotobooth.desktop.widgets.smart_beauty_panel import SmartBeautyDialog
from vietphotobooth.tests.test_mediapipe_face_analysis import _make_analyzed_face


class _CountingMockEnhancer(BasePortraitEnhancer):
    """Mô hình AI giả lập để đếm số lần suy luận thực sự và xác minh hoán đổi mô hình."""

    def __init__(self, delta_bgr: int = 20, available: bool = True):
        self.call_count = 0
        self._delta = delta_bgr
        self._available = available

    @property
    def model_id(self) -> str:
        return "mock_portrait_v1"

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def active_provider(self) -> str:
        return "MockExecutionProvider" if self._available else "unavailable"

    def enhance_aligned_crop(self, aligned_bgr: np.ndarray) -> np.ndarray:
        self.call_count += 1
        return np.clip(aligned_bgr.astype(np.int16) + self._delta, 0, 255).astype(np.uint8)


def test_offline_gfpgan_model_exists_and_registry_extensible():
    """Kiểm tra file ONNX offline và khả năng đăng ký/hoán đổi mô hình qua registry."""
    enhancer = create_portrait_enhancer()
    assert enhancer.is_available is True
    assert os.path.isfile(enhancer.model_path)
    assert enhancer.model_path.endswith("gfpgan_v1.4_fp16.onnx")
    assert os.path.getsize(enhancer.model_path) > 100_000_000

    assert "gfpgan_v1.4_fp16" in PORTRAIT_MODEL_REGISTRY
    assert "restoreformer_plus_plus" in PORTRAIT_MODEL_REGISTRY

    custom_spec = PortraitModelSpec(
        model_id="custom_test_spec",
        display_name="Custom Commercial Portrait AI",
        filename="custom_test.onnx",
        license_id="MIT",
    )
    register_portrait_model(custom_spec)
    assert "custom_test_spec" in PORTRAIT_MODEL_REGISTRY
    PORTRAIT_MODEL_REGISTRY.pop("custom_test_spec", None)


def test_missing_ai_model_fallback_preserves_smart_beauty():
    """Nếu file ONNX bị thiếu hoặc hỏng: engine không crash và fallback an toàn về SmartBeautyEngine."""
    engine = SmartBeautyEngine(ai_model_path="C:/does_not_exist_ai_model.onnx")
    assert engine.is_ai_available is False
    assert engine.ai_active_provider == "unavailable"

    img = np.full((360, 360, 3), 135, dtype=np.uint8)
    face = _make_analyzed_face(180.0, 180.0, scale=95.0)
    cv2.fillPoly(img, [face.regions.face_oval], (160, 185, 220))
    snap = img.copy()

    out_ai_only = engine.apply_beauty(
        img,
        skin_brighten_pct=0,
        skin_smooth_pct=0,
        lip_tint_pct=0,
        ai_enhance_pct=80,
        faces=[face],
    )
    assert np.array_equal(out_ai_only, img)
    assert np.array_equal(img, snap)


def test_cuda_fallback_to_cpu_execution_provider():
    """Nếu CUDAExecutionProvider khả dụng nhưng lỗi khởi tạo, tự động fallback về CPUExecutionProvider."""
    enhancer = create_portrait_enhancer(prefer_gpu=True)
    with patch("onnxruntime.get_available_providers", return_value=["CUDAExecutionProvider", "CPUExecutionProvider"]):
        calls: List[List[str]] = []

        class _DummyIO:
            def __init__(self, name):
                self.name = name

        class _DummySession:
            def get_inputs(self):
                return [_DummyIO("input")]

            def get_outputs(self):
                return [_DummyIO("output")]

            def get_providers(self):
                return ["CPUExecutionProvider"]

        def _fake_session(path, sess_options=None, providers=None):
            calls.append(list(providers or []))
            if providers and providers[0] == "CUDAExecutionProvider":
                raise RuntimeError("CUDA cublasLt64_12.dll missing")
            return _DummySession()

        with patch("onnxruntime.InferenceSession", side_effect=_fake_session):
            assert enhancer.warmup() is True
            assert enhancer.active_provider == "CPUExecutionProvider"
            assert calls[0][0] == "CUDAExecutionProvider"
            assert calls[1] == ["CPUExecutionProvider"]


def test_hybrid_ai_cache_prevents_repeat_inference_and_preserves_eye_regions():
    """
    Xác minh:
    1. Kéo slider AI từ 35% -> 85% sử dụng cache trung gian (không chạy lại neural inference).
    2. Mặt nạ giới hạn bảo toàn vùng mắt / nền ngoài khuôn mặt không bị AI làm sai lệch.
    """
    mock_ai = _CountingMockEnhancer(delta_bgr=40, available=True)
    engine = SmartBeautyEngine(ai_enhancer=mock_ai)
    assert engine.is_ai_available is True

    img = np.full((520, 520, 3), 90, dtype=np.uint8)
    face = _make_analyzed_face(260.0, 260.0, scale=120.0)
    cv2.fillPoly(img, [face.regions.face_oval], (155, 180, 210))
    # Vẽ nhãn cầu mắt màu tối sắc nét bên trong vùng mắt cần được bảo vệ
    cv2.fillPoly(img, [face.regions.left_eye], (25, 25, 30))
    cv2.fillPoly(img, [face.regions.right_eye], (25, 25, 30))
    orig_snapshot = img.copy()

    out_35 = engine.apply_beauty(
        img,
        skin_brighten_pct=20,
        skin_smooth_pct=20,
        ai_enhance_pct=35,
        enabled_effects={"brighten": True, "smooth": True, "ai_enhance": True},
        faces=[face],
    )
    assert mock_ai.call_count == 1
    assert np.array_equal(img, orig_snapshot)

    # Kéo lại AI từ 35 -> 85% (các thông số nền giữ nguyên): PHẢI cache hit -> call_count giữ nguyên == 1
    out_85 = engine.apply_beauty(
        img,
        skin_brighten_pct=20,
        skin_smooth_pct=20,
        ai_enhance_pct=85,
        enabled_effects={"brighten": True, "smooth": True, "ai_enhance": True},
        faces=[face],
    )
    assert mock_ai.call_count == 1, "Thay đổi % hòa trộn AI không được phép chạy lại suy luận neural"
    assert not np.array_equal(out_35, out_85)

    # Vùng nền bên ngoài (góc ảnh) không được thay đổi
    assert np.array_equal(out_85[:40, :40], img[:40, :40])

    # Tâm vùng mắt phải giữ nguyên độ bảo vệ cao (không bị cộng +40 delta toàn phần)
    lx, ly = int(face.left_eye[0]), int(face.left_eye[1])
    eye_diff = np.abs(out_85[ly - 2 : ly + 3, lx - 2 : lx + 3].astype(np.float32) - img[ly - 2 : ly + 3, lx - 2 : lx + 3].astype(np.float32))
    assert float(np.mean(eye_diff)) < 10.0

    # Hot-swap sang model khác phải reset cache và chạy model mới
    mock_ai2 = _CountingMockEnhancer(delta_bgr=-25, available=True)
    engine.set_ai_enhancer(mock_ai2)
    _ = engine.apply_beauty(
        img,
        skin_brighten_pct=20,
        skin_smooth_pct=20,
        ai_enhance_pct=50,
        enabled_effects={"brighten": True, "smooth": True, "ai_enhance": True},
        faces=[face],
    )
    assert mock_ai2.call_count == 1


def test_real_gfpgan_onnx_offline_inference_multiface_and_tilted():
    """Chạy thật mô hình GFPGAN v1.4 ONNX offline trên ảnh 1 khuôn mặt nghiêng và 2 khuôn mặt."""
    engine = SmartBeautyEngine()
    assert engine.is_available is True
    assert engine.is_ai_available is True

    # Ảnh mô phỏng 2 khuôn mặt (1 thẳng, 1 nghiêng 25 độ) với texture da thực tế
    canvas = np.full((600, 900, 3), 50, dtype=np.uint8)
    f1 = _make_analyzed_face(240.0, 290.0, scale=110.0, angle_deg=0.0)
    f2 = _make_analyzed_face(640.0, 300.0, scale=115.0, angle_deg=25.0)
    for f in (f1, f2):
        cv2.fillPoly(canvas, [f.regions.face_oval], (160, 182, 215))
    rng = np.random.default_rng(7)
    noise = rng.integers(-6, 7, size=canvas.shape, dtype=np.int16)
    portrait = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    orig = portrait.copy()

    out = engine.apply_beauty(
        portrait,
        skin_brighten_pct=25,
        skin_smooth_pct=30,
        ai_enhance_pct=60,
        enabled_effects={"brighten": True, "smooth": True, "ai_enhance": True},
        faces=[f1, f2],
    )
    assert out.shape == portrait.shape
    assert out.dtype == np.uint8
    assert np.array_equal(portrait, orig)
    assert not np.array_equal(out, portrait)

    # Kéo lại mức 30% phải reuse cache -> cực nhanh (< 50ms)
    out2 = engine.apply_beauty(
        portrait,
        skin_brighten_pct=25,
        skin_smooth_pct=30,
        ai_enhance_pct=30,
        enabled_effects={"brighten": True, "smooth": True, "ai_enhance": True},
        faces=[f1, f2],
    )
    assert not np.array_equal(out2, out)
    engine.close()


def test_customer_ui_cleaned_and_ai_slider_precision(qapp):
    """
    Xác minh UI SmartBeautyDialog dành cho khách hàng:
    - Không còn nhãn 'ĐANG XEM: BẢN LÀM ĐẸP AI' và nút 'Lưới 478 Điểm'.
    - Không chứa thông tin kỹ thuật trong trạng thái.
    - Thẻ 'Tăng cường chân dung AI' hoạt động với singleStep=1 và không làm tràn scroll ở 1382x725.
    """
    from PySide6.QtWidgets import QScrollArea, QLabel

    img = Image.new("RGB", (640, 480), color=(205, 180, 165))
    dlg = SmartBeautyDialog(
        img,
        shot_index=1,
        total_shots=2,
        developer_mode=False,
    )
    dlg.resize(1382, 725)
    dlg.show()
    qapp.processEvents()

    assert not hasattr(dlg, "lbl_compare_badge")
    assert not hasattr(dlg, "btn_toggle_mesh")
    for lbl in dlg.findChildren(QLabel):
        t = lbl.text()
        assert "ĐANG XEM:" not in t
        assert "MediaPipe" not in t
        assert "Fallback" not in t
        assert "ONNX" not in t

    # Thẻ AI mới hoạt động bước 1%
    assert dlg.slider_ai_enhance.singleStep() == 1
    assert dlg.slider_ai_enhance.minimum() == 0
    assert dlg.slider_ai_enhance.maximum() == 100
    dlg.btn_toggle_ai.setChecked(True)
    dlg.slider_ai_enhance.setValue(37)
    qapp.processEvents()
    assert dlg.lbl_ai_val.text() == "37%"
    _, settings, _ = dlg.get_result()
    assert settings["ai_enhance"] == 37.0

    # Mở tất cả 8 thẻ cùng lúc tại 1382x725 vẫn không bị tràn cuộn
    for card in dlg._effect_cards.values():
        if not card.toggle.isChecked():
            card.toggle.setChecked(True)
    qapp.processEvents()
    scroll = dlg.findChild(QScrollArea, "beauty_sliders_scroll")
    assert scroll is not None
    assert scroll.verticalScrollBar().maximum() == 0, (
        f"Tràn cuộn khi mở toàn bộ 8 hiệu ứng tại 1382x725 (max={scroll.verticalScrollBar().maximum()})"
    )

    dlg.close()
