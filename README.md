# PCM AI Assistant

A Slack bot built with Slack Bolt (Python) that replies when mentioned or when a configurable trigger phrase is used. The assistant can talk in channels or threads, pulling the full thread history for additional context, and it supports both OpenAI and OpenRouter as back-end language model providers.

## Features

- Responds only when directly mentioned (e.g. `@pcm-ai-assistant`) or when a configurable trigger phrase (default: `pcmbot`) is present in the message.
- Thread-aware replies: when invoked in a thread the assistant reads the entire thread to answer with full context.
- Pluggable AI provider supporting OpenAI or OpenRouter via environment configuration.
- Simple `.env` based setup with an example configuration.

## Getting started

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Create your environment file**

   Copy the example file and fill in the required secrets and options:

   ```bash
   cp .env.example .env
   ```

   Required values:

   - `SLACK_BOT_TOKEN` – the bot user OAuth token.
   - `SLACK_SIGNING_SECRET` – the signing secret from your Slack app.
   - `TRIGGER_PHRASE` – optional keyword that will also trigger the bot (default `pcmbot`).
   - `AI_PROVIDER` – set to `openai` or `openrouter`.
   - Provider specific API keys and model names (`OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, ...).

3. **Run the bot**

   ```bash
   python app.py
   ```

   By default the bot listens on port `3000`. Override this by setting the `PORT` environment variable in your `.env` file.

## Slack setup tips

- Enable the `app_mention` and `message.channels` events in your Slack app configuration so the bot receives mentions and channel messages.
- If you want the bot to respond in direct messages, also enable `message.im` events.
- When using OpenRouter it is recommended to set the optional `OPENROUTER_REFERER` and `OPENROUTER_TITLE` values.
