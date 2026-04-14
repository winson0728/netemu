from __future__ import annotations

import asyncio
import os

from core.command_runner import CommandRunner
from core.monitor import Monitor
from core.profile_store import ProfileStore
from core.rule_store import RuleStore
from core.settings import settings
from core.tc_builder import TCBuilder, TCConfig
from core.disconnect_scheduler import DisconnectScheduler
from core.variation import VariationService


class ServiceRegistry:
    def __init__(self):
        os.makedirs(settings.data_dir, exist_ok=True)
        self.runner = CommandRunner()
        self.tc = TCBuilder(self.runner)
        self.rules = RuleStore(settings.rules_path)
        self.profiles = ProfileStore(settings.preset_profiles_path, settings.custom_profiles_path)
        self.monitor = Monitor(self.tc, poll_interval_s=settings.monitor_interval_s)
        self.variation = VariationService(self.tc, self.rules, self.monitor)
        self.disconnect_scheduler = DisconnectScheduler(self.tc, self.rules, self.monitor)

    async def startup(self) -> None:
        await self.monitor.start()
        await self.restore_rules()
        await self.variation.restore()
        await self.disconnect_scheduler.restore()

    async def shutdown(self) -> None:
        await self.disconnect_scheduler.stop_all()
        await self.variation.stop_all()
        await self.monitor.stop()

    async def restore_rules(self) -> None:
        for rule in self.rules.list_rules():
            config = TCConfig(
                interface=rule.interface,
                bandwidth_kbit=rule.bandwidth_kbit,
                delay_ms=rule.delay_ms,
                jitter_ms=rule.jitter_ms,
                loss_pct=rule.loss_pct,
                duplicate_pct=rule.duplicate_pct,
                corrupt_pct=rule.corrupt_pct,
                disorder_pct=rule.disorder_pct,
                direction=rule.direction,
            )
            result = await asyncio.to_thread(self.tc.apply_rules, config)
            self.rules.update_rule_state(
                rule.id,
                status="active" if result["success"] else "error",
                tc_errors=result["errors"],
                variation_state=rule.variation_state,
            )


services = ServiceRegistry()
