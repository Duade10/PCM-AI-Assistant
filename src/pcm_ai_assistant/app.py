"""Entrypoint helpers for running the PCM AI Assistant."""

from __future__ import annotations

import logging
import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .config import BotConfig, load_config
from .slack_app import create_app


LOGGER = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure application-wide logging for terminal visibility."""

    if logging.getLogger().handlers:
        return

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    LOGGER.debug("Logging configured with level %s", logging.getLevelName(level))


def build_app() -> App:
    """Build the Slack Bolt application using environment configuration."""

    _configure_logging()
    LOGGER.info("Building Slack application")
    config = load_config()
    app = create_app(config)
    LOGGER.info("Slack application created")
    return app


def main() -> None:
    """Entry point used by the `python -m` invocation."""

    _configure_logging()
    LOGGER.info("Starting PCM AI Assistant")
    config = load_config()
    app = create_app(config)
    LOGGER.info("Starting Slack Bolt Socket Mode handler")
    handler = SocketModeHandler(app, config.slack_app_token)
    handler.start()


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
