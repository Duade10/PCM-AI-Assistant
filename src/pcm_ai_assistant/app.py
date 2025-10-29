"""Entrypoint helpers for running the PCM AI Assistant."""

from __future__ import annotations

from slack_bolt import App

from .config import BotConfig, load_config
from .slack_app import create_app


def build_app() -> App:
    """Build the Slack Bolt application using environment configuration."""

    config = load_config()
    return create_app(config)


def main() -> None:
    """Entry point used by the `python -m` invocation."""

    config = load_config()
    app = create_app(config)
    app.start(port=config.port)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
