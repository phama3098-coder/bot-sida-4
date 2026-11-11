"""
1998 TEAM — Smart Beauty Engine (MediaPipe 478-Landmark Region-Based Beauty Processing)
Tách biệt rõ ràng tầng xử lý làm đẹp (Beauty Processing) khỏi tầng phân tích khuôn mặt (Face Analysis):
- Sử dụng dữ liệu phân tích 478 facial landmarks & Face Mesh từ `vietphotobooth.filters.face_analysis`.
- Xây dựng mặt nạ giải phẫu chuyên biệt cho từng vùng:
  1. Da mặt tổng thể: Làm mịn edge-preserving + thu hồi micro-texture giữ lỗ chân lông thật, làm sáng soft-knee.
  2. Trán: Làm đều màu da trán (LAB tonal evening) không tràn vào tóc và lông mày.
  3. Hai má: Làm mịn & cân bằng phớt hồng má khỏe khoắn.
  4. Vùng mắt (dưới mắt): Xử lý quầng thâm và làm sáng dịu nhẹ mà không chạm vào nhãn cầu hay mi mắt.
  5. Môi: Tô son tự nhiên theo viền môi 478 điểm, loại trừ tuyệt đối răng và khoang miệng.
  6. Mũi: Định vị sống mũi tạo điểm sáng tự nhiên giúp khuôn mặt có chiều sâu.
  7. Đường viền mặt: Hỗ trợ hiệu chỉnh thon gọn đường hàm nhẹ nhàng tự nhiên khi người dùng bật.
- Xử lý không phá hủy trên bản sao ảnh trung gian; bảo toàn byte-for-byte ảnh gốc.
- Hỗ trợ cơ chế fallback an toàn khi thiếu MediaPipe hoặc không tìm thấy khuôn mặt.
"""

import os
import math
import hashlib
import threading
import logging
from collections import OrderedDict
from typing import List, Tuple, Optional, Dict, Any

import numpy as np
import cv2
from PIL import Image, ImageOps

from vietphotobooth.camera.face_detector import DetectedFace
from vietphotobooth.filters.face_analysis import (
    MediaPipeFaceAnalyzer,
    AnalyzedFace,
    FaceAnalysisResult,
    draw_face_mesh_overlay,
)
from vietphotobooth.filters.ai_portrait_enhancer import (
    BasePortraitEnhancer,
    FaceEnhancementPatch,
    DEFAULT_PORTRAIT_MODEL_ID,
    composite_face_patches,
    create_portrait_enhancer,
)

logger = logging.getLogger("VietPhotoBooth.filters.beauty_engine")

DEFAULT_ENABLED_EFFECTS: Dict[str, bool] = {
    "smooth": True,
    "brighten": True,
    "lips": True,
    "eye_brighten": True,
    "cheek_rosy": True,
    "nose_highlight": True,
    "face_slim": False,
    "ai_enhance": True,
}


