import queue
import threading
import time
import json
from datetime import datetime
from typing import Dict, List, Callable
import csv
import os

class RealtimeBus:
    def __init__(self):
        self.queues: Dict[str, queue.Queue] = {}
        self.subscribers: Dict[str, List[Callable]] = {}
        self.running = True
        self.performance_log = os.path.join("logs", r"performance_log.csv")
        self.message_count = 0
        self.start_time = time.time()
        
        # Initialize performance log
        os.makedirs("logs", exist_ok=True)
        if not os.path.exists(self.performance_log):
            with open(self.performance_log, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'event_type', 'throughput_per_sec', 'queue_size', 'total_messages'])
    
    def create_queue(self, name: str):
        """Create a new message queue"""
        self.queues[name] = queue.Queue()
        self.subscribers[name] = []
    
    def publish(self, topic: str, message: dict):
        """Publish message to topic"""
        if topic not in self.queues:
            self.create_queue(topic)
        
        message['timestamp'] = datetime.now().isoformat()
        self.queues[topic].put(message)
        self.message_count += 1
        
        # Notify subscribers immediately
        for callback in self.subscribers.get(topic, []):
            try:
                callback(message)
            except Exception as e:
                print(f"Subscriber error: {e}")
        
        self._log_performance(topic)
    
    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to topic with callback"""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
    
    def get_messages(self, topic: str, timeout: float = 1.0) -> List[dict]:
        """Get all messages from topic queue"""
        if topic not in self.queues:
            return []
        
        messages = []
        try:
            message = self.queues[topic].get(timeout=timeout)
            messages.append(message)
            self.queues[topic].task_done()
        except queue.Empty:
            return messages

        while not self.queues[topic].empty():
            try:
                message = self.queues[topic].get_nowait()
                messages.append(message)
                self.queues[topic].task_done()
            except queue.Empty:
                break
        return messages
    
    def _log_performance(self, topic: str):
        """Log throughput performance"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        throughput = self.message_count / elapsed if elapsed > 0 else 0
        queue_size = self.queues[topic].qsize()
        
        with open(self.performance_log, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                f"message_published_{topic}",
                f"{throughput:.2f}",
                queue_size,
                self.message_count
            ])
    
    def get_stats(self) -> dict:
        """Get bus statistics"""
        elapsed = time.time() - self.start_time
        return {
            'total_messages': self.message_count,
            'throughput_per_sec': self.message_count / elapsed if elapsed > 0 else 0,
            'active_queues': len(self.queues),
            'uptime_seconds': elapsed
        }

# Global bus instance
realtime_bus = RealtimeBus()