import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
import discord
from discord import app_commands
from discord.ext import commands
from agent import CivicAgent, IncidentReport, is_image

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DEV_GUILD_ID = int(os.getenv("DEV_GUILD_ID", "1384150666045558876"))

DATA_DIR = Path("data")
SETTINGS_FILE = DATA_DIR / "servers.json"
chroma_client = chromadb.PersistentClient(path="memory")
reports = chroma_client.get_or_create_collection(
    name="civic_reports",
    metadata={"description": "Public civic issue reports submitted through Discord"},
)
agent = CivicAgent()


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse {SETTINGS_FILE}: {exc}") from exc


def save_settings(settings: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def get_home_channel_id(guild_id: int) -> int | None:
    return load_settings().get(str(guild_id), {}).get("home_channel_id")


def set_home_channel_id(guild_id: int, channel_id: int | None) -> None:
    settings = load_settings()
    settings.setdefault(str(guild_id), {})
    if channel_id is None:
        settings[str(guild_id)].pop("home_channel_id", None)
    else:
        settings[str(guild_id)]["home_channel_id"] = channel_id
    save_settings(settings)


def store_report(
    *,
    analysis: IncidentReport,
    attachment: discord.Attachment,
    message: discord.Message | None,
    guild: discord.Guild | None,
    reporter_id: int,
    reporter_name: str,
    user_note: str,
) -> str:
    report_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        **analysis,
        "image_url": attachment.url,
        "source_message_url": message.jump_url if message else "",
        "guild_id": str(guild.id) if guild else "direct",
        "guild_name": guild.name if guild else "Direct message",
        "channel_id": str(message.channel.id) if message else "",
        "reporter_id": str(reporter_id),
        "reporter_name": reporter_name,
        "user_note": user_note[:1000],
        "created_at": created_at,
        "status": "open",
    }
    document = f"{analysis['category']}: {analysis['summary']}. {user_note}".strip()
    reports.add(ids=[report_id], documents=[document], metadatas=[metadata])
    return report_id


def public_reports(limit: int = 10) -> list[dict[str, Any]]:
    result = reports.get(
        limit=max(1, min(limit, 25)),
        include=["documents", "metadatas"],
    )
    rows = []
    for report_id, document, metadata in zip(
        result["ids"], result.get("documents", []), result.get("metadatas", [])
    ):
        rows.append({"id": report_id, "document": document, **metadata})
    return sorted(rows, key=lambda row: row.get("created_at", ""), reverse=True)


def format_report(row: dict[str, Any]) -> str:
    return (
        f"**{row['category'].replace('_', ' ').title()}** · {row['severity'].upper()} · "
        f"`{row['id'][:8]}`\n"
        f"{row['summary']}\n"
        f"[View image]({row['image_url']}) · Reported {row['created_at'][:10]}"
    )


async def create_report(
    attachment: discord.Attachment,
    message: discord.Message | None,
    guild: discord.Guild | None,
    reporter: discord.abc.User,
    user_note: str,
) -> tuple[str, IncidentReport]:
    analysis = await agent.analyze_attachment(attachment)
    report_id = await asyncio.to_thread(
        store_report,
        analysis=analysis,
        attachment=attachment,
        message=message,
        guild=guild,
        reporter_id=reporter.id,
        reporter_name=reporter.display_name,
        user_note=user_note,
    )
    return report_id, analysis


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    guild = discord.Object(id=DEV_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"Logged in as {bot.user} (id={bot.user.id})")
    print(f"Synced civic commands to guild {DEV_GUILD_ID}.")


@bot.tree.command(name="ping", description="Check if Civic Sense is online")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Civic Sense is online.", ephemeral=True)


@bot.tree.command(name="report", description="Analyze a civic issue photo and publish a report")
@app_commands.describe(
    image="Photo of the civic issue",
    note="Optional context, such as the street or nearest landmark",
)
async def report(
    interaction: discord.Interaction,
    image: discord.Attachment,
    note: str = "",
):
    await interaction.response.defer()
    try:
        report_id, analysis = await create_report(
            image, None, interaction.guild, interaction.user, note
        )
    except (ValueError, RuntimeError, discord.HTTPException) as exc:
        await interaction.followup.send(f"Could not create report: {exc}", ephemeral=True)
        return
    await interaction.followup.send(
        f"Report `{report_id[:8]}` published to the public civic database.\n"
        f"**{analysis['category'].replace('_', ' ').title()}** · {analysis['severity'].upper()}\n"
        f"{analysis['summary']}\n"
        f"Recommended action: {analysis['recommended_action']}"
    )


@bot.tree.command(name="issues", description="Browse the latest public civic reports")
@app_commands.describe(limit="Number of reports to show (1-10)")
async def issues(interaction: discord.Interaction, limit: app_commands.Range[int, 1, 10] = 5):
    rows = await asyncio.to_thread(public_reports, limit)
    if not rows:
        await interaction.response.send_message("No civic reports have been published yet.")
        return
    await interaction.response.send_message(
        "**Latest public civic reports**\n\n" + "\n\n".join(format_report(row) for row in rows)
    )


@bot.tree.command(name="set_home_channel", description="Analyze images posted in a channel automatically")
@app_commands.describe(channel="Channel to monitor for civic issue images")
async def set_home_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        await interaction.response.send_message("This command only works in a server.", ephemeral=True)
        return
    set_home_channel_id(interaction.guild.id, channel.id)
    await interaction.response.send_message(f"Automatic image analysis enabled in {channel.mention}.")


@bot.tree.command(name="disable_home_channel", description="Stop automatic image analysis in this server")
async def disable_home_channel(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command only works in a server.", ephemeral=True)
        return
    set_home_channel_id(interaction.guild.id, None)
    await interaction.response.send_message("Automatic image analysis disabled.", ephemeral=True)


@bot.tree.command(name="status", description="Show the public database and server configuration")
async def status(interaction: discord.Interaction):
    home_id = get_home_channel_id(interaction.guild.id) if interaction.guild else None
    count = await asyncio.to_thread(reports.count)
    await interaction.response.send_message(
        f"Public reports: **{count}**\n"
        f"Automatic channel: **{f'<#{home_id}>' if home_id else 'Not set'}**",
        ephemeral=True,
    )


async def should_analyze(message: discord.Message) -> bool:
    if message.author.bot or not message.guild or not message.attachments:
        return False
    if get_home_channel_id(message.guild.id) == message.channel.id:
        return True
    return bool(bot.user and bot.user in message.mentions)


@bot.event
async def on_message(message: discord.Message):
    if await should_analyze(message):
        images = [attachment for attachment in message.attachments if is_image(attachment)]
        if images:
            async with message.channel.typing():
                try:
                    report_id, analysis = await create_report(
                        images[0], message, message.guild, message.author, message.content
                    )
                    await message.reply(
                        f"Published civic report `{report_id[:8]}`: "
                        f"**{analysis['category'].replace('_', ' ').title()}** · "
                        f"{analysis['severity'].upper()}\n{analysis['summary']}"
                    )
                except (ValueError, RuntimeError, discord.HTTPException) as exc:
                    await message.reply(f"I could not analyze that image: {exc}")
    await bot.process_commands(message)


def main() -> None:
    if not TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN not set.")
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
