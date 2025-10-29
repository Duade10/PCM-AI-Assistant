"""Slack Bolt application wiring for the PCM AI Assistant."""

from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List

from slack_bolt import App
from slack_sdk.errors import SlackApiError

from .config import BotConfig
from .llm import LLMClient

logger = logging.getLogger(__name__)


def _strip_triggers(text: str, bot_user_id: str, trigger_phrase: str) -> str:
    """Remove bot mentions and trigger phrases from the provided text."""

    cleaned = text or ""
    if bot_user_id:
        mention_pattern = re.compile(rf"<@{re.escape(bot_user_id)}>\s*", re.IGNORECASE)
        cleaned = mention_pattern.sub("", cleaned)
    if trigger_phrase:
        trigger_pattern = re.compile(rf"\b{re.escape(trigger_phrase)}\b", re.IGNORECASE)
        cleaned = trigger_pattern.sub("", cleaned)
    return cleaned.strip()


def _build_conversation_messages(
    *,
    thread_messages: Iterable[Dict[str, str]],
    bot_user_id: str,
    system_prompt: str | None,
    trigger_phrase: str,
) -> List[Dict[str, str]]:
    """Convert Slack thread messages into the OpenAI chat format."""

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt.strip()})

    for message in thread_messages:
        text = _strip_triggers(message.get("text", ""), bot_user_id, trigger_phrase)
        if not text:
            text = (message.get("text") or "").strip()
        if not text:
            continue
        is_bot_message = (
            message.get("bot_id")
            or message.get("subtype") == "bot_message"
            or message.get("user") == bot_user_id
        )
        role = "assistant" if is_bot_message else "user"
        messages.append({"role": role, "content": text})

    if not messages:
        raise ValueError("No usable messages found in the Slack thread")

    return messages


def create_app(config: BotConfig) -> App:
    """Create and configure the Slack Bolt application."""

    app = App(token=config.slack_bot_token, signing_secret=config.slack_signing_secret)
    auth_response = app.client.auth_test()
    bot_user_id = auth_response["user_id"]
    llm_client = LLMClient(config)
    trigger_phrase = config.normalized_trigger

    def _collect_thread(event: Dict[str, str]) -> List[Dict[str, str]]:
        """Fetch the full thread history for the given event."""

        thread_ts = event.get("thread_ts") or event.get("ts")
        channel = event.get("channel")
        if not thread_ts or not channel:
            return [event]

        try:
            response = app.client.conversations_replies(channel=channel, ts=thread_ts)
        except SlackApiError as exc:  # pragma: no cover - network failure handling
            logger.error("Failed to fetch conversation history: %s", exc)
            raise

        return response.get("messages", [])

    def _should_ignore(event: Dict[str, str]) -> bool:
        if event.get("subtype") in {"message_changed", "message_deleted", "message_replied"}:
            return True
        if event.get("bot_id") or event.get("user") == bot_user_id:
            return True
        return False

    def _handle_event(event: Dict[str, str], say) -> None:
        if _should_ignore(event):
            return

        try:
            thread_messages = _collect_thread(event)
            messages = _build_conversation_messages(
                thread_messages=thread_messages,
                bot_user_id=bot_user_id,
                system_prompt=config.system_prompt,
                trigger_phrase=trigger_phrase,
            )
            reply = llm_client.generate_reply(messages)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to process message: %s", exc)
            say(
                "I'm sorry, I couldn't process that request right now.",
                thread_ts=event.get("thread_ts") or None,
            )
            return

        reply_kwargs: Dict[str, str] = {}
        if event.get("thread_ts"):
            reply_kwargs["thread_ts"] = event["thread_ts"]
        say(reply, **reply_kwargs)

    @app.event("url_verification")
    def handle_url_verification(body, ack):  # type: ignore[override]
        challenge = body.get("challenge")
        if challenge:
            ack({"challenge": challenge})
        else:  # pragma: no cover - defensive branch
            ack()

    @app.event("app_mention")
    def handle_app_mention(event, say):  # type: ignore[override]
        _handle_event(event, say)

    if trigger_phrase:
        pattern = re.compile(rf"\b{re.escape(trigger_phrase)}\b", re.IGNORECASE)

        @app.message(pattern)
        def handle_trigger(message, say):  # type: ignore[override]
            if f"<@{bot_user_id}>" in (message.get("text") or ""):
                return
            _handle_event(message, say)

    return app
