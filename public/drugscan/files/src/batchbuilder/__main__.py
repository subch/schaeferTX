"""Launcher.

Starts a small web server bound to the loopback address and opens the browser at
it. Nothing listens on the network interface, so no firewall rule or hosting is
involved: the analyst double-clicks the executable and gets a local page.

Nothing here is allowed to block or abort startup on account of Apollo. The
database lives on the lab network; the application must still come up on a
machine that cannot reach it, so a plate file can be loaded, checked and
inspected regardless.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

from . import APP_NAME, __version__
from .apollo import HealthProbe, RecordedApolloClient, SqlServerApolloClient
from .config import load
from .models import PbiSample, QcRecord

HOST = "127.0.0.1"

#: How long to wait for the server to start accepting before giving up on
#: opening a browser. The server itself keeps running either way.
BROWSER_WAIT_SECONDS = 20.0


def find_port(preferred: int = 0) -> int:
    """Reserve a port, preferring the configured one.

    Binding and immediately closing leaves a small window in which something
    else could take the port, which matters more on a machine running Docker.
    A failed handover is retried rather than crashing.
    """
    candidates = [preferred] if preferred else []
    candidates.append(0)
    last_error: OSError | None = None
    for candidate in candidates:
        for _ in range(5):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((HOST, candidate))
                    chosen = s.getsockname()[1]
                if preferred and candidate == 0:
                    print(f"[{APP_NAME}] Port {preferred} is in use; "
                          f"listening on {chosen} instead.", file=sys.stderr)
                return chosen
            except OSError as exc:
                last_error = exc
    raise OSError(
        f"Could not reserve a local port on {HOST}. On Windows, Docker and "
        f"Hyper-V reserve blocks of ports; run "
        f"'netsh interface ipv4 show excludedportrange protocol=tcp' to see "
        f"them, then choose a port outside those ranges with --port. ({last_error})"
    )


def wait_until_accepting(port: int, timeout: float) -> bool:
    """Poll until the server actually accepts a connection."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def open_browser_when_ready(url: str, port: int) -> None:
    """Open the browser only once there is something to open.

    Opening it eagerly is what turns any startup delay into a browser tab
    spinning against a port nothing is listening on.
    """
    if wait_until_accepting(port, BROWSER_WAIT_SECONDS):
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"[{APP_NAME}] Could not open a browser ({exc}). "
                  f"Open {url} manually.", file=sys.stderr)
    else:
        print(f"[{APP_NAME}] Server did not start within "
              f"{BROWSER_WAIT_SECONDS:.0f}s. Open {url} manually once it does.",
              file=sys.stderr)


def demo_client(path: Path):
    """Replay recorded Apollo results so the UI can run off the lab network."""
    data = json.loads(Path(path).read_text())
    return RecordedApolloClient(
        valid_mbns=data["valid_mbns"],
        pbi=[PbiSample(*row) for row in data["pbi"]],
        qc={mbn: [QcRecord(*row) for row in rows]
            for mbn, rows in data["qc_data"].items()},
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="batchbuilder", description=APP_NAME)
    parser.add_argument("--port", type=int, default=None,
                        help="port to listen on (default: pick a free one)")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser window")
    parser.add_argument("--config", type=Path, default=None,
                        help="path to batchbuilder.json")
    parser.add_argument("--demo", type=Path, metavar="FIXTURE.json",
                        help="run against recorded Apollo results instead of "
                             "the live database (for testing off-network)")
    parser.add_argument("--version", action="version",
                        version=f"{APP_NAME} {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load(args.config)

    if args.demo:
        apollo = demo_client(args.demo)
        print(f"[{APP_NAME}] DEMO MODE - using recorded data from {args.demo}")
    else:
        apollo = SqlServerApolloClient(
            server=config.apollo.server,
            database=config.apollo.database,
            uid=config.apollo.uid,
            pwd=config.apollo.pwd,
            driver=config.apollo.driver,
            timeout=config.apollo.timeout,
        )

    # Probed on a background thread. Reaching an unreachable database can take
    # minutes, and the application must not wait for it: the page reports the
    # connection state itself, and plate files can be loaded without it.
    health = HealthProbe(apollo)
    health.start(force=True)

    from .webapp import create_app  # imported late so --version stays instant

    app = create_app(config, apollo, health=health)
    port = find_port(args.port or config.port or 0)
    url = f"http://{HOST}:{port}/"

    if config.load_error:
        print(f"[{APP_NAME}] {config.load_error}", file=sys.stderr)

    print(f"[{APP_NAME}] v{__version__} listening on {url}")
    print(f"[{APP_NAME}] Apollo: {getattr(apollo, 'description', 'Apollo')} "
          f"(checking in the background)")
    print(f"[{APP_NAME}] Close this window to stop.")

    if not args.no_browser and config.open_browser:
        threading.Thread(target=open_browser_when_ready, args=(url, port),
                         name="open-browser", daemon=True).start()

    from waitress import serve

    try:
        serve(app, host=HOST, port=port, threads=8, _quiet=True)
    except KeyboardInterrupt:
        pass
    finally:
        app.cleanup_uploads()
        if hasattr(apollo, "close"):
            apollo.close()
    return 0


def run() -> int:
    """Entry point that never dies silently.

    A packaged build is launched by double-click; if it exits on an unhandled
    error the console window disappears with it and the analyst is left with a
    browser tab spinning at nothing.
    """
    try:
        return main()
    except SystemExit:
        raise
    except BaseException:
        print(f"\n[{APP_NAME}] Failed to start.\n", file=sys.stderr)
        traceback.print_exc()
        print(f"\n[{APP_NAME}] Send the text above to whoever maintains this "
              f"tool.", file=sys.stderr)
        try:
            input("\nPress Enter to close this window...")
        except (EOFError, KeyboardInterrupt):
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
