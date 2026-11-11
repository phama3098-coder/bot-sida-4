"""
1998 TEAM — Hybrid AI Portrait Enhancer (Swappable ONNX Backend)
Kiến trúc tách rời hoàn toàn cho AI làm đẹp chân dung thứ hai, hỗ trợ:
- Chạy 100% offline trên Windows qua ONNX Runtime (CPU + NVIDIA CUDA nếu khả dụng).
- Cơ chế adapter/registry cho phép thay thế mô hình AI (GFPGAN v1.4 FP16 mặc định,
  RestoreFormer++ hoặc ONNX tùy biến) mà không phải sửa UI, camera hay MediaPipe.
- Căn chỉnh khuôn mặt 5 điểm chuẩn FFHQ hỗ trợ mặt thẳng, mặt nghiêng và đa khuôn mặt.
- Sinh mặt nạ giới hạn giải phẫu dựa trên MediaPipe 478 điểm + bảo vệ kính mắt, tóc mai,
  răng và tròng mắt; xử lý trên từng ROI khuôn mặt để tối ưu RAM trên ảnh JPEG 24MP.
- Fallback an toàn khi thiếu model, thiếu runtime hoặc lỗi khởi tạo GPU/CPU.
"""

from __future__ import annotations

import os
import sys
import math
import time
import threading
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("VietPhotoBooth.filters.ai_portrait_enhancer")

# Chuẩn 5 điểm FFHQ trên khung hình 512x512 (mắt phải đối tượng / trái ảnh,
# mắt trái đối tượng / phải ảnh, đầu mũi, khóe miệng phải đối tượng, khóe miệng trái đối tượng)
FFHQ_5PT_512: np.ndarray = np.array(
    [
        [192.98138, 239.94708],
        [318.90277, 240.19360],
        [256.63416, 314.01935],
        [201.26117, 371.41043],
        [313.08905, 371.15118],
    ],
    dtype=np.float32,
)

DEFAULT_PORTRAIT_MODEL_ID = "gfpgan_v1.4_fp16"


@dataclass(frozen=True)
class PortraitModelSpec:
    """Đặc tả cấu hình một mô hình ONNX phục hồi / làm đẹp chân dung."""

    model_id: str
    display_name: str
    filename: str
    input_size: Tuple[int, int] = (512, 512)
    norm_mode: str = "neg1_pos1"       # "neg1_pos1" | "zero_one"
    color_order: str = "RGB"           # "RGB" | "BGR"
    alignment: str = "ffhq_5pt"
    license_id: str = "Apache-2.0"
    commercial_notes: str = ""


PORTRAIT_MODEL_REGISTRY: Dict[str, PortraitModelSpec] = {
    "gfpgan_v1.4_fp16": PortraitModelSpec(
        model_id="gfpgan_v1.4_fp16",
        display_name="GFPGAN v1.4 FP16 (ONNX)",
        filename="gfpgan_v1.4_fp16.onnx",
        input_size=(512, 512),
        norm_mode="neg1_pos1",
        color_order="RGB",
        alignment="ffhq_5pt",
        license_id="Apache-2.0 (see MODEL_LICENSES.txt for third-party/FFHQ notes)",
        commercial_notes="162.5 MB FP16 portrait restoration; swappable via registry.",
    ),
    "restoreformer_plus_plus": PortraitModelSpec(
        model_id="restoreformer_plus_plus",
        display_name="RestoreFormer++ (ONNX)",
        filename="restoreformer_plus_plus.onnx",
        input_size=(512, 512),
        norm_mode="neg1_pos1",
        color_order="RGB",
        alignment="ffhq_5pt",
        license_id="Apache-2.0",
        commercial_notes="280.6 MB optional Apache-2.0 spatial transformer face restorer.",
    ),
}


