import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).parent
PYTHON = sys.executable


def latest_mtime() -> float:
    return max(
        (p.stat().st_mtime for p in PROJECT.rglob("*.py") if "__pycache__" not in str(p)),
        default=0.0,
    )


def start_bot() -> subprocess.Popen:
    return subprocess.Popen([PYTHON, str(PROJECT / "main.py")], cwd=str(PROJECT))


def run():
    proc = start_bot()
    last_mtime = latest_mtime()

    try:
        while True:
            time.sleep(2)

            if proc.poll() is not None:
                print("Bot exited, restarting...", flush=True)
                proc = start_bot()
                last_mtime = latest_mtime()
                continue

            current_mtime = latest_mtime()
            if current_mtime > last_mtime:
                print(".py file changed, restarting bot...", flush=True)
                last_mtime = current_mtime
                proc.terminate()
                proc.wait()
                time.sleep(1)
                proc = start_bot()

    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.terminate()


if __name__ == "__main__":
    run()
