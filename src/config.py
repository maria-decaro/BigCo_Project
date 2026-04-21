import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY", "")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview") 
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4.20-reasoning")

def _parse_max_discoveries(raw_value: str):
    text = (raw_value or "").strip().lower()
    if text in {"", "none", "null", "all", "unlimited", "0", "-1"}:
        return None
    value = int(text)
    if value < 1:
        return None
    return value


MAX_DISCOVERIES_PER_PROVIDER = _parse_max_discoveries(
    os.getenv("MAX_DISCOVERIES_PER_PROVIDER", "none")
)
DISCOVERY_CONFIDENCE_THRESHOLD = 0.45
CONSENSUS_ACCEPT_THRESHOLD = 0.65
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "5"))
