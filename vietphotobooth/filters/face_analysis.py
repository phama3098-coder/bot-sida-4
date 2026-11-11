"""
1998 TEAM — Face Analysis Module (MediaPipe Face Landmarker 478 Points)
Tách biệt hoàn toàn phân tích cấu trúc khuôn mặt (Face Analysis) khỏi xử lý làm đẹp (Beauty Processing):
- Sử dụng Google MediaPipe Face Landmarker (`face_landmarker.task`) chạy 100% offline trên Windows.
- Phát hiện tối đa 6 khuôn mặt và trích xuất đầy đủ 478 điểm facial landmarks 3D.
- Tính toán góc nghiêng khuôn mặt 3D (Yaw, Pitch, Roll) từ transformation matrix / geometry fallback.
- Xây dựng Face Mesh topology và phân tách các vùng giải phẫu chuyên biệt:
  1. Da mặt tổng thể (Face Oval)
  2. Trán (Forehead)
  3. Hai má (Left / Right Cheeks)
  4. Vùng mắt & quầng thâm dưới mắt (Eyes & Infraorbital Under-Eye)
  5. Môi ngoài & khoang miệng trong (Lips Outer / Inner)
  6. Vùng mũi & sống mũi (Nose & Nasal Bridge)
  7. Đường viền mặt, xương hàm & cằm (Jawline & Chin)
- Hỗ trợ cơ chế fallback an toàn về OpenCV YuNet ONNX (`FaceEyeDetector`) nếu thiếu mô hình hoặc không khả dụng.
"""

import os
import math
import time
import threading
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any

import cv2
import numpy as np

from vietphotobooth.camera.face_detector import FaceEyeDetector, DetectedFace

logger = logging.getLogger("VietPhotoBooth.filters.face_analysis")

MEDIAPIPE_LANDMARK_COUNT = 478

# ==============================================================================
# CANONICAL MEDIAPIPE FACE MESH REGION TOPOLOGIES (478 LANDMARKS)
# Các chuỗi đỉnh được sắp xếp tuần tự theo chu vi khép kín để fillPoly chính xác.
# ==============================================================================

# Đường viền tổng thể khuôn mặt & cằm (36 điểm theo FaceLandmarksConnections.FACE_LANDMARKS_FACE_OVAL)
FACE_OVAL_INDICES: Tuple[int, ...] = (
    10, 338, 297, 332, 284, 251, 389, 356, 454,
    323, 361, 288, 397, 365, 379, 378, 400, 377,
    152, 148, 176, 149, 150, 136, 172, 58, 132,
    93, 234, 127, 162, 21, 54, 103, 67, 109,
)

# Vùng trán (từ biên trên của Face Oval xuống mép trên hai hàng lông mày)
FOREHEAD_INDICES: Tuple[int, ...] = (
    21, 54, 103, 67, 109, 10, 338, 297, 332, 284, 251,
    300, 293, 334, 296, 336, 9, 107, 66, 105, 63, 70,
)

# Mắt phải (Right Eye - phía trái ảnh chính diện)
RIGHT_EYE_INDICES: Tuple[int, ...] = (
    33, 246, 161, 160, 159, 158, 157, 173,
    133, 155, 154, 153, 145, 144, 163, 7,
)

# Mắt trái (Left Eye - phía phải ảnh chính diện)
LEFT_EYE_INDICES: Tuple[int, ...] = (
    263, 466, 388, 387, 386, 385, 384, 398,
    362, 382, 381, 380, 374, 373, 390, 249,
)

# Lông mày phải & trái
RIGHT_EYEBROW_INDICES: Tuple[int, ...] = (70, 63, 105, 66, 107, 55, 65, 52, 53, 46)
LEFT_EYEBROW_INDICES: Tuple[int, ...] = (300, 293, 334, 296, 336, 285, 295, 282, 283, 276)

# Vùng dưới mắt / quầng thâm mắt (dải infraorbital tear-trough dưới mí mắt, tách khỏi hàng mi dưới)
RIGHT_UNDER_EYE_INDICES: Tuple[int, ...] = (
    226, 31, 228, 229, 230, 231, 232, 233, 244,
    128, 121, 120, 119, 118, 117, 111,
)
LEFT_UNDER_EYE_INDICES: Tuple[int, ...] = (
    446, 261, 448, 449, 450, 451, 452, 453, 464,
    357, 350, 349, 348, 347, 346, 340,
)

