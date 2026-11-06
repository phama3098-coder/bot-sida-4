"""Responsive layout coverage for the Frame Designer page."""

import pytest

from PySide6.QtCore import QSize, QPoint
from PySide6.QtWidgets import QApplication, QBoxLayout, QWidget

from vietphotobooth.core import config as config_module


@pytest.fixture
def frame_designer_factory(monkeypatch, tmp_path, qapp):
    """Create isolated frame data so layout checks never touch user frame storage."""
    data_root = tmp_path / "user-data"
    monkeypatch.setattr(config_module, "get_user_data_dir", lambda: str(data_root))

    from vietphotobooth.frames import frame_manager as frame_manager_module
    from vietphotobooth.frames.frame_manager import FrameManager
    from vietphotobooth.desktop.widgets.frame_designer_page import FrameDesignerPage

    monkeypatch.setattr(
        frame_manager_module,
        "get_user_data_dir",
        lambda: str(data_root),
    )

    def create(size: QSize) -> FrameDesignerPage:
        manager = FrameManager(
            base_dir=str(tmp_path / f"base-{size.width()}x{size.height()}"),
            user_dir=str(tmp_path / f"user-{size.width()}x{size.height()}"),
        )
        page = FrameDesignerPage(manager)
        page.resize(size)
        page.show()
        qapp.processEvents()
        return page

    return create


@pytest.mark.parametrize(
    ("size", "orientation"),
    [
        (QSize(1277, 752), QBoxLayout.LeftToRight),
        (QSize(1648, 928), QBoxLayout.LeftToRight),
        (QSize(1920, 1080), QBoxLayout.LeftToRight),
        (QSize(1024, 680), QBoxLayout.TopToBottom),
    ],
)
def test_frame_designer_reflows_without_clipping_controls(
    frame_designer_factory, size, orientation
):
    page = frame_designer_factory(size)

    assert page.main_layout.direction() == orientation
    assert page.canvas.isVisible()
    assert page.scroll_area.isVisible()

    content = page.scroll_area.widget()
    viewport = page.scroll_area.viewport()
    assert content.width() <= viewport.width()

    for row_name in (
        "default_font_row",
        "slot_selector_row",
        "text_layer_selector_row",
        "text_font_row",
        "logo_selector_row",
    ):
        row = content.findChild(QWidget, row_name)
        assert row is not None
        expected_row_direction = (
            QBoxLayout.TopToBottom
            if row.width() < 470
            else QBoxLayout.LeftToRight
        )
        assert row.layout().direction() == expected_row_direction, row_name

    # Every control must remain inside the content width because horizontal
    # scrolling is intentionally disabled for the properties panel.
    for widget in content.findChildren(QWidget):
        if not widget.isVisibleTo(content):
            continue
        left = widget.mapTo(content, QPoint(0, 0)).x()
        assert left >= 0, widget.objectName()
        assert left + widget.width() <= content.width(), (
            widget.objectName(),
            left,
            widget.width(),
            content.width(),
        )

    vertical_bar = page.scroll_area.verticalScrollBar()
    assert vertical_bar.maximum() > 0
    initial_scroll = vertical_bar.value()
    vertical_bar.setValue(min(vertical_bar.maximum(), initial_scroll + vertical_bar.pageStep()))
    QApplication.processEvents()
    assert vertical_bar.value() > initial_scroll

    page.close()


def test_frame_designer_keeps_editing_controls_and_canvas_space(frame_designer_factory):
    page = frame_designer_factory(QSize(1277, 752))

    assert page.canvas.width() >= 220
    assert page.combo_def_font.isVisibleTo(page.scroll_area.widget())
    assert page.spin_def_size.isVisibleTo(page.scroll_area.widget())
    assert page.btn_def_bold.isVisibleTo(page.scroll_area.widget())
    assert page.btn_def_italic.isVisibleTo(page.scroll_area.widget())
    assert page.btn_bg_color.isVisibleTo(page.scroll_area.widget())
    assert page.combo_slots_selector.isVisibleTo(page.scroll_area.widget())
    assert page.combo_text_selector.isVisibleTo(page.scroll_area.widget())
    assert page.btn_text_color.isVisibleTo(page.scroll_area.widget())

    page.close()


@pytest.mark.parametrize(
    ("size", "orientation"),
    [
        (QSize(1024, 680), QBoxLayout.TopToBottom),
        (QSize(1277, 752), QBoxLayout.LeftToRight),
        (QSize(1648, 928), QBoxLayout.LeftToRight),
        (QSize(1920, 1080), QBoxLayout.LeftToRight),
    ],
)
def test_main_window_frame_designer_panel_fits_and_reflows(
    monkeypatch, tmp_path, qapp, size, orientation
):
    """Exercise the real tab/stack ancestors that constrain production width."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    data_root = tmp_path / "frame-data"
    monkeypatch.setattr(config_module, "get_user_data_dir", lambda: str(data_root))

    from vietphotobooth.frames import frame_manager as frame_manager_module
    monkeypatch.setattr(frame_manager_module, "get_user_data_dir", lambda: str(data_root))
    from vietphotobooth.desktop.main_window import MainWindow

    window = MainWindow(start_in_kiosk=False)
    window.resize(QSize(1648, 928))
    window.show()
    window.tabs.setCurrentIndex(1)
    window.frame_page.stack.setCurrentIndex(1)
    qapp.processEvents()
    window.resize(size)
    qapp.processEvents()

    page = window.frame_page.designer_page
    assert page.main_layout.direction() == orientation
    content = page.scroll_area.widget()
    viewport = page.scroll_area.viewport()
    assert content.width() <= viewport.width(), (
        content.width(), viewport.width(), page.size().toTuple()
    )

    controls = (
        page.combo_def_font, page.spin_def_size, page.btn_def_bold,
        page.btn_def_italic, page.btn_bg_color, page.chk_slot_safe,
        page.combo_slots_selector, page.combo_text_selector,
        page.combo_font, page.spin_font_size, page.btn_text_color,
    )
    for control in controls:
        assert control.isVisibleTo(content), control.objectName()
        point = control.mapTo(content, QPoint(0, 0))
        assert point.x() >= 0
        assert point.x() + control.width() <= content.width(), (
            control.objectName(), point.x(), control.width(), content.width()
        )

    for widget in content.findChildren(QWidget):
        if not widget.isVisibleTo(content):
            continue
        point = widget.mapTo(content, QPoint(0, 0))
        assert point.x() >= 0 and point.x() + widget.width() <= content.width(), (
            type(widget).__name__, widget.objectName(), point.x(),
            widget.width(), content.width()
        )

    bar = page.scroll_area.verticalScrollBar()
    assert bar.maximum() > 0
    old_value = bar.value()
    bar.setValue(min(bar.maximum(), old_value + bar.pageStep()))
    qapp.processEvents()
    assert bar.value() > old_value

    window.close()
