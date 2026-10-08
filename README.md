# Civic Sense Bot

Civic Sense is a Discord bot for reporting local problems such as potholes,
broken streetlights, flooding, waste, graffiti, and sidewalk damage. A photo is
classified by a DeepSeek vision-capable model and saved in a shared ChromaDB
collection that anyone using the bot can browse with `/issues`.

## Features

- `/report`: analyze and publish a civic issue photo, with optional location context.
- `/issues`: show the latest public reports and their image links.
- Automatic analysis for images posted in a configured home channel.
- `/status`, `/ping`, `/set_home_channel`, and `/disable_home_channel`.
- Persistent local database in `memory/` and server settings in `data/servers.json`.

## Architecture

- [`agent.py`](./agent.py) owns image attachment validation, DeepSeek vision
  requests, and strict parsing of the structured incident report.
- [`bot.py`](./bot.py) owns Discord commands/events and public ChromaDB
  persistence.

## Setup

1. Install Python 3.10 or newer.
2. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Create a `.env` file:

   ```env
   DISCORD_BOT_TOKEN=your_discord_bot_token
   DEEPSEEK_API_KEY=your_deepseek_api_key
   # Use the vision-capable model enabled for your DeepSeek-compatible endpoint.
   DEEPSEEK_VISION_MODEL=deepseek-chat
   # Optional: defaults to https://api.deepseek.com
   DEEPSEEK_BASE_URL=https://api.deepseek.com
   # Optional: guild where slash commands are synced immediately during development.
   DEV_GUILD_ID=1384150666045558876
   ```

4. Enable the **Message Content Intent** for the bot in the Discord Developer
   Portal if automatic home-channel analysis is needed.
5. Start the bot:

   ```bash
   python bot.py
   ```

The bot must have permission to view channels, read message history, send
messages, and use slash commands.

## Public data and privacy

Reports are intentionally public. The database stores the DeepSeek-generated
summary, category, severity, timestamps, Discord source links, reporter display
name, optional note, and the original Discord attachment URL. Do not submit
private, sensitive, or identifying images. Discord attachment URLs can be
accessible to anyone who receives them.

The local `memory/` directory is the database and should be backed up if reports
must survive redeployment. It is ignored by Git so reports remain on the running
host only unless you explicitly back up that directory.

## Development notes

DeepSeek-compatible vision endpoints must support OpenAI-style
`image_url` message content. If your provider uses a different model name,
change `DEEPSEEK_VISION_MODEL` without changing the bot code.