# Hai gò má (giữ tách biệt rõ nét khỏi sống mũi, mắt và khóe miệng)
RIGHT_CHEEK_INDICES: Tuple[int, ...] = (116, 117, 118, 119, 100, 36, 206, 207, 187, 123)
LEFT_CHEEK_INDICES: Tuple[int, ...] = (345, 346, 347, 348, 329, 266, 426, 427, 411, 352)

# Sống mũi & đầu mũi (xác định vùng đánh khối sáng nhẹ trên mũi)
NOSE_BRIDGE_INDICES: Tuple[int, ...] = (
    193, 188, 198, 131, 134, 51, 4, 281, 363, 360, 420, 412, 417, 168,
)
NOSE_REGION_INDICES: Tuple[int, ...] = (
    168, 193, 188, 198, 209, 49, 129, 98, 97, 2, 326, 327, 358, 279, 429, 420, 412, 417,
)

# Môi ngoài & khoang miệng trong (loại trừ răng và hốc miệng tối)
LIPS_OUTER_INDICES: Tuple[int, ...] = (
    61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291,
    375, 321, 405, 314, 17, 84, 181, 91, 146,
)
LIPS_INNER_INDICES: Tuple[int, ...] = (
    78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308,
    324, 318, 402, 317, 14, 87, 178, 88, 95,
)

# Đường xương hàm & cằm
JAWLINE_RIGHT_INDICES: Tuple[int, ...] = (234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152)
JAWLINE_LEFT_INDICES: Tuple[int, ...] = (454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152)
CHIN_LANDMARK_INDEX: int = 152

# Mống mắt (Iris indices từ MediaPipe 478)
RIGHT_IRIS_CENTER_INDEX: int = 468
LEFT_IRIS_CENTER_INDEX: int = 473


@dataclass
class HeadPose:
    """Thông tin hướng và góc nghiêng khuôn mặt (độ)."""
    yaw: float = 0.0    # Quay trái (-) / phải (+)
    pitch: float = 0.0  # Ngẩng (+) / cúi (-)
    roll: float = 0.0   # Nghiêng đầu trái / phải
    pose_label: str = "Thẳng diện"


@dataclass
class FaceMeshRegions:
    """Tập hợp đa giác tọa độ pixel (N, 2) int32 theo giải phẫu cho từng vùng khuôn mặt."""
    face_oval: Optional[np.ndarray] = None
    forehead: Optional[np.ndarray] = None
    left_cheek: Optional[np.ndarray] = None
    right_cheek: Optional[np.ndarray] = None
    left_eye: Optional[np.ndarray] = None
    right_eye: Optional[np.ndarray] = None
    left_eyebrow: Optional[np.ndarray] = None
    right_eyebrow: Optional[np.ndarray] = None
    left_under_eye: Optional[np.ndarray] = None
    right_under_eye: Optional[np.ndarray] = None
    nose_bridge: Optional[np.ndarray] = None
    nose: Optional[np.ndarray] = None
    lips_outer: Optional[np.ndarray] = None
    lips_inner: Optional[np.ndarray] = None
    jawline_left: Optional[np.ndarray] = None
    jawline_right: Optional[np.ndarray] = None
    chin_point: Optional[Tuple[float, float]] = None

    def scaled(self, ratio: float) -> "FaceMeshRegions":
        """Tạo bản sao toàn bộ tọa độ đa giác đã nhân tỷ lệ."""
        def _sc(arr: Optional[np.ndarray]) -> Optional[np.ndarray]:
            if arr is None:
                return None
            return np.round(arr.astype(np.float32) * ratio).astype(np.int32)

        chin = (
            (self.chin_point[0] * ratio, self.chin_point[1] * ratio)
            if self.chin_point is not None else None
        )
        return FaceMeshRegions(
            face_oval=_sc(self.face_oval),
            forehead=_sc(self.forehead),
            left_cheek=_sc(self.left_cheek),
            right_cheek=_sc(self.right_cheek),
            left_eye=_sc(self.left_eye),
            right_eye=_sc(self.right_eye),
            left_eyebrow=_sc(self.left_eyebrow),
            right_eyebrow=_sc(self.right_eyebrow),
            left_under_eye=_sc(self.left_under_eye),
            right_under_eye=_sc(self.right_under_eye),
            nose_bridge=_sc(self.nose_bridge),
            nose=_sc(self.nose),
            lips_outer=_sc(self.lips_outer),
            lips_inner=_sc(self.lips_inner),
            jawline_left=_sc(self.jawline_left),
            jawline_right=_sc(self.jawline_right),
            chin_point=chin,
        )


