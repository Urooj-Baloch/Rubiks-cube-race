import asyncio
import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from . import config
from .cube import MOVE_DESCRIPTIONS, MOVES, SOLVED, apply_move, face_rows, inverse_move

QUESTION_INSTRUCTIONS = "Choose the single next move most likely to progress toward the solved cube."

SYSTEM_PROMPT = (
    "You are playing a 3x3 Rubik's Cube. The state is a 54-character facelet string in the order "
    "U, R, F, D, L, B (nine facelets per face, row by row as seen looking at that face from outside; "
    "U is read with the back edge at the top, D with the front edge at the top). "
    "Each character is the colour of that facelet named after the face whose centre has that colour. "
    "The cube is solved when each face contains a single character. "
    "Moves use standard notation: a letter turns that face clockwise by 90 degrees, a letter followed by an apostrophe "
    "turns it counterclockwise by 90 degrees, and a letter followed by 2 turns it by 180 degrees. "
    "Allowed moves: " + ", ".join(MOVES) + ". "
    "Reply with exactly one move as JSON of the form {\"move\": \"R'\"} and nothing else."
)


_last_call = [0.0]
_throttle_lock = None


async def throttle():
    global _throttle_lock
    if config.MIN_CALL_INTERVAL <= 0:
        return
    if _throttle_lock is None:
        _throttle_lock = asyncio.Lock()
    async with _throttle_lock:
        wait = _last_call[0] + config.MIN_CALL_INTERVAL - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call[0] = time.monotonic()


@dataclass
class Attempt:
    move: Optional[str] = None
    error: Optional[str] = None
    latency: float = 0.0
    confidence: Optional[float] = None
    probabilities: Optional[dict] = None
    cost: float = 0.0
    raw: Optional[str] = None


def build_state_payload(state, recent):
    return {"cube_facelets": state, "recent_moves": list(recent)}


def decisions_target():
    if config.LOCAL:
        return config.OLLAMA_SYSTEMONE_URL, {"Content-Type": "application/json"}
    return config.DECISIONS_URL, {
        "Authorization": "Bearer " + config.OPENROUTER_API_KEY,
        "Content-Type": "application/json",
        "X-Title": "Rubik's Cube Race",
    }


async def warm_up(client, model_id):
    try:
        await client.post(
            config.OLLAMA_URL + "/api/generate",
            json={"model": model_id, "keep_alive": config.OLLAMA_KEEP_ALIVE},
            timeout=config.LOAD_TIMEOUT,
        )
    except httpx.HTTPError:
        pass


class DecisionsAdapter:
    simulated = False

    def __init__(self, spec, client):
        self.spec = spec
        self.client = client

    def payload(self, state, recent):
        body = {
            "model": self.spec["id"],
            "state": build_state_payload(state, recent),
            "questions": {
                "next_move": {
                    "type": "choice",
                    "instructions": QUESTION_INSTRUCTIONS,
                    "criteria": dict(MOVE_DESCRIPTIONS),
                }
            },
        }
        if config.LOCAL:
            body["keep_alive"] = config.OLLAMA_KEEP_ALIVE
        return body

    async def prepare(self):
        if not config.LOCAL:
            return
        url, headers = decisions_target()
        for _ in range(2):
            try:
                resp = await self.client.post(url, headers=headers, json=self.payload(SOLVED, []), timeout=config.LOAD_TIMEOUT)
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass

    async def call(self, state, recent, ctx=None):
        await throttle()
        start = time.perf_counter()
        att = Attempt()
        try:
            url, headers = decisions_target()
            resp = await self.client.post(
                url,
                headers=headers,
                json=self.payload(state, recent),
                timeout=config.CALL_TIMEOUT,
            )
            att.latency = time.perf_counter() - start
            att.raw = resp.text[:2000]
            if resp.status_code != 200:
                att.error = "http_%d" % resp.status_code
                return att
            data = resp.json()
            ans = data["answers"]["next_move"]
            move = ans.get("choice")
            att.confidence = ans.get("confidence")
            att.probabilities = ans.get("probabilities")
            att.cost = float((data.get("usage") or {}).get("cost") or 0.0)
            if move in MOVES:
                att.move = move
            else:
                att.error = "invalid_move"
        except (httpx.TimeoutException, asyncio.TimeoutError):
            att.latency = time.perf_counter() - start
            att.error = "timeout"
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            att.latency = time.perf_counter() - start
            att.error = "malformed"
        except httpx.HTTPError as exc:
            att.latency = time.perf_counter() - start
            att.error = "network_" + type(exc).__name__
        return att


