from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

INTERFACE_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


def validate_interface_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("interface is required")
    if not INTERFACE_RE.fullmatch(cleaned):
        raise ValueError("invalid interface name")
    return cleaned


class _InterfaceValidatorMixin(BaseModel):
    """Mixin that validates the ``interface`` field."""

    interface: str

    @field_validator("interface")
    @classmethod
    def _validate_interface(cls, value: str) -> str:
        return validate_interface_name(value)


class _NetworkParamsMixin(BaseModel):
    """Shared network-emulation parameter fields used by rules and profiles."""

    bandwidth_kbit: int = Field(default=0, ge=0, le=10_000_000)
    delay_ms: float = Field(default=0, ge=0, le=60_000)
    jitter_ms: float = Field(default=0, ge=0, le=60_000)
    loss_pct: float = Field(default=0, ge=0, le=100)
    corrupt_pct: float = Field(default=0, ge=0, le=100)
    duplicate_pct: float = Field(default=0, ge=0, le=100)
    disorder_pct: float = Field(default=0, ge=0, le=100)


class Direction(str, Enum):
    egress = "egress"
    ingress = "ingress"
    both = "both"


class Mode(str, Enum):
    routing = "routing"
    bridge = "bridge"


class VariationConfig(BaseModel):
    delay_range_ms: float = Field(default=0, ge=0, le=60_000)
    jitter_range_ms: float = Field(default=0, ge=0, le=60_000)
    loss_range_pct: float = Field(default=0, ge=0, le=100)
    bw_range_kbit: int = Field(default=0, ge=0, le=10_000_000)
    interval_s: int = Field(default=5, ge=1, le=3600)


class RuleBase(_InterfaceValidatorMixin, _NetworkParamsMixin):
    label: str = Field(default="", max_length=256)
    direction: Direction = Direction.egress
    variation_enabled: bool = False
    variation: VariationConfig | None = None


class RuleUpsertRequest(RuleBase):
    id: str | None = None


class RuleRecord(RuleBase):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    status: str = "active"
    tc_errors: list[str] = Field(default_factory=list)
    created_at: float
    updated_at: float
    variation_state: dict[str, Any] = Field(default_factory=dict)


class DisconnectRequest(_InterfaceValidatorMixin):
    disconnect: bool


class LinePair(BaseModel):
    wan_iface: str
    lan_iface: str

    @field_validator("wan_iface", "lan_iface")
    @classmethod
    def _validate_interface(cls, value: str) -> str:
        return validate_interface_name(value)


class ModeRequest(BaseModel):
    mode: Mode
    lines: list[LinePair] = Field(default_factory=list, max_length=4)

    # Backward compat: accept flat wan_iface/lan_iface for single-line callers
    wan_iface: str | None = None
    lan_iface: str | None = None

    @field_validator("wan_iface", "lan_iface", mode="before")
    @classmethod
    def _validate_opt_iface(cls, value):
        if value is not None and value != "":
            return validate_interface_name(value)
        return value

    def get_lines(self) -> list[LinePair]:
        if self.lines:
            return self.lines
        if self.wan_iface and self.lan_iface:
            return [LinePair(wan_iface=self.wan_iface, lan_iface=self.lan_iface)]
        return []


class ScheduledDisconnectRequest(_InterfaceValidatorMixin):
    duration_s: float = Field(default=5.0, ge=0.5, le=3600)


class ProfileRecord(_NetworkParamsMixin):
    id: str
    name: str = Field(max_length=256)
    description: str = Field(default="", max_length=1024)
    category: str = Field(default="custom", max_length=64)
    builtin: bool = False


class ProfileCreateRequest(_NetworkParamsMixin):
    id: str | None = None
    name: str = Field(max_length=256)
    description: str = Field(default="", max_length=1024)
    category: str = Field(default="custom", max_length=64)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned


class InterfaceSnapshot(BaseModel):
    name: str
    state: str
    flags: list[str] = Field(default_factory=list)
    mac: str = ""
    stats: dict[str, Any] = Field(default_factory=dict)
    qdisc: str = ""
    rate_rx_bps: float = 0
    rate_tx_bps: float = 0
