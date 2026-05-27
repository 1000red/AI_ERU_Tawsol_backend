from fastapi import WebSocket
from typing import Dict


class AnnouncementConnectionManager:
    def __init__(self):
        self._connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id] = websocket

    def disconnect(self, user_id: int) -> None:
        self._connections.pop(user_id, None)

    async def broadcast(self, payload: dict) -> None:
        dead: list[int] = []
        for uid, ws in self._connections.items():
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.disconnect(uid)


announcement_manager = AnnouncementConnectionManager()
