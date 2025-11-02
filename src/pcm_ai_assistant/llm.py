"""Language model helpers for the PCM AI Assistant."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List

from openai import OpenAI

from .config import BotConfig


LOGGER = logging.getLogger(__name__)


class LLMClient:
    """Wrapper that abstracts over the supported language model providers."""

    def __init__(self, config: BotConfig):
        provider = config.ai_provider.lower()

        LOGGER.info("Initializing LLM client for provider '%s'", provider)

        if provider not in {"openai", "openrouter"}:
            raise ValueError(
                "AI_PROVIDER must be either 'openai' or 'openrouter', got %s" % provider
            )

        if provider == "openai":
            if not config.openai_api_key:
                raise ValueError("OPENAI_API_KEY must be set when AI_PROVIDER=openai")
            self._client = OpenAI(api_key=config.openai_api_key)
            self._model = config.openai_model or "gpt-4o-mini"
            LOGGER.debug("Configured OpenAI model '%s'", self._model)
        else:
            if not config.openrouter_api_key:
                raise ValueError(
                    "OPENROUTER_API_KEY must be set when AI_PROVIDER=openrouter"
                )
            base_url = config.openrouter_base_url or "https://openrouter.ai/api/v1"
            headers: Dict[str, str] = {}
            if config.openrouter_referer:
                headers["HTTP-Referer"] = config.openrouter_referer
            if config.openrouter_title:
                headers["X-Title"] = config.openrouter_title

            self._client = OpenAI(
                api_key=config.openrouter_api_key,
                base_url=base_url,
                default_headers=headers or None,
            )
            self._model = config.openrouter_model or "openrouter/auto"
            LOGGER.debug(
                "Configured OpenRouter model '%s' with base URL '%s'", self._model, base_url
            )

    def generate_reply(self, messages: Iterable[Dict[str, str]]) -> str:
        """Generate a reply from the configured large language model."""

        payload: List[Dict[str, str]] = list(messages)
        if not payload:
            raise ValueError("No messages provided for completion")

        LOGGER.info("Requesting completion with %d messages", len(payload))
        response = self._client.chat.completions.create(
            model=self._model,
            messages=payload,
        )
        choice = response.choices[0]
        if not choice.message or not choice.message.content:
            raise RuntimeError("Received empty response from language model")
        reply = choice.message.content.strip()
        LOGGER.debug("Received response with %d characters", len(reply))
        return reply
