import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the parent directory (project root)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# --- LLM / OpenAI-compatible API ------------------------------------------
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.llm-wolof.live/v1")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "galsenai-chat")

# --- Database --------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "sqlite+aiosqlite:///./data/attaya.db"
)

# --- Game balance constants ------------------------------------------------
STARTING_HEALTH: int = 100
MAX_ROUNDS: int = 15

FOOD_CONSUMPTION_PER_ROUND: int = 1
WATER_CONSUMPTION_PER_ROUND: int = 1

NO_FOOD_DAMAGE: int = 10
NO_WATER_DAMAGE: int = 15

MEDICINE_HEAL: int = 20
SHELTER_DAMAGE_REDUCTION: float = 0.5

STARTING_RESOURCES: dict = {
    "ndox": 3,   # water
    "lekk": 3,   # food
    "garab": 1,  # medicine
    "mbëj": 1,   # shelter
    "paxal": 0,  # weapon
    "xaalis": 10,  # money (CFA francs concept)
}

SCAVENGE_MIN: int = 1
SCAVENGE_MAX: int = 3

REPUTATION_TRADE_BONUS: int = 5
REPUTATION_BETRAY_PENALTY: int = 15
REPUTATION_VOTE_PENALTY: int = 5

API_CALL_DELAY_MS: int = 2000
API_TIMEOUT_MS: int = 30000

# Boat mode constants
BOAT_MAX_ROUNDS = 10
BOAT_STARTING_XAALIS = 15
BOAT_STARTING_PAXAL = 1
BOAT_STARTING_GARAB = 1
BOAT_SCAVENGE_XAALIS_MIN = 0
BOAT_SCAVENGE_XAALIS_MAX = 3
BOAT_SCAVENGE_PAXAL_CHANCE = 0.15  # 15% chance to find a weapon each round
BOAT_SCAVENGE_GARAB_CHANCE = 0.10  # 10% chance to find antidote
BOAT_BRIBE_INFLUENCE = 2  # Each xaalis spent adds weight to briber's preferred vote
BOAT_STEAL_AMOUNT = 5
