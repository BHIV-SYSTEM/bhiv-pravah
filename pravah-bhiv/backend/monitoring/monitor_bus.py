#!/usr/bin/env python3
"""Monitor sovereign bus events in real-time."""

from control_plane.core.sovereign_bus import bus
import json

def print_event(message):
    """Print formatted event message."""
    print(f"[{message['timestamp']}] {message['event_type']}: {json.dumps(message['data'], indent=2)}")

def main():
    """Monitor bus events via file watching."""
    print("🚌 Sovereign Bus Monitor Started")
    print("Monitoring for NEW events only...")
    
    # Start from current message count (ignore history)
    last_count = len(bus.get_messages())
    print(f"Ignoring {last_count} historical events")
    
    import time
    for _ in range(30):
        messages = bus.get_messages()
        if len(messages) > last_count:
            # Show only new messages
            for msg in messages[last_count:]:
                print_event(msg)
            last_count = len(messages)
        time.sleep(1)
    print("\n🛑 Bus monitor completed bounded run")

if __name__ == "__main__":
    main()