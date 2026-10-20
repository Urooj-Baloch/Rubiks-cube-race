import httpx

from . import config


def check_ollama(timeout=5.0):
    try:
        resp = httpx.get(config.OLLAMA_TAGS_URL, timeout=timeout)
        resp.raise_for_status()
        names = {m.get("name", "") for m in resp.json().get("models", [])}
    except (httpx.HTTPError, ValueError):
        return (
            "Cannot reach Ollama at %s. Install and start Ollama (the app must be running), then try again."
            % config.OLLAMA_URL
        )
    missing = []
    for spec in config.MODEL_SPECS:
        tag = spec["id"]
        if tag not in names and (tag + ":latest") not in names:
            missing.append(tag)
    if missing:
        return "Models not downloaded yet. Run: " + " && ".join("ollama pull " + m for m in missing)
    return None


def check_backend():
    if config.LOCAL:
        return check_ollama()
    if not config.OPENROUTER_API_KEY:
        return "OPENROUTER_API_KEY is not set"
    return None