class SmartBeautyEngine:
    """
    Bộ xử lý làm đẹp thông minh theo vùng giải phẫu (Smart Beauty Engine).
    Kết hợp MediaPipeFaceAnalyzer (478 landmarks), xử lý OpenCV đa vùng và mô hình AI
    tăng cường chân dung thứ hai (Hybrid AI Beauty) với bộ nhớ đệm trung gian.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        landmarker_model_path: Optional[str] = None,
        ai_enhancer: Optional[BasePortraitEnhancer] = None,
        ai_model_path: Optional[str] = None,
        ai_model_id: str = DEFAULT_PORTRAIT_MODEL_ID,
    ):
        # Giữ tương thích bài test `test_missing_model_fallback`: nếu caller truyền đường dẫn model_path
        # không tồn tại rõ ràng (.onnx/.task), không tự nạp model dự phòng khác để báo unavailable đúng chuẩn.
        explicit_broken = False
        if model_path is not None and not os.path.exists(model_path):
            explicit_broken = True
        if landmarker_model_path is not None and not os.path.exists(landmarker_model_path):
            explicit_broken = True

        if explicit_broken:
            self._analyzer = MediaPipeFaceAnalyzer(
                landmarker_model_path=landmarker_model_path or "__non_existent__.task",
                fallback_yunet_path=model_path or "__non_existent__.onnx",
                enable_fallback=False,
            )
        else:
            self._analyzer = MediaPipeFaceAnalyzer(
                landmarker_model_path=landmarker_model_path,
                fallback_yunet_path=model_path,
                enable_fallback=True,
            )
        self._detector = self._analyzer._yunet

        if ai_enhancer is not None:
            self._ai_enhancer: BasePortraitEnhancer = ai_enhancer
        else:
            self._ai_enhancer = create_portrait_enhancer(
                model_id=ai_model_id,
                model_path=ai_model_path,
            )

        self._ai_cache_lock = threading.Lock()
        self._ai_patch_cache: OrderedDict[Tuple[Any, ...], List[FaceEnhancementPatch]] = OrderedDict()
        self._ai_cache_max_entries: int = 3

    @property
    def analyzer(self) -> MediaPipeFaceAnalyzer:
        return self._analyzer

    @property
    def ai_enhancer(self) -> BasePortraitEnhancer:
        return self._ai_enhancer

    def set_ai_enhancer(self, enhancer: BasePortraitEnhancer) -> None:
        """Thay thế mô hình AI tăng cường chân dung lúc chạy (hot-swap) và xóa cache cũ."""
        self._ai_enhancer = enhancer
        self.clear_ai_cache()

    def clear_ai_cache(self) -> None:
        """Giải phóng bộ nhớ đệm kết quả suy luận AI trung gian."""
        with self._ai_cache_lock:
            self._ai_patch_cache.clear()

    def close(self) -> None:
        """Giải phóng tài nguyên phân tích MediaPipe và mô hình AI chân dung."""
        self.clear_ai_cache()
        try:
            self._analyzer.close()
        except Exception:
            pass
        try:
            if self._ai_enhancer is not None:
                self._ai_enhancer.close()
        except Exception:
            pass

    @property
    def is_available(self) -> bool:
        """Kiểm tra hệ thống phân tích khuôn mặt (MediaPipe hoặc fallback YuNet) có khả dụng không."""
        return self._analyzer.is_available

    @property
    def is_mediapipe_available(self) -> bool:
        return self._analyzer.is_mediapipe_available

    @property
    def is_ai_available(self) -> bool:
        """Kiểm tra mô hình AI tăng cường chân dung thứ hai có sẵn sàng không."""
        return bool(self._ai_enhancer is not None and self._ai_enhancer.is_available)

    @property
    def ai_active_provider(self) -> str:
        return self._ai_enhancer.active_provider if self._ai_enhancer is not None else "unavailable"

    def analyze_faces(
        self,
        image_bgr_or_rgb: np.ndarray,
        is_bgr: bool = True,
        max_proc_width: int = 1280,
    ) -> FaceAnalysisResult:
        """Phân tích cấu trúc khuôn mặt 478 landmarks (tách riêng với bước chỉnh sửa ảnh)."""
        if not self.is_available or image_bgr_or_rgb is None or image_bgr_or_rgb.size == 0:
            return FaceAnalysisResult(source="none", is_mediapipe_active=False)
        return self._analyzer.analyze(image_bgr_or_rgb, is_bgr=is_bgr, max_proc_width=max_proc_width)

    def detect_faces(
        self,
        image_bgr_or_rgb: np.ndarray,
        is_bgr: bool = True,
        max_proc_width: int = 1280,
    ) -> List[AnalyzedFace]:
        """Nhận diện khuôn mặt và trả về danh sách AnalyzedFace tương thích ngược với DetectedFace."""
        return self.analyze_faces(image_bgr_or_rgb, is_bgr=is_bgr, max_proc_width=max_proc_width).faces

    # --------------------------------------------------------------------------
    # MASK GENERATION: 478-LANDMARK ANATOMICAL REGIONS + 10-POINT FALLBACK
    # --------------------------------------------------------------------------

    def _build_face_anatomical_polygon(
        self, face: Any, img_w: int, img_h: int
    ) -> np.ndarray:
        """
        Xây dựng đa giác bao quanh vùng da mặt.
        - Khi có vùng giải phẫu MediaPipe (face_oval): dùng trực tiếp viền mặt 36 điểm chuẩn xác.
        - Khi chỉ có DetectedFace 5 điểm: xây dựng đa giác giải phẫu 10 điểm xoay theo góc nghiêng đầu.
        """
        regions = getattr(face, "regions", None)
        if regions is not None and regions.face_oval is not None and len(regions.face_oval) >= 10:
            return np.clip(regions.face_oval, [0, 0], [img_w - 1, img_h - 1]).astype(np.int32)

        fx, fy, fw, fh = face.bbox
        re = getattr(face, "right_eye", None)
        le = getattr(face, "left_eye", None)
        mr = getattr(face, "mouth_right", None)
        ml = getattr(face, "mouth_left", None)

        valid_landmarks = (
            re is not None and le is not None and mr is not None and ml is not None and
            re[0] > 0 and re[1] > 0 and le[0] > 0 and le[1] > 0 and
            mr[0] > 0 and mr[1] > 0 and ml[0] > 0 and ml[1] > 0 and
            (le[0] != re[0] or le[1] != re[1])
        )

        if valid_landmarks:
            re_arr = np.array(re, dtype=np.float32)
            le_arr = np.array(le, dtype=np.float32)
            mr_arr = np.array(mr, dtype=np.float32)
            ml_arr = np.array(ml, dtype=np.float32)

            eye_vec = le_arr - re_arr
            d_eye = max(4.0, float(np.linalg.norm(eye_vec)))
            u = eye_vec / d_eye

            c_eyes = (re_arr + le_arr) / 2.0
            c_mouth = (mr_arr + ml_arr) / 2.0
            face_axis = c_mouth - c_eyes
            h_em = max(4.0, float(np.linalg.norm(face_axis)))
            v_face = face_axis / h_em

            pts = [
                c_eyes - 0.70 * h_em * v_face,
                le_arr + 0.45 * d_eye * u - 0.50 * h_em * v_face,
                le_arr + 0.58 * d_eye * u + 0.20 * h_em * v_face,
                ml_arr + 0.42 * d_eye * u + 0.15 * h_em * v_face,
                ml_arr + 0.22 * d_eye * u + 0.42 * h_em * v_face,
                c_mouth + 0.62 * h_em * v_face,
                mr_arr - 0.22 * d_eye * u + 0.42 * h_em * v_face,
                mr_arr - 0.42 * d_eye * u + 0.15 * h_em * v_face,
                re_arr - 0.58 * d_eye * u + 0.20 * h_em * v_face,
                re_arr - 0.45 * d_eye * u - 0.50 * h_em * v_face,
            ]
            return np.clip(np.array(pts, dtype=np.int32), [0, 0], [img_w - 1, img_h - 1])

        cx = int(fx + fw * 0.50)
        cy = int(fy + fh * 0.48)
        rx = max(2, int(fw * 0.38))
        ry = max(2, int(fh * 0.44))
        pts_ellipse = cv2.ellipse2Poly((cx, cy), (rx, ry), 0, 0, 360, 24)
        return np.clip(pts_ellipse, [0, 0], [img_w - 1, img_h - 1])

    @staticmethod
    def _shift_poly(poly: Optional[np.ndarray], ox: int, oy: int, rw: int, rh: int) -> Optional[np.ndarray]:
        if poly is None or len(poly) < 3:
            return None
        shifted = poly.copy().astype(np.int32)
        shifted[:, 0] = np.clip(shifted[:, 0] - ox, 0, max(0, rw - 1))
        shifted[:, 1] = np.clip(shifted[:, 1] - oy, 0, max(0, rh - 1))
        return shifted

    @staticmethod
    def _fill_poly_u8(rw: int, rh: int, polys: List[Optional[np.ndarray]]) -> np.ndarray:
        mask = np.zeros((rh, rw), dtype=np.uint8)
        for p in polys:
            if p is not None and len(p) >= 3:
                cv2.fillPoly(mask, [p], 255)
        return mask

    def _generate_regional_masks(
        self,
        roi_bgr: np.ndarray,
        face: Any,
        offset_x: int,
        offset_y: int,
    ) -> Dict[str, np.ndarray]:
        """
        Tạo trọn bộ mặt nạ vùng mặt chuyên biệt (np.float32 [0.0, 1.0]) từ dữ liệu Face Mesh hoặc Fallback:
        - skin_mask, lip_mask, exclusions_mask
        - forehead_mask, cheeks_mask, under_eye_mask, nose_bridge_mask
        """
        rh, rw = roi_bgr.shape[:2]
        fx, fy, fw, fh = face.bbox
        regions = getattr(face, "regions", None)
        has_mesh = regions is not None and regions.face_oval is not None

        # 1. Phân đoạn màu da hỗ trợ lọc bỏ tóc, cổ áo và nền (nới nhẹ dải tối cho ảnh ánh sáng yếu/tiệc)
        ycrcb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2YCrCb)
        skin_ycrcb = cv2.inRange(ycrcb, np.array([0, 126, 70]), np.array([255, 182, 136]))

        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        skin_hsv1 = cv2.inRange(hsv, np.array([0, 15, 35]), np.array([32, 245, 255]))
        skin_hsv2 = cv2.inRange(hsv, np.array([150, 15, 35]), np.array([180, 245, 255]))
        skin_hsv = cv2.bitwise_or(skin_hsv1, skin_hsv2)

        raw_skin = cv2.bitwise_and(skin_ycrcb, skin_hsv)
        # Bảo vệ khỏi bóng tối rũ hoặc tóc tối màu
        dark_hair = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 34]))

        exclusions_u8 = np.zeros((rh, rw), dtype=np.uint8)
        exclusions_u8 = cv2.bitwise_or(exclusions_u8, dark_hair)

        k_skin = max(3, (int(fw * 0.045) // 2) * 2 + 1)
        k_small = max(3, (int(fw * 0.025) // 2) * 2 + 1)

        if has_mesh:
            # --- CHẾ ĐỘ ĐỘ CHÍNH XÁC CAO: 478 LANDMARKS ---
            face_oval = self._shift_poly(regions.face_oval, offset_x, offset_y, rw, rh)
            anatomical_u8 = self._fill_poly_u8(rw, rh, [face_oval])

            # Nếu ảnh ánh sáng màu/tiệc khắc nghiệt khiến raw_skin quá ít pixel, hòa trộn an toàn theo face_oval
            skin_in_oval = cv2.bitwise_and(anatomical_u8, raw_skin)
            if np.count_nonzero(skin_in_oval) < 0.25 * max(1, np.count_nonzero(anatomical_u8)):
                skin_base_u8 = anatomical_u8
            else:
                # Lấp lỗ nhỏ do highlight sáng mạnh trên mặt nhưng vẫn loại tóc tối
                skin_base_u8 = cv2.morphologyEx(
                    skin_in_oval, cv2.MORPH_CLOSE, np.ones((k_small, k_small), np.uint8)
                )

            l_eye_p = self._shift_poly(regions.left_eye, offset_x, offset_y, rw, rh)
            r_eye_p = self._shift_poly(regions.right_eye, offset_x, offset_y, rw, rh)
            l_brow_p = self._shift_poly(regions.left_eyebrow, offset_x, offset_y, rw, rh)
            r_brow_p = self._shift_poly(regions.right_eyebrow, offset_x, offset_y, rw, rh)
            lips_outer_p = self._shift_poly(regions.lips_outer, offset_x, offset_y, rw, rh)
            lips_inner_p = self._shift_poly(regions.lips_inner, offset_x, offset_y, rw, rh)

            eyes_u8 = self._fill_poly_u8(rw, rh, [l_eye_p, r_eye_p])
            # Nới nhẹ viền mắt vài pixel để hàng mi luôn sắc nét tuyệt đối
            eyes_dilated_u8 = cv2.dilate(eyes_u8, np.ones((max(3, int(fw * 0.015)), max(3, int(fw * 0.015))), np.uint8))
            brows_u8 = self._fill_poly_u8(rw, rh, [l_brow_p, r_brow_p])
            lips_outer_u8 = self._fill_poly_u8(rw, rh, [lips_outer_p])
            lips_inner_u8 = self._fill_poly_u8(rw, rh, [lips_inner_p])

            exclusions_u8 = cv2.bitwise_or(exclusions_u8, eyes_dilated_u8)
            exclusions_u8 = cv2.bitwise_or(exclusions_u8, brows_u8)
            exclusions_u8 = cv2.bitwise_or(exclusions_u8, lips_outer_u8)

            # Mặt nạ môi chính xác: vành môi ngoài trừ khoang miệng trong + bảo vệ răng
            lip_u8 = cv2.bitwise_and(lips_outer_u8, cv2.bitwise_not(lips_inner_u8))
            teeth_hsv = cv2.inRange(hsv, np.array([0, 0, 175]), np.array([180, 55, 255]))
            dark_cavity = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 40]))
            lip_u8 = cv2.bitwise_and(lip_u8, cv2.bitwise_not(cv2.bitwise_or(teeth_hsv, dark_cavity)))

            # Các vùng giải phẫu chuyên biệt từ MediaPipe
            forehead_p = self._shift_poly(regions.forehead, offset_x, offset_y, rw, rh)
            l_cheek_p = self._shift_poly(regions.left_cheek, offset_x, offset_y, rw, rh)
            r_cheek_p = self._shift_poly(regions.right_cheek, offset_x, offset_y, rw, rh)
            l_ueye_p = self._shift_poly(regions.left_under_eye, offset_x, offset_y, rw, rh)
            r_ueye_p = self._shift_poly(regions.right_under_eye, offset_x, offset_y, rw, rh)
            nose_b_p = self._shift_poly(regions.nose_bridge, offset_x, offset_y, rw, rh)

            forehead_u8 = cv2.bitwise_and(self._fill_poly_u8(rw, rh, [forehead_p]), cv2.bitwise_not(exclusions_u8))
            cheeks_u8 = cv2.bitwise_and(self._fill_poly_u8(rw, rh, [l_cheek_p, r_cheek_p]), cv2.bitwise_not(exclusions_u8))
            under_eye_u8 = cv2.bitwise_and(
                self._fill_poly_u8(rw, rh, [l_ueye_p, r_ueye_p]),
                cv2.bitwise_not(cv2.bitwise_or(eyes_dilated_u8, dark_hair)),
            )
            nose_u8 = cv2.bitwise_and(self._fill_poly_u8(rw, rh, [nose_b_p]), cv2.bitwise_not(exclusions_u8))
        else:
            # --- CHẾ ĐỘ FALLBACK (10 ĐIỂM GIẢI PHẪU TỪ DETECTEDFACE) ---
            face_roi = DetectedFace(
                x=fx - offset_x,
                y=fy - offset_y,
                w=fw,
                h=fh,
                confidence=face.confidence,
                right_eye=(face.right_eye[0] - offset_x, face.right_eye[1] - offset_y) if face.right_eye else None,
                left_eye=(face.left_eye[0] - offset_x, face.left_eye[1] - offset_y) if face.left_eye else None,
                nose=(face.nose[0] - offset_x, face.nose[1] - offset_y) if face.nose else None,
                mouth_right=(face.mouth_right[0] - offset_x, face.mouth_right[1] - offset_y) if face.mouth_right else None,
                mouth_left=(face.mouth_left[0] - offset_x, face.mouth_left[1] - offset_y) if face.mouth_left else None,
            )
            face_poly = self._build_face_anatomical_polygon(face_roi, rw, rh)
            anatomical_u8 = self._fill_poly_u8(rw, rh, [face_poly])
            skin_base_u8 = cv2.bitwise_and(anatomical_u8, raw_skin)

            re, le = face_roi.right_eye, face_roi.left_eye
            mr, ml = face_roi.mouth_right, face_roi.mouth_left
            d_eye = math.hypot(le[0] - re[0], le[1] - re[1]) if (re and le) else (fw * 0.35)
            eye_rad = max(3, int(d_eye * 0.18))

            if re and 0 <= int(re[0]) < rw and 0 <= int(re[1]) < rh:
                cv2.circle(exclusions_u8, (int(re[0]), int(re[1])), eye_rad, 255, -1)
            if le and 0 <= int(le[0]) < rw and 0 <= int(le[1]) < rh:
                cv2.circle(exclusions_u8, (int(le[0]), int(le[1])), eye_rad, 255, -1)

            brow_dy = int(d_eye * 0.22)
            if re and 0 <= int(re[0]) < rw and 0 <= int(re[1] - brow_dy) < rh:
                cv2.ellipse(exclusions_u8, (int(re[0]), int(re[1] - brow_dy)), (int(d_eye * 0.26), int(d_eye * 0.12)), 0, 0, 360, 255, -1)
            if le and 0 <= int(le[0]) < rw and 0 <= int(le[1] - brow_dy) < rh:
                cv2.ellipse(exclusions_u8, (int(le[0]), int(le[1] - brow_dy)), (int(d_eye * 0.26), int(d_eye * 0.12)), 0, 0, 360, 255, -1)

            lip_u8 = np.zeros((rh, rw), dtype=np.uint8)
            if mr and ml:
                mcx = (mr[0] + ml[0]) / 2.0
                mcy = (mr[1] + ml[1]) / 2.0
                d_mouth = max(4.0, math.hypot(ml[0] - mr[0], ml[1] - mr[1]))
                m_angle = math.degrees(math.atan2(ml[1] - mr[1], ml[0] - mr[0]))
                cv2.ellipse(exclusions_u8, (int(mcx), int(mcy)), (int(d_mouth * 0.65), max(3, int(d_mouth * 0.38))), m_angle, 0, 360, 255, -1)
                cv2.ellipse(lip_u8, (int(mcx), int(mcy)), (int(d_mouth * 0.55), max(2, int(d_mouth * 0.26))), m_angle, 0, 360, 255, -1)
                teeth_hsv = cv2.inRange(hsv, np.array([0, 0, 160]), np.array([180, 60, 255]))
                dark_cav = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 45]))
                lip_u8 = cv2.bitwise_and(lip_u8, cv2.bitwise_not(cv2.bitwise_or(teeth_hsv, dark_cav)))

            forehead_u8 = np.zeros((rh, rw), dtype=np.uint8)
            cheeks_u8 = np.zeros((rh, rw), dtype=np.uint8)
            under_eye_u8 = np.zeros((rh, rw), dtype=np.uint8)
            nose_u8 = np.zeros((rh, rw), dtype=np.uint8)

        skin_clean_u8 = cv2.bitwise_and(skin_base_u8, cv2.bitwise_not(exclusions_u8))

        def _feather(u8_mask: np.ndarray, k: int) -> np.ndarray:
            if np.count_nonzero(u8_mask) == 0:
                return np.zeros((rh, rw), dtype=np.float32)
            return cv2.GaussianBlur(u8_mask, (k, k), 0).astype(np.float32) / 255.0

        return {
            "skin_mask": _feather(skin_clean_u8, k_skin),
            "lip_mask": _feather(lip_u8, k_small),
            "exclusions_mask": exclusions_u8.astype(np.float32) / 255.0,
            "forehead_mask": _feather(forehead_u8, k_skin),
            "cheeks_mask": _feather(cheeks_u8, k_skin),
            "under_eye_mask": _feather(under_eye_u8, k_small),
            "nose_bridge_mask": _feather(nose_u8, k_small),
        }

    def _generate_face_masks(
        self,
        roi_bgr: np.ndarray,
        face: Any,
        offset_x: int,
        offset_y: int,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Giữ API nội bộ trả về (skin_mask_feathered, lip_mask_feathered, exclusions_mask)."""
        regs = self._generate_regional_masks(roi_bgr, face, offset_x, offset_y)
        return regs["skin_mask"], regs["lip_mask"], regs["exclusions_mask"]

    # --------------------------------------------------------------------------
    # JAWLINE / FACE CONTOUR REFINEMENT (OPTIONAL)
    # --------------------------------------------------------------------------

    @staticmethod
    def _apply_jawline_contour(
        roi_bgr: np.ndarray,
        face: AnalyzedFace,
        offset_x: int,
        offset_y: int,
        slim_pct: float,
    ) -> np.ndarray:
        """
        Hiệu chỉnh nhẹ nhàng đường viền xương hàm (chỉ khi bật `face_slim` > 0%):
        Đẩy nhẹ các điểm hàm vào trục trung tâm khuôn mặt bằng phép nội suy `cv2.remap` mượt mà,
        không làm biến dạng phông nền hay các chi tiết mắt/môi.
        """
        if slim_pct <= 0.01 or getattr(face, "regions", None) is None:
            return roi_bgr
        reg = face.regions
        if reg.jawline_left is None or reg.jawline_right is None or reg.chin_point is None:
            return roi_bgr

        rh, rw = roi_bgr.shape[:2]
        fw = max(20.0, float(face.w))
        cx = (float(face.x) + fw * 0.5) - offset_x
        cy = (float(face.y) + float(face.h) * 0.55) - offset_y

        # Tối đa chỉ dịch chuyển ~2.8% chiều rộng khuôn mặt để giữ vẻ tự nhiên chân thật
        max_shift = fw * 0.028 * (slim_pct / 100.0)
        radius = fw * 0.24
        if max_shift < 0.3 or radius < 6.0:
            return roi_bgr

        # Chọn các điểm xương hàm hai bên (bỏ qua vùng tai và đỉnh cằm)
        control_pts = []
        for jaw_arr in (reg.jawline_right[2:-2], reg.jawline_left[2:-2]):
            for p in jaw_arr[::2]:
                px = float(p[0]) - offset_x
                py = float(p[1]) - offset_y
                vx = cx - px
                vy = cy - py
                dist_c = math.hypot(vx, vy)
                if dist_c > 5.0 and 0 <= px < rw and 0 <= py < rh:
                    ux = vx / dist_c
                    uy = vy / dist_c * 0.25  # ưu tiên thu gọn ngang tự nhiên
                    control_pts.append((px, py, ux * max_shift, uy * max_shift))

        if not control_pts:
            return roi_bgr

        yy, xx = np.mgrid[0:rh, 0:rw].astype(np.float32)
        dx_total = np.zeros((rh, rw), dtype=np.float32)
        dy_total = np.zeros((rh, rw), dtype=np.float32)
        r2 = radius * radius

        for px, py, sx, sy in control_pts:
            dist2 = (xx - px) ** 2 + (yy - py) ** 2
            w = np.clip(1.0 - dist2 / r2, 0.0, 1.0)
            w = w * w
            # Lưu ý remap ánh xạ ngược (lấy pixel từ phía ngoài vào trong)
            dx_total -= sx * w
            dy_total -= sy * w

        # Giới hạn biên độ warp cộng dồn
        dx_total = np.clip(dx_total, -max_shift * 1.4, max_shift * 1.4)
        dy_total = np.clip(dy_total, -max_shift * 1.4, max_shift * 1.4)

        map_x = np.clip(xx + dx_total, 0, rw - 1)
        map_y = np.clip(yy + dy_total, 0, rh - 1)
        return cv2.remap(roi_bgr, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # --------------------------------------------------------------------------
    # CORE BEAUTY PROCESSING
    # --------------------------------------------------------------------------

    def apply_beauty(
        self,
        image_bgr: np.ndarray,
        skin_brighten_pct: float = 0.0,
        skin_smooth_pct: float = 0.0,
        lip_tint_pct: float = 0.0,
        faces: Optional[List[Any]] = None,
        eye_brighten_pct: float = 0.0,
        cheek_rosy_pct: float = 0.0,
        nose_highlight_pct: float = 0.0,
        face_slim_pct: float = 0.0,
        enabled_effects: Optional[Dict[str, bool]] = None,
        ai_enhance_pct: float = 0.0,
    ) -> np.ndarray:
        """
        Áp dụng làm đẹp đa vùng lên bản sao trung gian của ảnh BGR theo kiến trúc Hybrid AI:
        Original -> MediaPipe Landmarks -> SmartBeautyEngine -> AI Enhancement -> Masked Blend.
        - Giữ nguyên tuyệt đối ảnh gốc khi mọi thông số hiệu dụng = 0.
        - Hỗ trợ bật/tắt độc lập từng hiệu ứng thông qua `enabled_effects`.
        - Cache bản vá AI trung gian theo ảnh đầu vào bước AI để kéo slider AI mượt mà tức thì.
        """
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr

        eff = dict(DEFAULT_ENABLED_EFFECTS)
        if enabled_effects:
            eff.update(enabled_effects)

        b_pct = max(0.0, min(100.0, float(skin_brighten_pct))) if eff.get("brighten", True) else 0.0
        s_pct = max(0.0, min(100.0, float(skin_smooth_pct))) if eff.get("smooth", True) else 0.0
        l_pct = max(0.0, min(100.0, float(lip_tint_pct))) if eff.get("lips", True) else 0.0
        e_pct = max(0.0, min(100.0, float(eye_brighten_pct))) if eff.get("eye_brighten", True) else 0.0
        c_pct = max(0.0, min(100.0, float(cheek_rosy_pct))) if eff.get("cheek_rosy", True) else 0.0
        n_pct = max(0.0, min(100.0, float(nose_highlight_pct))) if eff.get("nose_highlight", True) else 0.0
        sl_pct = max(0.0, min(100.0, float(face_slim_pct))) if eff.get("face_slim", True) else 0.0
        ai_pct = max(0.0, min(100.0, float(ai_enhance_pct))) if eff.get("ai_enhance", True) else 0.0

        # Fast path: mọi hiệu ứng đều tắt hoặc = 0 -> trả về bản sao nguyên vẹn
        if max(b_pct, s_pct, l_pct, e_pct, c_pct, n_pct, sl_pct, ai_pct) <= 0.01:
            return image_bgr.copy()

        if faces is None:
            faces = self.detect_faces(image_bgr, is_bgr=True)

        if not faces:
            return image_bgr.copy()

        out = image_bgr.copy()
        img_h, img_w = out.shape[:2]
        has_opencv_fx = max(b_pct, s_pct, l_pct, e_pct, c_pct, n_pct, sl_pct) > 0.01

        if has_opencv_fx:
            self._apply_opencv_regions_inplace(
                out, faces, img_w, img_h,
                b_pct=b_pct, s_pct=s_pct, l_pct=l_pct,
                e_pct=e_pct, c_pct=c_pct, n_pct=n_pct, sl_pct=sl_pct,
            )

        # 7. TĂNG CƯỜNG CHÂN DUNG AI (Hybrid AI Enhancement — giới hạn nghiêm ngặt trong mặt nạ MediaPipe)
        if ai_pct > 0.01 and self.is_ai_available:
            patches = self._get_or_compute_ai_patches(out, faces)
            if patches:
                out = composite_face_patches(out, patches, strength_pct=ai_pct)

        return out

    def _apply_opencv_regions_inplace(
        self,
        out: np.ndarray,
        faces: List[Any],
        img_w: int,
        img_h: int,
        *,
        b_pct: float,
        s_pct: float,
        l_pct: float,
        e_pct: float,
        c_pct: float,
        n_pct: float,
        sl_pct: float,
    ) -> None:
        """Áp dụng các hiệu ứng làm đẹp OpenCV theo từng vùng giải phẫu lên bản sao `out`."""
        for face in faces:
            fx, fy, fw, fh = [float(v) for v in face.bbox]
            if fw <= 4 or fh <= 4:
                continue

            margin_x = int(fw * 0.22)
            margin_y = int(fh * 0.22)
            x1 = max(0, int(fx - margin_x))
            y1 = max(0, int(fy - margin_y))
            x2 = min(img_w, int(fx + fw + margin_x))
            y2 = min(img_h, int(fy + fh + margin_y))

            roi = out[y1:y2, x1:x2].copy()
            rh, rw = roi.shape[:2]
            if rh < 8 or rw < 8:
                continue

            # 0. Đường viền mặt (Jawline Slimming) — chỉ thực hiện khi được bật
            if sl_pct > 0.01 and isinstance(face, AnalyzedFace):
                roi = self._apply_jawline_contour(roi, face, x1, y1, sl_pct)

            masks = self._generate_regional_masks(roi, face, x1, y1)
            skin_mask_f = masks["skin_mask"]
            lip_mask_f = masks["lip_mask"]
            forehead_mask_f = masks["forehead_mask"]
            cheeks_mask_f = masks["cheeks_mask"]
            under_eye_mask_f = masks["under_eye_mask"]
            nose_mask_f = masks["nose_bridge_mask"]

            cur_roi = roi

            # 1. DA MẶT & TRÁN: Làm mịn bảo toàn vân da + làm đều sắc độ trán
            if s_pct > 0.01:
                sigma = 16 + int(s_pct * 0.60)
                smoothed = cv2.bilateralFilter(cur_roi, d=9, sigmaColor=sigma, sigmaSpace=sigma)
                # Thu hồi 28% micro-texture giữ lỗ chân lông thật
                texture = cur_roi.astype(np.float32) - smoothed.astype(np.float32)
                smoothed_natural = np.clip(smoothed.astype(np.float32) + 0.28 * texture, 0, 255).astype(np.uint8)

                # Kết hợp làm mịn trán và hai má nhẹ hơn một chút để trông tự nhiên
                combined_skin = np.clip(skin_mask_f + 0.15 * forehead_mask_f + 0.15 * cheeks_mask_f, 0.0, 1.0)
                alpha_s = (combined_skin * (s_pct / 100.0))[:, :, np.newaxis]
                cur_roi = np.clip(cur_roi * (1.0 - alpha_s) + smoothed_natural * alpha_s, 0, 255).astype(np.uint8)

                # Làm đều màu vùng Trán (giảm loang sáng/đốm tối tần số thấp tại trán)
                if np.count_nonzero(forehead_mask_f > 0.15) > 25:
                    lab_fh = cv2.cvtColor(cur_roi, cv2.COLOR_BGR2LAB).astype(np.float32)
                    fh_bool = forehead_mask_f > 0.20
                    mean_l = float(np.mean(lab_fh[:, :, 0][fh_bool]))
                    mean_a = float(np.mean(lab_fh[:, :, 1][fh_bool]))
                    mean_b = float(np.mean(lab_fh[:, :, 2][fh_bool]))
                    ev_strength = (s_pct / 100.0) * 0.18
                    fh_w = (forehead_mask_f * ev_strength)
                    # Giữ micro-detail của L, chỉ điều hòa độ lệch màu lớn và cân bằng nhẹ L
                    lab_fh[:, :, 0] += fh_w * (mean_l - lab_fh[:, :, 0]) * 0.45
                    lab_fh[:, :, 1] += fh_w * (mean_a - lab_fh[:, :, 1])
                    lab_fh[:, :, 2] += fh_w * (mean_b - lab_fh[:, :, 2])
                    cur_roi = cv2.cvtColor(np.clip(lab_fh, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)

            # 2. VÙNG MẮT: Giảm quầng thâm và làm sáng dịu vùng dưới mắt (trừ hẳn mắt & mi)
            if e_pct > 0.01 and np.count_nonzero(under_eye_mask_f > 0.05) > 0:
                lab_eye = cv2.cvtColor(cur_roi, cv2.COLOR_BGR2LAB).astype(np.float32)
                ew = under_eye_mask_f * (e_pct / 100.0)
                # Nâng sáng nhẹ vùng bóng tối dưới mắt (soft-knee) và trung hòa sắc thâm xanh/tím
                l_chan = lab_eye[:, :, 0]
                lab_eye[:, :, 0] = np.clip(l_chan + ew * 20.0 * (1.0 - l_chan / 255.0), 0, 255)
                lab_eye[:, :, 2] = np.clip(lab_eye[:, :, 2] + ew * 3.5, 0, 255)
                eye_cand = cv2.cvtColor(lab_eye.astype(np.uint8), cv2.COLOR_LAB2BGR)
                alpha_e = (under_eye_mask_f * (e_pct / 100.0) * 0.85)[:, :, np.newaxis]
                cur_roi = np.clip(cur_roi * (1.0 - alpha_e) + eye_cand * alpha_e, 0, 255).astype(np.uint8)

            # 3. LÀM SÁNG DA TỔNG THỂ (Soft-knee bảo toàn highlight & ánh hồng tự nhiên)
            if b_pct > 0.01:
                lab = cv2.cvtColor(cur_roi, cv2.COLOR_BGR2LAB).astype(np.float32)
                L = lab[:, :, 0]
                A = lab[:, :, 1]

                gain = (b_pct / 100.0) * 26.0
                L_bright = L + gain * (1.0 - L / 255.0)
                A_rosy = A + (b_pct / 100.0) * 2.0

                lab[:, :, 0] = np.clip(L_bright, 0, 255)
                lab[:, :, 1] = np.clip(A_rosy, 0, 255)

                bright_cand = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
                alpha_b = (skin_mask_f * (b_pct / 100.0))[:, :, np.newaxis]
                cur_roi = np.clip(cur_roi * (1.0 - alpha_b) + bright_cand * alpha_b, 0, 255).astype(np.uint8)

            # 4. HAI MÁ: Cân bằng màu & phớt hồng má khỏe khoắn tự nhiên
            if c_pct > 0.01 and np.count_nonzero(cheeks_mask_f > 0.05) > 0:
                lab_chk = cv2.cvtColor(cur_roi, cv2.COLOR_BGR2LAB).astype(np.float32)
                cw = cheeks_mask_f * (c_pct / 100.0)
                lab_chk[:, :, 1] = np.clip(lab_chk[:, :, 1] + cw * 11.5, 0, 255)
                lab_chk[:, :, 2] = np.clip(lab_chk[:, :, 2] + cw * 3.5, 0, 255)
                chk_cand = cv2.cvtColor(lab_chk.astype(np.uint8), cv2.COLOR_LAB2BGR)
                alpha_c = (cheeks_mask_f * (c_pct / 100.0) * 0.72)[:, :, np.newaxis]
                cur_roi = np.clip(cur_roi * (1.0 - alpha_c) + chk_cand * alpha_c, 0, 255).astype(np.uint8)

            # 5. MŨI: Đánh khối sáng nhẹ tự nhiên dọc sống mũi
            if n_pct > 0.01 and np.count_nonzero(nose_mask_f > 0.05) > 0:
                lab_nose = cv2.cvtColor(cur_roi, cv2.COLOR_BGR2LAB).astype(np.float32)
                nw = nose_mask_f * (n_pct / 100.0)
                ln = lab_nose[:, :, 0]
                lab_nose[:, :, 0] = np.clip(ln + nw * 18.0 * (1.0 - ln / 255.0), 0, 255)
                nose_cand = cv2.cvtColor(lab_nose.astype(np.uint8), cv2.COLOR_LAB2BGR)
                alpha_n = (nose_mask_f * (n_pct / 100.0) * 0.75)[:, :, np.newaxis]
                cur_roi = np.clip(cur_roi * (1.0 - alpha_n) + nose_cand * alpha_n, 0, 255).astype(np.uint8)

            # 6. MÔI: Tô son tự nhiên theo mặt nạ vành môi chính xác (loại trừ răng & khoang miệng)
            if l_pct > 0.01 and np.count_nonzero(lip_mask_f > 0.05) > 0:
                lab_lip = cv2.cvtColor(cur_roi, cv2.COLOR_BGR2LAB).astype(np.float32)
                # Môi & vành răng
                lab_lip[:, :, 1] = np.clip(lab_lip[:, :, 1] + (l_pct / 100.0) * 34.0, 0, 255)
                lab_lip[:, :, 2] = np.clip(lab_lip[:, :, 2] + (l_pct / 100.0) * 11.0, 0, 255)
                tinted_lip = cv2.cvtColor(lab_lip.astype(np.uint8), cv2.COLOR_LAB2BGR)
                alpha_l = (lip_mask_f * (l_pct / 100.0))[:, :, np.newaxis]
                cur_roi = np.clip(cur_roi * (1.0 - alpha_l) + tinted_lip * alpha_l, 0, 255).astype(np.uint8)

            out[y1:y2, x1:x2] = cur_roi

    def _build_ai_constraint_mask(
        self,
        roi_bgr: np.ndarray,
        face: Any,
        offset_x: int,
        offset_y: int,
    ) -> np.ndarray:
        """
        Tạo mặt nạ giới hạn cho lớp AI thứ hai từ MediaPipe 478 điểm:
        - Chỉ cho phép tác động trên vùng da mặt, gò má, trán, sống mũi và dưới mắt.
        - Loại trừ nghiêm ngặt nhãn cầu/mi mắt, lông mày, răng/khoang miệng và tóc tối màu
          để bảo toàn danh tính, màu mắt, độ sắc nét kính và biểu cảm gốc.
        """
        regs = self._generate_regional_masks(roi_bgr, face, offset_x, offset_y)
        skin_f = regs["skin_mask"]
        under_eye_f = regs["under_eye_mask"] * 0.85
        lip_f = regs["lip_mask"] * 0.25
        raw = np.clip(np.maximum.reduce([skin_f, under_eye_f, lip_f]), 0.0, 1.0)
        excl = np.clip(regs["exclusions_mask"], 0.0, 1.0)
        # Vùng loại trừ cứng (mắt/tóc tối) giữ nguyên 100% lớp gốc bên dưới
        raw = raw * (1.0 - 0.90 * excl)
        fw = float(getattr(face, "w", getattr(face, "bbox", (0, 0, roi_bgr.shape[1], roi_bgr.shape[0]))[2]))
        k = max(5, (int(fw * 0.05) // 2) * 2 + 1)
        return cv2.GaussianBlur(raw.astype(np.float32), (k, k), 0)

    @staticmethod
    def _fingerprint_ai_input(image_bgr: np.ndarray, faces: List[Any], model_id: str) -> Tuple[Any, ...]:
        contig = np.ascontiguousarray(image_bgr)
        digest = hashlib.blake2b(contig.data, digest_size=16).hexdigest()
        faces_sig = tuple(
            (
                int(round(f.bbox[0])),
                int(round(f.bbox[1])),
                int(round(f.bbox[2])),
                int(round(f.bbox[3])),
                int(getattr(f, "landmark_count", 0)),
            )
            for f in faces
        )
        return (model_id, contig.shape, digest, faces_sig)

    def _get_or_compute_ai_patches(
        self,
        base_bgr: np.ndarray,
        faces: List[Any],
    ) -> List[FaceEnhancementPatch]:
        """Truy xuất hoặc tính mới bản vá AI trung gian (cache theo chữ ký ảnh & khuôn mặt)."""
        if not self.is_ai_available or not faces:
            return []

        key = self._fingerprint_ai_input(base_bgr, faces, self._ai_enhancer.model_id)
        with self._ai_cache_lock:
            cached = self._ai_patch_cache.get(key)
            if cached is not None:
                self._ai_patch_cache.move_to_end(key)
                return cached

        try:
            patches = self._ai_enhancer.generate_face_patches(
                base_bgr,
                faces,
                mask_builder=self._build_ai_constraint_mask,
            )
        except Exception as ex:
            logger.warning("Lỗi chạy AI tăng cường chân dung (fallback về SmartBeauty cơ bản): %s", ex)
            return []

        with self._ai_cache_lock:
            self._ai_patch_cache[key] = patches
            self._ai_patch_cache.move_to_end(key)
            while len(self._ai_patch_cache) > self._ai_cache_max_entries:
                self._ai_patch_cache.popitem(last=False)
        return patches

    def apply_beauty_pil(
        self,
        image_pil: Image.Image,
        skin_brighten_pct: float = 0.0,
        skin_smooth_pct: float = 0.0,
        lip_tint_pct: float = 0.0,
        faces: Optional[List[Any]] = None,
        eye_brighten_pct: float = 0.0,
        cheek_rosy_pct: float = 0.0,
        nose_highlight_pct: float = 0.0,
        face_slim_pct: float = 0.0,
        enabled_effects: Optional[Dict[str, bool]] = None,
        ai_enhance_pct: float = 0.0,
    ) -> Image.Image:
        """Áp dụng làm đẹp trực tiếp lên đối tượng PIL.Image (bảo toàn ảnh gốc, chuẩn EXIF)."""
        if image_pil is None:
            return image_pil

        upright_pil = ImageOps.exif_transpose(image_pil)

        eff = dict(DEFAULT_ENABLED_EFFECTS)
        if enabled_effects:
            eff.update(enabled_effects)
        has_any = any([
            skin_brighten_pct > 0.01 and eff.get("brighten", True),
            skin_smooth_pct > 0.01 and eff.get("smooth", True),
            lip_tint_pct > 0.01 and eff.get("lips", True),
            eye_brighten_pct > 0.01 and eff.get("eye_brighten", True),
            cheek_rosy_pct > 0.01 and eff.get("cheek_rosy", True),
            nose_highlight_pct > 0.01 and eff.get("nose_highlight", True),
            face_slim_pct > 0.01 and eff.get("face_slim", True),
            ai_enhance_pct > 0.01 and eff.get("ai_enhance", True),
        ])
        if not has_any:
            return upright_pil.copy()

        rgb_arr = np.array(upright_pil.convert("RGB"))
        bgr_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        out_bgr = self.apply_beauty(
            bgr_arr,
            skin_brighten_pct=skin_brighten_pct,
            skin_smooth_pct=skin_smooth_pct,
            lip_tint_pct=lip_tint_pct,
            faces=faces,
            eye_brighten_pct=eye_brighten_pct,
            cheek_rosy_pct=cheek_rosy_pct,
            nose_highlight_pct=nose_highlight_pct,
            face_slim_pct=face_slim_pct,
            enabled_effects=enabled_effects,
            ai_enhance_pct=ai_enhance_pct,
        )

        out_rgb = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(out_rgb)

    def generate_scaled_preview(
        self,
        image_bgr: np.ndarray,
        max_dim: int = 1080,
    ) -> Tuple[np.ndarray, List[AnalyzedFace], float]:
        """Tạo ảnh preview thu nhỏ và chạy Face Analysis trên tỷ lệ preview."""
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr, [], 1.0

        h, w = image_bgr.shape[:2]
        if max(h, w) <= max_dim:
            faces = self.detect_faces(image_bgr, is_bgr=True)
            return image_bgr.copy(), faces, 1.0

        scale = float(max_dim) / float(max(h, w))
        nw = max(1, int(w * scale))
        nh = max(1, int(h * scale))

        preview_bgr = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        faces = self.detect_faces(preview_bgr, is_bgr=True)
        return preview_bgr, faces, scale

    def map_faces_to_scale(
        self,
        faces: List[Any],
        scale_ratio: float,
    ) -> List[Any]:
        """Ánh xạ danh sách AnalyzedFace / DetectedFace (gồm cả 478 landmarks & Face Mesh) sang tỷ lệ mới."""
        if scale_ratio == 1.0 or not faces:
            return faces
        return [MediaPipeFaceAnalyzer.scale_analyzed_face(f, scale_ratio) for f in faces]

    # --------------------------------------------------------------------------
    # DEBUG MODE: MASK VISUALIZATION & EXPORT
    # --------------------------------------------------------------------------

    def generate_debug_masks(
        self,
        image_bgr: np.ndarray,
        faces: Optional[List[Any]] = None,
    ) -> Dict[str, np.ndarray]:
        """
        Xuất 6 hình ảnh kiểm tra mặt nạ (giữ nguyên hợp đồng 6 khóa chuẩn):
        'original', 'face_landmarks', 'skin_mask', 'excluded_features_mask', 'lip_mask', 'composite_preview'
        """
        if image_bgr is None or image_bgr.size == 0:
            return {}

        if faces is None:
            faces = self.detect_faces(image_bgr, is_bgr=True)

        h, w = image_bgr.shape[:2]
        skin_mask_full = np.zeros((h, w), dtype=np.uint8)
        lip_mask_full = np.zeros((h, w), dtype=np.uint8)
        excl_mask_full = np.zeros((h, w), dtype=np.uint8)

        vis_landmarks = draw_face_mesh_overlay(image_bgr, faces, show_tesselation=True, show_regions=True, show_landmarks=True)

        for face in faces:
            fx, fy, fw, fh = [int(v) for v in face.bbox]
            margin_x = int(fw * 0.22)
            margin_y = int(fh * 0.22)
            x1 = max(0, fx - margin_x)
            y1 = max(0, fy - margin_y)
            x2 = min(w, fx + fw + margin_x)
            y2 = min(h, fy + fh + margin_y)

            roi = image_bgr[y1:y2, x1:x2]
            if roi.shape[0] >= 8 and roi.shape[1] >= 8:
                regs = self._generate_regional_masks(roi, face, x1, y1)
                s_u8 = (regs["skin_mask"] * 255.0).astype(np.uint8)
                l_u8 = (regs["lip_mask"] * 255.0).astype(np.uint8)
                e_u8 = (regs["exclusions_mask"] * 255.0).astype(np.uint8)

                skin_mask_full[y1:y2, x1:x2] = cv2.bitwise_or(skin_mask_full[y1:y2, x1:x2], s_u8)
                lip_mask_full[y1:y2, x1:x2] = cv2.bitwise_or(lip_mask_full[y1:y2, x1:x2], l_u8)
                excl_mask_full[y1:y2, x1:x2] = cv2.bitwise_or(excl_mask_full[y1:y2, x1:x2], e_u8)

        beautified = self.apply_beauty(
            image_bgr,
            skin_brighten_pct=45,
            skin_smooth_pct=50,
            lip_tint_pct=45,
            eye_brighten_pct=40,
            cheek_rosy_pct=35,
            nose_highlight_pct=35,
            faces=faces,
        )

        overlay = beautified.copy()
        overlay[skin_mask_full > 30] = overlay[skin_mask_full > 30] * 0.6 + np.array([40, 180, 50]) * 0.4
        overlay[lip_mask_full > 30] = overlay[lip_mask_full > 30] * 0.4 + np.array([180, 40, 220]) * 0.6
        composite_preview = cv2.addWeighted(beautified, 0.7, overlay, 0.3, 0)

        return {
            "original": image_bgr.copy(),
            "face_landmarks": vis_landmarks,
            "skin_mask": skin_mask_full,
            "excluded_features_mask": excl_mask_full,
            "lip_mask": lip_mask_full,
            "composite_preview": composite_preview,
        }
