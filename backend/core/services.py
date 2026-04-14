from __future__ import annotations

import asyncio
import json
import logging
import os

from core.command_runner import CommandRunner
from core.monitor import Monitor
from core.profile_store import ProfileStore
from core.rule_store import RuleStore
from core.settings import settings
from core.tc_builder import TCBuilder, TCConfig
from core.disconnect_scheduler import DisconnectScheduler
from core.variation import VariationService

logger = logging.getLogger(__name__)


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
        self.bridge_config: dict = self._load_bridge_config()

    def _load_bridge_config(self) -> dict:
        try:
            if os.path.exists(settings.bridge_config_path):
                with open(settings.bridge_config_path, encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            logger.warning("Failed to load bridge config, using empty")
        return {}

    def save_bridge_config(self, config: dict) -> None:
        self.bridge_config = config
        with open(settings.bridge_config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    async def startup(self) -> None:
        await self._apply_saved_bridge()
        await self.monitor.start()
        await self.restore_rules()
        await self.variation.restore()
        await self.disconnect_scheduler.restore()

    async def _apply_saved_bridge(self) -> None:
        lines = self.bridge_config.get("lines", [])
        if not lines:
            return
        line_tuples = [(p["downlink"], p["uplink"]) for p in lines if p.get("downlink") and p.get("uplink")]
        if not line_tuples:
            return
        logger.info("Auto-applying saved bridge config: %s", line_tuples)
        result = await asyncio.to_thread(self.tc.set_bridge, line_tuples)
        if result["success"]:
            logger.info("Bridge auto-applied successfully")
        else:
            logger.error("Bridge auto-apply errors: %s", result["errors"])

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
