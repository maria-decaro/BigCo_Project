import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview") 
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4.20-reasoning")

MAX_DISCOVERIES_PER_PROVIDER = 4
DISCOVERY_CONFIDENCE_THRESHOLD = 0.45
CONSENSUS_ACCEPT_THRESHOLD = 0.65