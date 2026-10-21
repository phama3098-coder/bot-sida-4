"""
1998 TEAM — Photobooth Update Manifest Model
Defines the structured manifest format for checking, verifying, and delivering software updates.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

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
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateManifest":
        if not isinstance(data, dict):
            raise ValueError("Dữ liệu manifest phải là một từ điển JSON (JSON Object).")

        app = str(data.get("app", "1998 TEAM Photobooth"))
        version = str(data.get("version", "")).strip()
        if not version:
            raise ValueError("Manifest thiếu trường 'version' bắt buộc.")

        build = int(data.get("build", 0))
        release_date = str(data.get("release_date", ""))

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
            channel=channel
        )

    @classmethod
    def from_json(cls, json_str: str) -> "UpdateManifest":
        data = json.loads(json_str)
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
                errors.append(f"Đường dẫn tải về là địa chỉ mẫu (placeholder), chưa được cấu hình tệp cài đặt thật.")

        if not self.sha256 or not self.sha256.strip():
            errors.append("Thiếu mã băm SHA-256 xác thực tính toàn vẹn.")
        elif len(self.sha256.strip()) != 64 or not all(c in "0123456789abcdef" for c in self.sha256.lower().strip()):
            errors.append("Mã băm SHA-256 không hợp lệ (phải gồm đúng 64 ký tự hex).")

        if self.file_size_bytes < 0:
            errors.append("Dung lượng tệp cài đặt (file_size_bytes) không hợp lệ.")

        return errors
