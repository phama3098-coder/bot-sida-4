"""
Unit tests for Google Drive Cloud Integration, DPAPI Encryption, and Sync Manager.
"""

import os
import json
import time
import tempfile
import pytest
from PIL import Image

from vietphotobooth.cloud import GDriveAuth, GDriveClient, SyncManager, SyncStatus
from vietphotobooth.core.config import ConfigManager


def test_dpapi_encryption_roundtrip():
    """Kiểm tra mã hóa và giải mã dữ liệu token qua Windows DPAPI."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        token_path = os.path.join(tmp_dir, "test_token.dat")
        auth = GDriveAuth(token_path=token_path, simulation_mode=False)

        sample_tokens = {
            "access_token": "ya29.sample_test_access_token_12345",
            "refresh_token": "1//sample_test_refresh_token_67890",
            "expires_at": time.time() + 3600,
            "user_email": "test.studio@gmail.com"
        }

        auth.save_token(sample_tokens)
        assert os.path.exists(token_path)

        # File lưu trên đĩa phải là dạng mã hóa nhị phân
        with open(token_path, "rb") as f:
            raw_bytes = f.read()
        assert b"ya29.sample_test_access_token_12345" not in raw_bytes

        # Đọc và giải mã lại
        loaded = auth.load_token()
        assert loaded is not None
        assert loaded["access_token"] == sample_tokens["access_token"]
        assert loaded["user_email"] == "test.studio@gmail.com"


def test_gdrive_auth_simulation_mode():
    """Kiểm tra chế độ giả lập xác thực (Simulator mode) không cần internet."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        token_path = os.path.join(tmp_dir, "sim_token.dat")
        auth = GDriveAuth(token_path=token_path, simulation_mode=True)

        ok, msg = auth.authorize_interactive()
        assert ok is True
        assert "Giả lập" in msg
        assert auth.is_authenticated() is True
        assert auth.get_valid_access_token() == "simulated_gdrive_access_token"

        # Kiểm tra revoke
        rev_ok, rev_msg = auth.revoke()
        assert rev_ok is True
        assert auth._tokens is None


def test_gdrive_client_operations():
    """Kiểm tra client Google Drive API v3 (Folder, Upload, Permissions, Links)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        token_path = os.path.join(tmp_dir, "sim_client_token.dat")
        auth = GDriveAuth(token_path=token_path, simulation_mode=True)
        auth.authorize_interactive()
        client = GDriveClient(auth)

        # 1. Hồ sơ người dùng
        profile = client.get_user_profile()
        assert profile.get("email") == "studio1998.demo@gmail.com"

        # 2. Tạo/Tìm thư mục
        folder_id = client.get_or_create_folder("1998 TEAM — Dam Cuoi Minh Anh")
        assert folder_id is not None
        assert "sim_folder" in folder_id

        # 3. Cấp quyền chia sẻ công khai
        perm_ok = client.set_public_permission(folder_id)
        assert perm_ok is True

        # 4. Tải file ảnh lên
        img_path = os.path.join(tmp_dir, "test_session_final.jpg")
        img = Image.new("RGB", (300, 300), color="blue")
        img.save(img_path, "JPEG")

        upload_res = client.upload_photo(img_path, folder_id=folder_id)
        assert upload_res is not None
        assert "webViewLink" in upload_res
        assert "drive.google.com" in upload_res["webViewLink"]

        # 5. Link thư mục
        folder_link = client.get_folder_share_link(folder_id)
        assert "drive.google.com/drive/folders" in folder_link


def test_sync_manager_queue_and_registry():
    """Kiểm tra hàng đợi Offline-first và Registry đồng bộ dữ liệu."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ConfigManager()
        cfg.set("cloud.gdrive_simulation_mode", True)
        cfg.save()

        sync_mgr = SyncManager(cfg)
        sync_mgr.registry_file = os.path.join(tmp_dir, "test_registry.json")
        sync_mgr.auth.simulation_mode = True
        sync_mgr.auth.authorize_interactive()

        # Tạo file ảnh kiểm tra
        photo_path = os.path.join(tmp_dir, "Session_001_final.jpg")
        img = Image.new("RGB", (200, 200), color="gold")
        img.save(photo_path, "JPEG")

        # Đưa vào hàng đợi
        enq_ok = sync_mgr.enqueue(photo_path, "DamCuoi_Test", is_final=True)
        assert enq_ok is True

        # Đợi worker xử lý ngắn
        time.sleep(1.0)

        # Kiểm tra file registry
        info = sync_mgr.get_file_info(photo_path)
        assert info is not None
        assert info.get("status") == SyncStatus.SYNCED
        assert "drive.google.com" in info.get("web_link", "")

        # Kiểm tra trùng lặp (Deduplication)
        assert sync_mgr.enqueue(photo_path, "DamCuoi_Test") is True

        sync_mgr.close()
