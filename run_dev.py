from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5500"


def start_process(command: list[str], name: str) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(command, cwd=PROJECT_ROOT)
    print(f"Started {name}: {' '.join(command)}")
    return process


def stop_process(process: subprocess.Popen[bytes], name: str) -> None:
    if process.poll() is not None:
        return

    print(f"Stopping {name}...")
    process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    backend_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.api.main:app",
        "--reload",
    ]
    frontend_command = [
        sys.executable,
        "-m",
        "http.server",
        "5500",
        "--directory",
        "frontend",
    ]

    backend_process = start_process(backend_command, "backend")
    frontend_process = start_process(frontend_command, "frontend")

    print("")
    print("Local dev servers are starting.")
    print(f"Backend:  {BACKEND_URL}")
    print(f"Frontend: {FRONTEND_URL}")
    print("Press Ctrl+C to stop both.")

    try:
        while True:
            if backend_process.poll() is not None:
                print("Backend process exited unexpectedly.")
                return backend_process.returncode or 1

            if frontend_process.poll() is not None:
                print("Frontend process exited unexpectedly.")
                return frontend_process.returncode or 1

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("")
        print("Shutting down local dev servers...")
        return 0
    finally:
        stop_process(frontend_process, "frontend")
        stop_process(backend_process, "backend")


if __name__ == "__main__":
    raise SystemExit(main())
