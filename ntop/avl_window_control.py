"""
Utilities for positioning AVL graphics windows on Microsoft Windows.

This module provides a thin wrapper around the Win32 APIs (via ctypes) to
detect the graphics windows spawned by AVL and reposition them on the right
half of the user's screen.  The objective is to display the geometry plot on
the left portion of the right half, and the Trefftz plot on the rightmost
quarter of the screen.

The implementation favours a best-effort approach: it continuously monitors
for windows belonging to the AVL process for a limited amount of time and
repositions any qualifying windows as they appear.  If the platform is not
Windows, the module falls back to a no-op behaviour.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

LOGGER = logging.getLogger("avl_viewer.window_control")

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )


@dataclass(frozen=True)
class WindowPlacement:
    """Represents a window rectangle."""

    left: int
    top: int
    width: int
    height: int


def manage_windows_async(
    pid: Optional[int],
    timeout: float = 60.0,
    poll_interval: float = 0.5,
) -> None:
    """
    Start a background watcher that repositions AVL graphics windows.

    Args:
        pid: Process ID of the running AVL instance. If None or if running on
             non-Windows platforms, the function becomes a no-op.
        timeout: Maximum time (in seconds) spent searching for the windows.
        poll_interval: Interval (in seconds) between window enumerations.
    """
    if not IS_WINDOWS:
        LOGGER.info("Window management is only supported on Windows; skipping.")
        return

    if pid is None:
        LOGGER.warning("No process ID provided; unable to manage AVL windows.")
        return

    watcher = _WindowWatcher(
        pid=pid,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    watcher.start()


class _WindowWatcher(threading.Thread):
    """Background thread that tracks and repositions AVL plot windows."""

    def __init__(
        self,
        pid: int,
        timeout: float,
        poll_interval: float,
    ) -> None:
        super().__init__(daemon=True, name="AVLWindowWatcher")
        self._pid = pid
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._handled_windows: Set[int] = set()

    def run(self) -> None:  # pragma: no cover - involves GUI interaction
        LOGGER.debug("Starting AVL window watcher for PID %s", self._pid)
        deadline = time.time() + self._timeout

        geometry_rect, trefftz_rect = _compute_target_rectangles()
        LOGGER.debug(
            "Target rectangles - geometry: %s, trefftz: %s",
            geometry_rect,
            trefftz_rect,
        )

        while time.time() < deadline:
            hwnds = _collect_process_windows(self._pid)
            if not hwnds:
                time.sleep(self._poll_interval)
                continue

            for hwnd in hwnds:
                if hwnd in self._handled_windows:
                    continue

                target_rect = None
                if len(self._handled_windows) == 0:
                    target_rect = geometry_rect
                elif len(self._handled_windows) == 1:
                    target_rect = trefftz_rect

                if target_rect is None:
                    # Additional windows (e.g., text console) are ignored.
                    self._handled_windows.add(hwnd)
                    continue

                if _move_window(hwnd, target_rect):
                    LOGGER.info(
                        "Positioned window %s at %s", hex(hwnd), target_rect
                    )
                else:
                    LOGGER.warning(
                        "Failed to move window %s to %s", hex(hwnd), target_rect
                    )
                self._handled_windows.add(hwnd)

            if len(self._handled_windows) >= 2:
                LOGGER.debug("Both AVL windows have been positioned.")
                return

            time.sleep(self._poll_interval)

        LOGGER.warning(
            "Timed out (%ss) while waiting for AVL windows to appear.",
            self._timeout,
        )


def _compute_target_rectangles() -> Tuple[WindowPlacement, WindowPlacement]:
    """Compute target rectangles for the geometry and Trefftz windows."""
    if not IS_WINDOWS:
        raise RuntimeError("Window placement calculations require Windows APIs.")

    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)

    right_half_left = screen_width // 2
    right_half_width = screen_width - right_half_left
    mid_point = right_half_left + right_half_width // 2

    geometry_rect = WindowPlacement(
        left=right_half_left,
        top=0,
        width=mid_point - right_half_left,
        height=screen_height,
    )
    trefftz_rect = WindowPlacement(
        left=mid_point,
        top=0,
        width=screen_width - mid_point,
        height=screen_height,
    )

    return geometry_rect, trefftz_rect


def _collect_process_windows(pid: int) -> List[int]:
    """Enumerate visible top-level windows owned by the specified process."""
    hwnds: List[int] = []

    @EnumWindowsProc
    def enum_proc(hwnd: int, lparam: int) -> bool:  # pylint: disable=unused-argument
        if not user32.IsWindowVisible(hwnd):
            return True

        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value != pid:
            return True

        title = _get_window_text(hwnd)
        if not title:
            return True

        hwnds.append(hwnd)
        return True

    if not user32.EnumWindows(enum_proc, 0):
        LOGGER.debug("EnumWindows returned FALSE (error=%s)", ctypes.get_last_error())

    return hwnds


def _get_window_text(hwnd: int) -> str:
    """Return the Unicode window title."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip()


def _move_window(hwnd: int, rect: WindowPlacement) -> bool:
    """Move the window to the specified rectangle."""
    success = user32.MoveWindow(
        hwnd,
        rect.left,
        rect.top,
        rect.width,
        rect.height,
        True,
    )
    if not success:
        LOGGER.debug(
            "MoveWindow failed (hwnd=%s, error=%s)",
            hex(hwnd),
            ctypes.get_last_error(),
        )
    return bool(success)


__all__ = [
    "manage_windows_async",
]

