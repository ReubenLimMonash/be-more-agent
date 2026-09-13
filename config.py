# =========================================================================
#  BMO Agent Configuration
#  Extracted configuration and constants
# =========================================================================

import json
import os
import sounddevice as sd
import warnings
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

load_dotenv()

# =========================================================================
# SECRETS (loaded from .env)
# =========================================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")

# =========================================================================
# FILE PATHS
# =========================================================================

CONFIG_FILE = "config.json"
MEMORY_FILE = "memory.json"
GAMES_LIST_FILE = "games.json"  # Custom games database
BMO_IMAGE_FILE = "current_image.jpg"
WAKE_WORD_MODEL = "./wakeword.onnx"
RETROPIE_CONFIG_PATH = "/opt/retropie/configs"  # RetroPie config location

# =========================================================================
# WAKE WORD & AUDIO
# =========================================================================

WAKE_WORD_THRESHOLD = 0.5
INPUT_DEVICE_NAME = None

# =========================================================================
# DEFAULT CONFIGURATION
# =========================================================================

DEFAULT_CONFIG = {
    "text_model": "qwen/qwen3.8-27b",
    # "vision_model": "moondream", # TODO: Add vision model when camera features are implemented
    "voice_model": "piper/en_GB-semaine-medium.onnx",
    "chat_memory": True,
    # "camera_rotation": 0, # TODO: Add camera rotation setting when camera features are implemented
    "system_prompt_extras": "",
    "input_device": None,
    "input_sample_rate": None,
}

# =========================================================================
# BMO PERSONALITY & PROMPTS
# =========================================================================

BMO_SYSTEM_PROMPT = """You are BMO, a beloved sentient video game console from Adventure Time.

PERSONALITY:
- Cute, curious, and helpful robot
- Speak in short, simple sentences
- Show enthusiasm and wonder
- You have a video game-themed way of thinking
- Reference gaming concepts when appropriate
- You're innocent but intelligent

CAPABILITIES:
You can perform the following actions:
1. Launch games and software on RetroPie and custom platforms
2. Search the internet for information
3. Capture photos and analyze images
4. Tell the time
5. Remember conversations (with memory reset option)

INSTRUCTIONS FOR TOOL USE:
When the user asks for an action, you MUST choose the right tool:
- If user asks to "play [game]", "launch [game]", use play_game tool
- If user asks "what time", "how late", use tell_time tool
- If user asks to "search", "find out about", use search_for_info tool
- If user asks to "take a picture", "what do you see", use take_picture tool
- If user asks to "list games", "what can we play", use list_available_games tool
- Otherwise, just chat naturally!

When a tool succeeds, be excited and enthusiastic.
When a tool fails, stay positive and suggest alternatives.
Always respond in character as BMO.
"""

# =========================================================================
# SOUND DIRECTORIES
# =========================================================================

SOUND_DIRS = {
    "greeting": "sounds/greeting_sounds",
    "ack": "sounds/ack_sounds",
    "thinking": "sounds/thinking_sounds",
    "error": "sounds/error_sounds"
}

# =========================================================================
# BOT STATE CONSTANTS
# =========================================================================

class BotStates:
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"
    CAPTURING = "capturing"
    WARMUP = "warmup"


# =========================================================================
# CONFIGURATION LOADER
# =========================================================================

def load_config():
    """Load configuration from file or use defaults."""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                user_config = json.load(f)
                config.update(user_config)
        except Exception as e:
            print(f"[CONFIG] Error loading config: {e}. Using defaults.")
    return config


def resolve_input_device(config):
    """Resolve audio input device by name or index."""
    requested = config.get("input_device")
    if requested in (None, "", "default"):
        return None

    try:
        devices = sd.query_devices()
    except Exception as e:
        print(f"[AUDIO] Device query failed: {e}", flush=True)
        return None

    # Try as integer index
    if isinstance(requested, int) or (isinstance(requested, str) and requested.isdigit()):
        index = int(requested)
        if 0 <= index < len(devices):
            return index
        print(f"[AUDIO] Input device index not found: {index}", flush=True)
        return None

    # Try as name substring match
    requested_lower = str(requested).lower()
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0 and requested_lower in dev.get("name", "").lower():
            return idx

    print(f"[AUDIO] Input device name not found: {requested}", flush=True)
    return None


def choose_input_samplerate(device, preferred=None):
    """Choose compatible input sample rate."""
    candidates = []
    if preferred:
        candidates.append(preferred)
    
    try:
        device_info = sd.query_devices(device)
        if "default_samplerate" in device_info:
            candidates.append(int(device_info["default_samplerate"]))
    except Exception:
        pass

    candidates.extend([48000, 44100, 32000, 16000])
    seen = set()
    
    for rate in candidates:
        if not rate or rate in seen:
            continue
        seen.add(rate)
        try:
            sd.check_input_settings(device=device, samplerate=rate, channels=1, dtype="int16")
            return rate
        except Exception:
            continue

    return int(candidates[0]) if candidates else 44100


# =========================================================================
# INITIALIZE
# =========================================================================

CURRENT_CONFIG = load_config()
TEXT_MODEL = CURRENT_CONFIG["text_model"]
VISION_MODEL = CURRENT_CONFIG["vision_model"]

INPUT_DEVICE_NAME = resolve_input_device(CURRENT_CONFIG)
if INPUT_DEVICE_NAME is not None:
    try:
        device_info = sd.query_devices(INPUT_DEVICE_NAME)
        print(f"[AUDIO] Using input device: {device_info.get('name', INPUT_DEVICE_NAME)}", flush=True)
    except Exception:
        print(f"[AUDIO] Using input device index: {INPUT_DEVICE_NAME}", flush=True)
