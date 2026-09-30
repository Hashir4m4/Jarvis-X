import unittest
import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy deps
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()

from backend.api.websocket_manager import WebSocketManager

class TestWebSocketManager(unittest.IsolatedAsyncioTestCase):
    async def test_connect_disconnect(self):
        manager = WebSocketManager()
        mock_ws = AsyncMock()
        
        await manager.connect(mock_ws)
        self.assertEqual(len(manager.active_connections), 1)
        mock_ws.accept.assert_awaited_once()
        
        manager.disconnect(mock_ws)
        self.assertEqual(len(manager.active_connections), 0)

    async def test_broadcast(self):
        manager = WebSocketManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        await manager.connect(mock_ws1)
        await manager.connect(mock_ws2)
        
        await manager.broadcast("test", {"hello": "world"})
        
        mock_ws1.send_text.assert_awaited_once()
        mock_ws2.send_text.assert_awaited_once()

if __name__ == "__main__":
    unittest.main()
