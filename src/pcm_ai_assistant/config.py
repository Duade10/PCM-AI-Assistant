"""Configuration utilities for the PCM AI Assistant."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from typing import Mapping, Optional


LOGGER = logging.getLogger(__name__)


# Mapping of environment variable names to BotConfig attributes that may be
# overridden at runtime through the configuration store.
OVERRIDABLE_ENV_VARS = {
    "AI_PROVIDER": "ai_provider",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_MODEL": "openai_model",
    "OPENROUTER_API_KEY": "openrouter_api_key",
    "OPENROUTER_MODEL": "openrouter_model",
    "OPENROUTER_BASE_URL": "openrouter_base_url",
}


@dataclass(frozen=True)
class BotConfig:
    """Configuration values required to run the assistant."""

    slack_bot_token: str
    slack_signing_secret: str
    slack_app_token: str
    trigger_phrase: str
    ai_provider: str
    openai_api_key: Optional[str]
    openai_model: Optional[str]
    openrouter_api_key: Optional[str]
    openrouter_model: Optional[str]
    openrouter_base_url: Optional[str]
    openrouter_referer: Optional[str]
    openrouter_title: Optional[str]
    system_prompt: Optional[str]

    @property
    def normalized_trigger(self) -> str:
        """Return the trigger phrase lower-cased for matching."""

        return (self.trigger_phrase or "").strip().lower()


def load_config() -> BotConfig:
    """Load configuration values from environment variables."""

    slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
    slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    slack_app_token = os.getenv("SLACK_APP_TOKEN")

    if not slack_bot_token:
        LOGGER.error("Missing SLACK_BOT_TOKEN environment variable")
        raise ValueError("SLACK_BOT_TOKEN must be set")
    if not slack_signing_secret:
        LOGGER.error("Missing SLACK_SIGNING_SECRET environment variable")
        raise ValueError("SLACK_SIGNING_SECRET must be set")
    if not slack_app_token:
        LOGGER.error("Missing SLACK_APP_TOKEN environment variable")
        raise ValueError("SLACK_APP_TOKEN must be set")

    trigger_phrase = os.getenv("TRIGGER_PHRASE", "pcmbot")
    ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
    LOGGER.debug("Using AI provider: %s", ai_provider)

    config = BotConfig(
        slack_bot_token=slack_bot_token,
        slack_signing_secret=slack_signing_secret,
        slack_app_token=slack_app_token,
        trigger_phrase=trigger_phrase,
        ai_provider=ai_provider,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        openrouter_model=os.getenv("OPENROUTER_MODEL"),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL"),
        openrouter_referer=os.getenv("OPENROUTER_REFERER"),
        openrouter_title=os.getenv("OPENROUTER_TITLE"),
        system_prompt=os.getenv("SYSTEM_PROMPT"),
    )
    LOGGER.info(
        "Configuration loaded (trigger='%s', ai_provider='%s')",
        trigger_phrase,
        ai_provider,
    )
    LOGGER.debug(
        "OpenAI credentials provided: %s | OpenRouter credentials provided: %s",
        bool(config.openai_api_key),
        bool(config.openrouter_api_key),
    )
    return config


def apply_overrides(config: BotConfig, overrides: Mapping[str, Optional[str]]) -> BotConfig:
    """Return a copy of ``config`` with supported overrides applied."""

    if not overrides:
        return config

    updates: dict[str, Optional[str]] = {}
    for env_key, attribute in OVERRIDABLE_ENV_VARS.items():
        if env_key not in overrides:
            continue
        value = overrides[env_key]
        if value is None:
            updates[attribute] = None
        else:
            updates[attribute] = str(value)

    if not updates:
        return config

    if "ai_provider" in updates and updates["ai_provider"]:
        updates["ai_provider"] = updates["ai_provider"].lower()

    new_config = replace(config, **updates)
    return new_config
