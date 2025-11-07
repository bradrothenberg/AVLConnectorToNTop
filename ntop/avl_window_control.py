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
    geometry_pid: Optional[int] = None,
    trefftz_pid: Optional[int] = None,
    pid: Optional[int] = None,
    timeout: float = 60.0,
    poll_interval: float = 0.5,
) -> None:
    """
    Start a background watcher that repositions AVL graphics windows.

    Args:
        geometry_pid: Process ID of the AVL instance showing geometry plot.
        trefftz_pid: Process ID of the AVL instance showing Trefftz plot.
        pid: Legacy parameter for single-process mode (deprecated, use
             geometry_pid/trefftz_pid instead).
        timeout: Maximum time (in seconds) spent searching for the windows.
        poll_interval: Interval (in seconds) between window enumerations.
    """
    if not IS_WINDOWS:
        LOGGER.info("Window management is only supported on Windows; skipping.")
        return

    # Support legacy single-PID mode for backward compatibility
    if pid is not None:
        if geometry_pid is not None or trefftz_pid is not None:
            LOGGER.warning(
                "Both 'pid' and geometry_pid/trefftz_pid provided. Using geometry_pid/trefftz_pid."
            )
        else:
            geometry_pid = pid

    if geometry_pid is None and trefftz_pid is None:
        LOGGER.warning("No process IDs provided; unable to manage AVL windows.")
        return

    watcher = _WindowWatcher(
        geometry_pid=geometry_pid,
        trefftz_pid=trefftz_pid,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    watcher.start()


class _WindowWatcher(threading.Thread):
    """Background thread that tracks and repositions AVL plot windows."""

    def __init__(
        self,
        geometry_pid: Optional[int],
        trefftz_pid: Optional[int],
        timeout: float,
        poll_interval: float,
    ) -> None:
        super().__init__(daemon=True, name="AVLWindowWatcher")
        self._geometry_pid = geometry_pid
        self._trefftz_pid = trefftz_pid
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._geometry_window: Optional[int] = None
        self._trefftz_window: Optional[int] = None

    def run(self) -> None:  # pragma: no cover - involves GUI interaction
        LOGGER.debug(
            "Starting AVL window watcher - Geometry PID: %s, Trefftz PID: %s",
            self._geometry_pid,
            self._trefftz_pid,
        )
        deadline = time.time() + self._timeout

        geometry_rect, trefftz_rect = _compute_target_rectangles()
        LOGGER.debug(
            "Target rectangles - geometry: %s, trefftz: %s",
            geometry_rect,
            trefftz_rect,
        )

        while time.time() < deadline:
            # Collect windows from geometry process
            if self._geometry_pid is not None and self._geometry_window is None:
                geometry_hwnds = _collect_process_windows(self._geometry_pid)
                if geometry_hwnds:
                    # Use the first graphics window found
                    for hwnd in geometry_hwnds:
                        if _move_window(hwnd, geometry_rect):
                            self._geometry_window = hwnd
                            LOGGER.info(
                                "Positioned geometry window %s (PID %s) at %s",
                                hex(hwnd),
                                self._geometry_pid,
                                geometry_rect,
                            )
                            break

            # Collect windows from Trefftz process
            if self._trefftz_pid is not None and self._trefftz_window is None:
                trefftz_hwnds = _collect_process_windows(self._trefftz_pid)
                if trefftz_hwnds:
                    # Use the first graphics window found
                    for hwnd in trefftz_hwnds:
                        if _move_window(hwnd, trefftz_rect):
                            self._trefftz_window = hwnd
                            LOGGER.info(
                                "Positioned Trefftz window %s (PID %s) at %s",
                                hex(hwnd),
                                self._trefftz_pid,
                                trefftz_rect,
                            )
                            break

            # Check if both windows are positioned
            geometry_done = self._geometry_pid is None or self._geometry_window is not None
            trefftz_done = self._trefftz_pid is None or self._trefftz_window is not None

            if geometry_done and trefftz_done:
                LOGGER.debug("All AVL windows have been positioned.")
                return

            time.sleep(self._poll_interval)

        if self._geometry_window is None and self._geometry_pid is not None:
            LOGGER.warning(
                "Timed out (%ss) while waiting for geometry window (PID %s) to appear.",
                self._timeout,
                self._geometry_pid,
            )
        if self._trefftz_window is None and self._trefftz_pid is not None:
            LOGGER.warning(
                "Timed out (%ss) while waiting for Trefftz window (PID %s) to appear.",
                self._timeout,
                self._trefftz_pid,
            )


def _compute_target_rectangles() -> Tuple[WindowPlacement, WindowPlacement]:
    """Compute target rectangles for the geometry and Trefftz windows."""
    if not IS_WINDOWS:
        raise RuntimeError("Window placement calculations require Windows APIs.")

    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)

    right_half_left = screen_width // 2
    right_half_width = screen_width - right_half_left
    half_height = screen_height // 2

    geometry_rect = WindowPlacement(
        left=right_half_left,
        top=0,
        width=right_half_width,
        height=half_height,
    )
    trefftz_rect = WindowPlacement(
        left=right_half_left,
        top=half_height,
        width=right_half_width,
        height=screen_height - half_height,
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

