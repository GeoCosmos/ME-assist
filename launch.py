"""Double-click launcher used by start.bat / start.command.

Picks a free port, opens the browser, and runs the server bound to localhost
only. Kept in Python so the Windows and macOS launchers stay thin and identical
in behaviour.
"""

import socket
import sys
import threading
import webbrowser

import uvicorn

DEFAULT_PORT = 8000
PORT_ATTEMPTS = 20


def find_free_port(start: int = DEFAULT_PORT, attempts: int = PORT_ATTEMPTS) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(
        f"Could not find a free port between {start} and {start + attempts - 1}."
    )


def main() -> None:
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    print()
    print("  ME ASSISTANT")
    print(f"  Running at {url}")
    print("  Close this window (or press Ctrl+C) to stop the server.")
    if port != DEFAULT_PORT:
        print(f"  Note: port {DEFAULT_PORT} was busy, using {port} instead.")
    print()

    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    try:
        # Bound to localhost on purpose: the settings page can write API keys,
        # so the server must not be reachable from the rest of the network.
        uvicorn.run("main:app", host="127.0.0.1", port=port, log_level="warning")
    except KeyboardInterrupt:
        print("\n  Stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
