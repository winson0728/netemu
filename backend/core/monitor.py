from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from core.tc_builder import TCBuilder

logger = logging.getLogger(__name__)


class Monitor:
    def __init__(self, tc_builder: TCBuilder, *, poll_interval_s: float = 2.0):
        self.tc_builder = tc_builder
        self.poll_interval_s = poll_interval_s
        self._running = False
        self._clients: set = set()
        self._task: asyncio.Task | None = None
        self._stats_cache: dict[str, dict[str, Any]] = {}
        self._prev_stats: dict[str, dict[str, float]] = {}
        self._prev_time = 0.0

    def register(self, websocket) -> None:
        self._clients.add(websocket)

    def unregister(self, websocket) -> None:
        self._clients.discard(websocket)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="netemu-monitor")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while self._running:
            try:
                await self._collect()
                await self._broadcast("stats", self._stats_cache)
            except Exception as exc:
                logger.exception("Monitor loop failed: %s", exc)
            await asyncio.sleep(self.poll_interval_s)

    async def _collect(self) -> None:
        now = time.time()
        # Single subprocess call gets all interfaces + stats
        interfaces = await asyncio.to_thread(self.tc_builder.get_interfaces_with_stats)
        if not interfaces:
            return

        # Parallel qdisc queries for all interfaces
        names = [item["name"] for item in interfaces]
        qdisc_results = await asyncio.gather(
            *(asyncio.to_thread(self.tc_builder.get_current_qdisc, n) for n in names)
        )

        current_stats: dict[str, dict[str, float]] = {}
        snapshot: dict[str, dict[str, Any]] = {}
        for item, qdisc in zip(interfaces, qdisc_results):
            name = item["name"]
            raw_stats = item["stats"]
            rate_rx = 0.0
            rate_tx = 0.0
            if name in self._prev_stats and self._prev_time > 0:
                dt = now - self._prev_time
                if dt > 0:
                    rate_rx = max(0.0, (raw_stats["rx_bytes"] - self._prev_stats[name].get("rx_bytes", 0.0)) / dt)
                    rate_tx = max(0.0, (raw_stats["tx_bytes"] - self._prev_stats[name].get("tx_bytes", 0.0)) / dt)
            current_stats[name] = {
                "rx_bytes": float(raw_stats["rx_bytes"]),
                "tx_bytes": float(raw_stats["tx_bytes"]),
            }
            snapshot[name] = {
                "interface": name,
                "state": item["state"],
                "stats": {**raw_stats, "rate_rx_bps": rate_rx, "rate_tx_bps": rate_tx},
                "qdisc": qdisc,
                "timestamp": now,
            }
        self._prev_stats = current_stats
        self._prev_time = now
        self._stats_cache = snapshot

    async def _broadcast(self, event_type: str, payload: Any) -> None:
        if not self._clients:
            return
        message = json.dumps({"type": event_type, "data": payload, "timestamp": time.time()})
        dead: set = set()

        async def _send(ws) -> None:
            try:
                await asyncio.wait_for(ws.send_text(message), timeout=5.0)
            except Exception:
                logger.debug("WebSocket send failed, marking client as dead", exc_info=True)
                dead.add(ws)

        await asyncio.gather(*(_send(ws) for ws in list(self._clients)))
        self._clients -= dead

    async def push_event(self, event_type: str, payload: Any) -> None:
        await self._broadcast(event_type, payload)

    def get_snapshot(self) -> dict[str, dict[str, Any]]:
        return dict(self._stats_cache)
