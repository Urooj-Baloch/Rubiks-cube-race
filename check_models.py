import sys

import httpx

from race import config
from race.preflight import check_ollama


def main():
    if config.LOCAL:
        problem = check_ollama()
        for spec in config.MODEL_SPECS:
            print("%-14s %-10s %s" % (spec["id"], spec["interface"], "assigned" if not spec["substitute"] else "stand-in for the frontier LLM"))
        if problem:
            print(problem)
            sys.exit(2)
        print("Ollama is running and all models are downloaded")
        return
    if not config.OPENROUTER_API_KEY:
        print("OPENROUTER_API_KEY is not set")
        sys.exit(2)
    r = httpx.get(config.MODELS_URL, headers={"Authorization": "Bearer " + config.OPENROUTER_API_KEY}, timeout=30)
    r.raise_for_status()
    available = {m["id"] for m in r.json().get("data", [])}
    for spec in config.MODEL_SPECS:
        ok = spec["id"] in available
        print("%-34s %-10s %s" % (spec["id"], spec["interface"], "listed" if ok else "NOT LISTED on /models (decisions models may be absent from this list; verify on the model page)"))


if __name__ == "__main__":
    main()
