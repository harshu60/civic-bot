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
KONARK_WARD_CONTACTS = (
    (1, "Aniket Mallhe", "9970629517", "Parikshit Gorle", "7558417462"),
    (2, "Ashish Sahare", "7030940231", "Rohit Hadale", "7030940242"),
    (3, "Shahu Javanjal", "7020516122", "Imran Khan", "8485027964"),
    (4, "Avesh Sheikh", "7030940251", "Atil Aqil Ahmed", "8983461146"),
    (5, "Nikhil Khangale", "8668454381", "Manish Nakwal", "7030940228"),
    (6, "Meghraj Dendwal", "8766486063", "Syed Asrarul Haq", "7020811041"),
    (7, "Anjikya Javanjal", "7276752423", "Dhaniram Kalose", "7030922934"),
    (8, "Sunil Chorapagar", "7030922942", "Shailesh Dongre", "7030940230"),
    (9, "Mohit Jadhav", "7030940235", "Nilesh Tambole", "9511796783"),
    (10, "Sanjay Mahurkar", "8788280598", "Vinod Tank", "7030922951"),
    (11, "Manish Hadale", "7030922921", "Prasad Kulkarni", "7030922966"),
    (12, "Shakti Piwal", "8446644931", "Yogesh Kundare", "7030922907"),
    (13, "Mithun Usre", "7030940237", "Prashant Gavner", "7030922928"),
    (14, "Jivan Rathod", "7030940233", "Dharmendra Dike", "9069671212"),
    (15, "Sagar Ingole", "9555858930", "Vilas Dendule", "8530576157"),
    (16, "Pathak Harmkar", "8459319359", "Aniket Luke", "7030922966"),
    (17, "Dipak Sangle", "7030922943", "Darshan Deshmukh", "9823344712"),
    (18, "Mithun Waghmare", "9405300177", "Pawan Chaware", "8237301884"),
    (19, "Sopan Mahurkar", "7030940252", "Mithun Chaware", "8308637965"),
    (20, "Sagar Rajurkar", "7030940224", "Vaibhav Kharad", "9960597664"),
    (21, "Pravin Usre", "9834553855", "Dinesh Shindhane", "7030922954"),
    (22, "Priyanka Bais", "9823178712", "Sumedh Meshram", "7030940247"),
)
KONARK_ZONE_CONTACTS = (
    ("North zone", "Nandkishor Tikhile", "7030922889", "Rohit Sangle", "8766914002"),
    ("Central zone", "Bhushan Pustakar", "7030922880", "Lakhan Raj", "9922475619"),
    ("East zone", "Nitin Lolde", "9096589789", "Shubham Hajare", "9130895513"),
    ("South zone", "Dhananjay Shinde", "7030922919", "Rohit Lakre", "8600237002"),
    ("West zone", "M. R. Shahale", "8806377599", "Manish Choule", "9822991922"),
)
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
