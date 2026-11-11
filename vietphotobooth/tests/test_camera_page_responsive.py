"""Responsive layout and connection control verification for CameraPage."""

import pytest
from PySide6.QtCore import QSize, QPoint
from PySide6.QtWidgets import QApplication

from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.desktop.widgets.camera_page import CameraPage


@pytest.mark.parametrize(
    "size",
    [
        QSize(1920, 1080),
        QSize(1366, 768),
        QSize(1277, 752),
    ],
)
def test_camera_page_responsive_layout_and_buttons(qapp, size):
    """Verify CameraPage controls and tables fit and do not clip across resolutions."""
    cam_mgr = CameraManager(default_backend="simulator")
    page = CameraPage(camera_mgr=cam_mgr)

    # Stop background workers to keep test isolated and fast
    if hasattr(page, "_initial_diag_timer") and page._initial_diag_timer.isActive():
        page._initial_diag_timer.stop()
    if hasattr(page, "_diag_worker") and page._diag_worker and page._diag_worker.isRunning():
        page._diag_worker.quit()
        page._diag_worker.wait(500)

    page.resize(size)
    page.show()
    qapp.processEvents()

    # 1. Connection buttons must not be squished
    assert hasattr(page, "btn_switch")
    assert hasattr(page, "btn_disconnect")
    assert page.btn_switch.isVisible()
    assert page.btn_disconnect.isVisible()
    assert page.btn_switch.width() >= 140, f"btn_switch too narrow: {page.btn_switch.width()}"
    assert page.btn_disconnect.width() >= 100, f"btn_disconnect too narrow: {page.btn_disconnect.width()}"

    # 2. Diagnostic actions (Run, Export, Test AF) must all be within right column bounds
    assert hasattr(page, "btn_run_diag")
    assert hasattr(page, "btn_export_diag")
    assert hasattr(page, "btn_test_af")
    assert page.btn_run_diag.isVisible()
    assert page.btn_export_diag.isVisible()
    assert page.btn_test_af.isVisible()

    col_right = page.col_right_widget
    for btn in (page.btn_run_diag, page.btn_export_diag, page.btn_test_af, page.btn_switch, page.btn_disconnect):
        pt = btn.mapTo(col_right, QPoint(0, 0))
        assert pt.x() >= 0, f"{btn.text()} x position negative"
        assert pt.x() + btn.width() <= col_right.width() + 10, f"{btn.text()} clipped on right edge"

    # 3. Preview action buttons must all be visible
    preview_btns = (
        page.btn_af, page.btn_face_eye_af, page.btn_face_detect,
        page.btn_test_shot, page.btn_grid, page.btn_fullscreen, page.btn_reset
    )
    col_left = page.col_left_widget
    for btn in preview_btns:
        assert btn.isVisible()
        pt = btn.mapTo(col_left, QPoint(0, 0))
        assert pt.x() >= 0
        assert pt.x() + btn.width() <= col_left.width() + 10

    # 4. Scroll area and tables configuration
    assert hasattr(page, "scroll_area")
    assert page.scroll_area.widgetResizable() is True
    assert page.table_diag.maximumHeight() <= 300
    assert page.table_compat.maximumHeight() <= 300

    page.close()
    page.deleteLater()
    cam_mgr.disconnect()
