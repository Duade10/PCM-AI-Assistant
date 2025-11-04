"""Slack Bolt application wiring for the PCM AI Assistant."""

from __future__ import annotations

import json
import logging
import re
from html import unescape
from typing import Dict, Iterable, List

from slack_bolt import App
from slack_sdk.errors import SlackApiError

from .config import BotConfig, apply_overrides
from .config_store import RuntimeConfigStore
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


def _format_for_slack(raw: str) -> str:
    """Return the raw response without Slack-specific formatting."""

    if not raw:
        return ""

    return unescape(str(raw))


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
    logger.info("Slack Bolt app initialized, verifying authentication")
    auth_response = app.client.auth_test()
    bot_user_id = auth_response["user_id"]
    logger.info("Authenticated as bot user %s", bot_user_id)
    config_store = RuntimeConfigStore()
    logger.debug("Loaded runtime overrides: %s", config_store.get_overrides())

    base_config = config

    def _current_config() -> BotConfig:
        return apply_overrides(base_config, config_store.get_overrides())

    active_config = _current_config()
    trigger_phrase = active_config.normalized_trigger
    if trigger_phrase:
        logger.info("Trigger phrase configured: '%s'", trigger_phrase)
    else:
        logger.info("No trigger phrase configured; relying on mentions only")

    def _collect_thread(event: Dict[str, str]) -> List[Dict[str, str]]:
        """Fetch the full thread history for the given event."""

        thread_ts = event.get("thread_ts") or event.get("ts")
        channel = event.get("channel")
        if not thread_ts or not channel:
            logger.debug(
                "Processing standalone event in channel %s with ts %s", channel, thread_ts
            )
            return [event]

        logger.debug("Fetching thread %s in channel %s", thread_ts, channel)
        try:
            response = app.client.conversations_replies(channel=channel, ts=thread_ts)
        except SlackApiError as exc:  # pragma: no cover - network failure handling
            logger.error("Failed to fetch conversation history: %s", exc)
            raise

        return response.get("messages", [])

    def _should_ignore(event: Dict[str, str]) -> bool:
        if event.get("subtype") in {"message_changed", "message_deleted", "message_replied"}:
            logger.debug("Ignoring event due to subtype %s", event.get("subtype"))
            return True
        if event.get("bot_id") or event.get("user") == bot_user_id:
            logger.debug("Ignoring bot/self message")
            return True
        return False

    def _handle_event(event: Dict[str, str], say) -> None:
        logger.info(
            "Handling event in channel %s (ts=%s)",
            event.get("channel"),
            event.get("ts"),
        )
        if _should_ignore(event):
            return

        try:
            thread_messages = _collect_thread(event)
            logger.debug("Collected %d messages from thread", len(thread_messages))
            runtime_config = _current_config()
            messages = _build_conversation_messages(
                thread_messages=thread_messages,
                bot_user_id=bot_user_id,
                system_prompt=runtime_config.system_prompt,
                trigger_phrase=runtime_config.normalized_trigger or trigger_phrase,
            )
            logger.debug("Prepared %d messages for LLM", len(messages))
            llm_client = LLMClient(runtime_config)
            reply = llm_client.generate_reply(messages)
            reply = _format_for_slack(reply)
            logger.debug("Generated reply with %d characters", len(reply))
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
            logger.debug("Replying in thread %s", event["thread_ts"])
        else:
            logger.debug("Replying in channel %s", event.get("channel"))
        say(reply, **reply_kwargs)
        logger.info("Reply sent")

    @app.event("url_verification")
    def handle_url_verification(body, ack):  # type: ignore[override]
        challenge = body.get("challenge")
        if challenge:
            ack({"challenge": challenge})
        else:  # pragma: no cover - defensive branch
            ack()

    @app.event("app_mention")
    def handle_app_mention(event, say):  # type: ignore[override]
        logger.debug("Received app_mention event: %s", event.get("ts"))
        _handle_event(event, say)

    if trigger_phrase:
        pattern = re.compile(rf"\b{re.escape(trigger_phrase)}\b", re.IGNORECASE)

        @app.message(pattern)
        def handle_trigger(message, say):  # type: ignore[override]
            if f"<@{bot_user_id}>" in (message.get("text") or ""):
                logger.debug("Skipping trigger because mention present")
                return
            logger.debug("Trigger phrase detected in message %s", message.get("ts"))
            _handle_event(message, say)

    @app.command("/pcm-config")
    def handle_config_command(ack, respond, command):  # type: ignore[override]
        ack()
        text = (command.get("text") or "").strip()
        logger.info("Received runtime configuration command: %s", text or "show")

        if not text or text.lower() == "show":
            template = config_store.build_template(_current_config())
            respond(
                response_type="ephemeral",
                text=(
                    "Here is the current runtime configuration template:\n"
                    f"```{template}```\n"
                    "Submit updates with `/pcm-config set {\"AI_PROVIDER\": \"openrouter\"}`.\n"
                    "Use JSON `null` or an empty string to remove an override, or run"
                    " `/pcm-config reset` to clear all overrides."
                ),
            )
            return

        if text.lower() == "reset":
            config_store.clear()
            respond(
                response_type="ephemeral",
                text="All runtime configuration overrides have been cleared.",
            )
            return

        if text.lower().startswith("set"):
            payload = text[3:].strip()
            if not payload:
                respond(
                    response_type="ephemeral",
                    text=(
                        "Please provide a JSON object after `set`. Example:\n"
                        "`/pcm-config set {\"AI_PROVIDER\": \"openrouter\"}`"
                    ),
                )
                return

            try:
                updates = json.loads(payload)
            except json.JSONDecodeError as exc:
                respond(
                    response_type="ephemeral",
                    text=f"Unable to parse JSON payload: {exc}",
                )
                return

            if not isinstance(updates, dict):
                respond(
                    response_type="ephemeral",
                    text="Configuration updates must be provided as a JSON object.",
                )
                return

            overrides = config_store.update(updates)
            logger.info("Runtime overrides updated: %s", overrides)
            template = config_store.build_template(_current_config())
            respond(
                response_type="ephemeral",
                text=(
                    "Configuration updated. Effective runtime settings:\n"
                    f"```{template}```"
                ),
            )
            return

        respond(
            response_type="ephemeral",
            text=(
                "Unrecognised configuration command. Use `/pcm-config`,"
                " `/pcm-config set { ... }`, or `/pcm-config reset`."
            ),
        )

    return app
