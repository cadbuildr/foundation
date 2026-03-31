"""Command-line helpers for executing CADbuildr foundation code with feedback."""

import argparse
import base64
import json
import runpy
import sys
from typing import List, Optional


def _run_code(command: str, argv: List[str]) -> None:
    """Execute a Python command string in a __main__ namespace."""
    sys.argv = ["-c"] + argv
    namespace = {
        "__name__": "__main__",
        "__package__": None,
        "__cached__": None,
    }
    exec(compile(command, "<build-with-feedback>", "exec"), namespace)


def _run_file(filename: str, argv: List[str]) -> None:
    """Execute a Python script file in a __main__ namespace."""
    sys.argv = [filename] + argv
    runpy.run_path(filename, run_name="__main__")


def main(argv: List[str] | None = None) -> int:
    """Entry point for the build-with-feedback command."""
    utils_webrtc = None

    try:
        from cadbuildr.foundation.coms import utils_webrtc as webrtc_module

        utils_webrtc = webrtc_module
        if hasattr(utils_webrtc, "drain_recorded_request_ids"):
            utils_webrtc.drain_recorded_request_ids()
    except Exception as e:
        print(f"DEBUG: Failed to import feedback functions: {e}")
        # Feedback collection not available
        utils_webrtc = None

    parser = argparse.ArgumentParser(
        prog="build-with-feedback",
        description=(
            "Run CADbuildr foundation scripts with convenient helpers. "
            "Supports executing inline code (-c) or Python files."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-c",
        "--command",
        dest="command",
        help="Program passed in as a string (similar to python -c).",
    )
    group.add_argument(
        "script",
        nargs="?",
        help="Path to a Python script file to execute.",
    )
    parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to the executed command or script.",
    )
    parser.add_argument(
        "--no-feedback",
        action="store_true",
        help="Skip collecting and displaying build feedback.",
    )

    args = parser.parse_args(argv)

    if args.command is not None:
        _run_code(args.command, args.script_args)
    elif args.script is not None:
        _run_file(args.script, args.script_args)
    else:
        parser.print_usage()
        return 1

    if (
        not args.no_feedback
        and utils_webrtc
        and hasattr(utils_webrtc, "collect_and_display_feedback")
    ):
        from cadbuildr.foundation.coms.utils_webrtc import collect_and_display_feedback

        collect_and_display_feedback()
    return 0


def get_screenshot_main(argv: List[str] | None = None) -> int:
    """Entry point for the get-screenshot command."""
    parser = argparse.ArgumentParser(
        prog="get-screenshot",
        description="Get current viewer screenshot from broker.",
    )
    parser.add_argument(
        "--broker-url",
        help="Optional broker base URL (default: http://localhost:5050)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path (default: stdout). If provided, decodes base64 and saves as PNG.",
    )

    args = parser.parse_args(argv)

    try:
        # Request current viewer screenshot
        import requests

        broker_url = args.broker_url or "http://localhost:5050"

        # Request screenshot from viewer - broker will wait synchronously for response
        response = requests.post(
            f"{broker_url}/screenshot/request", json={}, timeout=15.0
        )

        if response.status_code != 200:
            error_data = (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {}
            )
            error_msg = error_data.get("message", f"HTTP {response.status_code}")
            print(f"Error: {error_msg}")
            return 1

        data = response.json()
        screenshot_data = data.get("data_url")

        if not screenshot_data:
            print("Error: No screenshot data_url in response")
            return 1

        if screenshot_data:
            if args.output:
                # Decode base64 data URL and save to file
                if screenshot_data.startswith("data:image"):
                    # Extract base64 part: data:image/png;base64,<data>
                    base64_data = screenshot_data.split(",", 1)[1]
                    image_data = base64.b64decode(base64_data)
                    with open(args.output, "wb") as f:
                        f.write(image_data)
                    print(f"Screenshot saved to {args.output}")
                else:
                    # Assume it's already base64
                    image_data = base64.b64decode(screenshot_data)
                    with open(args.output, "wb") as f:
                        f.write(image_data)
                    print(f"Screenshot saved to {args.output}")
            else:
                # Output data URL to stdout for piping
                print(screenshot_data)
            return 0
        else:
            return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
