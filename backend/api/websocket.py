from __future__ import annotations

import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.services import services

router = APIRouter()


@router.websocket("/stats")
async def stats_socket(websocket: WebSocket):
    await websocket.accept()
    services.monitor.register(websocket)
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "stats",
                    "data": services.monitor.get_snapshot(),
                    "timestamp": time.time(),
                }
            )
        )
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    finally:
        services.monitor.unregister(websocket)