def register_portrait_model(spec: PortraitModelSpec) -> None:
    """Đăng ký hoặc ghi đè một cấu hình mô hình chân dung trong registry dùng chung."""
    PORTRAIT_MODEL_REGISTRY[spec.model_id] = spec


def resolve_offline_model_path(filename: str, explicit_path: Optional[str] = None) -> str:
    """Tìm đường dẫn file ONNX cục bộ trong dự án hoặc bundle PyInstaller (_MEIPASS)."""
    if explicit_path is not None:
        return explicit_path

    candidates: List[str] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "Assets", "Models", filename))

    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates.append(os.path.join(exe_dir, "_internal", "Assets", "Models", filename))
    candidates.append(os.path.join(exe_dir, "Assets", "Models", filename))

    proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates.append(os.path.join(proj_root, "Assets", "Models", filename))
    candidates.append(os.path.join(os.getcwd(), "Assets", "Models", filename))

    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return candidates[0]


def extract_5pt_landmarks(face: Any) -> Optional[np.ndarray]:
    """
    Trích xuất 5 điểm chuẩn FFHQ [right_eye, left_eye, nose, mouth_right, mouth_left]
    từ AnalyzedFace (478 landmarks) hoặc DetectedFace (5 điểm fallback).
    """
    lm_px = getattr(face, "landmarks_px", None)
    if lm_px is not None and len(lm_px) >= 478:
        pts = lm_px[:, :2]
        re = np.mean(pts[[33, 133]], axis=0)
        le = np.mean(pts[[362, 263]], axis=0)
        nose = pts[1]
        mr = pts[61]
        ml = pts[291]
        arr = np.array([re, le, nose, mr, ml], dtype=np.float32)
        if np.linalg.norm(le - re) >= 3.0:
            return arr

    re = getattr(face, "right_eye", None)
    le = getattr(face, "left_eye", None)
    nose = getattr(face, "nose", None)
    mr = getattr(face, "mouth_right", None)
    ml = getattr(face, "mouth_left", None)

    if None not in (re, le, nose, mr, ml):
        arr = np.array([re, le, nose, mr, ml], dtype=np.float32)
        if np.linalg.norm(arr[1] - arr[0]) >= 3.0:
            return arr

    # Fallback ước lượng nội suy từ bounding box nếu thiếu landmark chi tiết
    bbox = getattr(face, "bbox", None)
    if bbox is None:
        fx = float(getattr(face, "x", 0.0))
        fy = float(getattr(face, "y", 0.0))
        fw = float(getattr(face, "w", 0.0))
        fh = float(getattr(face, "h", 0.0))
    else:
        fx, fy, fw, fh = [float(v) for v in bbox]

    if fw < 8.0 or fh < 8.0:
        return None

    return np.array(
        [
            [fx + fw * 0.34, fy + fh * 0.38],
            [fx + fw * 0.66, fy + fh * 0.38],
            [fx + fw * 0.50, fy + fh * 0.56],
            [fx + fw * 0.36, fy + fh * 0.74],
            [fx + fw * 0.64, fy + fh * 0.74],
        ],
        dtype=np.float32,
    )


def compute_face_roi_bounds(face: Any, img_w: int, img_h: int, margin_ratio: float = 0.24) -> Optional[Tuple[int, int, int, int]]:
    """Tính khung ROI khuôn mặt (x1, y1, x2, y2) an toàn trong biên ảnh."""
    bbox = getattr(face, "bbox", None)
    if bbox is None:
        fx = float(getattr(face, "x", 0.0))
        fy = float(getattr(face, "y", 0.0))
        fw = float(getattr(face, "w", 0.0))
        fh = float(getattr(face, "h", 0.0))
    else:
        fx, fy, fw, fh = [float(v) for v in bbox]

    if fw < 8.0 or fh < 8.0:
        return None

    mx = int(fw * margin_ratio)
    my = int(fh * margin_ratio)
    x1 = max(0, int(math.floor(fx - mx)))
    y1 = max(0, int(math.floor(fy - my)))
    x2 = min(img_w, int(math.ceil(fx + fw + mx)))
    y2 = min(img_h, int(math.ceil(fy + fh + my)))
    if (x2 - x1) < 12 or (y2 - y1) < 12:
        return None
    return (x1, y1, x2, y2)


