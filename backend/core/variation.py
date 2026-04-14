from __future__ import annotations

import asyncio
import logging
import random
import time

from core.models import RuleRecord
from core.monitor import Monitor
from core.rule_store import RuleStore
from core.tc_builder import TCBuilder, TCConfig

logger = logging.getLogger(__name__)


class VariationService:
    def __init__(self, tc_builder: TCBuilder, rule_store: RuleStore, monitor: Monitor):
        self.tc_builder = tc_builder
        self.rule_store = rule_store
        self.monitor = monitor
        self._tasks: dict[str, asyncio.Task] = {}

    async def sync_rule(self, rule: RuleRecord) -> None:
        if rule.variation_enabled and rule.variation is not None:
            self.start(rule)
        else:
            self.stop(rule.id)

    def start(self, rule: RuleRecord) -> None:
        self.stop(rule.id)
        self._tasks[rule.id] = asyncio.create_task(self._run(rule.id), name=f"netemu-var-{rule.id}")

    def stop(self, rule_id: str) -> None:
        task = self._tasks.pop(rule_id, None)
        if task:
            task.cancel()

    async def stop_all(self) -> None:
        task_ids = list(self._tasks.keys())
        for rule_id in task_ids:
            self.stop(rule_id)
        await asyncio.sleep(0)

    async def restore(self) -> None:
        for rule in self.rule_store.list_rules():
            if rule.variation_enabled and rule.variation is not None:
                self.start(rule)

    async def _run(self, rule_id: str) -> None:
        try:
            while True:
                rule = self.rule_store.get_rule(rule_id)
                if not rule or not rule.variation_enabled or rule.variation is None:
                    return
                await asyncio.sleep(rule.variation.interval_s)
                current_rule = self.rule_store.get_rule(rule_id)
                if not current_rule or not current_rule.variation_enabled or current_rule.variation is None:
                    return
                varied = self._perturb(current_rule)
                result = await asyncio.to_thread(self.tc_builder.apply_rules, varied)
                state = {
                    "applied_at": time.time(),
                    "current_delay_ms": varied.delay_ms,
                    "current_jitter_ms": varied.jitter_ms,
                    "current_loss_pct": varied.loss_pct,
                    "current_bw_kbit": varied.bandwidth_kbit,
                }
                updated = self.rule_store.update_rule_state(
                    rule_id,
                    status="active_varied" if result["success"] else "error",
                    tc_errors=result["errors"],
                    variation_state=state,
                )
                if updated:
                    await self.monitor.push_event(
                        "rule_changed",
                        {"rule": updated.model_dump(mode="json"), "tc_result": result},
                    )
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.exception("Variation task failed for %s: %s", rule_id, exc)

    def _perturb(self, rule: RuleRecord) -> TCConfig:
        variation = rule.variation
        assert variation is not None

        def jitter(base: float, span: float) -> float:
            if span <= 0:
                return base
            return max(0.0, base + random.uniform(-span, span))

        return TCConfig(
            interface=rule.interface,
            bandwidth_kbit=int(jitter(float(rule.bandwidth_kbit), float(variation.bw_range_kbit))),
            delay_ms=jitter(rule.delay_ms, variation.delay_range_ms),
            jitter_ms=jitter(rule.jitter_ms, variation.jitter_range_ms),
            loss_pct=jitter(rule.loss_pct, variation.loss_range_pct),
            duplicate_pct=rule.duplicate_pct,
            corrupt_pct=rule.corrupt_pct,
            disorder_pct=rule.disorder_pct,
            direction=rule.direction,
        )
