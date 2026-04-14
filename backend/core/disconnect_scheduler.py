from __future__ import annotations

import asyncio
import logging
import time

from core.models import RuleRecord
from core.monitor import Monitor
from core.rule_store import RuleStore
from core.tc_builder import TCBuilder

logger = logging.getLogger(__name__)


class DisconnectScheduler:
    """Runs periodic disconnect/reconnect cycles per rule."""

    def __init__(self, tc_builder: TCBuilder, rule_store: RuleStore, monitor: Monitor):
        self.tc_builder = tc_builder
        self.rule_store = rule_store
        self.monitor = monitor
        self._tasks: dict[str, asyncio.Task] = {}

    async def sync_rule(self, rule: RuleRecord) -> None:
        sched = rule.disconnect_schedule
        if sched and sched.enabled:
            self.start(rule)
        else:
            self.stop(rule.id)

    def start(self, rule: RuleRecord) -> None:
        self.stop(rule.id)
        self._tasks[rule.id] = asyncio.create_task(
            self._run(rule.id), name=f"netemu-disco-{rule.id}"
        )

    def stop(self, rule_id: str) -> None:
        task = self._tasks.pop(rule_id, None)
        if task:
            task.cancel()

    async def stop_all(self) -> None:
        for rule_id in list(self._tasks):
            self.stop(rule_id)
        await asyncio.sleep(0)

    async def restore(self) -> None:
        for rule in self.rule_store.list_rules():
            sched = rule.disconnect_schedule
            if sched and sched.enabled:
                self.start(rule)

    async def _run(self, rule_id: str) -> None:
        cycle = 0
        try:
            while True:
                rule = self.rule_store.get_rule(rule_id)
                if not rule or not rule.disconnect_schedule or not rule.disconnect_schedule.enabled:
                    return
                sched = rule.disconnect_schedule

                # Wait for the connected interval
                await asyncio.sleep(sched.interval_s)

                # Re-check rule still exists and schedule is still enabled
                rule = self.rule_store.get_rule(rule_id)
                if not rule or not rule.disconnect_schedule or not rule.disconnect_schedule.enabled:
                    return

                # Disconnect
                await asyncio.to_thread(self.tc_builder.set_disconnect, rule.interface, True)
                self.rule_store.update_rule_state(rule_id, status="disconnected")
                await self.monitor.push_event(
                    "disconnect_changed",
                    {"interface": rule.interface, "disconnect": True, "cycle": cycle + 1},
                )
                logger.info("Disconnect cycle %d: %s disconnected for %.1fs", cycle + 1, rule.interface, sched.disconnect_s)

                # Wait for disconnect duration
                await asyncio.sleep(sched.disconnect_s)

                # Reconnect
                rule = self.rule_store.get_rule(rule_id)
                if not rule:
                    return
                await asyncio.to_thread(self.tc_builder.set_disconnect, rule.interface, False)
                self.rule_store.update_rule_state(rule_id, status="active")
                await self.monitor.push_event(
                    "disconnect_changed",
                    {"interface": rule.interface, "disconnect": False, "cycle": cycle + 1},
                )
                logger.info("Disconnect cycle %d: %s reconnected", cycle + 1, rule.interface)

                cycle += 1
                if sched.repeat > 0 and cycle >= sched.repeat:
                    logger.info("Disconnect schedule completed %d cycles for %s", cycle, rule.interface)
                    return

        except asyncio.CancelledError:
            # Ensure reconnect on cancel
            rule = self.rule_store.get_rule(rule_id)
            if rule:
                await asyncio.to_thread(self.tc_builder.set_disconnect, rule.interface, False)
                self.rule_store.update_rule_state(rule_id, status="active")
            return
        except Exception as exc:
            logger.exception("Disconnect scheduler failed for %s: %s", rule_id, exc)
