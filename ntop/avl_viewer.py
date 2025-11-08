#!/usr/bin/env python3
"""
AVL Viewer Application for nTop Integration
===========================================

This script provides a command-line entry point that can be launched from the
nTop command line. It orchestrates the generation (or loading) of AVL geometry,
creates run cases, executes AVL, and positions the resulting graphics windows
so that the geometry and Trefftz plots appear on the right half of the user's
screen.

The application is split into a few helper modules:

* avl_window_control.py  - Platform-specific window management utilities.
* avl_viewer_commands.py - Builders for AVL command scripts and helpers that
                           interact with AVL command sequences.

The high-level flow is:
1. Parse command-line arguments.
2. Ensure an AVL geometry file exists (regenerating from nTop CSV data if
   necessary).
3. Generate the AVL run file and command script for the requested operating
   condition(s).
4. Launch AVL, piping in the generated command script.
5. Monitor the AVL graphics windows and reposition them according to the user's
   preferences (geometry plot on left side of the right-half screen, Trefftz
   plot on the right side).

This module focuses on the orchestration responsibilities and keeps the logic
for command sequence generation and window placement in the dedicated helper
modules so they can be tested independently.
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional


try:
    import avl_window_control
    import avl_viewer_commands
except ImportError:
    # When running inside the repository root, the modules will live next to
    # this file. Ensure the parent directory is on sys.path before retrying.
    CURRENT_FILE = Path(__file__).resolve()
    PARENT_DIR = CURRENT_FILE.parent
    if str(PARENT_DIR) not in sys.path:
        sys.path.insert(0, str(PARENT_DIR))
    import avl_window_control  # type: ignore  # noqa: E402
    import avl_viewer_commands  # type: ignore  # noqa: E402


LOGGER = logging.getLogger("avl_viewer")
NEUTRAL_POINT_PATTERN = re.compile(
    r"Neutral point\s*(?::\s*)?(?:Xnp|x/c)\s*=\s*([-+0-9.eE]+)"
)


def capture_and_save_neutral_point(
    stability_file: Path,
    summary_file: Path,
    timeout: float = 10.0,
) -> Optional[float]:
    """Wait for AVL to write the stability file, extract the neutral point, and save it."""
    deadline = time.time() + timeout
    last_exception: Optional[Exception] = None

    while time.time() < deadline:
        if stability_file.exists():
            try:
                text = stability_file.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                last_exception = exc
                time.sleep(0.2)
                continue

            match = NEUTRAL_POINT_PATTERN.search(text)
            if match is not None:
                try:
                    neutral_value = float(match.group(1))
                except ValueError as exc:  # pragma: no cover - defensive
                    last_exception = exc
                    time.sleep(0.2)
                    continue

                try:
                    summary_file.write_text(
                        f"Xnp\n{neutral_value:.6f}\n",
                        encoding="utf-8",
                    )
                except OSError as exc:  # pragma: no cover - defensive
                    LOGGER.warning(
                        "Failed to write neutral point summary %s: %s",
                        summary_file,
                        exc,
                    )
                else:
                    LOGGER.info(
                        "Neutral point %.6f saved to %s",
                        neutral_value,
                        summary_file,
                    )
                return neutral_value

        time.sleep(0.2)

    if last_exception is not None:
        LOGGER.debug(
            "Encountered error while waiting for stability file %s: %s",
            stability_file,
            last_exception,
        )
    LOGGER.warning(
        "Timed out after %.1fs waiting for neutral point in %s",
        timeout,
        stability_file,
    )
    return None


def schedule_neutral_point_capture(
    stability_file: Optional[Path],
    summary_file: Optional[Path],
) -> Optional[threading.Thread]:
    """Launch a background task to capture the neutral point without blocking."""
    if stability_file is None or summary_file is None:
        return None

    thread = threading.Thread(
        target=capture_and_save_neutral_point,
        args=(stability_file, summary_file),
        kwargs={"timeout": 10.0},
        name="NeutralPointCapture",
    )
    thread.daemon = True
    thread.start()
    return thread


def parse_arguments(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments for the AVL viewer application."""
    parser = argparse.ArgumentParser(
        description="Launch AVL with geometry + Trefftz plots positioned on the right half of the screen.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--le",
        type=Path,
        help="CSV file containing leading edge points exported from nTop.",
    )
    parser.add_argument(
        "--te",
        type=Path,
        help="CSV file containing trailing edge points exported from nTop.",
    )
    parser.add_argument(
        "--avl",
        type=Path,
        help="Existing AVL geometry file to use instead of regenerating from CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory where generated AVL/run/command files will be stored.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=3.0,
        help="Angle of attack (degrees) for the initial operating point.",
    )
    parser.add_argument(
        "--mach",
        type=float,
        default=0.75,
        help="Mach number for the initial operating point.",
    )
    parser.add_argument(
        "--avl-exe",
        type=Path,
        help="Path to AVL executable (if not specified, the script will attempt to auto-detect).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging verbosity.",
    )

    args = parser.parse_args(argv)
    args.output_dir = args.output_dir.resolve()
    if args.avl is not None:
        args.avl = args.avl.resolve()
    if args.le is not None:
        args.le = args.le.resolve()
    if args.te is not None:
        args.te = args.te.resolve()
    if args.avl_exe is not None:
        args.avl_exe = args.avl_exe.resolve()
    return args


