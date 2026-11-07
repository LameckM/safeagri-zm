"""Load SafeAgri's local backend configuration from backend/.env."""
import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(ENV_FILE, override=True)

DATABASE_PATH = Path(os.getenv("DB_PATH", str(BACKEND_DIR / "data" / "irrigation.db")))
OWNER_EMAIL = os.getenv("SAFEAGRI_OWNER_EMAIL", "owner@safeagri.local").strip().lower()
OWNER_PASSWORD = os.getenv("SAFEAGRI_OWNER_PASSWORD", "")
OWNER_NAME = os.getenv("SAFEAGRI_OWNER_NAME", "SafeAgri Owner").strip()
FARM_NAME = os.getenv("SAFEAGRI_FARM_NAME", "Kafubu Demonstration Farm").strip()
FARM_LOCATION = os.getenv("SAFEAGRI_FARM_LOCATION", "Kafubu Block, Luanshya").strip()

def owner_settings():
    """Read current owner settings after backend/.env has been loaded."""
    return {
        "email": os.getenv("SAFEAGRI_OWNER_EMAIL", "owner@safeagri.local").strip().lower(),
        "password": os.getenv("SAFEAGRI_OWNER_PASSWORD", ""),
        "full_name": os.getenv("SAFEAGRI_OWNER_NAME", "SafeAgri Owner").strip(),
        "farm_name": os.getenv("SAFEAGRI_FARM_NAME", "Kafubu Demonstration Farm").strip(),
        "location": os.getenv("SAFEAGRI_FARM_LOCATION", "Kafubu Block, Luanshya").strip(),
    }
