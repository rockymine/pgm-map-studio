"""Start, stop, restart, and inspect the PGM Map Studio dev server.

Examples:
    python tools/run_studio_dev.py start --host localhost --port 7893
    python tools/run_studio_dev.py restart --host 0.0.0.0 --port 7892
    python tools/run_studio_dev.py stop --port 7893
    python tools/run_studio_dev.py status --port 7893
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = PROJECT_ROOT / ".tmp"


def pid_file(port: int) -> Path:
    return TMP_DIR / f"studio-dev-{port}.pid"


def log_file(port: int) -> Path:
    return TMP_DIR / f"studio-dev-{port}.log"


def is_process_running(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            return bool(
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                and exit_code.value == still_active
            )
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_pid(port: int) -> int | None:
    path = pid_file(port)
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def wait_until_ready(host: str, port: int, timeout_seconds: float = 10.0) -> bool:
    url_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{url_host}:{port}/"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                return 200 <= response.status < 500
        except OSError:
            time.sleep(0.25)
    return False


def start_server(host: str, port: int) -> None:
    TMP_DIR.mkdir(exist_ok=True)

    existing_pid = read_pid(port)
    if existing_pid and is_process_running(existing_pid):
        print(f"Server already running on port {port}, pid {existing_pid}.")
        return

    code = (
        "from pgm_map_studio.studio import create_app\n"
        "app = create_app()\n"
        f"app.run(host={host!r}, port={port}, debug=False, use_reloader=False)\n"
    )

    log_path = log_file(port)
    log_handle = log_path.open("a", encoding="utf-8")

    process = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    if wait_until_ready(host, port):
        listener_pids = _pids_on_port(port)
        server_pid = listener_pids[0] if listener_pids else process.pid
        pid_file(port).write_text(str(server_pid), encoding="utf-8")
        print(f"Started PGM Map Studio at http://{host}:{port}/")
        print(f"PID: {server_pid}")
        print(f"Log: {log_path}")
    else:
        print(f"Started process {process.pid}, but server did not become ready in time.")
        print(f"Check log: {log_path}")
        sys.exit(1)


def _pids_on_port(port: int) -> list[int]:
    """Return PIDs listening on *port* using ss (Linux) or netstat (Windows/fallback)."""
    pids: list[int] = []
    try:
        if os.name == "nt":
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "TCP"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            pids.extend(_parse_windows_netstat_pids(out, port))
        else:
            out = subprocess.check_output(
                ["ss", "-tlnp", f"sport = :{port}"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for line in out.splitlines():
                for chunk in line.split(","):
                    if chunk.startswith("pid="):
                        try:
                            pids.append(int(chunk.split("=")[1]))
                        except (ValueError, IndexError):
                            pass
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return pids


def _parse_windows_netstat_pids(output: str, port: int) -> list[int]:
    """Parse TCP listeners without depending on the localized state label."""
    pids: set[int] = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 5 or parts[0].upper() != "TCP":
            continue

        local_address, remote_address = parts[1], parts[2]
        if not local_address.endswith(f":{port}") or not remote_address.endswith(":0"):
            continue

        try:
            pids.add(int(parts[-1]))
        except ValueError:
            continue
    return sorted(pids)


def _wait_until_stopped(port: int, timeout_seconds: float = 5.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _pids_on_port(port):
            return True
        time.sleep(0.1)
    return not _pids_on_port(port)


def stop_server(port: int) -> None:
    path = pid_file(port)
    pid = read_pid(port)

    # Collect all PIDs to kill: the one in the PID file plus any orphan on the port.
    to_kill: set[int] = set()
    if pid and is_process_running(pid):
        to_kill.add(pid)
    for p in _pids_on_port(port):
        if is_process_running(p):
            to_kill.add(p)

    if not to_kill:
        if pid:
            print(f"PID {pid} is not running. Cleaning up PID file.")
        else:
            print(f"No server found on port {port}.")
        path.unlink(missing_ok=True)
        return

    print(f"Stopping server on port {port}, pids {sorted(to_kill)}...")

    try:
        for p in sorted(to_kill):
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(p), "/T", "/F"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    os.kill(p, signal.SIGTERM)
            except OSError:
                pass
        if os.name != "nt":
            time.sleep(1)
            for p in sorted(to_kill):
                if is_process_running(p):
                    try:
                        os.kill(p, signal.SIGKILL)
                    except OSError:
                        pass
        if not _wait_until_stopped(port):
            listeners = _pids_on_port(port)
            raise RuntimeError(
                f"Server did not stop; port {port} is still owned by {listeners}"
            )
    finally:
        path.unlink(missing_ok=True)

    print("Stopped.")


def status_server(host: str, port: int) -> None:
    pid = read_pid(port)
    running = bool(pid and is_process_running(pid))
    ready = wait_until_ready(host, port, timeout_seconds=1.0)

    print(f"Port:            {port}")
    print(f"Host:            {host}")
    print(f"PID:             {pid or '-'}")
    print(f"Process running: {running}")
    print(f"HTTP ready:      {ready}")
    print(f"Log:             {log_file(port)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "stop", "restart", "status"])
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=7893)
    args = parser.parse_args()

    if args.command == "start":
        start_server(args.host, args.port)
    elif args.command == "stop":
        stop_server(args.port)
    elif args.command == "restart":
        stop_server(args.port)
        start_server(args.host, args.port)
    elif args.command == "status":
        status_server(args.host, args.port)


if __name__ == "__main__":
    main()
