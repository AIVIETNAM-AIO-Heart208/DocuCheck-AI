"""Locale-independent JSON-line protocol. Never drops/replaces receipt text."""

import json
import sys


def message_line(payload: dict) -> str:
    # ASCII is also valid UTF-8: even a redirected Windows CP1252 stream can
    # transport the frame unchanged. json.loads restores the exact Unicode text.
    return json.dumps(payload, ensure_ascii=True, allow_nan=False) + "\n"


def worker_environment(env: dict) -> dict:
    return {**env, "PYTHONUTF8":"1", "PYTHONIOENCODING":"utf-8", "PYTHONUNBUFFERED":"1"}


def configure_stdio() -> None:
    for stream in (sys.stdin, sys.stdout):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="strict")
    reconfigure = getattr(sys.stderr, "reconfigure", None)
    if reconfigure:
        # Tracebacks must remain printable even for a malformed external path.
        reconfigure(encoding="utf-8", errors="backslashreplace")
