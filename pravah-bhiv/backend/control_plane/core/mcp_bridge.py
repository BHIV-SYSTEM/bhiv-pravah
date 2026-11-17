import json
import os
from datetime import datetime
from core.sovereign_bus import bus

class MCPBridge:
    """Bridge between MCP agents and sovereign bus."""
    
    def __init__(self, inbox_path="mcp_inbox.json", outbox_path="mcp_outbox.json"):
        self.inbox_path = inbox_path
        self.outbox_path = outbox_path
        self._setup_endpoints()
        self._setup_bus_listeners()
    
    def _setup_endpoints(self):
        """Initialize JSON endpoints."""
        for path in [self.inbox_path, self.outbox_path]:
            if not os.path.exists(path):
                with open(path, 'w') as f:
                    json.dump([], f)
    
    def _setup_bus_listeners(self):
        """Subscribe to bus events and forward to MCP."""
        events = ["deploy.success", "deploy.failure", "issue.detected", "heal.triggered", "rl.learned"]
        for event in events:
            bus.subscribe(event, self._forward_to_mcp)
    
    def _forward_to_mcp(self, message):
        """Forward bus message to MCP outbox."""
        import random
        mcp_message = {
            "context_id": f"ctx_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(100,999)}",
            "timestamp": message["timestamp"],
            "event_type": message["event_type"],
            "payload": message.get("data", {}),
            "source": "sovereign_bus"
        }
        
        # Append to outbox
        try:
            with open(self.outbox_path, 'r') as f:
                messages = json.load(f)
        except:
            messages = []
        
        messages.append(mcp_message)
        
        with open(self.outbox_path, 'w') as f:
            json.dump(messages[-100:], f, indent=2)  # Keep last 100
    
    def process_mcp_inbox(self):
        """Process messages from MCP and publish to bus."""
        try:
            with open(self.inbox_path, 'r') as f:
                messages = json.load(f)
            
            for msg in messages:
                if msg.get("processed"):
                    continue
                
                # Translate MCP message to bus event
                event_type = msg.get("event_type", "mcp.message")
                data = msg.get("payload", {})
                data["mcp_context_id"] = msg.get("context_id")
                
                bus.publish(event_type, data)
                msg["processed"] = True
            
            # Update inbox with processed flags
            with open(self.inbox_path, 'w') as f:
                json.dump(messages, f, indent=2)
                
        except Exception as e:
            print(f"MCP Bridge error: {e}")
    
    def get_outbox_messages(self):
        """Get messages for MCP consumption."""
        try:
            with open(self.outbox_path, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def add_inbox_message(self, message):
        """Add message from MCP to inbox."""
        try:
            with open(self.inbox_path, 'r') as f:
                messages = json.load(f)
        except:
            messages = []
        
        messages.append(message)
        
        with open(self.inbox_path, 'w') as f:
            json.dump(messages, f, indent=2)

# Global bridge instance
mcp_bridge = MCPBridge()