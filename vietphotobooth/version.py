"""
1998 TEAM — Photobooth Version Definition
Centralized Single Source of Truth for application versioning, build number, and release metadata.
"""

import re
from typing import Tuple

__app_name__ = "1998 TEAM — Photobooth"
__version__ = "2.1.0"
__build__ = 217
__channel__ = ""
__release_date__ = "2026-11-10"
__publisher__ = "1998 Studio phóng sự cưới"
__copyright__ = "© 2026 1998 Studio. All rights reserved."

def get_version_string(include_build: bool = True) -> str:
    """Trả về chuỗi phiên bản chuẩn, ví dụ: '1.0.0' hoặc '1.0.0 (Build 101)'."""
    if include_build and __build__ > 0:
        return f"{__version__} (Build {__build__})"
    return __version__

def parse_semver(ver_str: str) -> Tuple[int, int, int]:
    """
    Phân tích chuỗi phiên bản dạng semver (ví dụ '1.0.0', 'v1.2.3', '2.1') thành tuple (major, minor, patch).
    Bỏ qua các tiền tố 'v' hoặc hậu tố '-beta', '-rc'.
    """
    if not ver_str:
        return (0, 0, 0)
    cleaned = str(ver_str).strip().lstrip("vV")
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", cleaned)
    if not match:
        return (0, 0, 0)
    major = int(match.group(1)) if match.group(1) is not None else 0
    minor = int(match.group(2)) if match.group(2) is not None else 0
    patch = int(match.group(3)) if match.group(3) is not None else 0
    return (major, minor, patch)

def is_newer_version(
    current_ver: str,
    candidate_ver: str,
    current_build: int = 0,
    candidate_build: int = 0
) -> bool:
    """
    So sánh hai phiên bản để xác định xem phiên bản ứng cử viên (candidate) có mới hơn không.
    Ưu tiên so sánh Semantic Versioning (Major.Minor.Patch).
    Nếu SemVer bằng nhau, so sánh Build Number.
    """
    c_sem = parse_semver(current_ver)
    cand_sem = parse_semver(candidate_ver)

    if cand_sem > c_sem:
        return True
    elif cand_sem < c_sem:
        return False

    # SemVer bằng nhau, so sánh build number
    return int(candidate_build) > int(current_build)
