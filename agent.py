import asyncio
import base64
import json
import os
from pathlib import Path
from typing import TypedDict

import discord
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MAX_IMAGE_BYTES = 10 * 1024 * 1024
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
REPORT_CATEGORIES = {
    "pothole",
    "streetlight",
    "waste",
    "flooding",
    "road_damage",
    "sidewalk",
    "graffiti",
    "other",
}
SEVERITIES = {"low", "medium", "high", "critical"}


class IncidentReport(TypedDict):
    category: str
    summary: str
    severity: str
    location_hint: str
    recommended_action: str


VISION_PROMPT = """Analyze this civic issue photo for a public community report.
Return valid JSON only with exactly these keys:
category (one of pothole, streetlight, waste, flooding, road_damage, sidewalk, graffiti, other),
summary (one concise sentence),
severity (one of low, medium, high, critical),
location_hint (a visible landmark or "not visible"),
recommended_action (one concise sentence).
Do not identify or guess any person's identity. If the image is not a civic issue,
use category "other", severity "low", and explain that in summary."""


def is_image(attachment: discord.Attachment) -> bool:
    content_type = attachment.content_type or ""
    return content_type.startswith("image/") or Path(attachment.filename).suffix.lower() in (
        SUPPORTED_IMAGE_EXTENSIONS
    )


class CivicAgent:
    """Validates civic images and turns them into structured incident reports."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.model = model or os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-chat")
        self.client = (
            OpenAI(
                api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
                base_url=base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
            if api_key or os.getenv("DEEPSEEK_API_KEY")
            else None
        )

    async def analyze_attachment(self, attachment: discord.Attachment) -> IncidentReport:
        if not is_image(attachment):
            raise ValueError("Please attach a JPG, PNG, WEBP, or GIF image.")
        if attachment.size > MAX_IMAGE_BYTES:
            raise ValueError("That image is larger than the 10 MB processing limit.")

        image_bytes = await attachment.read(use_cached=True)
        content_type = attachment.content_type or "image/jpeg"
        return await asyncio.to_thread(self._analyze_image, image_bytes, content_type)

    def _analyze_image(self, image_bytes: bytes, content_type: str) -> IncidentReport:
        if self.client is None:
            raise RuntimeError("DeepSeek is not configured. Set DEEPSEEK_API_KEY in .env.")

        encoded = base64.b64encode(image_bytes).decode("ascii")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a careful civic issue classifier."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
            temperature=0.1,
            max_tokens=300,
        )
        return self._parse_report(response.choices[0].message.content or "")

    @staticmethod
    def _parse_report(content: str) -> IncidentReport:
        content = content.strip()
        if content.startswith("```") and content.endswith("```"):
            content = (
                content.removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("DeepSeek returned invalid report data.") from exc

        required = set(IncidentReport.__annotations__)
        if not required.issubset(parsed) or not all(
            isinstance(parsed[key], str) and parsed[key].strip() for key in required
        ):
            raise RuntimeError("DeepSeek returned an incomplete report.")
        if parsed["category"] not in REPORT_CATEGORIES:
            parsed["category"] = "other"
        if parsed["severity"] not in SEVERITIES:
            parsed["severity"] = "low"
        return {key: parsed[key].strip() for key in required}

