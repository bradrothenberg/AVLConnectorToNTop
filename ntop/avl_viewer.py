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
import subprocess
import sys
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
        default=0.0,
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
        geometry_process = subprocess.Popen(
            launch_cmd,
            cwd=orchestrator.working_directory,
            stdin=subprocess.PIPE,
            text=True,
        )

        # Launch Trefftz plot instance
        LOGGER.debug("Launching Trefftz AVL instance: %s", launch_cmd)
        trefftz_process = subprocess.Popen(
            launch_cmd,
            cwd=orchestrator.working_directory,
            stdin=subprocess.PIPE,
            text=True,
        )

        # Start window management for both processes
        avl_window_control.manage_windows_async(
            geometry_pid=geometry_process.pid,
            trefftz_pid=trefftz_process.pid,
        )

        # Send commands to geometry process
        if geometry_process.stdin and orchestrator.geometry_command_input:
            geometry_process.stdin.write(orchestrator.geometry_command_input)
            geometry_process.stdin.flush()
            geometry_process.stdin.close()

        # Send commands to Trefftz process
        if trefftz_process.stdin and orchestrator.trefftz_command_input:
            trefftz_process.stdin.write(orchestrator.trefftz_command_input)
            trefftz_process.stdin.flush()
            trefftz_process.stdin.close()

        LOGGER.info(
            "Both AVL instances launched. Geometry PID: %s, Trefftz PID: %s",
            geometry_process.pid,
            trefftz_process.pid,
        )
        LOGGER.info("Windows will remain open for viewing. Close manually when done.")

        # Don't wait for processes to exit - they stay open for viewing
        # The processes will remain running until the user closes the windows

    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Failed to launch AVL viewer: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

