from __future__ import annotations

import os
from pathlib import Path
import signal


class RuntimeStateError(RuntimeError):
    pass


def acquire_pid_file(pid_file: str | Path, *, pid: int | None = None) -> int:
    path = Path(pid_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    current_pid = pid if pid is not None else os.getpid()

    existing_pid = read_pid_file(path)
    if existing_pid is not None:
        if is_process_running(existing_pid):
            raise RuntimeStateError(f"Process already running with pid {existing_pid}")
        path.unlink()

    path.write_text(f"{current_pid}\n", encoding="ascii")
    return current_pid


def release_pid_file(pid_file: str | Path) -> None:
    path = Path(pid_file)
    if path.exists():
        path.unlink()


def read_pid_file(pid_file: str | Path) -> int | None:
    path = Path(pid_file)
    if not path.exists():
        return None

    content = path.read_text(encoding="ascii").strip()
    if not content:
        return None
    try:
        return int(content)
    except ValueError as error:
        raise RuntimeStateError(f"Invalid pid file contents in {path}") from error


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_process(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)

