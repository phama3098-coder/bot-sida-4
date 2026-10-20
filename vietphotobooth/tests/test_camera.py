"""
Automated Tests for Camera Adapters and Camera Manager
"""

import pytest
from vietphotobooth.camera.simulator import CameraSimulator
from vietphotobooth.camera.directshow import DirectShowCameraAdapter
from vietphotobooth.camera.manager import CameraManager

def test_camera_simulator():
    sim = CameraSimulator()
    assert sim.is_connected() is True

    info = sim.get_info()
    assert info.is_simulator is True
    assert "Simulator" in info.name
    assert info.capabilities["can_capture"] is True

    # Capture test
    img = sim.capture_image()
    assert img is not None
    assert img.size == (2400, 1600)

    # Liveview test
    frame = sim.get_liveview_frame()
    assert frame is not None
    assert len(frame) > 1000
    assert frame.startswith(b"\xff\xd8")  # JPEG Header

    # Parameter test
    sim.set_parameters({"iso": "800", "shutter_speed": "1/250"})
    params = sim.get_parameters()
    assert params["iso"] == "800"
    assert params["shutter_speed"] == "1/250"

    # Disconnect simulation test
    sim.simulate_disconnect = True
    assert sim.is_connected() is False
    assert sim.capture_image() is None

def test_directshow_camera():
    adapter = DirectShowCameraAdapter(device_index=0)
    devices = adapter.detect_devices()
    assert isinstance(devices, list)

    if devices:
        conn = adapter.connect(device_id=0)
        if conn:
            assert adapter.is_connected() is True
            img = adapter.capture_image()
            if img:
                assert img.size[0] > 0
                assert img.size[1] > 0
            liveview = adapter.get_liveview_frame()
            if liveview:
                assert liveview.startswith(b"\xff\xd8")
            adapter.disconnect()
            assert adapter.is_connected() is False

def test_camera_manager_switching_and_safety():
    mgr = CameraManager(default_backend="simulator")
    assert mgr.is_connected() is True
    assert mgr.get_info()["is_simulator"] is True

    # Capture through manager
    img = mgr.capture()
    assert img is not None

    # Switch to directshow
    mgr.switch_backend("directshow", device_index=0)
    assert mgr.backend_name == "directshow"

    # Switch back to simulator
    mgr.switch_backend("simulator")
    assert mgr.backend_name == "simulator"
    assert mgr.is_connected() is True
