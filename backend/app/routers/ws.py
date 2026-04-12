import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core import security

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/dashboard/{venue_id}")
async def websocket_dashboard(websocket: WebSocket, venue_id: str):
    platform = websocket.app.state.platform_service
    security.verify_websocket_access(websocket, security.WS_DASHBOARD_REQUIRED_ROLES)

    await platform.ws_manager.connect(websocket, "dashboard")
    try:
        await platform.broadcast_venue_state(venue_id)
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        platform.ws_manager.disconnect(websocket, "dashboard")
    except Exception:
        platform.ws_manager.disconnect(websocket, "dashboard")


@router.websocket("/ws/fan/{venue_id}")
async def websocket_fan(websocket: WebSocket, venue_id: str):
    platform = websocket.app.state.platform_service
    security.verify_websocket_access(websocket, security.WS_FAN_REQUIRED_ROLES)

    await platform.ws_manager.connect(websocket, "fan")
    try:
        await platform.broadcast_venue_state(venue_id)
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("type") == "set_section":
                section = msg.get("section", "")
                await websocket.send_json(
                    {
                        "type": "section_ack",
                        "section": section,
                        "message": f"Personalized recommendations for {section}",
                    }
                )
    except WebSocketDisconnect:
        platform.ws_manager.disconnect(websocket, "fan")
    except Exception:
        platform.ws_manager.disconnect(websocket, "fan")
