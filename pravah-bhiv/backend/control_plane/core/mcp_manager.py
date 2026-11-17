import json
import os
import time
from datetime import datetime

class MCPManager:
    def __init__(self, message_file="messages.json"):
        self.message_file = message_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Ensure message file exists and is valid JSON."""
        try:
            if not os.path.exists(self.message_file):
                with open(self.message_file, "w") as f:
                    json.dump([], f)
            else:
                # Validate existing file
                with open(self.message_file, "r") as f:
                    json.load(f)
        except (json.JSONDecodeError, IOError):
            # Fix corrupted file
            with open(self.message_file, "w") as f:
                json.dump([], f)

    def send_message(self, sender, receiver, content):
        """Send a message to another agent"""
        try:
            with open(self.message_file, "r") as f:
                messages = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            messages = []
        
        message = {
            "id": f"msg_{int(time.time() * 1000)}",  # Unique message ID
            "sender": sender,
            "receiver": receiver,
            "content": content,
            "timestamp": time.time(),
            "iso_timestamp": datetime.now().isoformat(),
            "processed": False
        }
        
        messages.append(message)
        
        # Keep only last 1000 messages to prevent file bloat
        if len(messages) > 1000:
            messages = messages[-1000:]
        
        try:
            with open(self.message_file, "w") as f:
                json.dump(messages, f, indent=2)
        except IOError as e:
            print(f"MCP Manager: Error writing messages - {e}")

    def read_messages(self, receiver):
        """Read messages for a specific receiver"""
        try:
            with open(self.message_file, "r") as f:
                messages = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
        
        inbox = [msg for msg in messages if msg["receiver"] == receiver]
        return inbox
    
    def read_unprocessed_messages(self, receiver):
        """Read only unprocessed messages for a receiver."""
        messages = self.read_messages(receiver)
        return [msg for msg in messages if not msg.get("processed", False)]
    
    def mark_processed(self, message_id):
        """Mark a message as processed."""
        try:
            with open(self.message_file, "r") as f:
                messages = json.load(f)
            
            for msg in messages:
                if msg.get("id") == message_id:
                    msg["processed"] = True
                    break
            
            with open(self.message_file, "w") as f:
                json.dump(messages, f, indent=2)
        except (json.JSONDecodeError, FileNotFoundError, IOError):
            pass
    
    def get_message_stats(self):
        """Get message statistics."""
        try:
            with open(self.message_file, "r") as f:
                messages = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"total": 0, "processed": 0, "unprocessed": 0}
        
        total = len(messages)
        processed = len([msg for msg in messages if msg.get("processed", False)])
        
        return {
            "total": total,
            "processed": processed,
            "unprocessed": total - processed
        }

    def clear_messages(self):
        """Clear all messages"""
        try:
            with open(self.message_file, "w") as f:
                json.dump([], f)
        except IOError as e:
            print(f"MCP Manager: Error clearing messages - {e}")
    
    def clear_processed_messages(self):
        """Clear only processed messages to save space."""
        try:
            with open(self.message_file, "r") as f:
                messages = json.load(f)
            
            # Keep only unprocessed messages
            unprocessed = [msg for msg in messages if not msg.get("processed", False)]
            
            with open(self.message_file, "w") as f:
                json.dump(unprocessed, f, indent=2)
                
        except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
            print(f"MCP Manager: Error clearing processed messages - {e}")