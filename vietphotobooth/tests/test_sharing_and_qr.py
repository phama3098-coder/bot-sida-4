"""
Automated Tests for Local LAN Sharing and QR Code Generator
"""

import os
import tempfile
import pytest
from vietphotobooth.sharing.token_manager import TokenManager

def test_token_lifecycle_and_qr():
    with tempfile.TemporaryDirectory() as tmpdir:
        sample_file = os.path.join(tmpdir, "photo_final.jpg")
        with open(sample_file, "wb") as f:
            f.write(b"sample_image_data")

        mgr = TokenManager(port=8080)
        local_ip = mgr.get_local_ip()
        assert local_ip is not None

        # Create token
        tok = mgr.create_share_token(file_path=sample_file, event_name="Wedding2026", expire_hours=24)
        assert len(tok.token) >= 16
        assert tok.is_valid is True

        # URL format
        url = mgr.get_share_url(tok.token)
        assert f":8080/s/{tok.token}" in url

        # QR code generation
        qr_bytes = mgr.generate_qr_bytes(url)
        assert qr_bytes.startswith(b"\x89PNG")  # PNG Header

        # Query token
        found = mgr.get_token(tok.token)
        assert found is not None
        assert found.filename == "photo_final.jpg"

        # Revocation
        assert mgr.revoke_token(tok.token) is True
        assert mgr.get_token(tok.token) is None  # Should be invalid now
