import subprocess
import sys
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

PROJECT = Path(__file__).parent
PYTHON = sys.executable


class RestartHandler(FileSystemEventHandler):
    def __init__(self):
        self.should_restart = False

    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            self.should_restart = True

    def on_created(self, event):
        if event.src_path.endswith(".py"):
            self.should_restart = True


def run():
    handler = RestartHandler()
    observer = Observer()
    observer.schedule(handler, str(PROJECT), recursive=True)
    observer.start()

    proc = None
    try:
        while True:
            if proc is None or proc.poll() is not None:
                if proc is not None:
                    print("Bot exited, restarting...", flush=True)
                proc = subprocess.Popen([PYTHON, str(PROJECT / "main.py")], cwd=str(PROJECT))

            if handler.should_restart:
                handler.should_restart = False
                print(".py file changed, restarting bot...", flush=True)
                proc.terminate()
                proc.wait()
                time.sleep(1)
                proc = subprocess.Popen([PYTHON, str(PROJECT / "main.py")], cwd=str(PROJECT))

            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
        observer.stop()
        observer.join()


if __name__ == "__main__":
    run()
