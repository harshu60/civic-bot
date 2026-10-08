import asyncio
import json
from typing import Any
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ext import commands
from agent import CivicAgent, IncidentReport, is_image
from config import (
    AMC_DEPARTMENT_BY_CATEGORY,
    AMC_ADDRESS,
    AMC_EMAIL,
    AMC_GRIEVANCE_PORTAL,
    AMC_LOCALITIES,
    AMC_NAME,
    AMC_WEBSITE,
    AMC_WHATSAPP_NUMBER,
    DATA_DIR,
    DEV_GUILD_ID,
    DISCORD_BOT_TOKEN,
    WARDS_FILE,
)
from ticket import TicketStore

agent = CivicAgent()
ticket_store = TicketStore()


def load_wards() -> dict[str, Any]:
    if not WARDS_FILE.exists():
        return {}
    try:
        return json.loads(WARDS_FILE.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise RuntimeError(f"Could not parse {WARDS_FILE}: {exc}") from exc


def save_wards(wards: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WARDS_FILE.write_text(json.dumps(wards, indent=2), encoding="utf-8")


def get_ward(guild_id: int) -> dict[str, Any]:
    return load_wards().get(str(guild_id), {})


def set_home_channel_id(guild_id: int, channel_id: int | None) -> None:
    wards = load_wards()
    wards.setdefault(str(guild_id), {})
    if channel_id is None:
        wards[str(guild_id)].pop("home_channel_id", None)
    else:
        wards[str(guild_id)]["home_channel_id"] = channel_id
    save_wards(wards)


def get_home_channel_id(guild_id: int) -> int | None:
    return get_ward(guild_id).get("home_channel_id")


def department_for(category: str, ward: dict[str, Any]) -> str:
    return str(
        ward.get("municipal_department")
        or AMC_DEPARTMENT_BY_CATEGORY.get(category, AMC_DEPARTMENT_BY_CATEGORY["other"])
    )


def authority_for(note: str, ward: dict[str, Any]) -> str:
    configured = ward.get("authority")
    if configured:
        return str(configured)
    normalized_note = note.lower()
    if any(locality in normalized_note for locality in AMC_LOCALITIES):
        return AMC_NAME
    return "Local authority not identified"


def whatsapp_url(
    *,
    category: str,
    summary: str,
    location: str,
) -> str:
    message = (
        f"Hello, I would like to report a {category.replace('_', ' ')} issue.\n"
        f"Issue: {summary}\n"
        f"Location: {location}\n"
        "Please advise on the next steps."
    )
    return f"https://wa.me/{AMC_WHATSAPP_NUMBER.lstrip('+')}?text={quote(message)}"


def whatsapp_action_label(category: str) -> str:
    if category in {"waste", "flooding"}:
        return "Request cleanup"
    return "Report to AMC"


def category_label(category: str) -> str:
    return category.replace("_", " ").title()


def format_report(row: dict[str, Any]) -> str:
    location = row.get("user_note") or row.get("location_hint") or "Not provided"
    authority = row.get("authority", "Local authority not identified")
    department = row.get("municipal_department") or department_for(row["category"], row)
    whatsapp = whatsapp_url(
        category=row["category"],
        summary=row["summary"],
        location=location,
    )
    return (
        f"### {category_label(row['category'])} · {row.get('status', 'open').title()}\n"
        f"> {row['summary']}\n\n"
        f"**Location:** {location}\n"
        f"**Department:** {department}\n"
        f"**Reported:** {row['created_at'][:10]}\n\n"
        f"[{whatsapp_action_label(row['category'])}]({whatsapp}) · "
        f"[View image]({row['image_url']}) · Ticket `{row['id'][:8]}`"
    )


def can_edit_ticket(interaction: discord.Interaction, ticket: dict[str, Any]) -> bool:
    if interaction.user.id == int(ticket["reporter_id"]):
        return True
    return bool(
        interaction.guild
        and isinstance(interaction.user, discord.Member)
        and interaction.user.guild_permissions.manage_guild
    )


async def create_report(
    attachment: discord.Attachment,
    message: discord.Message | None,
    guild: discord.Guild | None,
    reporter: discord.abc.User,
    user_note: str,
) -> tuple[str, IncidentReport]:
    analysis = await agent.analyze_attachment(attachment, user_note)
    ward = dict(get_ward(guild.id if guild else 0))
    ward.setdefault("authority", authority_for(user_note, ward))
    if ward["authority"] == AMC_NAME:
        ward.setdefault("complaint_portal", AMC_GRIEVANCE_PORTAL)
    report_id = await asyncio.to_thread(
        ticket_store.create,
        analysis=analysis,
        attachment=attachment,
        message=message,
        guild=guild,
        reporter_id=reporter.id,
        reporter_name=reporter.display_name,
        user_note=user_note,
        ward=ward,
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
    ward = get_ward(interaction.guild.id if interaction.guild else 0)
    location = note.strip() or analysis["location_hint"]
    authority = authority_for(note, ward)
    department = department_for(analysis["category"], ward)
    whatsapp = whatsapp_url(
        category=analysis["category"],
        summary=analysis["summary"],
        location=location,
    )
    await interaction.followup.send(
        f"## Report published\n"
        f"**{category_label(analysis['category'])}** · `{report_id[:8]}`\n\n"
        f"> {analysis['summary']}\n\n"
        f"**Location:** {location}\n"
        f"**Authority:** {authority}\n"
        f"**Department:** {department}\n\n"
        f"**Next steps**\n"
        f"- [AMC grievance portal]({AMC_GRIEVANCE_PORTAL})\n"
        f"- [{whatsapp_action_label(analysis['category'])}]({whatsapp})\n"
        f"- {analysis['recommended_action']}"
    )


@bot.tree.command(name="contacts", description="Show official AMC contact channels")
async def contacts(interaction: discord.Interaction):
    await interaction.response.send_message(
        "## Official AMC contacts\n"
        f"**Website:** {AMC_WEBSITE}\n"
        f"**Grievance portal:** {AMC_GRIEVANCE_PORTAL}\n"
        f"**WhatsApp:** https://wa.me/{AMC_WHATSAPP_NUMBER.lstrip('+')}\n"
        f"**Email:** `{AMC_EMAIL}`\n"
        f"**Address:** {AMC_ADDRESS}\n\n"
        "_WhatsApp links open a pre-filled draft. Review it and press Send._",
        ephemeral=True,
    )


@bot.tree.command(name="issues", description="Browse the latest public civic reports")
@app_commands.describe(limit="Number of reports to show (1-10)")
async def issues(interaction: discord.Interaction, limit: app_commands.Range[int, 1, 10] = 5):
    rows = await asyncio.to_thread(ticket_store.public, limit)
    if not rows:
        await interaction.response.send_message(
            "## No reports yet\nNo civic reports have been published."
        )
        return
    await interaction.response.send_message(
        "## Latest civic reports\n\n" + "\n\n".join(format_report(row) for row in rows)
    )


@bot.tree.command(name="edit_ticket", description="Edit a civic ticket you reported")
@app_commands.describe(
    ticket="Full ticket ID or the first 8 characters",
    note="Replacement public note",
    status="open, in_progress, resolved, or rejected",
    severity="low, medium, high, or critical",
)
async def edit_ticket(
    interaction: discord.Interaction,
    ticket: str,
    note: str | None = None,
    status: str | None = None,
    severity: str | None = None,
):
    current = await asyncio.to_thread(ticket_store.find, ticket)
    if current is None:
        await interaction.response.send_message("Ticket not found.", ephemeral=True)
        return
    if not can_edit_ticket(interaction, current):
        await interaction.response.send_message(
            "Only the reporter or a server moderator can edit this ticket.", ephemeral=True
        )
        return
    changes: dict[str, str] = {}
    if note is not None:
        changes["user_note"] = note[:1000]
    if status is not None:
        if status not in {"open", "in_progress", "resolved", "rejected"}:
            await interaction.response.send_message(
                "Status must be open, in_progress, resolved, or rejected.", ephemeral=True
            )
            return
        changes["status"] = status
    if severity is not None:
        if severity not in {"low", "medium", "high", "critical"}:
            await interaction.response.send_message(
                "Severity must be low, medium, high, or critical.", ephemeral=True
            )
            return
        changes["severity"] = severity
    if not changes:
        await interaction.response.send_message(
            "Provide at least one field to change: note, status, or severity.", ephemeral=True
        )
        return
    updated = await asyncio.to_thread(ticket_store.update, current["id"], changes)
    await interaction.response.send_message(
        f"## Ticket updated\n"
        f"`{updated['id'][:8]}` is now **{updated['status'].replace('_', ' ').title()}**."
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


@bot.tree.command(name="configure_ward", description="Configure this server's ward and municipal dispatch routing")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(
    ward_number="Municipal ward number",
    locality="Locality or area, for example East Badnera",
    authority="Responsible local authority; defaults to Amravati Municipal Corporation",
    municipal_department="Optional override for the automatically selected AMC department",
    dispatch_channel="Channel for future internal dispatch notifications",
)
async def configure_ward(
    interaction: discord.Interaction,
    ward_number: str,
    locality: str,
    authority: str | None = None,
    municipal_department: str | None = None,
    dispatch_channel: discord.TextChannel | None = None,
):
    if not interaction.guild:
        await interaction.response.send_message("This command only works in a server.", ephemeral=True)
        return
    wards = load_wards()
    ward = wards.setdefault(str(interaction.guild.id), {})
    ward["ward_number"] = ward_number.strip()
    ward["locality"] = locality.strip()
    ward["authority"] = (authority or AMC_NAME).strip()
    ward["complaint_portal"] = AMC_GRIEVANCE_PORTAL
    if municipal_department is not None:
        ward["municipal_department"] = municipal_department.strip()
    if dispatch_channel is not None:
        ward["dispatch_channel_id"] = dispatch_channel.id
    save_wards(wards)
    dispatch_id = ward.get("dispatch_channel_id")
    dispatch_text = dispatch_channel.mention if dispatch_channel else (
        f"<#{dispatch_id}>" if dispatch_id else "Not configured (optional)"
    )
    await interaction.response.send_message(
        "## Jurisdiction saved\n"
        f"**Locality:** {locality}\n"
        f"**Ward:** {ward_number}\n"
        f"**Authority:** {ward['authority']}\n"
        f"**Department:** {municipal_department or 'Automatic AMC routing'}\n"
        f"**Dispatch channel:** {dispatch_text}",
        ephemeral=True,
    )


@bot.tree.command(name="status", description="Show the public database and server configuration")
async def status(interaction: discord.Interaction):
    ward = get_ward(interaction.guild.id) if interaction.guild else {}
    home_id = ward.get("home_channel_id")
    dispatch_id = ward.get("dispatch_channel_id")
    count = await asyncio.to_thread(ticket_store.count)
    await interaction.response.send_message(
        "## Civic Sense status\n"
        f"**Public reports:** {count}\n"
        f"**Ward:** {ward.get('ward_number') or 'Not set'}\n"
        f"**Department:** {ward.get('municipal_department') or 'Automatic routing'}\n"
        f"**Automatic channel:** {f'<#{home_id}>' if home_id else 'Not set'}\n"
        f"**Authority:** {ward.get('authority') or AMC_NAME}\n"
        f"**AMC grievance portal:** {ward.get('complaint_portal') or AMC_GRIEVANCE_PORTAL}",
        ephemeral=True,
    )


async def should_analyze(message: discord.Message) -> bool:
    if message.author.bot or not message.guild or not message.attachments:
        return False
    if get_home_channel_id(message.guild.id) == message.channel.id:
        return True
    return bool(bot.user and bot.user in message.mentions)


async def is_bot_conversation(message: discord.Message) -> bool:
    if not bot.user:
        return False
    if bot.user in message.mentions:
        return True
    if message.reference and message.reference.message_id:
        try:
            referenced = message.reference.resolved or await message.channel.fetch_message(
                message.reference.message_id
            )
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            return False
        return isinstance(referenced, discord.Message) and referenced.author.id == bot.user.id
    return False


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
                    location = message.content or analysis["location_hint"]
                    whatsapp = whatsapp_url(
                        category=analysis["category"],
                        summary=analysis["summary"],
                        location=location,
                    )
                    await message.reply(
                        f"## Report published\n"
                        f"**{category_label(analysis['category'])}** · `{report_id[:8]}`\n\n"
                        f"> {analysis['summary']}\n\n"
                        f"**Location:** {location}\n"
                        f"**Authority:** "
                        f"{authority_for(message.content, get_ward(message.guild.id))}\n"
                        f"**Department:** "
                        f"{department_for(analysis['category'], get_ward(message.guild.id))}\n\n"
                        f"[{whatsapp_action_label(analysis['category'])}]({whatsapp})"
                    )
                except (ValueError, RuntimeError, discord.HTTPException) as exc:
                    await message.reply(f"I could not analyze that image: {exc}")
    elif await is_bot_conversation(message):
        prompt = message.content
        if bot.user:
            prompt = prompt.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "")
        try:
            async with message.channel.typing():
                await message.reply(await agent.respond_to_text(prompt))
        except (RuntimeError, discord.HTTPException) as exc:
            await message.reply(f"I could not answer that: {exc}")
    await bot.process_commands(message)


def main() -> None:
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN not set.")
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
