import logging
import json
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages active WebSocket connections for the Jarvis Dashboard."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accepts a new connection and adds it to the pool."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("New WebSocket connection accepted.")

    def disconnect(self, websocket: WebSocket):
        """Removes a disconnected client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket connection closed.")

    async def broadcast(self, message_type: str, data: Dict[str, Any]):
        """
        Broadcasts a JSON message to all connected clients.
        Used for streaming chat, system updates, or agent status.
        """
        if not self.active_connections:
            return

        payload = {
            "type": message_type,
            "data": data
        }
        json_payload = json.dumps(payload)

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json_payload)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(connection)
                
        # Cleanup broken connections
        for conn in disconnected:
            self.disconnect(conn)