class ChatAdapter:
    simulated = False

    def __init__(self, spec, client):
        self.spec = spec
        self.client = client
        self.structured = True

    def body(self, state, recent, structured):
        user = json.dumps(
            {
                "cube_facelets": state,
                "faces": face_rows(state),
                "recent_moves": list(recent),
                "allowed_moves": list(MOVES),
            }
        )
        body = {
            "model": self.spec["id"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if structured:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "cube_move",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"move": {"type": "string", "enum": list(MOVES)}},
                        "required": ["move"],
                        "additionalProperties": False,
                    },
                },
            }
        return body

    async def _post(self, state, recent, structured):
        return await self.client.post(
            config.CHAT_URL,
            headers={
                "Authorization": "Bearer " + config.OPENROUTER_API_KEY,
                "Content-Type": "application/json",
                "X-Title": "Rubik's Cube Race",
            },
            json=self.body(state, recent, structured),
            timeout=config.CALL_TIMEOUT,
        )

    async def call(self, state, recent, ctx=None):
        await throttle()
        start = time.perf_counter()
        att = Attempt()
        try:
            resp = await self._post(state, recent, self.structured)
            if resp.status_code == 400 and self.structured:
                self.structured = False
                resp = await self._post(state, recent, False)
            att.latency = time.perf_counter() - start
            att.raw = resp.text[:2000]
            if resp.status_code != 200:
                att.error = "http_%d" % resp.status_code
                return att
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            att.cost = float((data.get("usage") or {}).get("cost") or 0.0)
            parsed = parse_move_json(content)
            move = parsed["move"]
            if move in MOVES:
                att.move = move
            else:
                att.error = "invalid_move"
        except (httpx.TimeoutException, asyncio.TimeoutError):
            att.latency = time.perf_counter() - start
            att.error = "timeout"
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            att.latency = time.perf_counter() - start
            att.error = "malformed"
        except httpx.HTTPError as exc:
            att.latency = time.perf_counter() - start
            att.error = "network_" + type(exc).__name__
        return att


def parse_move_json(content):
    text = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S)
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        pass
    for found in reversed(re.findall(r"\{[^{}]*\}", text)):
        try:
            obj = json.loads(found)
        except ValueError:
            continue
        if isinstance(obj, dict) and "move" in obj:
            return obj
    raise ValueError("no json object")


