import pytest
from unittest.mock import MagicMock
from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog


@pytest.fixture
def headless_dialog(monkeypatch):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)
    cfg = AppConfig.load()
    dlg = WallpaperSelectorDialog(cfg)
    dlg.root = MagicMock()
    dlg.attrib_lbl = MagicMock()
    dlg.status_lbl = MagicMock()
    dlg.scroll_container = MagicMock()
    return dlg


def test_window_configure_debounces_rapid_resize_events(headless_dialog):
    """Verify that rapid window resize events cancel prior timers and debounce layout recalculation."""
    dlg = headless_dialog
    
    cancelled_ids = []
    timer_counter = [0]

    def mock_after(delay, cb):
        timer_counter[0] += 1
        return f"timer_{timer_counter[0]}"

    dlg.root.after = MagicMock(side_effect=mock_after)
    dlg.root.after_cancel = MagicMock(side_effect=lambda timer_id: cancelled_ids.append(timer_id))
    
    # Simulate first resize event
    event1 = MagicMock()
    event1.widget = dlg.root
    event1.width = 720
    event1.height = 800
    
    dlg._on_window_configure(event1)
    timer1 = dlg._resize_debounce_timer
    assert timer1 is not None
    assert dlg._last_conf_w == 720
    assert dlg._last_conf_h == 800

    # Simulate second resize event 10ms later
    event2 = MagicMock()
    event2.widget = dlg.root
    event2.width = 740
    event2.height = 800
    
    dlg._on_window_configure(event2)
    timer2 = dlg._resize_debounce_timer
    assert timer2 is not None
    assert timer1 in cancelled_ids
    assert dlg._last_conf_w == 740

    # Identical dimensions should be ignored
    dlg._on_window_configure(event2)
    assert dlg._resize_debounce_timer == timer2

    dlg.cleanup()


def test_apply_debounced_resize_layout_updates_wraplength_and_canvas(headless_dialog):
    """Verify that applying debounced layout updates text wraplength and canvas fitting."""
    dlg = headless_dialog

    dlg.root.winfo_width = MagicMock(return_value=800)
    dlg._apply_debounced_canvas_fit = MagicMock()

    dlg._apply_debounced_resize_layout()

    # Wrap should be max(380, 800 - 70) = 730
    assert dlg._last_applied_wrap == 730
    dlg.attrib_lbl.configure.assert_called_with(wraplength=730)
    dlg.status_lbl.configure.assert_called_with(wraplength=730)
    dlg._apply_debounced_canvas_fit.assert_called_once()

    dlg.cleanup()


def test_scrollable_canvas_configure_debounces_fit(headless_dialog):
    """Verify that scrollable canvas configure events debounce inner frame itemconfigure."""
    dlg = headless_dialog

    cancelled_fit_ids = []
    timer_counter = [0]

    def mock_after(delay, cb):
        timer_counter[0] += 1
        return f"fit_timer_{timer_counter[0]}"

    dlg.root.after = MagicMock(side_effect=mock_after)
    dlg.root.after_cancel = MagicMock(side_effect=lambda timer_id: cancelled_fit_ids.append(timer_id))

    event1 = MagicMock()
    dlg._on_scrollable_canvas_configure(event1)
    fit_timer1 = dlg._canvas_fit_timer
    assert fit_timer1 is not None

    event2 = MagicMock()
    dlg._on_scrollable_canvas_configure(event2)
    fit_timer2 = dlg._canvas_fit_timer
    assert fit_timer2 is not None
    assert fit_timer1 in cancelled_fit_ids

    dlg.cleanup()


def test_apply_debounced_canvas_fit_invokes_itemconfigure(headless_dialog):
    """Verify that _apply_debounced_canvas_fit updates the inner window width on the parent canvas."""
    dlg = headless_dialog
    mock_canvas = MagicMock()
    mock_canvas.winfo_width.return_value = 650
    mock_canvas.bbox.return_value = (0, 0, 650, 1200)

    dlg.scroll_container._parent_canvas = mock_canvas
    dlg.scroll_container._create_window_id = 999

    dlg._apply_debounced_canvas_fit()

    mock_canvas.itemconfigure.assert_called_once_with(999, width=650)
    mock_canvas.configure.assert_called_once_with(scrollregion=(0, 0, 650, 1200))


def test_cleanup_cancels_all_active_resize_timers(headless_dialog):
    """Verify that cleanup cancels both resize debounce and canvas fit timers safely."""
    dlg = headless_dialog

    dlg._resize_debounce_timer = "timer_resize_123"
    dlg._canvas_fit_timer = "timer_canvas_456"

    cancelled = []
    dlg.root.after_cancel = MagicMock(side_effect=lambda t: cancelled.append(t))

    dlg.cleanup()

    assert "timer_resize_123" in cancelled
    assert "timer_canvas_456" in cancelled
    assert dlg._resize_debounce_timer is None
    assert dlg._canvas_fit_timer is None
