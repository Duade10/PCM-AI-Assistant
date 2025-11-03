"""Helpers for persisting runtime configuration overrides."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Dict, Mapping, Optional

from .config import BotConfig, OVERRIDABLE_ENV_VARS, apply_overrides


LOGGER = logging.getLogger(__name__)

# Default location for storing runtime overrides. The path lives alongside the
# project source so that deployments can persist updates across restarts.
DEFAULT_OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "runtime_config.json"


class RuntimeConfigStore:
    """Persist and expose supported runtime configuration overrides."""

    def __init__(self, path: Optional[Path | str] = None):
        self._path = Path(path) if path else DEFAULT_OVERRIDES_PATH
        self._lock = Lock()
        self._overrides: Dict[str, str] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                for key, value in data.items():
                    if not isinstance(key, str):
                        continue
                    canonical = key.upper()
                    if canonical in OVERRIDABLE_ENV_VARS and isinstance(value, str):
                        self._overrides[canonical] = value
            LOGGER.debug("Loaded %d runtime overrides", len(self._overrides))
        except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - defensive
            LOGGER.warning("Failed to load runtime overrides: %s", exc)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(self._overrides, indent=2, sort_keys=True)
        self._path.write_text(serialized, encoding="utf-8")
        LOGGER.debug("Runtime overrides written to %s", self._path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_overrides(self) -> Dict[str, str]:
        """Return a copy of the currently stored overrides."""

        with self._lock:
            return dict(self._overrides)

    def clear(self) -> None:
        """Remove all overrides from disk and memory."""

        with self._lock:
            self._overrides.clear()
            try:
                if self._path.exists():
                    self._path.unlink()
            except OSError as exc:  # pragma: no cover - defensive
                LOGGER.warning("Failed to remove runtime overrides file: %s", exc)

    def update(self, updates: Mapping[str, object]) -> Dict[str, str]:
        """Persist supported overrides and return the resulting override set."""

        normalised: Dict[str, Optional[str]] = {}
        for key, value in updates.items():
            canonical = key.upper()
            if canonical not in OVERRIDABLE_ENV_VARS:
                LOGGER.warning("Ignoring unsupported override key '%s'", key)
                continue
            if value is None:
                normalised[canonical] = None
            elif isinstance(value, str):
                trimmed = value.strip()
                normalised[canonical] = trimmed or None
            else:
                normalised[canonical] = str(value)

        if not normalised:
            return self.get_overrides()

        with self._lock:
            changed = False
            for key, value in normalised.items():
                if not value:
                    if key in self._overrides:
                        del self._overrides[key]
                        changed = True
                    continue
                if self._overrides.get(key) != value:
                    self._overrides[key] = value
                    changed = True

            if changed:
                self._save()

            return dict(self._overrides)

    def build_template(self, base_config: BotConfig) -> str:
        """Return a JSON template showing the effective runtime configuration."""

        effective_config = apply_overrides(base_config, self.get_overrides())
        payload: Dict[str, Optional[str]] = {}
        for env_key, attribute in OVERRIDABLE_ENV_VARS.items():
            value = getattr(effective_config, attribute)
            payload[env_key] = value or ""

        return json.dumps(payload, indent=2, sort_keys=True)