def build_edge_preservation_guard(roi_bgr: np.ndarray, face_w: float) -> np.ndarray:
    """
    Phát hiện các chi tiết sắc nét dễ bị AI tái tạo sai (gọng kính mảnh, sợi tóc mái lòa xòa)
    để giảm nhẹ trọng số AI trên các cạnh mảnh độ tương phản cao trong vùng mặt.
    Trả về hệ số giữ nguyên chi tiết [0.0..1.0], trong đó 1.0 = cho phép AI đầy đủ, thấp = bảo vệ cạnh.
    """
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)

    # Cạnh sắc nét thực sự (gọng kính / sợi tóc đen trên nền da) thường có gradient cục bộ > 0.32
    strong_edges = np.clip((mag - 0.30) / 0.45, 0.0, 1.0)
    k = max(3, (int(face_w * 0.012) // 2) * 2 + 1)
    strong_edges = cv2.dilate(strong_edges, np.ones((k, k), dtype=np.float32), iterations=1)
    strong_edges = cv2.GaussianBlur(strong_edges, (5, 5), 0)
    # Bảo vệ tối đa 70% tín hiệu gốc tại cạnh kính/tóc để không biến dạng mà không gây viền cứng
    return np.clip(1.0 - 0.70 * strong_edges, 0.25, 1.0).astype(np.float32)


@dataclass
class FaceEnhancementPatch:
    """Bản vá khuôn mặt đã được AI xử lý và mặt nạ giới hạn vùng tương ứng trên ROI."""

    x1: int
    y1: int
    x2: int
    y2: int
    enhanced_roi_bgr: np.ndarray
    constraint_mask: np.ndarray  # float32 [0.0, 1.0], shape (rh, rw)


def composite_face_patches(
    base_bgr: np.ndarray,
    patches: List[FaceEnhancementPatch],
    strength_pct: float,
) -> np.ndarray:
    """
    Hòa trộn danh sách các bản vá khuôn mặt AI đã giới hạn mặt nạ vào bản sao của ảnh nền `base_bgr`
    theo cường độ `strength_pct` (0..100%). Hoàn toàn không làm biến đổi `base_bgr`.
    """
    s = max(0.0, min(100.0, float(strength_pct))) / 100.0
    if s <= 0.001 or not patches:
        return base_bgr.copy()

    out = base_bgr.copy()
    h, w = out.shape[:2]
    for patch in patches:
        x1 = max(0, patch.x1)
        y1 = max(0, patch.y1)
        x2 = min(w, patch.x2)
        y2 = min(h, patch.y2)
        if x2 <= x1 or y2 <= y1:
            continue

        px1 = x1 - patch.x1
        py1 = y1 - patch.y1
        px2 = px1 + (x2 - x1)
        py2 = py1 + (y2 - y1)

        roi_dst = out[y1:y2, x1:x2]
        roi_ai = patch.enhanced_roi_bgr[py1:py2, px1:px2]
        mask_f = patch.constraint_mask[py1:py2, px1:px2]
        if roi_dst.shape[:2] != roi_ai.shape[:2] or roi_dst.shape[:2] != mask_f.shape[:2]:
            continue

        alpha = np.clip(mask_f * s, 0.0, 1.0)[:, :, np.newaxis]
        blended = roi_dst.astype(np.float32) * (1.0 - alpha) + roi_ai.astype(np.float32) * alpha
        out[y1:y2, x1:x2] = np.clip(blended, 0.0, 255.0).astype(np.uint8)

    return out


class BasePortraitEnhancer(ABC):
    """Giao diện chuẩn trừu tượng cho mọi mô hình AI làm đẹp chân dung."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        ...

    @property
    @abstractmethod
    def active_provider(self) -> str:
        ...

    @property
    def init_error(self) -> str:
        return ""

    @abstractmethod
    def enhance_aligned_crop(self, aligned_bgr: np.ndarray) -> np.ndarray:
        """Xử lý trực tiếp một ảnh khuôn mặt đã được căn chỉnh (ví dụ 512x512 BGR)."""
        ...

    def close(self) -> None:
        """Giải phóng tài nguyên thực thi của mô hình AI khi đóng."""
        pass

    def generate_face_patches(
        self,
        image_bgr: np.ndarray,
        faces: List[Any],
        mask_builder: Optional[Callable[[np.ndarray, Any, int, int], np.ndarray]] = None,
    ) -> List[FaceEnhancementPatch]:
        """
        Chạy AI làm đẹp trên từng khuôn mặt phát hiện được (tự căn chỉnh 5 điểm và ánh xạ ngược
        vào riêng ROI của từng khuôn mặt) kèm mặt nạ giới hạn giải phẫu MediaPipe.
        """
        if not self.is_available or image_bgr is None or image_bgr.size == 0 or not faces:
            return []

        img_h, img_w = image_bgr.shape[:2]
        patches: List[FaceEnhancementPatch] = []

        for face in faces:
            bounds = compute_face_roi_bounds(face, img_w, img_h, margin_ratio=0.25)
            if bounds is None:
                continue
            x1, y1, x2, y2 = bounds
            rw, rh = x2 - x1, y2 - y1

            src_5pt = extract_5pt_landmarks(face)
            if src_5pt is None:
                continue

            in_w, in_h = self.input_size
            target_5pt = FFHQ_5PT_512.copy()
            if (in_w, in_h) != (512, 512):
                target_5pt[:, 0] *= in_w / 512.0
                target_5pt[:, 1] *= in_h / 512.0

            M, _ = cv2.estimateAffinePartial2D(src_5pt, target_5pt, method=cv2.LMEDS)
            if M is None:
                continue

            aligned_bgr = cv2.warpAffine(
                image_bgr,
                M,
                (in_w, in_h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REFLECT_101,
            )

            enhanced_aligned = self.enhance_aligned_crop(aligned_bgr)

            # Ánh xạ trực tiếp kết quả 512x512 về hệ tọa độ cục bộ (rw x rh) của ROI khuôn mặt
            # để tránh cấp phát ma trận khổng lồ với ảnh JPEG 24MP.
            M_3x3 = np.vstack([M.astype(np.float64), [0.0, 0.0, 1.0]])
            T_roi = np.array([[1.0, 0.0, float(x1)], [0.0, 1.0, float(y1)], [0.0, 0.0, 1.0]], dtype=np.float64)
            M_roi_to_crop = (M_3x3 @ T_roi)[:2, :]
            inv_M_roi = cv2.invertAffineTransform(M_roi_to_crop)

            enhanced_roi = cv2.warpAffine(
                enhanced_aligned,
                inv_M_roi,
                (rw, rh),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REFLECT_101,
            )

            # Mặt nạ hộp chuyển biên mượt trên khung crop chuẩn để tránh đường cắt vuông ở mép cổ/tóc
            box_crop = np.ones((in_h, in_w), dtype=np.float32)
            pad_b = max(12, in_h // 18)
            box_crop[:pad_b, :] = 0.0
            box_crop[-pad_b:, :] = 0.0
            box_crop[:, :pad_b] = 0.0
            box_crop[:, -pad_b:] = 0.0
            box_crop = cv2.GaussianBlur(box_crop, (35, 35), 0)
            box_roi_mask = cv2.warpAffine(box_crop, inv_M_roi, (rw, rh), flags=cv2.INTER_LINEAR)

            roi_bgr = image_bgr[y1:y2, x1:x2]
            if mask_builder is not None:
                anat_mask = mask_builder(roi_bgr, face, x1, y1)
            else:
                anat_mask = np.ones((rh, rw), dtype=np.float32)

            edge_guard = build_edge_preservation_guard(
                roi_bgr,
                float(getattr(face, "w", getattr(face, "bbox", (0, 0, rw, rh))[2])),
            )
            combined_mask = np.clip(anat_mask * box_roi_mask * edge_guard, 0.0, 1.0).astype(np.float32)

            patches.append(
                FaceEnhancementPatch(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    enhanced_roi_bgr=enhanced_roi,
                    constraint_mask=combined_mask,
                )
            )

        return patches

    @property
    def input_size(self) -> Tuple[int, int]:
        return (512, 512)


class OnnxPortraitEnhancer(BasePortraitEnhancer):
    """
    Bộ thực thi ONNX Runtime cho mô hình AI làm đẹp chân dung (mặc định GFPGAN v1.4 FP16).
    Khởi tạo session lười (lazy-load) và an toàn đa luồng; tự động phát hiện NVIDIA CUDA
    với fallback mượt về CPU khi máy không có GPU hoặc thiếu thư viện CUDA.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_PORTRAIT_MODEL_ID,
        model_path: Optional[str] = None,
        spec: Optional[PortraitModelSpec] = None,
        prefer_gpu: bool = True,
        intra_threads: Optional[int] = None,
    ):
        self._spec = spec or PORTRAIT_MODEL_REGISTRY.get(
            model_id,
            PortraitModelSpec(model_id=model_id, display_name=model_id, filename=f"{model_id}.onnx"),
        )
        self._model_path = resolve_offline_model_path(self._spec.filename, explicit_path=model_path)
        self._prefer_gpu = bool(prefer_gpu)
        self._intra_threads = intra_threads or min(4, max(2, (os.cpu_count() or 4)))

        self._lock = threading.Lock()
        self._session: Any = None
        self._input_name: str = "input"
        self._output_name: str = "output"
        self._active_provider: str = "uninitialized"
        self._init_error: str = ""
        self._load_failed: bool = False
        self._ort_importable: bool = self._check_ort_importable()

        if not os.path.isfile(self._model_path) or os.path.getsize(self._model_path) < 1024:
            self._load_failed = True
            self._active_provider = "unavailable"
            self._init_error = f"Không tìm thấy mô hình AI cục bộ: {self._model_path}"
        elif not self._ort_importable:
            self._load_failed = True
            self._active_provider = "unavailable"
            self._init_error = "Thư viện onnxruntime không khả dụng."

    @staticmethod
    def _check_ort_importable() -> bool:
        try:
            import onnxruntime  # noqa: F401
            return True
        except Exception:
            return False

    @property
    def spec(self) -> PortraitModelSpec:
        return self._spec

    @property
    def model_path(self) -> str:
        return self._model_path

    @property
    def model_id(self) -> str:
        return self._spec.model_id

    @property
    def input_size(self) -> Tuple[int, int]:
        return self._spec.input_size

    @property
    def is_available(self) -> bool:
        return (not self._load_failed) and self._ort_importable and os.path.isfile(self._model_path)

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    @property
    def active_provider(self) -> str:
        return self._active_provider

    @property
    def init_error(self) -> str:
        return self._init_error

    def _ensure_session(self) -> bool:
        if self._session is not None:
            return True
        if self._load_failed:
            return False

        with self._lock:
            if self._session is not None:
                return True
            if self._load_failed:
                return False

            try:
                import onnxruntime as ort

                # Hạn chế cảnh báo log thừa từ ORT constant folding
                ort.set_default_logger_severity(3)
                avail_providers = list(ort.get_available_providers())

                so = ort.SessionOptions()
                so.intra_op_num_threads = int(self._intra_threads)
                so.inter_op_num_threads = 1
                so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                so.enable_mem_pattern = True
                try:
                    so.add_session_config_entry("session.intra_op.allow_spinning", "0")
                except Exception:
                    pass

                t0 = time.perf_counter()
                sess = None

                # Ưu tiên NVIDIA CUDA nếu trình thực thi & phần cứng sẵn sàng; fallback an toàn sang CPU
                if self._prefer_gpu and "CUDAExecutionProvider" in avail_providers:
                    try:
                        sess = ort.InferenceSession(
                            self._model_path,
                            sess_options=so,
                            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                        )
                    except Exception as cuda_ex:
                        logger.warning(
                            "Không thể khởi tạo CUDAExecutionProvider (%s); tự động fallback sang CPU.",
                            cuda_ex,
                        )
                        sess = None

                if sess is None:
                    sess = ort.InferenceSession(
                        self._model_path,
                        sess_options=so,
                        providers=["CPUExecutionProvider"],
                    )

                self._session = sess
                self._input_name = sess.get_inputs()[0].name
                self._output_name = sess.get_outputs()[0].name
                sess_providers = sess.get_providers()
                self._active_provider = sess_providers[0] if sess_providers else "CPUExecutionProvider"

                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    "Khởi tạo %s thành công (provider=%s, %.1f ms): %s",
                    self._spec.display_name,
                    self._active_provider,
                    elapsed_ms,
                    self._model_path,
                )
                return True
            except Exception as ex:
                self._load_failed = True
                self._active_provider = "unavailable"
                self._init_error = str(ex)
                logger.warning("Không thể nạp mô hình AI %s (fallback về SmartBeauty cơ bản): %s", self._model_path, ex)
                return False

    def warmup(self) -> bool:
        """Chủ động nạp session trước khi chụp/chỉnh nếu cần."""
        return self._ensure_session()

    def close(self) -> None:
        """Giải phóng ONNX InferenceSession sạch sẽ khi tắt ứng dụng."""
        with self._lock:
            self._session = None
            self._active_provider = "uninitialized"

    def enhance_aligned_crop(self, aligned_bgr: np.ndarray) -> np.ndarray:
        """Chạy suy luận mạng neural trên khuôn mặt đã căn chỉnh (512x512 BGR)."""
        if not self._ensure_session() or aligned_bgr is None or aligned_bgr.size == 0:
            return aligned_bgr.copy() if aligned_bgr is not None else aligned_bgr

        in_w, in_h = self._spec.input_size
        resized = aligned_bgr
        if aligned_bgr.shape[:2] != (in_h, in_w):
            resized = cv2.resize(aligned_bgr, (in_w, in_h), interpolation=cv2.INTER_AREA)

        if self._spec.color_order.upper() == "RGB":
            arr = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        else:
            arr = resized.astype(np.float32) / 255.0

        if self._spec.norm_mode == "neg1_pos1":
            arr = (arr - 0.5) / 0.5

        tensor = np.transpose(arr, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

        with self._lock:
            out_tensor = self._session.run([self._output_name], {self._input_name: tensor})[0][0]

        out_img = np.transpose(out_tensor, (1, 2, 0))
        if self._spec.norm_mode == "neg1_pos1":
            out_img = (out_img * 0.5) + 0.5
        out_u8 = np.clip(out_img * 255.0, 0.0, 255.0).astype(np.uint8)

        if self._spec.color_order.upper() == "RGB":
            return cv2.cvtColor(out_u8, cv2.COLOR_RGB2BGR)
        return out_u8


def create_portrait_enhancer(
    model_id: str = DEFAULT_PORTRAIT_MODEL_ID,
    model_path: Optional[str] = None,
    prefer_gpu: bool = True,
) -> OnnxPortraitEnhancer:
    """Factory tạo instance AI Portrait Enhancer theo tên hoặc đường dẫn mô hình."""
    return OnnxPortraitEnhancer(model_id=model_id, model_path=model_path, prefer_gpu=prefer_gpu)
