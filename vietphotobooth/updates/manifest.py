"""
1998 TEAM — Photobooth Update Manifest Model
Defines the structured manifest format for checking, verifying, and delivering software updates.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests

@dataclass
class UpdateManifest:
    app: str
    version: str
    build: int = 0
    release_date: str = ""
    release_notes: List[str] = field(default_factory=list)
    download_url: str = ""
    sha256: str = ""
    file_size_bytes: int = 0
    minimum_supported_version: str = "1.0.0"
    is_mandatory: bool = False
    channel: str = "stable"  # "stable", "beta"
    package_type: str = "installer"  # "installer", "portable"
    architecture: str = "x64"  # "x64", "x86", "arm64", "all"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app": self.app,
            "version": self.version,
            "build": self.build,
            "release_date": self.release_date,
            "release_notes": self.release_notes,
            "download_url": self.download_url,
            "sha256": self.sha256.lower().strip(),
            "file_size_bytes": self.file_size_bytes,
            "minimum_supported_version": self.minimum_supported_version,
            "is_mandatory": self.is_mandatory,
            "channel": self.channel,
            "package_type": self.package_type,
            "architecture": self.architecture,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def is_github_release(cls, data: Dict[str, Any]) -> bool:
        """
        Nhận diện chính xác định dạng GitHub Release từ GitHub Releases API:
        Có các trường đặc trưng của GitHub Release như 'tag_name', 'assets', 'upload_url', 'tarball_url', 'zipball_url', 'published_at'
        và không phải cấu trúc manifest nội bộ (chứa cả 'version' và 'download_url' cấp cao nhất).
        """
        if not isinstance(data, dict):
            return False
        if "download_url" in data and "version" in data:
            return False
        gh_fields = ("tag_name", "assets", "upload_url", "tarball_url", "zipball_url", "published_at")
        return any(f in data for f in gh_fields)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateManifest":
        if not isinstance(data, dict):
            raise ValueError("Dữ liệu manifest phải là một từ điển JSON (JSON Object).")

        # Phân biệt rõ hai định dạng: nếu là dữ liệu GitHub Release, chuyển tiếp sang from_github_release
        if cls.is_github_release(data):
            return cls.from_github_release(data)

        app = str(data.get("app", "1998 TEAM Photobooth"))
        version = str(data.get("version", "")).strip()
        if not version:
            raise ValueError("Manifest thiếu trường 'version' bắt buộc.")

        build = int(data.get("build", 0))
        release_date = str(data.get("release_date", "")).strip()

        notes = data.get("release_notes", [])
        if isinstance(notes, str):
            notes = [notes]
        elif not isinstance(notes, list):
            notes = []
        release_notes = [str(n) for n in notes]

        download_url = str(data.get("download_url", "")).strip()
        sha256 = str(data.get("sha256", "")).lower().strip()
        file_size_bytes = int(data.get("file_size_bytes", 0))
        minimum_supported_version = str(data.get("minimum_supported_version", "1.0.0"))
        is_mandatory = bool(data.get("is_mandatory", False))
        channel = str(data.get("channel", "stable"))
        package_type = str(data.get("package_type", "installer"))
        architecture = str(data.get("architecture", "x64"))

        return cls(
            app=app,
            version=version,
            build=build,
            release_date=release_date,
            release_notes=release_notes,
            download_url=download_url,
            sha256=sha256,
            file_size_bytes=file_size_bytes,
            minimum_supported_version=minimum_supported_version,
            is_mandatory=is_mandatory,
            channel=channel,
            package_type=package_type,
            architecture=architecture
        )

    @classmethod
    def from_github_release(cls, data: Dict[str, Any]) -> "UpdateManifest":
        """
        Phân tích đối tượng Release trả về trực tiếp từ GitHub Releases API chính thức:
        https://api.github.com/repos/{owner}/{repo}/releases/latest
        Trích xuất phiên bản, ngày phát hành, ghi chú, tìm asset bộ cài Windows (.exe)
        và đối chiếu mã băm SHA-256 từ các nguồn đáng tin cậy.
        """
        if not isinstance(data, dict):
            raise ValueError("Dữ liệu GitHub Release phải là một từ điển JSON (JSON Object).")

        # 1. Tên ứng dụng
        app_name = str(data.get("name") or "1998 TEAM Photobooth")

        # 2. Phiên bản (Version) và Build Number
        tag_name = str(data.get("tag_name", "")).strip()
        version_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", tag_name)
        if version_match:
            version = version_match.group(1)
        else:
            version = tag_name.lstrip("vV").strip()

        if not version:
            rel_name = str(data.get("name", ""))
            name_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", rel_name)
            version = name_match.group(1) if name_match else ""

        if not version:
            raise ValueError(f"Không thể xác định số phiên bản từ release tag '{tag_name}'.")

        # Xác định build number từ tiêu đề hoặc mô tả (nếu có)
        build = 0
        raw_text = f"{data.get('name', '')} {data.get('body', '')}"
        build_match = re.search(r"[Bb]uild\s*[:#-]?\s*(\d+)", raw_text)
        if build_match:
            build = int(build_match.group(1))
        else:
            parts = version.split(".")
            if len(parts) >= 2:
                try:
                    build = int(parts[0]) * 100 + int(parts[1]) * 10 + (int(parts[2]) if len(parts) > 2 else 0)
                except ValueError:
                    build = 0

        # 3. Ngày phát hành
        published_at = str(data.get("published_at") or data.get("created_at") or "")
        release_date = published_at[:10] if len(published_at) >= 10 else datetime.now().strftime("%Y-%m-%d")

        # 4. Ghi chú phát hành
        body = str(data.get("body", "")).strip()
        release_notes = []
        if body:
            for line in body.splitlines():
                cleaned = line.strip()
                if cleaned and not cleaned.startswith("#"):
                    cleaned = re.sub(r"^[-*•]\s*", "", cleaned)
                    release_notes.append(cleaned)
        if not release_notes:
            release_notes = [f"Bản phát hành v{version} từ kho lưu trữ GitHub chính thức."]

        # 5. Tìm asset bộ cài đặt Windows (.exe) thực tế
        # Không tự đoán tên file, không ghép URL thủ công, không dùng file ZIP nguồn
        assets = data.get("assets", [])
        if not assets:
            raise ValueError(
                f"Bản phát hành GitHub (tag '{tag_name}') không có bất kỳ tệp đính kèm (asset) nào. "
                "Cần đính kèm tệp bộ cài đặt Windows (.exe) khi phát hành."
            )

        exe_assets = [
            a for a in assets
            if isinstance(a, dict) and str(a.get("name", "")).lower().endswith(".exe")
        ]

        if not exe_assets:
            avail_names = [str(a.get("name", "")) for a in assets if isinstance(a, dict)]
            raise ValueError(
                f"Không tìm thấy bộ cài đặt Windows (.exe) trong bản phát hành '{tag_name}'. "
                f"Các asset hiện có trên GitHub: {', '.join(avail_names) if avail_names else 'Trống'}."
            )

        # Ưu tiên tìm đúng file cài Windows .exe cho phiên bản hiện tại:
        # 1. Ưu tiên cao nhất: Tên file chứa phiên bản của release (ví dụ: v1.2.1 hoặc 1.2.1) kèm setup
        chosen_asset = None
        for a in exe_assets:
            aname = str(a.get("name", "")).strip().lower()
            if (f"v{version.lower()}" in aname or version.lower() in aname) and "setup" in aname:
                chosen_asset = a
                break

        # 2. Ưu tiên thứ hai: Tên file chính xác "1998-TEAM-Setup.exe" (không phân biệt hoa thường)
        if not chosen_asset:
            for a in exe_assets:
                aname = str(a.get("name", "")).strip().lower()
                if aname == "1998-team-setup.exe":
                    chosen_asset = a
                    break

        # 3. Ưu tiên thứ ba: Chứa cả "setup" và "1998"
        if not chosen_asset:
            for a in exe_assets:
                aname = str(a.get("name", "")).strip().lower()
                if "setup" in aname and "1998" in aname:
                    chosen_asset = a
                    break

        # 4. Ưu tiên thứ tư: Chứa từ khóa setup / installer / photobooth
        if not chosen_asset:
            for a in exe_assets:
                aname = str(a.get("name", "")).strip().lower()
                if any(k in aname for k in ("setup", "installer", "photobooth")):
                    chosen_asset = a
                    break

        # 5. Fallback: Asset .exe đầu tiên
        if not chosen_asset:
            chosen_asset = exe_assets[0]

        asset_name = str(chosen_asset.get("name", ""))
        download_url = str(chosen_asset.get("browser_download_url", "")).strip()
        file_size_bytes = int(chosen_asset.get("size", 0))

        if not download_url:
            raise ValueError(f"Asset '{asset_name}' không có liên kết tải trực tiếp (browser_download_url).")

        # 6. Xác minh mã băm SHA-256 từ nguồn đáng tin cậy đã công bố
        sha256 = ""
        # Nguồn A: Thuộc tính 'digest' chính thức của GitHub Release Asset (e.g. 'sha256:02ed4c...')
        digest_val = str(chosen_asset.get("digest", "")).strip().lower()
        if digest_val.startswith("sha256:"):
            sha256 = digest_val.replace("sha256:", "").strip()

        # Nguồn B: Tìm trong Release Notes / Body được tác giả ghi rõ
        if not sha256 or len(sha256) != 64:
            m_hash = re.search(r"(?:sha-?256|sha256)[\s:=]+([a-fA-F0-9]{64})", body, re.IGNORECASE)
            if m_hash:
                sha256 = m_hash.group(1).lower()
            else:
                m_file_hash = re.search(rf"([a-fA-F0-9]{{64}})\s+\*?{re.escape(asset_name)}", body, re.IGNORECASE)
                if m_file_hash:
                    sha256 = m_file_hash.group(1).lower()

        # Nguồn C: Tìm tệp checksum companion đính kèm trong assets (*.sha256, checksums.txt)
        if not sha256 or len(sha256) != 64:
            for a in assets:
                an = str(a.get("name", "")).lower()
                if an in (f"{asset_name.lower()}.sha256", "sha256sums.txt", "checksums.txt", "sha256.txt"):
                    c_url = a.get("browser_download_url")
                    if c_url:
                        try:
                            c_resp = requests.get(
                                c_url,
                                timeout=4.0,
                                headers={"User-Agent": "1998TeamPhotobooth-Updater/1.0"}
                            )
                            if c_resp.status_code == 200:
                                for line in c_resp.text.splitlines():
                                    if asset_name.lower() in line.lower() or len(line.strip()) == 64:
                                        m_ch = re.search(r"([a-fA-F0-9]{64})", line)
                                        if m_ch:
                                            sha256 = m_ch.group(1).lower()
                                            break
                        except Exception:
                            pass
                if sha256 and len(sha256) == 64:
                    break

        return cls(
            app=app_name,
            version=version,
            build=build,
            release_date=release_date,
            release_notes=release_notes,
            download_url=download_url,
            sha256=sha256,
            file_size_bytes=file_size_bytes,
            package_type="installer",
            architecture="x64"
        )

    @classmethod
    def from_json(cls, json_str: str) -> "UpdateManifest":
        try:
            data = json.loads(json_str)
        except Exception as e:
            raise ValueError(f"Dữ liệu không đúng định dạng JSON: {e}")
        if not isinstance(data, dict):
            raise ValueError("Dữ liệu cập nhật JSON phải là một JSON Object.")
        if cls.is_github_release(data):
            return cls.from_github_release(data)
        return cls.from_dict(data)

    def validate_integrity(self) -> List[str]:
        """Kiểm tra tính hợp lệ về cấu trúc của manifest."""
        errors = []
        if not self.version or not self.version.strip():
            errors.append("Thiếu thông tin phiên bản (version).")

        if not self.download_url or not self.download_url.strip():
            errors.append("Thiếu đường dẫn tải bộ cài (download_url).")
        else:
            placeholder_domains = ["example.com", "example.org", "placeholder", "your-domain.com", "url_bo_cai_that"]
            if any(p in self.download_url.lower() for p in placeholder_domains):
                errors.append("Đường dẫn tải về là địa chỉ mẫu (placeholder), chưa được cấu hình tệp cài đặt thật.")

        if not self.sha256 or not self.sha256.strip():
            errors.append("Thiếu mã băm SHA-256 xác thực tính toàn vẹn.")
        elif len(self.sha256.strip()) != 64 or not all(c in "0123456789abcdef" for c in self.sha256.lower().strip()):
            errors.append("Mã băm SHA-256 không hợp lệ (phải gồm đúng 64 ký tự hex).")

        if self.file_size_bytes < 0:
            errors.append("Dung lượng tệp cài đặt (file_size_bytes) không hợp lệ.")

        # Kiểm tra ngày phát hành không được là ngày trong tương lai
        if self.release_date:
            try:
                r_date = datetime.strptime(self.release_date.strip(), "%Y-%m-%d").date()
                if r_date > datetime.now().date():
                    errors.append(f"Ngày phát hành không hợp lệ (ngày tương lai: {self.release_date}).")
            except ValueError:
                errors.append(f"Định dạng ngày phát hành không hợp lệ: '{self.release_date}'. Định dạng chuẩn là YYYY-MM-DD.")

        # Kiểm tra kiến trúc gói cài đặt
        if self.architecture and self.architecture.lower() not in ("x64", "x86_64", "amd64", "all"):
            errors.append(f"Kiến trúc gói cài đặt ({self.architecture}) không tương thích với hệ thống (x64).")

        return errors
