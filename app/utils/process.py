"""
Helpers for running subprocesses with cooperative cancellation.
"""
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Sequence


class CancelledProcessError(RuntimeError):
    """Raised when a subprocess was stopped due to pipeline cancellation."""


def _terminate_process(process: subprocess.Popen[str]):
    """Terminate a process and wait for it to exit."""
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_command(
    command: Sequence[str],
    *,
    cancel_event: threading.Event | None = None,
    cwd: str | Path | None = None,
    line_callback: Callable[[str], None] | None = None,
) -> str:
    """
    Run a subprocess while continuously draining output and honoring cancellation.
    Returns combined stdout/stderr text.
    Raises CalledProcessError on non-zero exit and CancelledProcessError on stop.
    """
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output_lines: list[str] = []
    reader_error: list[BaseException] = []

    def _reader():
        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.rstrip()
                if not line:
                    continue
                output_lines.append(line)
                if line_callback is not None:
                    line_callback(line)
        except BaseException as exc:  # pragma: no cover - defensive reader guard
            reader_error.append(exc)

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    cancelled = False
    try:
        while process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                _terminate_process(process)
                break
            time.sleep(0.1)
        return_code = process.wait()
    finally:
        reader_thread.join(timeout=2)
        if process.stdout is not None:
            process.stdout.close()

    if reader_error:
        raise RuntimeError(f"Ошибка чтения вывода процесса: {reader_error[0]}") from reader_error[0]

    output = "\n".join(output_lines)
    if cancelled:
        raise CancelledProcessError(output)

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, list(command), output=output)

    return output