@dataclass
class AnalyzedFace:
    """
    Dữ liệu phân tích khuôn mặt đầy đủ (tương thích ngược với các trường của DetectedFace):
    - Chứa bounding box + 5 điểm chính (right_eye, left_eye, nose, mouth_right, mouth_left).
    - Khi dùng MediaPipe: chứa đủ `landmarks_px` shape (478, 3), `head_pose`, và `regions` giải phẫu.
    """
    x: float
    y: float
    w: float
    h: float
    confidence: float
    right_eye: Optional[Tuple[float, float]] = None
    left_eye: Optional[Tuple[float, float]] = None
    nose: Optional[Tuple[float, float]] = None
    mouth_right: Optional[Tuple[float, float]] = None
    mouth_left: Optional[Tuple[float, float]] = None
    landmarks_px: Optional[np.ndarray] = None       # (478, 3) float32
    landmarks_norm: Optional[np.ndarray] = None     # (478, 3) float32
    head_pose: HeadPose = field(default_factory=HeadPose)
    regions: Optional[FaceMeshRegions] = None
    analysis_source: str = "mediapipe_478"

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.w, self.h)

    @property
    def landmark_count(self) -> int:
        if self.landmarks_px is None:
            return 0
        return int(self.landmarks_px.shape[0])

    @property
    def has_mesh(self) -> bool:
        return self.landmarks_px is not None and self.landmarks_px.shape[0] >= 468 and self.regions is not None

    def to_detected_face(self) -> DetectedFace:
        return DetectedFace(
            x=self.x, y=self.y, w=self.w, h=self.h,
            confidence=self.confidence,
            right_eye=self.right_eye,
            left_eye=self.left_eye,
            nose=self.nose,
            mouth_right=self.mouth_right,
            mouth_left=self.mouth_left,
        )


@dataclass
class FaceAnalysisResult:
    """Kết quả phân tích toàn bộ ảnh vừa chụp."""
    faces: List[AnalyzedFace] = field(default_factory=list)
    source: str = "none"              # "mediapipe_face_landmarker" | "yunet_fallback" | "none"
    elapsed_ms: float = 0.0
    is_mediapipe_active: bool = False
    error_message: str = ""

    @property
    def face_count(self) -> int:
        return len(self.faces)

    @property
    def total_landmarks(self) -> int:
        return sum(f.landmark_count for f in self.faces)

    @property
    def status_summary(self) -> str:
        n = len(self.faces)
        if n == 0:
            return "Không Phát Hiện Khuôn Mặt"
        if self.source == "mediapipe_face_landmarker":
            pts = self.faces[0].landmark_count
            if n == 1:
                return f"MediaPipe {pts} Điểm · 1 Khuôn Mặt ({self.faces[0].head_pose.pose_label})"
            return f"MediaPipe {pts} Điểm · {n} Khuôn Mặt"
        return f"Nhận Diện {n} Khuôn Mặt (Fallback)"


def _get_tesselation_edges() -> List[Tuple[int, int]]:
    """Trả về danh sách cạnh lưới Face Mesh (2556 cạnh từ MediaPipe)."""
    try:
        from mediapipe.tasks.python.vision import FaceLandmarksConnections
        return [(int(c.start), int(c.end)) for c in FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION]
    except Exception:
        return []


def _extract_poly(landmarks_px: np.ndarray, indices: Tuple[int, ...]) -> Optional[np.ndarray]:
    if landmarks_px is None or len(landmarks_px) == 0:
        return None
    max_idx = landmarks_px.shape[0]
    valid = [i for i in indices if 0 <= i < max_idx]
    if len(valid) < 3:
        return None
    return np.round(landmarks_px[valid, :2]).astype(np.int32)


