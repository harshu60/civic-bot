import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL")
AI_VISION_MODEL = os.getenv("AI_VISION_MODEL")
DATA_DIR = Path(os.getenv("CIVIC_DATA_DIR", "data"))
MEMORY_DIR = Path(os.getenv("CIVIC_MEMORY_DIR", "memory"))
SERVER_SETTINGS_FILE = DATA_DIR / "server_settings.json"

AMC_NAME = "Amravati Municipal Corporation"
AMC_WEBSITE = "http://www.amtcorp.org/"
AMC_GRIEVANCE_PORTAL = "https://crm.amravaticorporation.in/"
AMC_WHATSAPP_NUMBER = "+917030782345"
AMC_EMAIL = "amravaticorporation@yahoo.in"
AMC_ADDRESS = "Rajkamal Square, Amravati, Maharashtra 444601, India"
AMC_DEPARTMENT_BY_CATEGORY = {
    "pothole": "Roads and Works",
    "road_damage": "Roads and Works",
    "sidewalk": "Roads and Works",
    "streetlight": "Electrical",
    "waste": "Sanitation",
    "flooding": "Water Supply and Drainage",
    "graffiti": "Sanitation and Encroachment",
    "other": "General Administration",
}