class OllamaChatAdapter:
    simulated = False

    def __init__(self, spec, client):
        self.spec = spec
        self.client = client
        self.structured = True
        self.think_off = True

    def body(self, state, recent):
        user = json.dumps(
            {
                "cube_facelets": state,
                "faces": face_rows(state),
                "recent_moves": list(recent),
                "allowed_moves": list(MOVES),
            }
        )
        body = {
            "model": self.spec["id"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "options": {"temperature": 0, "num_predict": config.OLLAMA_NUM_PREDICT},
        }
        if self.structured:
            body["format"] = {
                "type": "object",
                "properties": {"move": {"type": "string", "enum": list(MOVES)}},
                "required": ["move"],
            }
        if self.think_off:
            body["think"] = False
        return body

    async def prepare(self):
        await warm_up(self.client, self.spec["id"])

    async def _post(self, state, recent):
        return await self.client.post(config.OLLAMA_CHAT_URL, json=self.body(state, recent), timeout=config.CALL_TIMEOUT)

    async def call(self, state, recent, ctx=None):
        await throttle()
        start = time.perf_counter()
        att = Attempt()
        try:
            resp = await self._post(state, recent)
            for _ in range(2):
                if resp.status_code != 400:
                    break
                text = resp.text.lower()
                if "think" in text and self.think_off:
                    self.think_off = False
                elif self.structured:
                    self.structured = False
                else:
                    break
                resp = await self._post(state, recent)
            att.latency = time.perf_counter() - start
            att.raw = resp.text[:2000]
            if resp.status_code != 200:
                att.error = "http_%d" % resp.status_code
                return att
            data = resp.json()
            content = data["message"]["content"]
            parsed = parse_move_json(content)
            move = parsed["move"]
            if move in MOVES:
                att.move = move
            else:
                att.error = "invalid_move"
        except (httpx.TimeoutException, asyncio.TimeoutError):
            att.latency = time.perf_counter() - start
            att.error = "timeout"
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            att.latency = time.perf_counter() - start
            att.error = "malformed"
        except httpx.HTTPError as exc:
            att.latency = time.perf_counter() - start
            att.error = "network_" + type(exc).__name__
        return att


SIM_PROFILES = {
    "jev": {"p": 0.62, "lat": (0.08, 0.22), "bad": 0.0},
    "luna": {"p": 0.55, "lat": (0.12, 0.30), "bad": 0.0},
    "clef": {"p": 0.45, "lat": (0.05, 0.15), "bad": 0.0},
    "opus": {"p": 0.92, "lat": (1.6, 4.2), "bad": 0.04},
    "qwen": {"p": 0.78, "lat": (0.9, 2.4), "bad": 0.03},
    "deepseek": {"p": 0.85, "lat": (2.0, 5.0), "bad": 0.05},
    "gemma": {"p": 0.6, "lat": (0.5, 1.4), "bad": 0.03},
}


class SimulatedAdapter:
    simulated = True

    def __init__(self, spec, seed):
        self.spec = spec
        self.profile = SIM_PROFILES.get(spec["key"], SIM_PROFILES["opus"])
        self.rng = random.Random("%s:%s" % (seed, spec["key"]))

    async def call(self, state, recent, ctx=None):
        lo, hi = self.profile["lat"]
        latency = self.rng.uniform(lo, hi) * config.SIM_LATENCY_SCALE
        await asyncio.sleep(latency)
        att = Attempt(latency=latency)
        if self.rng.random() < self.profile["bad"]:
            att.error = "malformed"
            att.raw = "simulated malformed output"
            return att
        oracle = (ctx or {}).get("oracle") or []
        if oracle and self.rng.random() < self.profile["p"]:
            move = oracle[0]
        else:
            move = self.rng.choice(MOVES)
        probs = {m: 0.01 for m in MOVES}
        probs[move] = 0.82
        total = sum(probs.values())
        att.move = move
        att.confidence = round(probs[move] / total, 3)
        att.probabilities = {m: round(v / total, 4) for m, v in probs.items()}
        return att


def update_oracle(oracle, move):
    if oracle and oracle[0] == move:
        return oracle[1:]
    return [inverse_move(move)] + oracle


@dataclass
class ModelEntry:
    spec: dict
    adapter: object
    simulated: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def key(self):
        return self.spec["key"]

    @property
    def label(self):
        return self.spec["label"] + (" (sim)" if self.simulated else "")

    @property
    def category(self):
        return self.spec["category"]


def build_entries(mode, client, seed, keys=None):
    entries = []
    for spec in config.MODEL_SPECS:
        if keys and spec["key"] not in keys:
            continue
        if mode == "sim":
            entries.append(ModelEntry(spec, SimulatedAdapter(spec, seed), simulated=True))
        elif spec["interface"] == "decisions":
            entries.append(ModelEntry(spec, DecisionsAdapter(spec, client)))
        elif config.LOCAL:
            entries.append(ModelEntry(spec, OllamaChatAdapter(spec, client)))
        else:
            entries.append(ModelEntry(spec, ChatAdapter(spec, client)))
    return entries
