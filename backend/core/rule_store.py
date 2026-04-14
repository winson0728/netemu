from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Optional

import logging

from core.models import RuleRecord, RuleUpsertRequest

logger = logging.getLogger(__name__)


class RuleStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._rules: dict[str, RuleRecord] = {}
        self._load()

    def _load(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self._rules = {item["id"]: RuleRecord.model_validate(item) for item in raw}
        except Exception:
            logger.error("Failed to load rules from %s, starting with empty rules", self.path, exc_info=True)
            self._rules = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump([rule.model_dump(mode="json") for rule in self.list_rules()], handle, indent=2)

    def list_rules(self) -> list[RuleRecord]:
        with self._lock:
            return sorted((rule.model_copy(deep=True) for rule in self._rules.values()), key=lambda item: item.interface)

    def get_rule(self, rule_id: str) -> Optional[RuleRecord]:
        with self._lock:
            rule = self._rules.get(rule_id)
            return rule.model_copy(deep=True) if rule else None

    def get_rule_by_interface(self, interface: str) -> Optional[RuleRecord]:
        with self._lock:
            for rule in self._rules.values():
                if rule.interface == interface:
                    return rule.model_copy(deep=True)
        return None

    def upsert_rule(self, request: RuleUpsertRequest, *, status: str, tc_errors: list[str]) -> RuleRecord:
        with self._lock:
            now = time.time()
            existing = self.get_rule(request.id) if request.id else None
            if existing is None:
                existing = self.get_rule_by_interface(request.interface)
            rule_id = existing.id if existing else (request.id or uuid.uuid4().hex[:8])
            created_at = existing.created_at if existing else now
            record = RuleRecord(
                id=rule_id,
                created_at=created_at,
                updated_at=now,
                status=status,
                tc_errors=list(tc_errors),
                variation_state=(existing.variation_state if existing else {}),
                **request.model_dump(exclude={"id"}),
            )
            self._rules = {rid: rule for rid, rule in self._rules.items() if rule.interface != record.interface or rid == rule_id}
            self._rules[rule_id] = record
            self._save()
            return record.model_copy(deep=True)

    def update_rule_state(
        self,
        rule_id: str,
        *,
        status: str | None = None,
        tc_errors: list[str] | None = None,
        variation_state: dict | None = None,
    ) -> Optional[RuleRecord]:
        with self._lock:
            record = self._rules.get(rule_id)
            if record is None:
                return None
            data = record.model_dump(mode="python")
            data["updated_at"] = time.time()
            if status is not None:
                data["status"] = status
            if tc_errors is not None:
                data["tc_errors"] = list(tc_errors)
            if variation_state is not None:
                data["variation_state"] = variation_state
            updated = RuleRecord.model_validate(data)
            self._rules[rule_id] = updated
            self._save()
            return updated.model_copy(deep=True)

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id not in self._rules:
                return False
            del self._rules[rule_id]
            self._save()
            return True
