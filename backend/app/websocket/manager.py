import threading

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {
            "dashboard": [],
            "fan": [],
        }
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket, client_type: str):
        await websocket.accept()
        with self._lock:
            if client_type not in self.active_connections:
                self.active_connections[client_type] = []
            self.active_connections[client_type].append(websocket)

    def disconnect(self, websocket: WebSocket, client_type: str):
        with self._lock:
            if client_type in self.active_connections:
                self.active_connections[client_type] = [
                    ws for ws in self.active_connections[client_type] if ws != websocket
                ]

    async def broadcast(self, client_type: str, message: dict):
        with self._lock:
            connections = list(self.active_connections.get(client_type, []))

        dead_connections: list[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead, client_type)

    async def broadcast_all(self, message: dict):
        for client_type in list(self.active_connections.keys()):
            await self.broadcast(client_type, message)
