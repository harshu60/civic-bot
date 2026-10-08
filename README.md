# Civic Sense Bot

Civic Sense is an Amravati-focused Discord bot for reporting local problems such as potholes,
broken streetlights, flooding, waste, graffiti, and sidewalk damage. A photo is
classified by an OpenAI-compatible vision model and saved in a shared ChromaDB
collection that anyone using the bot can browse with `/issues`.

## Features

- `/report`: analyze and publish a civic issue photo, using the note as location
  and incident context.
- `/issues`: show the latest public reports and their image links.
- `/edit_ticket`: let the reporter or a server moderator update a ticket's note,
  status, or severity.
- Automatic analysis for images posted in a configured home channel.
- `/status`, `/ping`, `/contacts`, `/set_home_channel`, `/disable_home_channel`, and
  administrator-only `/configure_ward`.
- Persistent local database in `memory/` and ward routing in `data/wards.json`.
- Amravati Municipal Corporation routing for roads, electrical, sanitation,
  water/drainage, health, fire-safety, and general civic issues.
- User notes are passed to the vision agent, stored with the ticket, and shown
  as location context. The configured municipal department and dispatch channel
  are shown on the published report.
- `/contacts` shows official AMC website, grievance portal, WhatsApp, email,
  and office address.
- Mention the bot or reply to one of its messages to ask a civic question
  without using a slash command. It does not respond to ordinary chat messages.

## Architecture

- [`agent.py`](./agent.py) owns image attachment validation, OpenAI-compatible
  vision requests, and strict parsing of the structured incident report.
- [`bot.py`](./bot.py) owns Discord commands/events and public ChromaDB
  persistence.
- [`config.py`](./config.py) is the single environment-backed configuration
  module; secrets are never stored in source control.
- [`ticket.py`](./ticket.py) owns public incident-ticket persistence.
- [`data/wards.json`](./data/wards.json) maps each Discord server to its ward,
  municipal department, home channel, and optional dispatch channel.

## Setup

1. Install Python 3.10 or newer.
2. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in the real credentials:

   ```env
   DISCORD_BOT_TOKEN=your_discord_bot_token
   AI_API_KEY=your_provider_api_key
   # OpenAI-compatible API endpoint supplied by your provider.
   AI_BASE_URL=https://your-provider.example/v1
   AI_VISION_MODEL=your-vision-model
   # Optional: guild where slash commands are synced immediately during development.
   DEV_GUILD_ID=1384150666045558876
   ```

   `.env` is ignored by Git and must never be committed. The values in the
   example above are placeholders.

4. Enable the **Message Content Intent** for the bot in the Discord Developer
   Portal if automatic home-channel analysis is needed.
5. Start the bot:

   ```bash
   python bot.py
   ```

The bot must have permission to view channels, read message history, send
messages, and use slash commands.

## Amravati setup

The bot is configured for **Amravati Municipal Corporation (AMC)**. Set the
actual AMC ward number for your server with:

```text
/configure_ward ward_number: 12
```

The bot then routes reports by category, for example potholes to Roads and
Works, waste to Sanitation, and flooding to Water Supply and Drainage. The
official corporation site is [amravaticorporation.in](https://amravaticorporation.in/).

`dispatch_channel_id` is optional. It means a private Discord channel inside
your server where future internal notifications can be sent; it is not an AMC
phone number, email address, or government dispatch system. Leave it empty until
you create such a channel.

The official AMC complaint system is [AMC Complaint Request Entry](https://crm.amravaticorporation.in/).

The `/contacts` command provides only the official AMC channels supplied for
this bot: the AMC website, grievance portal, business WhatsApp, email, and
office address. Individual contacts and third-party services are excluded.
After a report is created, the bot provides an official AMC WhatsApp link with
the report details pre-filled. WhatsApp still requires the user to review and
press **Send**; the bot does not send messages automatically.

## Public data and privacy

Reports are intentionally public. The database stores the model-generated
summary, category, severity, timestamps, Discord source links, reporter display
name, optional note, and the original Discord attachment URL. Do not submit
private, sensitive, or identifying images. Discord attachment URLs can be
accessible to anyone who receives them.

The local `memory/` directory is the database and should be backed up if reports
must survive redeployment. It is ignored by Git so reports remain on the running
host only unless you explicitly back up that directory.

## Development notes

The configured endpoint must support OpenAI-style `image_url` message content.
To switch providers, change `AI_API_KEY`, `AI_BASE_URL`, and `AI_VISION_MODEL`
without changing the bot code.
