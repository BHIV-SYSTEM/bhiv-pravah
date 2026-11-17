import json
import time
from core.sovereign_bus import bus

class MCPAdapter:
    """Adapter for Ritesh's MCP Manager integration."""
    
    def __init__(self, mcp_manager, agent_name="sovereign_bus"):
        self.mcp_manager = mcp_manager
        self.agent_name = agent_name
        self.last_check = time.time()
        self._setup_bus_listeners()
    
    def _setup_bus_listeners(self):
        """Subscribe to bus events and forward to MCP."""
        events = ["deploy.success", "deploy.failure", "issue.detected", "heal.triggered", "rl.learned"]
        for event in events:
            bus.subscribe(event, self._forward_to_mcp)
    
    def _forward_to_mcp(self, message):
        """Forward bus message to MCP system."""
        mcp_content = {
            "event_type": message["event_type"],
            "data": message.get("data", {}),
            "bus_timestamp": message["timestamp"]
        }
        
        # Send to MCP using Ritesh's format
        self.mcp_manager.send_message(
            sender=self.agent_name,
            receiver="mcp_agents", 
            content=mcp_content
        )
    
    def process_mcp_messages(self):
        """Check for new MCP messages and forward to bus."""
        messages = self.mcp_manager.read_messages(self.agent_name)
        
        for msg in messages:
            if msg["timestamp"] > self.last_check:
                # Convert MCP message to bus event
                content = msg["content"]
                event_type = content.get("event_type", "mcp.message")
                data = content.get("data", {})
                data["mcp_sender"] = msg["sender"]
                
                bus.publish(event_type, data)
        
        self.last_check = time.time()
    
    def send_to_mcp(self, receiver, event_type, data):
        """Send message to specific MCP agent."""
        content = {
            "event_type": event_type,
            "data": data,
            "timestamp": time.time()
        }
        
        self.mcp_manager.send_message(
            sender=self.agent_name,
            receiver=receiver,
            content=content
        )