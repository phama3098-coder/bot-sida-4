"""
Automated Tests for State Machine Flow and FastAPI Server Endpoints
"""

import os
import time
import tempfile
import pytest
from starlette.testclient import TestClient

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.processing.template_engine import TemplateEngine
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.sharing.token_manager import TokenManager
from vietphotobooth.core.state_machine import SessionManager, STATE_IDLE, STATE_PREVIEW
from vietphotobooth.server import create_app

def test_session_manager_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = ConfigManager(config_path=os.path.join(tmpdir, "config.json"))
        cfg.set("countdown_seconds", 1)  # Đặt 1 giây để test chạy nhanh
        cfg.set("delay_between_shots", 0)
        cfg.set("photos_per_session", 2)
        cfg.save()

        ev = EventManager(storage_root=tmpdir, current_event="TestSessionEvent")
        cam = CameraManager(default_backend="simulator")
        tpl = TemplateEngine()
        prn = PrintManager()
        tok = TokenManager()

        sm = SessionManager(
            config=cfg,
            event_mgr=ev,
            camera_mgr=cam,
            template_engine=tpl,
            print_mgr=prn,
            token_mgr=tok
        )

        assert sm.state == STATE_IDLE
        res = sm.start_session()
        assert res["success"] is True

        # Chờ session hoàn tất chụp 2 kiểu và ghép ảnh
        timeout = 10
        start_t = time.time()
        while sm.state != STATE_PREVIEW and time.time() - start_t < timeout:
            time.sleep(0.2)

        assert sm.state == STATE_PREVIEW
        status = sm.get_status()
        assert status["has_final"] is True
        assert status["final_filename"] is not None
        assert status["share_token"] is not None

        # Reset về màn hình chờ
        sm.reset_to_idle()
        assert sm.state == STATE_IDLE

def test_fastapi_endpoints():
    app = create_app()
    client = TestClient(app)

    # 1. Kiosk View
    res = client.get("/")
    assert res.status_code == 200
    assert "VietPhotoBooth" in res.text

    # 2. Camera Info
    res = client.get("/api/camera/info")
    assert res.status_code == 200
    data = res.json()
    assert "name" in data

    # 3. Printer List
    res = client.get("/api/printer/list")
    assert res.status_code == 200
    data = res.json()
    assert "printers" in data

    # 4. Events
    res = client.get("/api/events")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data

    # 5. Templates
    res = client.get("/api/templates")
    assert res.status_code == 200
    data = res.json()
    assert "templates" in data

    # 6. Admin PIN verification
    res = client.post("/api/admin/verify-pin", data={"pin": "1234"})
    assert res.status_code == 200
    assert res.json()["success"] is True

    res = client.post("/api/admin/verify-pin", data={"pin": "0000"})
    assert res.status_code == 200
    assert res.json()["success"] is False
