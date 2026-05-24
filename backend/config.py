import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env in the root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Data and Paths
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "assistive_system.db")))
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(DATA_DIR / "models" / "emotion_model.h5")))

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", 60))

# DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_URL = os.getenv("DEEPSEEK_URL", "https://api.deepseek.com/chat/completions")

# Detection and monitoring
LOW_CONFIDENCE_THRESHOLD = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", 0.65))
ENABLE_PRIVACY_MODE = os.getenv("ENABLE_PRIVACY_MODE", "false").lower() == "true"
STRESS_EMOTIONS = {"fear", "sad", "angry"}
REMOTE_STREAM_MAX_AGE_SECONDS = 10

# Trend windows
HR_TREND_WINDOW_SECONDS = 60
TEACHER_WATCHLIST_WINDOW_SECONDS = 300
DOCTOR_TREND_WINDOW_SECONDS = 120
DOCTOR_SUSTAINED_ALERT_SECONDS = 120
SMOOTHING_WINDOW_SIZE = 5 # 5 frames for temporal consistency
