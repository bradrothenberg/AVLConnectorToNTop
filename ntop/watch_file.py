#!/usr/bin/env python3

import argparse
import os
import sys
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a file and exit when it changes."
    )
    parser.add_argument(
        "path",
        help="Path to the file to watch.",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=0.5,
        help="Polling interval in seconds (default: 0.5).",
    )
    return parser.parse_args()


def get_mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return None


def main() -> int:
    args = parse_args()
    path = os.path.abspath(args.path)

    if not os.path.exists(path):
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    baseline_mtime = get_mtime(path)

    try:
        while True:
            current_mtime = get_mtime(path)
            if current_mtime != baseline_mtime:
                print("True")
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        # Exit gracefully when interrupted.
        return 130


if __name__ == "__main__":
    sys.exit(main())

