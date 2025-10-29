"""Run the PCM AI Assistant Slack Bolt application."""

from __future__ import annotations

from dotenv import load_dotenv

from src.pcm_ai_assistant.app import main


if __name__ == "__main__":
    load_dotenv()
    main()
