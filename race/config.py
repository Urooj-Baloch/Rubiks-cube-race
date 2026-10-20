import os

from dotenv import load_dotenv

load_dotenv()


def _f(name, default):
    return float(os.getenv(name, default))


def _i(name, default):
    return int(os.getenv(name, default))


def _b(name, default):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


BACKEND = os.getenv("BACKEND", "openrouter").strip().lower()
LOCAL = BACKEND == "ollama"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
DECISIONS_URL = os.getenv("OPENROUTER_DECISIONS_URL", "https://openrouter.ai/api/alpha/decisions")
CHAT_URL = os.getenv("OPENROUTER_CHAT_URL", "https://openrouter.ai/api/v1/chat/completions")
MODELS_URL = os.getenv("OPENROUTER_MODELS_URL", "https://openrouter.ai/api/v1/models")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").strip().rstrip("/")
OLLAMA_SYSTEMONE_URL = OLLAMA_URL + "/v1/systemone"
OLLAMA_CHAT_URL = OLLAMA_URL + "/api/chat"
OLLAMA_TAGS_URL = OLLAMA_URL + "/api/tags"
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
LOAD_TIMEOUT = float(os.getenv("LOAD_TIMEOUT_SECONDS", "900"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "400"))

MAX_MOVES = _i("MAX_MOVES", 30)
CALL_TIMEOUT = _f("CALL_TIMEOUT_SECONDS", 180 if LOCAL else 60)
MAX_RETRIES = _i("MAX_RETRIES", 2)
TRIAL_TIME_LIMIT = _f("TRIAL_TIME_LIMIT_SECONDS", 900 if LOCAL else 300)
RECENT_MOVES = _i("RECENT_MOVES", 6)
SIM_LATENCY_SCALE = _f("SIM_LATENCY_SCALE", 1.0)
SEQUENTIAL = _b("SEQUENTIAL", "1" if LOCAL else "0")

STUDENT_NAME = os.getenv("STUDENT_NAME", "Urooj Baloch")
STUDENT_ROLL = os.getenv("STUDENT_ROLL", "23K-0071")

_DEFAULTS = [
    ("jev", "Jev 1.13", "Decision model", "decisions", "typesafe/jev-1.13"),
    ("luna", "GPT-6 Luna Decisions", "Decision model", "decisions", "openai/gpt-6-luna-decisions"),
    ("clef", "Cloudflare Clef", "Decision model", "decisions", "cloudflare/clef"),
    ("opus", "Claude Opus 5.5", "Frontier LLM", "chat", "anthropic/claude-opus-5.5"),
]

_OLLAMA_DEFAULTS = [
    ("clef", "Clef Flash", "Decision model", "decisions", "clef-flash", None),
    ("qwen", "Qwen", "Frontier LLM", "chat", "qwen3.5", "anthropic/claude-opus-5.5"),
    ("deepseek", "DeepSeek", "Frontier LLM", "chat", "deepseek-r1", "anthropic/claude-opus-5.5"),
    ("gemma", "Gemma", "Frontier LLM", "chat", "gemma3", "anthropic/claude-opus-5.5"),
]


def _build_specs():
    specs = []
    for key, label, category, interface, default_id in _DEFAULTS:
        model_id = os.getenv("MODEL_" + key.upper(), default_id).strip() or default_id
        iface = os.getenv("INTERFACE_" + key.upper(), interface).strip() or interface
        substitute = model_id != default_id
        specs.append(
            {
                "key": key,
                "label": (model_id + " [substitute for " + label + "]") if substitute else label,
                "short": model_id.split("/")[-1] if substitute else label,
                "category": category,
                "interface": iface,
                "id": model_id,
                "default_id": default_id,
                "substitute": substitute,
            }
        )
    return specs


def _build_ollama_specs():
    specs = []
    for key, name, category, interface, tag, replaces in _OLLAMA_DEFAULTS:
        model_id = os.getenv("OLLAMA_MODEL_" + key.upper(), tag).strip() or tag
        specs.append(
            {
                "key": key,
                "label": "%s (%s)" % (name, model_id),
                "short": name,
                "category": category,
                "interface": interface,
                "id": model_id,
                "default_id": replaces or model_id,
                "substitute": replaces is not None,
            }
        )
    return specs


MODEL_SPECS = _build_ollama_specs() if LOCAL else _build_specs()
MIN_CALL_INTERVAL = _f("MIN_SECONDS_BETWEEN_CALLS", 0)
BACKOFF_SECONDS = _f("RATE_LIMIT_BACKOFF_SECONDS", 8)


def live_ready():
    return LOCAL or bool(OPENROUTER_API_KEY)


def live_name():
    return "Ollama (local)" if LOCAL else "OpenRouter"


TIERS = {
    "warmup": {"min": 3, "max": 4, "count": 2},
    "primary": {"min": 4, "max": 5, "count": 10},
    "extension": {"min": 15, "max": 20, "count": 3},
}
