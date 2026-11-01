"""
1998 TEAM — Smart Beauty Engine (AI Face Retouching & Natural Beauty)
Core algorithms for natural skin smoothing, skin brightening, and lip tinting.
- EXIF orientation auto-transpose (upright coordinate preservation).
- OpenCV YuNet ONNX for face bounding box and facial landmarks.
- 10-point oriented anatomical facial polygon (constrained strictly inside facial boundary).
- Accurate exclusions: eyes, eyebrows, lips, teeth, and oral cavity.
- Edge-preserving bilateral filter with high-frequency micro-texture recovery to preserve natural skin pores.
- Soft-knee highlight-preserving skin brightening in LAB luminance space with subtle healthy rosy tint.
- Precise oriented lip tinting in LAB color space with teeth and oral cavity exclusion.
- Comprehensive debug mode exporting original, landmarks, skin mask, exclusions, lip mask, and composite preview.
- Non-destructive processing: preserves original image byte-for-byte when sliders are 0%.
"""

import os
import math
import time
import logging
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import cv2
from PIL import Image, ImageOps

from vietphotobooth.camera.face_detector import FaceEyeDetector, DetectedFace

logger = logging.getLogger("VietPhotoBooth.filters.beauty_engine")


class SmartBeautyEngine:
    """
    Bộ xử lý làm đẹp thông minh tự nhiên (Smart Beauty Engine).
    Hỗ trợ làm sáng da, làm mịn da giữ texture thật và tô son môi tự nhiên.
    """

    def __init__(self, model_path: Optional[str] = None):
        self._detector = FaceEyeDetector(model_path=model_path)

    @property
    def is_available(self) -> bool:
        """Kiểm tra mô hình nhận diện khuôn mặt có khả dụng không."""
        return self._detector.is_available

    def detect_faces(
        self,
        image_bgr_or_rgb: np.ndarray,
        is_bgr: bool = True,
        max_proc_width: int = 640
    ) -> List[DetectedFace]:
        """
        Nhận diện khuôn mặt và các điểm mốc trên ảnh.
        """
        if not self._detector.is_available or image_bgr_or_rgb is None or image_bgr_or_rgb.size == 0:
            return []

        try:
            if is_bgr:
                rgb = cv2.cvtColor(image_bgr_or_rgb, cv2.COLOR_BGR2RGB)
            else:
                rgb = image_bgr_or_rgb
            return self._detector.detect_faces(rgb, max_proc_width=max_proc_width)
        except Exception as ex:
            logger.error("Lỗi nhận diện khuôn mặt trong SmartBeautyEngine: %s", ex)
            return []

    # --------------------------------------------------------------------------
    # MASK GENERATION: ANATOMICAL FACE POLYGON & EXCLUSIONS
    # --------------------------------------------------------------------------

    def _build_face_anatomical_polygon(
        self, face: DetectedFace, img_w: int, img_h: int
    ) -> np.ndarray:
        """
        Xây dựng đa giác 10 điểm theo giải phẫu khuôn mặt dựa trên các điểm mốc (landmarks).
        Đa giác tự động xoay theo góc nghiêng của đầu, ôm sát hai gò má và xương hàm,
        tuyệt đối không tràn ra phông nền, cổ áo hay tóc.
        """
        fx, fy, fw, fh = face.bbox
        re = getattr(face, "right_eye", None)
        le = getattr(face, "left_eye", None)
        mr = getattr(face, "mouth_right", None)
        ml = getattr(face, "mouth_left", None)

        # Kiểm tra tính hợp lệ của landmarks
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
            u = eye_vec / d_eye  # Trục ngang mắt

            c_eyes = (re_arr + le_arr) / 2.0
            c_mouth = (mr_arr + ml_arr) / 2.0
            face_axis = c_mouth - c_eyes
            h_em = max(4.0, float(np.linalg.norm(face_axis)))
            v_face = face_axis / h_em  # Trục dọc khuôn mặt (hướng xuống cằm)

            # 10 điểm giải phẫu bao quanh vùng da mặt
            pts = [
                c_eyes - 0.70 * h_em * v_face,                               # Đỉnh trán
                le_arr + 0.45 * d_eye * u - 0.50 * h_em * v_face,           # Thái dương trái
                le_arr + 0.58 * d_eye * u + 0.20 * h_em * v_face,           # Gò má trên trái
                ml_arr + 0.42 * d_eye * u + 0.15 * h_em * v_face,           # Má dưới trái
                ml_arr + 0.22 * d_eye * u + 0.42 * h_em * v_face,           # Xương hàm trái
                c_mouth + 0.62 * h_em * v_face,                             # Đáy cằm
                mr_arr - 0.22 * d_eye * u + 0.42 * h_em * v_face,           # Xương hàm phải
                mr_arr - 0.42 * d_eye * u + 0.15 * h_em * v_face,           # Má dưới phải
                re_arr - 0.58 * d_eye * u + 0.20 * h_em * v_face,           # Gò má trên phải
                re_arr - 0.45 * d_eye * u - 0.50 * h_em * v_face            # Thái dương phải
            ]
            polygon = np.clip(np.array(pts, dtype=np.int32), [0, 0], [img_w - 1, img_h - 1])
            return polygon

        # Fallback an toàn khi thiếu hoặc mất landmarks: Elip bảo thủ bên trong bounding box
        cx = int(fx + fw * 0.50)
        cy = int(fy + fh * 0.48)
        rx = max(2, int(fw * 0.38))
        ry = max(2, int(fh * 0.44))
        pts_ellipse = cv2.ellipse2Poly((cx, cy), (rx, ry), 0, 0, 360, 24)
        return np.clip(pts_ellipse, [0, 0], [img_w - 1, img_h - 1])

    def _generate_face_masks(
        self,
        roi_bgr: np.ndarray,
        face: DetectedFace,
        offset_x: int,
        offset_y: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Tạo các mặt nạ da và môi độc lập trong vùng ROI:
        Trả về (skin_mask_feathered, lip_mask_feathered, exclusions_mask).
        Tất cả mask trả về dạng np.float32 [0.0, 1.0].
        """
        rh, rw = roi_bgr.shape[:2]
        fx, fy, fw, fh = face.bbox

        # Chuyển đổi tọa độ khuôn mặt về hệ tọa độ cục bộ của ROI
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

        # 1. Mặt nạ đa giác giải phẫu khuôn mặt
        face_poly = self._build_face_anatomical_polygon(face_roi, rw, rh)
        anatomical_mask = np.zeros((rh, rw), dtype=np.uint8)
        cv2.fillPoly(anatomical_mask, [face_poly], 255)

        # 2. Phân đoạn tinh chỉnh màu da (YCrCb + HSV) chỉ bên trong đa giác giải phẫu
        ycrcb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2YCrCb)
        skin_ycrcb = cv2.inRange(ycrcb, np.array([0, 130, 75]), np.array([255, 180, 130]))

        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        skin_hsv1 = cv2.inRange(hsv, np.array([0, 20, 50]), np.array([28, 240, 255]))
        skin_hsv2 = cv2.inRange(hsv, np.array([155, 20, 50]), np.array([180, 240, 255]))
        skin_hsv = cv2.bitwise_or(skin_hsv1, skin_hsv2)

        raw_skin = cv2.bitwise_and(skin_ycrcb, skin_hsv)
        skin_base = cv2.bitwise_and(anatomical_mask, raw_skin)

        # 3. Mặt nạ loại trừ (mắt, lông mày, môi, tóc đen)
        exclusions_mask = np.zeros((rh, rw), dtype=np.uint8)

        re = face_roi.right_eye
        le = face_roi.left_eye
        mr = face_roi.mouth_right
        ml = face_roi.mouth_left

        d_eye = math.hypot(le[0] - re[0], le[1] - re[1]) if (re and le) else (fw * 0.35)
        eye_rad = max(3, int(d_eye * 0.18))

        # Loại trừ mắt
        if re and 0 <= int(re[0]) < rw and 0 <= int(re[1]) < rh:
            cv2.circle(exclusions_mask, (int(re[0]), int(re[1])), eye_rad, 255, -1)
        if le and 0 <= int(le[0]) < rw and 0 <= int(le[1]) < rh:
            cv2.circle(exclusions_mask, (int(le[0]), int(le[1])), eye_rad, 255, -1)

        # Loại trừ lông mày (vùng ngay trên mắt)
        brow_dy = int(d_eye * 0.22)
        if re and 0 <= int(re[0]) < rw and 0 <= int(re[1] - brow_dy) < rh:
            cv2.ellipse(exclusions_mask, (int(re[0]), int(re[1] - brow_dy)), (int(d_eye * 0.26), int(d_eye * 0.12)), 0, 0, 360, 255, -1)
        if le and 0 <= int(le[0]) < rw and 0 <= int(le[1] - brow_dy) < rh:
            cv2.ellipse(exclusions_mask, (int(le[0]), int(le[1] - brow_dy)), (int(d_eye * 0.26), int(d_eye * 0.12)), 0, 0, 360, 255, -1)

        # Loại trừ bóng tối sâu hoặc tóc rũ
        dark_hair = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 38]))
        exclusions_mask = cv2.bitwise_or(exclusions_mask, dark_hair)

        # 4. Tạo mặt nạ son môi xoay theo góc nghiêng miệng
        lip_mask = np.zeros((rh, rw), dtype=np.uint8)
        if mr and ml:
            mcx = (mr[0] + ml[0]) / 2.0
            mcy = (mr[1] + ml[1]) / 2.0
            d_mouth = max(4.0, math.hypot(ml[0] - mr[0], ml[1] - mr[1]))
            m_angle = math.degrees(math.atan2(ml[1] - mr[1], ml[0] - mr[0]))

            # Loại trừ toàn bộ vùng miệng khỏi mặt nạ da
            cv2.ellipse(
                exclusions_mask,
                (int(mcx), int(mcy)),
                (int(d_mouth * 0.65), max(3, int(d_mouth * 0.38))),
                m_angle, 0, 360, 255, -1
            )

            # Mặt nạ son môi elip xoay
            cv2.ellipse(
                lip_mask,
                (int(mcx), int(mcy)),
                (int(d_mouth * 0.55), max(2, int(d_mouth * 0.26))),
                m_angle, 0, 360, 255, -1
            )

            # Loại trừ răng trắng sáng và khoang miệng tối bên trong
            teeth_hsv = cv2.inRange(hsv, np.array([0, 0, 160]), np.array([180, 60, 255]))
            dark_cavity = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 45]))
            inner_mouth = cv2.bitwise_or(teeth_hsv, dark_cavity)
            lip_mask = cv2.bitwise_and(lip_mask, cv2.bitwise_not(inner_mouth))

        # Áp dụng loại trừ lên mặt nạ da
        skin_clean = cv2.bitwise_and(skin_base, cv2.bitwise_not(exclusions_mask))

        # 5. Làm mềm viền mặt nạ (Feathering Gaussian) để hiệu ứng hòa trộn mượt mà
        k_skin = max(3, (int(fw * 0.04) // 2) * 2 + 1)
        k_lip = max(3, (int(fw * 0.02) // 2) * 2 + 1)

        skin_mask_f = cv2.GaussianBlur(skin_clean, (k_skin, k_skin), 0).astype(np.float32) / 255.0
        lip_mask_f = cv2.GaussianBlur(lip_mask, (k_lip, k_lip), 0).astype(np.float32) / 255.0
        exclusions_f = exclusions_mask.astype(np.float32) / 255.0

        return skin_mask_f, lip_mask_f, exclusions_f

    # --------------------------------------------------------------------------
    # CORE BEAUTY PROCESSING
    # --------------------------------------------------------------------------

    def apply_beauty(
        self,
        image_bgr: np.ndarray,
        skin_brighten_pct: float = 0.0,
        skin_smooth_pct: float = 0.0,
        lip_tint_pct: float = 0.0,
        faces: Optional[List[DetectedFace]] = None
    ) -> np.ndarray:
        """
        Áp dụng làm đẹp lên ảnh BGR:
        - Giữ nguyên ảnh gốc khi cả 3 thông số = 0.
        - Xử lý ROI độc lập cho từng khuôn mặt.
        - Mịn da bảo toàn 25% micro-texture vân da thật.
        - Sáng da soft-knee chống cháy sáng highlight trong không gian LAB.
        - Tô son môi tự nhiên tránh vùng răng và da xung quanh.
        """
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr

        skin_brighten_pct = max(0.0, min(100.0, float(skin_brighten_pct)))
        skin_smooth_pct = max(0.0, min(100.0, float(skin_smooth_pct)))
        lip_tint_pct = max(0.0, min(100.0, float(lip_tint_pct)))

        # Fast path: không áp dụng hiệu ứng
        if skin_brighten_pct <= 0.01 and skin_smooth_pct <= 0.01 and lip_tint_pct <= 0.01:
            return image_bgr.copy()

        if faces is None:
            faces = self.detect_faces(image_bgr, is_bgr=True)

        if not faces:
            return image_bgr.copy()

        out = image_bgr.copy()
        img_h, img_w = out.shape[:2]

        for face in faces:
            fx, fy, fw, fh = [float(v) for v in face.bbox]
            if fw <= 4 or fh <= 4:
                continue

            # ROI có lề mở rộng 20%
            margin_x = int(fw * 0.20)
            margin_y = int(fh * 0.20)
            x1 = max(0, int(fx - margin_x))
            y1 = max(0, int(fy - margin_y))
            x2 = min(img_w, int(fx + fw + margin_x))
            y2 = min(img_h, int(fy + fh + margin_y))

            roi = out[y1:y2, x1:x2]
            rh, rw = roi.shape[:2]
            if rh < 8 or rw < 8:
                continue

            skin_mask_f, lip_mask_f, _ = self._generate_face_masks(roi, face, x1, y1)

            # A. LÀM MỊN DA (Bilateral Filter + 25% Micro-texture Recovery)
            smooth_roi = roi.copy()
            if skin_smooth_pct > 0.01:
                sigma = 18 + int(skin_smooth_pct * 0.65)
                smoothed = cv2.bilateralFilter(roi, d=9, sigmaColor=sigma, sigmaSpace=sigma)

                # Thu hồi 25% vân da tự nhiên để tránh hiệu ứng nhựa nhân tạo
                texture = roi.astype(np.float32) - smoothed.astype(np.float32)
                smoothed_natural = np.clip(smoothed.astype(np.float32) + 0.25 * texture, 0, 255).astype(np.uint8)

                alpha_s = (skin_mask_f * (skin_smooth_pct / 100.0))[:, :, np.newaxis]
                smooth_roi = np.clip(roi * (1.0 - alpha_s) + smoothed_natural * alpha_s, 0, 255).astype(np.uint8)

            # B. LÀM SÁNG DA (LAB Luminance Soft-knee + Rosy Tone)
            bright_roi = smooth_roi.copy()
            if skin_brighten_pct > 0.01:
                lab = cv2.cvtColor(bright_roi, cv2.COLOR_BGR2LAB).astype(np.float32)
                L = lab[:, :, 0]
                A = lab[:, :, 1]

                # Tăng sáng có bảo toàn vùng highlight (soft-knee)
                gain = (skin_brighten_pct / 100.0) * 28.0
                L_bright = L + gain * (1.0 - L / 255.0)

                # Nâng nhẹ sắc hồng khỏe khoắn
                A_rosy = A + (skin_brighten_pct / 100.0) * 2.2

                lab[:, :, 0] = np.clip(L_bright, 0, 255)
                lab[:, :, 1] = np.clip(A_rosy, 0, 255)

                bright_cand = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
                alpha_b = (skin_mask_f * (skin_brighten_pct / 100.0))[:, :, np.newaxis]
                bright_roi = np.clip(smooth_roi * (1.0 - alpha_b) + bright_cand * alpha_b, 0, 255).astype(np.uint8)

            # C. TÔ SON MÔI (LAB Color Tint)
            final_roi = bright_roi.copy()
            if lip_tint_pct > 0.01 and np.count_nonzero(lip_mask_f > 0.05) > 0:
                lab_lip = cv2.cvtColor(final_roi, cv2.COLOR_BGR2LAB).astype(np.float32)

                # Nâng sắc đỏ hồng rạng rỡ (A) và ấm nhẹ (B)
                lab_lip[:, :, 1] = np.clip(lab_lip[:, :, 1] + (lip_tint_pct / 100.0) * 36.0, 0, 255)
                lab_lip[:, :, 2] = np.clip(lab_lip[:, :, 2] + (lip_tint_pct / 100.0) * 12.0, 0, 255)

                tinted_lip = cv2.cvtColor(lab_lip.astype(np.uint8), cv2.COLOR_LAB2BGR)
                alpha_l = (lip_mask_f * (lip_tint_pct / 100.0))[:, :, np.newaxis]
                final_roi = np.clip(final_roi * (1.0 - alpha_l) + tinted_lip * alpha_l, 0, 255).astype(np.uint8)

            out[y1:y2, x1:x2] = final_roi

        return out

    def apply_beauty_pil(
        self,
        image_pil: Image.Image,
        skin_brighten_pct: float = 0.0,
        skin_smooth_pct: float = 0.0,
        lip_tint_pct: float = 0.0,
        faces: Optional[List[DetectedFace]] = None
    ) -> Image.Image:
        """
        Áp dụng làm đẹp trực tiếp lên đối tượng PIL.Image (tự động chuẩn hóa EXIF orientation).
        """
        if image_pil is None:
            return image_pil

        # Tự động xoay chuẩn theo EXIF orientation để tọa độ pixel luôn thẳng đứng
        upright_pil = ImageOps.exif_transpose(image_pil)

        if skin_brighten_pct <= 0.01 and skin_smooth_pct <= 0.01 and lip_tint_pct <= 0.01:
            return upright_pil.copy()

        rgb_arr = np.array(upright_pil.convert("RGB"))
        bgr_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        out_bgr = self.apply_beauty(
            bgr_arr,
            skin_brighten_pct=skin_brighten_pct,
            skin_smooth_pct=skin_smooth_pct,
            lip_tint_pct=lip_tint_pct,
            faces=faces
        )

        out_rgb = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(out_rgb)

    def generate_scaled_preview(
        self,
        image_bgr: np.ndarray,
        max_dim: int = 1080
    ) -> Tuple[np.ndarray, List[DetectedFace], float]:
        """
        Tạo ảnh preview thu nhỏ và phát hiện khuôn mặt trên tỷ lệ preview.
        Trả về (preview_bgr, preview_faces, scale_factor).
        """
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
        faces: List[DetectedFace],
        scale_ratio: float
    ) -> List[DetectedFace]:
        """
        Ánh xạ danh sách khuôn mặt sang tỷ lệ kích thước khác (scale_ratio = target / source).
        """
        if scale_ratio == 1.0 or not faces:
            return faces

        scaled = []
        for f in faces:
            r_eye = (f.right_eye[0] * scale_ratio, f.right_eye[1] * scale_ratio) if f.right_eye else None
            l_eye = (f.left_eye[0] * scale_ratio, f.left_eye[1] * scale_ratio) if f.left_eye else None
            nose = (f.nose[0] * scale_ratio, f.nose[1] * scale_ratio) if f.nose else None
            m_r = (f.mouth_right[0] * scale_ratio, f.mouth_right[1] * scale_ratio) if f.mouth_right else None
            m_l = (f.mouth_left[0] * scale_ratio, f.mouth_left[1] * scale_ratio) if f.mouth_left else None

            scaled.append(DetectedFace(
                x=f.x * scale_ratio,
                y=f.y * scale_ratio,
                w=f.w * scale_ratio,
                h=f.h * scale_ratio,
                confidence=f.confidence,
                right_eye=r_eye,
                left_eye=l_eye,
                nose=nose,
                mouth_right=m_r,
                mouth_left=m_l
            ))
        return scaled

    # --------------------------------------------------------------------------
    # DEBUG MODE: MASK VISUALIZATION & EXPORT
    # --------------------------------------------------------------------------

    def generate_debug_masks(
        self,
        image_bgr: np.ndarray,
        faces: Optional[List[DetectedFace]] = None
    ) -> Dict[str, np.ndarray]:
        """
        Chế độ Debug phục vụ kiểm tra chất lượng phân đoạn mặt nạ (Requirement B4):
        Xuất 6 hình ảnh:
        - 'original': Ảnh gốc
        - 'face_landmarks': Bounding box, landmarks và đa giác giải phẫu 10 điểm
        - 'skin_mask': Mặt nạ vùng da (0-255)
        - 'excluded_features_mask': Mặt nạ các vùng bị loại trừ (mắt, mày, miệng, tóc)
        - 'lip_mask': Mặt nạ môi (0-255)
        - 'composite_preview': Ảnh kết quả ghép mask với lớp màu overlay bán trong suốt
        """
        if image_bgr is None or image_bgr.size == 0:
            return {}

        if faces is None:
            faces = self.detect_faces(image_bgr, is_bgr=True)

        h, w = image_bgr.shape[:2]
        skin_mask_full = np.zeros((h, w), dtype=np.uint8)
        lip_mask_full = np.zeros((h, w), dtype=np.uint8)
        excl_mask_full = np.zeros((h, w), dtype=np.uint8)

        vis_landmarks = image_bgr.copy()

        for face in faces:
            fx, fy, fw, fh = [int(v) for v in face.bbox]
            # Vẽ BBox
            cv2.rectangle(vis_landmarks, (fx, fy), (fx + fw, fy + fh), (55, 175, 212), 2)

            # Vẽ đa giác 10 điểm giải phẫu
            poly = self._build_face_anatomical_polygon(face, w, h)
            cv2.polylines(vis_landmarks, [poly], True, (0, 255, 255), 2)

            # Vẽ landmarks 5 điểm
            if face.right_eye:
                cv2.circle(vis_landmarks, (int(face.right_eye[0]), int(face.right_eye[1])), 4, (0, 255, 0), -1)
            if face.left_eye:
                cv2.circle(vis_landmarks, (int(face.left_eye[0]), int(face.left_eye[1])), 4, (0, 255, 0), -1)
            if face.nose:
                cv2.circle(vis_landmarks, (int(face.nose[0]), int(face.nose[1])), 4, (255, 0, 0), -1)
            if face.mouth_right:
                cv2.circle(vis_landmarks, (int(face.mouth_right[0]), int(face.mouth_right[1])), 4, (0, 0, 255), -1)
            if face.mouth_left:
                cv2.circle(vis_landmarks, (int(face.mouth_left[0]), int(face.mouth_left[1])), 4, (0, 0, 255), -1)

            # Trích xuất mask trong ROI
            margin_x = int(fw * 0.20)
            margin_y = int(fh * 0.20)
            x1 = max(0, fx - margin_x)
            y1 = max(0, fy - margin_y)
            x2 = min(w, fx + fw + margin_x)
            y2 = min(h, fy + fh + margin_y)

            roi = image_bgr[y1:y2, x1:x2]
            if roi.shape[0] >= 8 and roi.shape[1] >= 8:
                s_mask_f, l_mask_f, excl_f = self._generate_face_masks(roi, face, x1, y1)
                s_u8 = (s_mask_f * 255.0).astype(np.uint8)
                l_u8 = (l_mask_f * 255.0).astype(np.uint8)
                e_u8 = (excl_f * 255.0).astype(np.uint8)

                skin_mask_full[y1:y2, x1:x2] = cv2.bitwise_or(skin_mask_full[y1:y2, x1:x2], s_u8)
                lip_mask_full[y1:y2, x1:x2] = cv2.bitwise_or(lip_mask_full[y1:y2, x1:x2], l_u8)
                excl_mask_full[y1:y2, x1:x2] = cv2.bitwise_or(excl_mask_full[y1:y2, x1:x2], e_u8)

        # Tạo ảnh composite preview hiển thị mask màu (Xanh lá = Da, Hồng = Môi)
        composite = image_bgr.copy()
        # Áp dụng làm đẹp mẫu (50% sáng, 50% mịn, 50% son)
        beautified = self.apply_beauty(image_bgr, 50, 50, 50, faces=faces)

        # Overlay translucent mask
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
            "composite_preview": composite_preview
        }
