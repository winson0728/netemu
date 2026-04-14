from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from core.services import services

router = APIRouter()


@router.get("/")
async def list_interfaces():
    interfaces = await asyncio.to_thread(services.tc.get_interfaces)
    snapshot = services.monitor.get_snapshot()
    result = []
    for item in interfaces:
        snap = snapshot.get(item["name"], {})
        stats = snap.get("stats", {})
        result.append(
            {
                **item,
                "stats": stats,
                "qdisc": snap.get("qdisc", ""),
                "rate_rx_bps": stats.get("rate_rx_bps", 0),
                "rate_tx_bps": stats.get("rate_tx_bps", 0),
            }
        )
    return result


@router.get("/{name}/stats")
async def get_interface_stats(name: str):
    if not services.tc.interface_exists(name):
        raise HTTPException(status_code=404, detail="Interface not found")
    stats = await asyncio.to_thread(services.tc.get_interface_stats, name)
    qdisc = await asyncio.to_thread(services.tc.get_current_qdisc, name)
    return {"interface": name, "stats": stats, "qdisc": qdisc}


@router.get("/{name}/qdisc")
async def get_interface_qdisc(name: str):
    if not services.tc.interface_exists(name):
        raise HTTPException(status_code=404, detail="Interface not found")
    qdisc = await asyncio.to_thread(services.tc.get_current_qdisc, name)
    return {"interface": name, "qdisc": qdisc}
