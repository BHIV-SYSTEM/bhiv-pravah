import asyncio
import websockets
import json
from core.sovereign_bus import bus

class WebSocketServer:
    """Real-time WebSocket server for dashboard updates."""
    
    def __init__(self, port=8765):
        self.port = port
        self.clients = set()
        self._setup_bus_listeners()
    
    def _setup_bus_listeners(self):
        """Subscribe to bus events for real-time updates."""
        events = ["deploy.success", "deploy.failure", "issue.detected", "heal.triggered"]
        for event in events:
            bus.subscribe(event, self._broadcast_update)
    
    async def _broadcast_update(self, message):
        """Broadcast bus message to all connected clients."""
        if self.clients:
            update = {
                "type": "agent_update",
                "event": message["event_type"],
                "data": message.get("data", {}),
                "timestamp": message["timestamp"]
            }
            
            disconnected = set()
            for client in self.clients:
                try:
                    await client.send(json.dumps(update))
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)
            
            # Remove disconnected clients
            self.clients -= disconnected
    
    async def handle_client(self, websocket, path):
        """Handle new WebSocket client connection."""
        self.clients.add(websocket)
        print(f"📡 Dashboard client connected ({len(self.clients)} total)")
        
        try:
            # Send initial status
            await websocket.send(json.dumps({
                "type": "status",
                "agents": {
                    "deploy": "active",
                    "monitor": "watching", 
                    "heal": "ready",
                    "rl": "learning"
                }
            }))
            
            # Keep connection alive
            await websocket.wait_closed()
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"📡 Dashboard client disconnected ({len(self.clients)} total)")
    
    def start_server(self):
        """Start WebSocket server."""
        print(f"🌐 WebSocket server starting on port {self.port}")
        return websockets.serve(self.handle_client, "localhost", self.port)

# Global server instance
ws_server = WebSocketServer()