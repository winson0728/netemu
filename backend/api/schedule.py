from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from core.models import ScheduledDisconnectRequest
from core.services import services

router = APIRouter()
logger = logging.getLogger(__name__)
_scheduled_tasks: dict[str, asyncio.Task] = {}


@router.post("/disconnect")
async def schedule_disconnect(request: ScheduledDisconnectRequest):
    if not services.tc.interface_exists(request.interface):
        raise HTTPException(status_code=404, detail=f"Interface `{request.interface}` not found")

    task_key = f"disconnect:{request.interface}"
    previous = _scheduled_tasks.pop(task_key, None)
    if previous:
        previous.cancel()

    async def _run() -> None:
        try:
            await asyncio.to_thread(services.tc.set_disconnect, request.interface, True)
            rule = services.rules.get_rule_by_interface(request.interface)
            if rule:
                services.rules.update_rule_state(rule.id, status="disconnected")
            await services.monitor.push_event("disconnect_changed", {"interface": request.interface, "disconnect": True})
            await asyncio.sleep(request.duration_s)
            await asyncio.to_thread(services.tc.set_disconnect, request.interface, False)
            rule = services.rules.get_rule_by_interface(request.interface)
            if rule:
                services.rules.update_rule_state(rule.id, status="active")
            await services.monitor.push_event("disconnect_changed", {"interface": request.interface, "disconnect": False})
            logger.info("Auto reconnected %s after %.1fs", request.interface, request.duration_s)
        finally:
            _scheduled_tasks.pop(task_key, None)

    _scheduled_tasks[task_key] = asyncio.create_task(_run(), name=f"netemu-disconnect-{request.interface}")
    return {"scheduled": True, "interface": request.interface, "duration_s": request.duration_s}
