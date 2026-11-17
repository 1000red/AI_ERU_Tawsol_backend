from fastapi import WebSocket
from typing import Dict, Optional


class AnnouncementConnectionManager:
    def __init__(self):
        self._connections: Dict[int, WebSocket] = {}
        self._admin_users: set[int] = set()

    def connect(self, user_id: int, websocket: WebSocket, *, is_admin: bool = False) -> None:
        self._connections[user_id] = websocket
        if is_admin:
            self._admin_users.add(user_id)

    def disconnect(self, user_id: int) -> None:
        self._connections.pop(user_id, None)
        self._admin_users.discard(user_id)

    async def broadcast(self, payload: dict) -> None:
        dead: list[int] = []
        for uid, ws in self._connections.items():
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.disconnect(uid)

    async def disconnect_all(
        self,
        reason: str = "Platform temporarily stopped",
        *,
        maintenance_message: Optional[str] = None,
        exclude_admins: bool = True,
    ) -> int:
        closed = 0
        payload = {
            "type": "error",
            "error": "platform_stopped",
            "maintenance_mode": True,
            "detail": maintenance_message or reason,
        }
        for uid, ws in list(self._connections.items()):
            if exclude_admins and uid in self._admin_users:
                continue
            try:
                await ws.send_json(payload)
            except Exception:
                pass
            try:
                await ws.close(code=1013, reason=reason)
                closed += 1
            except Exception:
                pass
            self.disconnect(uid)
        return closed


announcement_manager = AnnouncementConnectionManager()
