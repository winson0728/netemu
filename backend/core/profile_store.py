from __future__ import annotations

import json
import logging
import os
import re

from core.models import ProfileCreateRequest, ProfileRecord

SLUG_RE = re.compile(r"[^a-z0-9]+")
logger = logging.getLogger(__name__)


def slugify(value: str) -> str:
    return SLUG_RE.sub("_", value.lower()).strip("_") or "profile"


class ProfileStore:
    def __init__(self, preset_path: str, custom_path: str):
        self.preset_path = preset_path
        self.custom_path = custom_path
        self._preset_cache: list[ProfileRecord] | None = None
        self._custom_cache: dict[str, ProfileRecord] | None = None
        self._custom_mtime: float = 0.0

    def _load_json_map(self, path: str) -> dict[str, dict]:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save_custom(self, profiles: dict[str, ProfileRecord]) -> None:
        os.makedirs(os.path.dirname(self.custom_path), exist_ok=True)
        payload = {item.id: item.model_dump(mode="json") for item in profiles.values()}
        with open(self.custom_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        self._custom_cache = dict(profiles)
        self._custom_mtime = os.path.getmtime(self.custom_path) if os.path.exists(self.custom_path) else 0.0

    def _get_presets(self) -> list[ProfileRecord]:
        if self._preset_cache is None:
            self._preset_cache = [
                ProfileRecord.model_validate({**raw, "builtin": True})
                for raw in self._load_json_map(self.preset_path).values()
            ]
        return self._preset_cache

    def _get_custom(self) -> dict[str, ProfileRecord]:
        mtime = os.path.getmtime(self.custom_path) if os.path.exists(self.custom_path) else 0.0
        if self._custom_cache is None or mtime != self._custom_mtime:
            self._custom_cache = {
                key: ProfileRecord.model_validate({**value, "builtin": False})
                for key, value in self._load_json_map(self.custom_path).items()
            }
            self._custom_mtime = mtime
        return self._custom_cache

    def list_profiles(self) -> list[ProfileRecord]:
        records: list[ProfileRecord] = list(self._get_presets())
        records.extend(self._get_custom().values())
        return sorted(records, key=lambda item: (item.category, item.name.lower()))

    def get_profile(self, profile_id: str) -> ProfileRecord | None:
        for preset in self._get_presets():
            if preset.id == profile_id:
                return preset
        custom = self._get_custom()
        return custom.get(profile_id)

    def save_profile(self, request: ProfileCreateRequest) -> ProfileRecord:
        custom_profiles = dict(self._get_custom())
        profile_id = request.id or slugify(request.name)
        record = ProfileRecord(id=profile_id, builtin=False, **request.model_dump(exclude={"id"}))
        custom_profiles[record.id] = record
        self._save_custom(custom_profiles)
        return record

    def delete_profile(self, profile_id: str) -> bool:
        custom_profiles = dict(self._get_custom())
        if profile_id not in custom_profiles:
            return False
        del custom_profiles[profile_id]
        self._save_custom(custom_profiles)
        return True
