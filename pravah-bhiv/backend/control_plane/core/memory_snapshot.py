#!/usr/bin/env python3
"""
Memory Snapshot Utilities
Utilities for saving, loading, and visualizing agent memory snapshots.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from core.agent_memory import AgentMemory


def save_memory_snapshot(memory: AgentMemory, filepath: str) -> bool:
    """Save agent memory to JSON snapshot file.
    
    Args:
        memory: AgentMemory instance
        filepath: Path to save snapshot
        
    Returns:
        True if successful
    """
    try:
        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Get snapshot and save
        memory.to_json(filepath)
        
        return True
    
    except Exception as e:
        print(f"Error saving memory snapshot: {e}")
        return False


def load_memory_snapshot(filepath: str) -> Optional[Dict[str, Any]]:
    """Load memory snapshot from JSON file.
    
    Args:
        filepath: Path to snapshot file
        
    Returns:
        Snapshot dictionary or None
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
        return snapshot
    
    except FileNotFoundError:
        print(f"Snapshot file not found: {filepath}")
        return None
    
    except Exception as e:
        print(f"Error loading memory snapshot: {e}")
        return None


def visualize_memory(memory: AgentMemory, show_details: bool = False):
    """Print human-readable visualization of agent memory.
    
    Args:
        memory: AgentMemory instance
        show_details: Whether to show detailed decision/state info
    """
    print("="*70)
    print("AGENT MEMORY VISUALIZATION")
    print("="*70)
    print()
    
    # Memory stats
    stats = memory.get_memory_stats()
    print("[Memory Statistics]")
    print(f"  Agent ID: {stats['agent_id']}")
    print(f"  Created: {stats['created_at']}")
    print()
    
    print("[Decision Memory]")
    print(f"  Current: {stats['decision_count']}/{stats['decision_capacity']}")
    print(f"  Utilization: {stats['decision_utilization']}")
    print(f"  Total Seen: {stats['total_decisions_seen']}")
    print(f"  Evicted: {stats['decisions_evicted']}")
    print()
    
    print("[App State Memory]")
    print(f"  Tracked Apps: {stats['app_count']}")
    print(f"  Total States: {stats['total_app_states']}")
    print(f"  Max Per App: {stats['max_states_per_app']}")
    print()
    
    if show_details:
        # Show recent decisions
        print("[Recent Decisions]")
        recent = memory.recall_recent_decisions(5)
        if recent:
            for i, decision in enumerate(recent[-5:], 1):
                print(f"  {i}. {decision.decision_type} at {decision.timestamp}")
                print(f"     Outcome: {decision.outcome or 'pending'}")
        else:
            print("  No decisions in memory")
        print()
        
        # Show app states
        print("[App States]")
        if memory.app_state_memory:
            for app_id, states in list(memory.app_state_memory.items())[:5]:
                latest = states[-1] if states else None
                if latest:
                    print(f"  {app_id}: {latest.status} ({len(states)} states tracked)")
        else:
            print("  No app states in memory")
        print()
    
    print("="*70)


def export_memory_snapshot_summary(memory: AgentMemory, filepath: str):
    """Export memory summary to text file.
    
    Args:
        memory: AgentMemory instance
        filepath: Path to save summary
    """
    try:
        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        stats = memory.get_memory_stats()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("AGENT MEMORY SUMMARY\n")
            f.write("="*70 + "\n\n")
            
            f.write(f"Generated: {datetime.utcnow().isoformat()}\n")
            f.write(f"Agent ID: {stats['agent_id']}\n\n")
            
            f.write("[Decision Memory]\n")
            f.write(f"  Current: {stats['decision_count']}/{stats['decision_capacity']}\n")
            f.write(f"  Utilization: {stats['decision_utilization']}\n")
            f.write(f"  Total Seen: {stats['total_decisions_seen']}\n")
            f.write(f"  Evicted: {stats['decisions_evicted']}\n\n")
            
            f.write("[App State Memory]\n")
            f.write(f"  Tracked Apps: {stats['app_count']}\n")
            f.write(f"  Total States: {stats['total_app_states']}\n\n")
            
            # Recent decisions
            f.write("[Recent Decisions]\n")
            recent = memory.recall_recent_decisions(10)
            for decision in recent:
                f.write(f"  - {decision.timestamp}: {decision.decision_type}\n")
            
            f.write("\n" + "="*70 + "\n")
    
    except Exception as e:
        print(f"Error exporting summary: {e}")


def compare_memory_snapshots(filepath1: str, filepath2: str) -> Dict[str, Any]:
    """Compare two memory snapshots.
    
    Args:
        filepath1: Path to first snapshot
        filepath2: Path to second snapshot
        
    Returns:
        Comparison dictionary
    """
    snapshot1 = load_memory_snapshot(filepath1)
    snapshot2 = load_memory_snapshot(filepath2)
    
    if not snapshot1 or not snapshot2:
        return {"error": "Could not load snapshots"}
    
    stats1 = snapshot1.get('memory_stats', {})
    stats2 = snapshot2.get('memory_stats', {})
    
    return {
        "decision_count_change": stats2.get('decision_count', 0) - stats1.get('decision_count', 0),
        "app_count_change": stats2.get('app_count', 0) - stats1.get('app_count', 0),
        "total_states_change": stats2.get('total_app_states', 0) - stats1.get('total_app_states', 0),
        "time_delta": snapshot2.get('timestamp', '') + " vs " + snapshot1.get('timestamp', ''),
        "snapshot1_file": filepath1,
        "snapshot2_file": filepath2
    }


def cleanup_old_snapshots(directory: str, keep_count: int = 10):
    """Clean up old memory snapshots, keeping only the most recent.
    
    Args:
        directory: Directory containing snapshots
        keep_count: Number of snapshots to keep
    """
    try:
        snapshot_dir = Path(directory)
        
        if not snapshot_dir.exists():
            return
        
        # Find all JSON snapshot files
        snapshot_files = sorted(
            snapshot_dir.glob("memory_snapshot_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        # Remove old snapshots
        for old_snapshot in snapshot_files[keep_count:]:
            try:
                old_snapshot.unlink()
                print(f"Removed old snapshot: {old_snapshot.name}")
            except Exception as e:
                print(f"Error removing {old_snapshot.name}: {e}")
    
    except Exception as e:
        print(f"Error cleaning up snapshots: {e}")


if __name__ == "__main__":
    # Example usage
    from core.agent_memory import AgentMemory
    
    # Create sample memory
    memory = AgentMemory(agent_id="demo-agent")
    
    # Add some test data
    memory.remember_decision("test_decision", {"action": 1}, "success")
    memory.remember_decision("test_decision", {"action": 2}, "success")
    memory.remember_app_state("app1", "running", {"cpu": 50}, ["deploy"])
    
    # Visualize
    visualize_memory(memory, show_details=True)
    
    # Save snapshot
    save_memory_snapshot(memory, "logs/agent/test_snapshot.json")
    print("\nSnapshot saved to logs/agent/test_snapshot.json")