def _compute_head_pose_from_matrix(matrix: Optional[np.ndarray], landmarks_px: np.ndarray) -> HeadPose:
    """Tính Yaw/Pitch/Roll từ facial transformation matrix 4x4 (fallback hình học 2D nếu thiếu)."""
    yaw = pitch = roll = 0.0
    if matrix is not None and isinstance(matrix, np.ndarray) and matrix.shape[:2] == (4, 4):
        try:
            r_mat = matrix[:3, :3].astype(np.float64)
            # Chuẩn hóa ma trận xoay loại bỏ scale
            col_norms = np.linalg.norm(r_mat, axis=0)
            col_norms[col_norms < 1e-8] = 1.0
            r_norm = r_mat / col_norms

            # Phân rã góc Euler Y-X-Z (Yaw quanh Y, Pitch quanh X, Roll quanh Z)
            sy = math.sqrt(r_norm[0, 0] * r_norm[0, 0] + r_norm[1, 0] * r_norm[1, 0])
            singular = sy < 1e-6
            if not singular:
                pitch = math.degrees(math.atan2(r_norm[2, 1], r_norm[2, 2]))
                yaw = math.degrees(math.atan2(-r_norm[2, 0], sy))
                roll = math.degrees(math.atan2(r_norm[1, 0], r_norm[0, 0]))
            else:
                pitch = math.degrees(math.atan2(-r_norm[1, 2], r_norm[1, 1]))
                yaw = math.degrees(math.atan2(-r_norm[2, 0], sy))
                roll = 0.0
        except Exception:
            yaw = pitch = roll = 0.0
    elif landmarks_px is not None and landmarks_px.shape[0] >= 468:
        # Fallback ước lượng hình học từ 2 mắt, chóp mũi, cằm và 2 bên má
        re = landmarks_px[33, :2]
        le = landmarks_px[263, :2]
        nose = landmarks_px[1, :2]
        right_cheek = landmarks_px[234, :2]
        left_cheek = landmarks_px[454, :2]
        roll = math.degrees(math.atan2(float(le[1] - re[1]), float(le[0] - re[0])))
        face_w = max(1.0, float(np.linalg.norm(left_cheek - right_cheek)))
        mid_x = 0.5 * (float(left_cheek[0]) + float(right_cheek[0]))
        yaw = ((float(nose[0]) - mid_x) / (face_w * 0.5)) * 45.0

    # Làm tròn gọn và phân loại hướng khuôn mặt
    yaw = round(float(yaw), 1)
    pitch = round(float(pitch), 1)
    roll = round(float(roll), 1)

    if yaw > 15.0:
        label = "Nghiêng trái"
    elif yaw < -15.0:
        label = "Nghiêng phải"
    elif pitch > 18.0:
        label = "Ngẩng nhẹ"
    elif pitch < -18.0:
        label = "Cúi nhẹ"
    elif abs(roll) > 15.0:
        label = "Nghiêng đầu"
    else:
        label = "Thẳng diện"

    return HeadPose(yaw=yaw, pitch=pitch, roll=roll, pose_label=label)


def build_face_regions(landmarks_px: np.ndarray) -> FaceMeshRegions:
    """Xây dựng toàn bộ các vùng giải phẫu khuôn mặt từ 478 facial landmarks."""
    chin_pt = None
    if landmarks_px is not None and landmarks_px.shape[0] > CHIN_LANDMARK_INDEX:
        chin_pt = (float(landmarks_px[CHIN_LANDMARK_INDEX, 0]), float(landmarks_px[CHIN_LANDMARK_INDEX, 1]))

    return FaceMeshRegions(
        face_oval=_extract_poly(landmarks_px, FACE_OVAL_INDICES),
        forehead=_extract_poly(landmarks_px, FOREHEAD_INDICES),
        left_cheek=_extract_poly(landmarks_px, LEFT_CHEEK_INDICES),
        right_cheek=_extract_poly(landmarks_px, RIGHT_CHEEK_INDICES),
        left_eye=_extract_poly(landmarks_px, LEFT_EYE_INDICES),
        right_eye=_extract_poly(landmarks_px, RIGHT_EYE_INDICES),
        left_eyebrow=_extract_poly(landmarks_px, LEFT_EYEBROW_INDICES),
        right_eyebrow=_extract_poly(landmarks_px, RIGHT_EYEBROW_INDICES),
        left_under_eye=_extract_poly(landmarks_px, LEFT_UNDER_EYE_INDICES),
        right_under_eye=_extract_poly(landmarks_px, RIGHT_UNDER_EYE_INDICES),
        nose_bridge=_extract_poly(landmarks_px, NOSE_BRIDGE_INDICES),
        nose=_extract_poly(landmarks_px, NOSE_REGION_INDICES),
        lips_outer=_extract_poly(landmarks_px, LIPS_OUTER_INDICES),
        lips_inner=_extract_poly(landmarks_px, LIPS_INNER_INDICES),
        jawline_left=np.round(landmarks_px[list(JAWLINE_LEFT_INDICES), :2]).astype(np.int32)
        if landmarks_px is not None and landmarks_px.shape[0] > 454 else None,
        jawline_right=np.round(landmarks_px[list(JAWLINE_RIGHT_INDICES), :2]).astype(np.int32)
        if landmarks_px is not None and landmarks_px.shape[0] > 234 else None,
        chin_point=chin_pt,
    )


