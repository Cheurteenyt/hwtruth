"""Minimal client for the LACT daemon's unix socket.

Same request grammar as the LACT GUI/CLI (verified against LACT 0.10.1):
one JSON line per request. This is how hwtruth applies and restores fan
curves and clock offsets without the GUI — including its Revert button,
which does not work on all versions.
"""
import json
import socket

SOCKET_PATH = "/run/lactd.sock"


class LactError(RuntimeError):
    pass


def request(command, args=None, timeout=10):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(timeout)
        sock.connect(SOCKET_PATH)
        with sock.makefile("rwb") as stream:
            stream.write((json.dumps({"command": command, "args": args}) + "\n").encode())
            stream.flush()
            response = json.loads(stream.readline())
    if response.get("status") != "ok":
        raise LactError(response)
    return response.get("data")
