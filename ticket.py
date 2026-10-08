import uuid
from datetime import datetime, timezone
from typing import Any

import chromadb
import discord

from agent import IncidentReport
from config import AMC_NAME, MEMORY_DIR


class TicketStore:
    """Persistent public civic incident tickets backed by ChromaDB."""

    def __init__(self, path=MEMORY_DIR):
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(
            name="civic_reports",
            metadata={"description": "Public civic issue reports submitted through Discord"},
        )

    def create(
        self,
        *,
        analysis: IncidentReport,
        attachment: discord.Attachment,
        message: discord.Message | None,
        guild: discord.Guild | None,
        reporter_id: int,
        reporter_name: str,
        user_note: str,
        ward: dict[str, Any] | None = None,
    ) -> str:
        ticket_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        ward = ward or {}
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
            "ward_number": str(ward.get("ward_number", "")),
            "municipal_department": str(ward.get("municipal_department", "")),
            "dispatch_channel_id": str(ward.get("dispatch_channel_id", "")),
            "authority": str(ward.get("authority", AMC_NAME)),
            "complaint_portal": str(ward.get("complaint_portal", "")),
            "locality": str(ward.get("locality", "")),
        }
        document = f"{analysis['category']}: {analysis['summary']}. {user_note}".strip()
        self.collection.add(ids=[ticket_id], documents=[document], metadatas=[metadata])
        return ticket_id

    def public(self, limit: int = 10) -> list[dict[str, Any]]:
        result = self.collection.get(
            limit=max(1, min(limit, 25)),
            include=["documents", "metadatas"],
        )
        rows = []
        for ticket_id, document, metadata in zip(
            result["ids"], result.get("documents", []), result.get("metadatas", [])
        ):
            rows.append({"id": ticket_id, "document": document, **metadata})
        return sorted(rows, key=lambda row: row.get("created_at", ""), reverse=True)

    def find(self, ticket_reference: str) -> dict[str, Any] | None:
        reference = ticket_reference.strip().lower()
        result = self.collection.get(include=["documents", "metadatas"])
        for ticket_id, document, metadata in zip(
            result["ids"], result.get("documents", []), result.get("metadatas", [])
        ):
            if ticket_id.lower() == reference or ticket_id.lower().startswith(reference):
                return {"id": ticket_id, "document": document, **metadata}
        return None

    def update(self, ticket_id: str, changes: dict[str, str]) -> dict[str, Any] | None:
        current = self.find(ticket_id)
        if current is None:
            return None
        metadata = {key: value for key, value in current.items() if key not in {"id", "document"}}
        metadata.update(changes)
        document = f"{metadata['category']}: {metadata['summary']}. {metadata.get('user_note', '')}".strip()
        self.collection.update(ids=[current["id"]], documents=[document], metadatas=[metadata])
        return {"id": current["id"], "document": document, **metadata}

    def count(self) -> int:
        return self.collection.count()
