from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Settings:
    app_name: str
    app_version: str
    host: str
    port: int
    data_dir: str
    rules_path: str
    custom_profiles_path: str
    preset_profiles_path: str
    monitor_interval_s: float
    allowed_origins: list[str]
    allow_credentials: bool


def _parse_origins() -> tuple[list[str], bool]:
    raw = os.getenv("NETEMU_ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if not origins:
        origins = ["http://localhost:8080", "http://127.0.0.1:8080"]
    if origins == ["*"]:
        return origins, False
    return origins, True


def _parse_env_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except ValueError:
        logger.error("Invalid integer for %s: %r, using default %s", name, raw, default)
        return int(default)


def _parse_env_float(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        return float(raw)
    except ValueError:
        logger.error("Invalid float for %s: %r, using default %s", name, raw, default)
        return float(default)


def load_settings() -> Settings:
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.getenv("NETEMU_DATA_DIR", os.path.join(backend_dir, "data"))
    origins, allow_credentials = _parse_origins()
    port = _parse_env_int("NETEMU_PORT", "8080")
    monitor_interval = _parse_env_float("NETEMU_MONITOR_INTERVAL_S", "2.0")
    if not (1 <= port <= 65535):
        logger.error("NETEMU_PORT=%d out of range 1-65535, using 8080", port)
        port = 8080
    if monitor_interval <= 0:
        logger.error("NETEMU_MONITOR_INTERVAL_S must be positive, using 2.0")
        monitor_interval = 2.0
    os.makedirs(data_dir, exist_ok=True)
    return Settings(
        app_name="NetEmu",
        app_version="2.0.0",
        host=os.getenv("NETEMU_HOST", "0.0.0.0"),
        port=port,
        data_dir=data_dir,
        rules_path=os.path.join(data_dir, "rules.json"),
        custom_profiles_path=os.path.join(data_dir, "custom_profiles.json"),
        preset_profiles_path=os.path.join(backend_dir, "profiles", "presets.json"),
        monitor_interval_s=monitor_interval,
        allowed_origins=origins,
        allow_credentials=allow_credentials,
    )


settings = load_settings()
