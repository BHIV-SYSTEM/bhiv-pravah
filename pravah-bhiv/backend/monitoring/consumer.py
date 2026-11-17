"""Passive Pravah stream consumer.

Reads normalized execution signals without mutating them.
"""

from pravah_stream.stream import read_stream


def _format_entry(event: dict) -> str:
    signal_type = event.get("signal_type", "unknown")
    trace_id = event.get("trace_id", "missing")
    execution_id = event.get("execution_id", "missing")
    source = event.get("source", "unknown")
    return (
        f"[{signal_type}] trace_id={trace_id} "
        f"execution_id={execution_id} source={source}"
    )


def consume_stream() -> list[dict]:
    events = read_stream()

    for event in events:
        print(_format_entry(event))
        print(event)

    return events


if __name__ == "__main__":
    consume_stream()