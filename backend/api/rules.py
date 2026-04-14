from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from core.models import DisconnectRequest, ModeRequest, RuleUpsertRequest
from core.services import services
from core.tc_builder import TCConfig

router = APIRouter()
logger = logging.getLogger(__name__)


def _tc_config_from_request(request: RuleUpsertRequest) -> TCConfig:
    return TCConfig(
        interface=request.interface,
        bandwidth_kbit=request.bandwidth_kbit,
        delay_ms=request.delay_ms,
        jitter_ms=request.jitter_ms,
        loss_pct=request.loss_pct,
        duplicate_pct=request.duplicate_pct,
        corrupt_pct=request.corrupt_pct,
        disorder_pct=request.disorder_pct,
        direction=request.direction,
    )


@router.get("/")
async def list_rules():
    return [item.model_dump(mode="json") for item in services.rules.list_rules()]


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    rule = services.rules.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule.model_dump(mode="json")


@router.post("/")
async def create_or_update_rule(request: RuleUpsertRequest):
    if not services.tc.interface_exists(request.interface):
        raise HTTPException(status_code=404, detail=f"Interface `{request.interface}` not found")
    result = await asyncio.to_thread(services.tc.apply_rules, _tc_config_from_request(request))
    rule = services.rules.upsert_rule(
        request,
        status="active" if result["success"] else "error",
        tc_errors=result["errors"],
    )
    await services.variation.sync_rule(rule)
    logger.info("Rule %s on %s: status=%s", "updated" if request.id else "created", request.interface, rule.status)
    payload = {"rule": rule.model_dump(mode="json"), "tc_result": result}
    await services.monitor.push_event("rule_changed", payload)
    return payload


@router.post("/{rule_id}/clear")
async def clear_rule(rule_id: str):
    rule = services.rules.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    result = await asyncio.to_thread(services.tc.clear_rules, rule.interface)
    services.rules.update_rule_state(rule_id, status="cleared", tc_errors=[])
    logger.info("Rule cleared: id=%s interface=%s", rule_id, rule.interface)
    services.variation.stop(rule_id)
    await services.monitor.push_event("rule_cleared", {"rule_id": rule_id, "interface": rule.interface})
    return result


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    rule = services.rules.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await asyncio.to_thread(services.tc.clear_rules, rule.interface)
    await asyncio.to_thread(services.tc.set_disconnect, rule.interface, False)
    services.variation.stop(rule_id)
    services.rules.delete_rule(rule_id)
    logger.info("Rule deleted: id=%s interface=%s", rule_id, rule.interface)
    await services.monitor.push_event("rule_deleted", {"rule_id": rule_id, "interface": rule.interface})
    return {"deleted": rule_id}


@router.post("/disconnect")
async def set_disconnect(request: DisconnectRequest):
    if not services.tc.interface_exists(request.interface):
        raise HTTPException(status_code=404, detail=f"Interface `{request.interface}` not found")
    result = await asyncio.to_thread(services.tc.set_disconnect, request.interface, request.disconnect)
    rule = services.rules.get_rule_by_interface(request.interface)
    if rule:
        services.rules.update_rule_state(
            rule.id,
            status="disconnected" if request.disconnect else "active",
            tc_errors=result.get("errors", []),
        )
    await services.monitor.push_event(
        "disconnect_changed",
        {"interface": request.interface, "disconnect": request.disconnect, "result": result},
    )
    return result


@router.post("/mode")
async def set_mode(request: ModeRequest):
    if request.wan_iface == request.lan_iface:
        raise HTTPException(status_code=400, detail="WAN and LAN interfaces must be different")
    missing = [name for name in (request.wan_iface, request.lan_iface) if not services.tc.interface_exists(name)]
    if missing:
        raise HTTPException(status_code=404, detail=f"Interface not found: {', '.join(missing)}")
    result = await asyncio.to_thread(services.tc.set_mode, request.mode.value, request.wan_iface, request.lan_iface)
    await services.monitor.push_event("mode_changed", {"mode": request.mode.value, "result": result})
    return result
