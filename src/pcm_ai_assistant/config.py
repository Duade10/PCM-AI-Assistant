"""Configuration utilities for the PCM AI Assistant."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BotConfig:
    """Configuration values required to run the assistant."""

    slack_bot_token: str
    slack_signing_secret: str
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
    port: int

    @property
    def normalized_trigger(self) -> str:
        """Return the trigger phrase lower-cased for matching."""

        return (self.trigger_phrase or "").strip().lower()


def load_config() -> BotConfig:
    """Load configuration values from environment variables."""

    slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
    slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")

    if not slack_bot_token:
        raise ValueError("SLACK_BOT_TOKEN must be set")
    if not slack_signing_secret:
        raise ValueError("SLACK_SIGNING_SECRET must be set")

    trigger_phrase = os.getenv("TRIGGER_PHRASE", "pcmbot")
    ai_provider = os.getenv("AI_PROVIDER", "openai").lower()

    port_str = os.getenv("PORT", "3000")
    try:
        port = int(port_str)
    except ValueError as exc:
        raise ValueError("PORT must be an integer") from exc

    return BotConfig(
        slack_bot_token=slack_bot_token,
        slack_signing_secret=slack_signing_secret,
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
        port=port,
    )