class MediaPipeFaceAnalyzer:
    """
    Bộ phân tích khuôn mặt offline sử dụng MediaPipe Face Landmarker (478 landmarks).
    Có cơ chế fallback an toàn về OpenCV YuNet ONNX khi không có tệp model hoặc thiết bị thiếu hỗ trợ.
    """

    def __init__(
        self,
        landmarker_model_path: Optional[str] = None,
        fallback_yunet_path: Optional[str] = None,
        max_num_faces: int = 6,
        min_detection_confidence: float = 0.45,
        enable_fallback: bool = True,
    ):
        self._max_num_faces = max_num_faces
        self._min_conf = min_detection_confidence
        self._lock = threading.Lock()
        self._landmarker = None
        self._mp_module = None
        self._mediapipe_ready = False
        self._model_path = landmarker_model_path or self._resolve_default_landmarker_path()

        # Chỉ dùng fallback YuNet nếu không truyền riêng path hỏng (bảo toàn kiểm thử missing_model_fallback)
        self._enable_fallback = enable_fallback
        if fallback_yunet_path is not None:
            self._yunet = FaceEyeDetector(model_path=fallback_yunet_path)
        else:
            self._yunet = FaceEyeDetector()

        if self._model_path and os.path.exists(self._model_path):
            self._init_mediapipe()
        else:
            logger.warning("Không tìm thấy mô hình MediaPipe Face Landmarker tại: %s", self._model_path)

    @classmethod
    def _resolve_default_landmarker_path(cls) -> Optional[str]:
        fname = "face_landmarker.task"
        candidates = []
        if hasattr(os, "_MEIPASS"):
            meipass = getattr(os, "_MEIPASS")
            candidates.append(os.path.join(meipass, "Assets", "Models", fname))

        candidates.append(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Assets", "Models", fname))
        )
        candidates.append(os.path.abspath(os.path.join(os.getcwd(), "Assets", "Models", fname)))

        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def _init_mediapipe(self) -> bool:
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode

            options = FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=self._model_path),
                running_mode=RunningMode.IMAGE,
                num_faces=self._max_num_faces,
                min_face_detection_confidence=self._min_conf,
                min_face_presence_confidence=self._min_conf,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
            )
            self._landmarker = FaceLandmarker.create_from_options(options)
            self._mp_module = mp
            self._mediapipe_ready = True
            logger.info("Khởi tạo MediaPipe Face Landmarker thành công (478 điểm, offline): %s", self._model_path)
            return True
        except Exception as ex:
            logger.error("Lỗi khởi tạo MediaPipe Face Landmarker: %s", ex)
            self._landmarker = None
            self._mediapipe_ready = False
            return False

    @property
    def is_mediapipe_available(self) -> bool:
        return self._mediapipe_ready and self._landmarker is not None

    @property
    def is_available(self) -> bool:
        return self.is_mediapipe_available or (self._enable_fallback and self._yunet.is_available)

    @property
    def model_path(self) -> str:
        return self._model_path or ""

    def close(self) -> None:
        with self._lock:
            if self._landmarker is not None:
                try:
                    self._landmarker.close()
                except Exception:
                    pass
                self._landmarker = None
                self._mediapipe_ready = False

    def analyze(
        self,
        image_bgr_or_rgb: np.ndarray,
        is_bgr: bool = True,
        max_proc_width: int = 1280,
    ) -> FaceAnalysisResult:
        """
        Phân tích ảnh khuôn mặt hoàn toàn offline:
        - Ưu tiên MediaPipe Face Landmarker (478 landmarks + góc nghiêng + Face Mesh regions).
        - Tự động fallback sang YuNet nếu MediaPipe không khả dụng hoặc không phát hiện mặt trên ảnh đơn giản/tổng hợp.
        """
        t0 = time.perf_counter()
        if image_bgr_or_rgb is None or image_bgr_or_rgb.size == 0:
            return FaceAnalysisResult(source="none", elapsed_ms=0.0, is_mediapipe_active=self.is_mediapipe_available)

        rgb = cv2.cvtColor(image_bgr_or_rgb, cv2.COLOR_BGR2RGB) if is_bgr else image_bgr_or_rgb
        if not rgb.flags["C_CONTIGUOUS"]:
            rgb = np.ascontiguousarray(rgb)

        orig_h, orig_w = rgb.shape[:2]
        if orig_h < 8 or orig_w < 8:
            return FaceAnalysisResult(source="none", elapsed_ms=0.0, is_mediapipe_active=self.is_mediapipe_available)

        # Thu nhỏ tạm thời cho tốc độ infer tối ưu rồi ánh xạ tọa độ về kích thước gốc
        scale = 1.0
        if orig_w > max_proc_width:
            scale = float(max_proc_width) / float(orig_w)
            proc_w = max_proc_width
            proc_h = max(8, int(round(orig_h * scale)))
            proc_rgb = cv2.resize(rgb, (proc_w, proc_h), interpolation=cv2.INTER_LINEAR)
        else:
            proc_rgb = rgb

        # 1. Thử phân tích bằng MediaPipe Face Landmarker (478 điểm)
        if self.is_mediapipe_available:
            try:
                mp = self._mp_module
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=proc_rgb)
                with self._lock:
                    mp_result = self._landmarker.detect(mp_img) if self._landmarker is not None else None

                if mp_result is not None and mp_result.face_landmarks:
                    faces_out: List[AnalyzedFace] = []
                    matrices = getattr(mp_result, "facial_transformation_matrixes", None) or []

                    for idx, lm_list in enumerate(mp_result.face_landmarks):
                        lm_norm = np.array([[lm.x, lm.y, lm.z] for lm in lm_list], dtype=np.float32)
                        lm_px = np.empty_like(lm_norm)
                        lm_px[:, 0] = np.clip(lm_norm[:, 0] * orig_w, 0.0, max(0.0, float(orig_w - 1)))
                        lm_px[:, 1] = np.clip(lm_norm[:, 1] * orig_h, 0.0, max(0.0, float(orig_h - 1)))
                        lm_px[:, 2] = lm_norm[:, 2] * orig_w

                        # Bounding box từ toàn bộ 478 landmarks
                        xs = lm_px[:, 0]
                        ys = lm_px[:, 1]
                        min_x, max_x = float(np.min(xs)), float(np.max(xs))
                        min_y, max_y = float(np.min(ys)), float(np.max(ys))
                        fw = max(4.0, max_x - min_x)
                        fh = max(4.0, max_y - min_y)

                        # Điểm mắt/mũi/môi chuẩn tương thích ngược
                        r_eye_pt = (
                            (float(lm_px[RIGHT_IRIS_CENTER_INDEX, 0]), float(lm_px[RIGHT_IRIS_CENTER_INDEX, 1]))
                            if lm_px.shape[0] > RIGHT_IRIS_CENTER_INDEX
                            else (float(np.mean(lm_px[list(RIGHT_EYE_INDICES), 0])), float(np.mean(lm_px[list(RIGHT_EYE_INDICES), 1])))
                        )
                        l_eye_pt = (
                            (float(lm_px[LEFT_IRIS_CENTER_INDEX, 0]), float(lm_px[LEFT_IRIS_CENTER_INDEX, 1]))
                            if lm_px.shape[0] > LEFT_IRIS_CENTER_INDEX
                            else (float(np.mean(lm_px[list(LEFT_EYE_INDICES), 0])), float(np.mean(lm_px[list(LEFT_EYE_INDICES), 1])))
                        )
                        nose_pt = (float(lm_px[1, 0]), float(lm_px[1, 1]))
                        mr_pt = (float(lm_px[61, 0]), float(lm_px[61, 1]))
                        ml_pt = (float(lm_px[291, 0]), float(lm_px[291, 1]))

                        t_mat = matrices[idx] if idx < len(matrices) else None
                        pose = _compute_head_pose_from_matrix(t_mat, lm_px)
                        regions = build_face_regions(lm_px)

                        faces_out.append(AnalyzedFace(
                            x=min_x,
                            y=min_y,
                            w=fw,
                            h=fh,
                            confidence=0.95,
                            right_eye=r_eye_pt,
                            left_eye=l_eye_pt,
                            nose=nose_pt,
                            mouth_right=mr_pt,
                            mouth_left=ml_pt,
                            landmarks_px=lm_px,
                            landmarks_norm=lm_norm,
                            head_pose=pose,
                            regions=regions,
                            analysis_source="mediapipe_478",
                        ))

                    elapsed = (time.perf_counter() - t0) * 1000.0
                    return FaceAnalysisResult(
                        faces=faces_out,
                        source="mediapipe_face_landmarker",
                        elapsed_ms=elapsed,
                        is_mediapipe_active=True,
                    )
            except Exception as ex:
                logger.warning("MediaPipe FaceLandmarker lỗi runtime, chuyển sang fallback YuNet: %s", ex)

        # 2. Fallback an toàn sang OpenCV YuNet nếu được bật
        if self._enable_fallback and self._yunet.is_available:
            try:
                yunet_faces = self._yunet.detect_faces(rgb, max_proc_width=max_proc_width)
                if yunet_faces:
                    fallback_list: List[AnalyzedFace] = []
                    for yf in yunet_faces:
                        roll = 0.0
                        if yf.right_eye and yf.left_eye:
                            roll = round(
                                math.degrees(math.atan2(yf.left_eye[1] - yf.right_eye[1], yf.left_eye[0] - yf.right_eye[0])),
                                1,
                            )
                        fallback_list.append(AnalyzedFace(
                            x=yf.x, y=yf.y, w=yf.w, h=yf.h,
                            confidence=yf.confidence,
                            right_eye=yf.right_eye,
                            left_eye=yf.left_eye,
                            nose=yf.nose,
                            mouth_right=yf.mouth_right,
                            mouth_left=yf.mouth_left,
                            landmarks_px=None,
                            landmarks_norm=None,
                            head_pose=HeadPose(yaw=0.0, pitch=0.0, roll=roll, pose_label="Fallback 5 điểm"),
                            regions=None,
                            analysis_source="yunet_fallback",
                        ))
                    elapsed = (time.perf_counter() - t0) * 1000.0
                    return FaceAnalysisResult(
                        faces=fallback_list,
                        source="yunet_fallback",
                        elapsed_ms=elapsed,
                        is_mediapipe_active=self.is_mediapipe_available,
                    )
            except Exception as ex:
                logger.error("Fallback YuNet thất bại: %s", ex)

        elapsed = (time.perf_counter() - t0) * 1000.0
        return FaceAnalysisResult(
            faces=[],
            source="none",
            elapsed_ms=elapsed,
            is_mediapipe_active=self.is_mediapipe_available,
        )

    @staticmethod
    def scale_analyzed_face(face: Any, scale_ratio: float) -> Any:
        """Ánh xạ dữ liệu AnalyzedFace hoặc DetectedFace sang kích thước ảnh khác."""
        if scale_ratio == 1.0:
            return face

        r_eye = (face.right_eye[0] * scale_ratio, face.right_eye[1] * scale_ratio) if face.right_eye else None
        l_eye = (face.left_eye[0] * scale_ratio, face.left_eye[1] * scale_ratio) if face.left_eye else None
        nose = (face.nose[0] * scale_ratio, face.nose[1] * scale_ratio) if face.nose else None
        m_r = (face.mouth_right[0] * scale_ratio, face.mouth_right[1] * scale_ratio) if face.mouth_right else None
        m_l = (face.mouth_left[0] * scale_ratio, face.mouth_left[1] * scale_ratio) if face.mouth_left else None

        if isinstance(face, AnalyzedFace):
            scaled_lm = None
            if face.landmarks_px is not None:
                scaled_lm = face.landmarks_px.copy()
                scaled_lm[:, 0] *= scale_ratio
                scaled_lm[:, 1] *= scale_ratio
                scaled_lm[:, 2] *= scale_ratio

            scaled_regions = face.regions.scaled(scale_ratio) if face.regions is not None else None
            return AnalyzedFace(
                x=face.x * scale_ratio,
                y=face.y * scale_ratio,
                w=face.w * scale_ratio,
                h=face.h * scale_ratio,
                confidence=face.confidence,
                right_eye=r_eye,
                left_eye=l_eye,
                nose=nose,
                mouth_right=m_r,
                mouth_left=m_l,
                landmarks_px=scaled_lm,
                landmarks_norm=face.landmarks_norm,
                head_pose=face.head_pose,
                regions=scaled_regions,
                analysis_source=face.analysis_source,
            )

        return DetectedFace(
            x=face.x * scale_ratio,
            y=face.y * scale_ratio,
            w=face.w * scale_ratio,
            h=face.h * scale_ratio,
            confidence=face.confidence,
            right_eye=r_eye,
            left_eye=l_eye,
            nose=nose,
            mouth_right=m_r,
            mouth_left=m_l,
        )