def ensure_logging(level: str) -> None:
    """Configure logging according to the requested verbosity."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for the AVL viewer application."""
    args = parse_arguments(argv)
    ensure_logging(args.log_level)

    try:
        orchestrator = avl_viewer_commands.AVLViewerOrchestrator(
            le_csv=args.le,
            te_csv=args.te,
            avl_geometry=args.avl,
            output_dir=args.output_dir,
            alpha=args.alpha,
            mach=args.mach,
            avl_executable=args.avl_exe,
        )
        orchestrator.prepare()

        LOGGER.info("Launching dual AVL instances for geometry and Trefftz plots")
        launch_cmd = orchestrator.build_avl_launch_command(orchestrator.geometry_command_script)

        # Launch geometry plot instance
        LOGGER.debug("Launching geometry AVL instance: %s", launch_cmd)
        try:
            geometry_process = subprocess.Popen(
                launch_cmd,
                cwd=orchestrator.working_directory,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to launch geometry AVL instance: {exc}") from exc

        # Launch Trefftz plot instance
        LOGGER.debug("Launching Trefftz AVL instance: %s", launch_cmd)
        try:
            trefftz_process = subprocess.Popen(
                launch_cmd,
                cwd=orchestrator.working_directory,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception as exc:
            # Clean up geometry process if Trefftz fails
            try:
                geometry_process.terminate()
            except Exception:
                pass
            raise RuntimeError(f"Failed to launch Trefftz AVL instance: {exc}") from exc

        # Start window management for both processes
        watcher = avl_window_control.manage_windows_async(
            geometry_pid=geometry_process.pid,
            trefftz_pid=trefftz_process.pid,
        )

        # Send commands to geometry process
        try:
            if geometry_process.stdin and orchestrator.geometry_command_input:
                geometry_process.stdin.write(orchestrator.geometry_command_input)
                geometry_process.stdin.flush()
        except Exception as exc:
            LOGGER.warning("Failed to send commands to geometry process: %s", exc)

        # Send commands to Trefftz process
        try:
            if trefftz_process.stdin and orchestrator.trefftz_command_input:
                trefftz_process.stdin.write(orchestrator.trefftz_command_input)
                trefftz_process.stdin.flush()
        except Exception as exc:
            LOGGER.warning("Failed to send commands to Trefftz process: %s", exc)

        LOGGER.info(
            "Both AVL instances launched. Geometry PID: %s, Trefftz PID: %s",
            geometry_process.pid,
            trefftz_process.pid,
        )
        LOGGER.info("Windows will remain open for viewing. Close manually when done.")

        if watcher is not None:
            watcher_timeout = 5.0
            deadline = time.time() + watcher_timeout

            while time.time() < deadline:
                if watcher.is_alive():
                    time.sleep(0.1)
                else:
                    LOGGER.debug("AVL windows positioned before refresh commands are sent.")
                    break
            else:
                LOGGER.warning(
                    "Window positioning thread still running after %.1fs; proceeding",
                    watcher_timeout,
                )

        # Allow time for window manager to reposition windows before refreshing plots
        time.sleep(1.0)

        geometry_refresh_commands = "\n\n" + "\n".join([
            "",
            "OPER",
            "G",
            "V",
            "-90 -90",
            "X",
            "C",
            "",
        ]) + "\n"
        trefftz_refresh_commands = "\nOPER\nT\nX\nS\n6.5\n\n"

        # geometry_refresh_commands expects us to be in OPER. send full sequence
        try:
            if geometry_process.stdin:
                geometry_process.stdin.write(geometry_refresh_commands)
                geometry_process.stdin.flush()
        except Exception as exc:
            LOGGER.warning("Failed to refresh geometry plot after resize: %s", exc)

        time.sleep(0.3)

        try:
            if trefftz_process.stdin:
                trefftz_process.stdin.write(trefftz_refresh_commands)
                trefftz_process.stdin.flush()
        except Exception as exc:
            LOGGER.warning("Failed to refresh Trefftz plot after resize: %s", exc)

        # Give processes time to initialize and open windows
        # Check that processes are still running after a brief delay
        time.sleep(3.0)

        # Verify processes are still alive
        geometry_alive = geometry_process.poll() is None
        trefftz_alive = trefftz_process.poll() is None

        if not geometry_alive:
            return_code = geometry_process.returncode
            LOGGER.error(
                "Geometry AVL process exited unexpectedly with code %s", return_code
            )
            raise RuntimeError(f"Geometry AVL process crashed with exit code {return_code}")

        if not trefftz_alive:
            return_code = trefftz_process.returncode
            LOGGER.error(
                "Trefftz AVL process exited unexpectedly with code %s", return_code
            )
            raise RuntimeError(f"Trefftz AVL process crashed with exit code {return_code}")

        LOGGER.info("Both AVL processes are running successfully.")

        capture_thread = schedule_neutral_point_capture(
            orchestrator.stability_file,
            orchestrator.neutral_point_summary,
        )

        LOGGER.info("Waiting for AVL windows to be closed (Ctrl+C to abort)...")
        try:
            geometry_return = geometry_process.wait()
            LOGGER.info(
                "Geometry AVL process exited with code %s", geometry_return
            )
        except KeyboardInterrupt:
            LOGGER.info("Keyboard interrupt received; terminating AVL processes...")
            geometry_process.terminate()
            trefftz_process.terminate()
            raise

        if trefftz_process.poll() is None:
            try:
                trefftz_return = trefftz_process.wait()
                LOGGER.info(
                    "Trefftz AVL process exited with code %s", trefftz_return
                )
            except KeyboardInterrupt:
                LOGGER.info(
                    "Keyboard interrupt received while waiting for Trefftz process; terminating..."
                )
                trefftz_process.terminate()
                raise
        else:
            trefftz_return = trefftz_process.returncode
            LOGGER.info(
                "Trefftz AVL process exited earlier with code %s", trefftz_return
            )

        if capture_thread is not None:
            capture_thread.join(timeout=1.0)

        if geometry_return not in (0, None):
            raise RuntimeError(
                f"Geometry AVL process exited with non-zero status {geometry_return}"
            )
        if trefftz_return not in (0, None):
            raise RuntimeError(
                f"Trefftz AVL process exited with non-zero status {trefftz_return}"
            )

    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Failed to launch AVL viewer: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

