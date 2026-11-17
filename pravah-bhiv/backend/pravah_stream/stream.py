from copy import deepcopy
from threading import Lock

from .rules import validate_signal_passthrough


_STREAM_LOCK = Lock()
_STREAM_BUFFER: list[dict] = []


def emit(signal: dict):
    signal = validate_signal_passthrough(signal)
    signal_snapshot = deepcopy(signal)

    with _STREAM_LOCK:
        _STREAM_BUFFER.append(signal_snapshot)

    return signal_snapshot


def read_stream() -> list[dict]:
    with _STREAM_LOCK:
        return deepcopy(_STREAM_BUFFER)


def clear_stream() -> None:
    with _STREAM_LOCK:
        _STREAM_BUFFER.clear()