def draw_face_mesh_overlay(
    image_bgr: np.ndarray,
    faces: List[Any],
    show_tesselation: bool = True,
    show_regions: bool = True,
    show_landmarks: bool = True,
) -> np.ndarray:
    """
    Vẽ lưới Face Mesh (478 điểm), các vùng giải phẫu và góc nghiêng đầu lên bản sao ảnh để kiểm tra trực quan.
    Không làm thay đổi ảnh gốc đầu vào.
    """
    if image_bgr is None or image_bgr.size == 0:
        return image_bgr

    canvas = image_bgr.copy()
    edges = _get_tesselation_edges() if show_tesselation else []

    for face in faces:
        if isinstance(face, AnalyzedFace) and face.has_mesh and face.landmarks_px is not None:
            pts_xy = np.round(face.landmarks_px[:, :2]).astype(np.int32)

            # 1. Vẽ lưới tesselation mảnh (Champagne Gold mờ)
            if show_tesselation and edges:
                mesh_layer = canvas.copy()
                n_pts = len(pts_xy)
                for s_idx, e_idx in edges:
                    if s_idx < n_pts and e_idx < n_pts:
                        cv2.line(mesh_layer, tuple(pts_xy[s_idx]), tuple(pts_xy[e_idx]), (185, 200, 220), 1, cv2.LINE_AA)
                canvas = cv2.addWeighted(canvas, 0.72, mesh_layer, 0.28, 0)

            # 2. Vẽ ranh giới từng vùng giải phẫu phân biệt bằng màu sắc
            if show_regions and face.regions is not None:
                reg = face.regions
                region_specs = [
                    (reg.face_oval, (99, 154, 185), 2),         # Đường viền mặt (Gold)
                    (reg.forehead, (220, 185, 110), 2),         # Trán (Sky Blue)
                    (reg.left_cheek, (140, 210, 140), 2),       # Má trái (Sage Green)
                    (reg.right_cheek, (140, 210, 140), 2),      # Má phải (Sage Green)
                    (reg.left_under_eye, (90, 220, 240), 2),    # Vùng dưới mắt trái (Amber)
                    (reg.right_under_eye, (90, 220, 240), 2),   # Vùng dưới mắt phải (Amber)
                    (reg.nose_bridge, (235, 165, 140), 2),      # Sống mũi (Soft Cyan)
                    (reg.lips_outer, (130, 105, 225), 2),       # Viền môi ngoài (Rose)
                    (reg.lips_inner, (80, 80, 180), 1),         # Môi trong / khoang miệng
                    (reg.left_eye, (180, 240, 180), 1),
                    (reg.right_eye, (180, 240, 180), 1),
                ]
                for poly, col, thick in region_specs:
                    if poly is not None and len(poly) >= 3:
                        cv2.polylines(canvas, [poly], True, col, thick, cv2.LINE_AA)

            # 3. Vẽ các điểm landmarks (478 điểm)
            if show_landmarks:
                for pt in pts_xy:
                    cv2.circle(canvas, tuple(pt), 1, (240, 240, 240), -1, cv2.LINE_AA)

            # 4. Nhãn hướng đầu gọn phía trên bounding box (ASCII an toàn hoặc UTF-8 PIL)
            pose = face.head_pose
            pose_ascii = {
                "Thẳng diện": "Thang dien",
                "Nghiêng trái": "Nghieng trai",
                "Nghiêng phải": "Nghieng phai",
                "Ngẩng nhẹ": "Ngang nhe",
                "Cúi nhẹ": "Cui nhe",
                "Nghiêng đầu": "Nghieng dau",
                "Fallback 5 điểm": "Fallback 5pt",
            }.get(pose.pose_label, "Face")
            label = f"{face.landmark_count} pts | {pose_ascii} (Y:{pose.yaw:+.0f} P:{pose.pitch:+.0f} R:{pose.roll:+.0f})"
            tx = max(6, int(face.x))
            ty = max(24, int(face.y) - 10)
            cv2.putText(canvas, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (25, 25, 25), 3, cv2.LINE_AA)
            cv2.putText(canvas, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (160, 220, 245), 1, cv2.LINE_AA)
        else:
            # Fallback bounding box + 5 điểm
            fx, fy, fw, fh = [int(v) for v in face.bbox]
            cv2.rectangle(canvas, (fx, fy), (fx + fw, fy + fh), (55, 175, 212), 2)
            for kp in (face.right_eye, face.left_eye, face.nose, face.mouth_right, face.mouth_left):
                if kp is not None:
                    cv2.circle(canvas, (int(kp[0]), int(kp[1])), 4, (0, 255, 180), -1)

    return canvas
