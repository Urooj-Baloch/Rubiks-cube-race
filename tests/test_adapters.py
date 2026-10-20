import asyncio
import json

import httpx

from race import config
from race.cube import MOVES, SOLVED
from race.models import ChatAdapter, DecisionsAdapter
from race.runner import play_trial
from race.models import ModelEntry

SPEC_D = {"key": "jev", "label": "Jev 1.13", "category": "Decision model", "interface": "decisions", "id": "typesafe/jev-1.13"}
SPEC_C = {"key": "opus", "label": "Claude Opus 5.5", "category": "Frontier LLM", "interface": "chat", "id": "anthropic/claude-opus-5.5"}


def run(coro):
    return asyncio.run(coro)


def decisions_client(choice):
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "typesafe/jev-1.13"
        q = body["questions"]["next_move"]
        assert q["type"] == "choice" and set(q["criteria"]) == set(MOVES)
        assert len(body["state"]["cube_facelets"]) == 54
        return httpx.Response(
            200,
            json={"answers": {"next_move": {"type": "choice", "choice": choice, "confidence": 0.7, "probabilities": {choice: 0.7}}}, "usage": {"cost": 0.00001}},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_decisions_adapter_valid_move():
    async def go():
        async with decisions_client("R'") as c:
            a = await DecisionsAdapter(SPEC_D, c).call(SOLVED, [])
            return a

    a = run(go())
    assert a.move == "R'" and a.error is None and a.confidence == 0.7 and a.cost > 0


def test_decisions_adapter_invalid_move_is_flagged():
    async def go():
        async with decisions_client("X9") as c:
            return await DecisionsAdapter(SPEC_D, c).call(SOLVED, [])

    a = run(go())
    assert a.move is None and a.error == "invalid_move"


def test_chat_adapter_parses_json_and_flags_malformed():
    def make(content):
        def handler(request):
            body = json.loads(request.content)
            assert body["response_format"]["json_schema"]["schema"]["properties"]["move"]["enum"] == list(MOVES)
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def go(content):
        async with make(content) as c:
            return await ChatAdapter(SPEC_C, c).call(SOLVED, ["R"])

    assert run(go('{"move": "U2"}')).move == "U2"
    assert run(go("I think R")).error == "malformed"
    assert run(go('{"move": "Z"}')).error == "invalid_move"


def test_chat_adapter_http_error_and_fallback():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append("response_format" in body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "unsupported"})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"move": "F"}'}}]})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            ad = ChatAdapter(SPEC_C, c)
            return await ad.call(SOLVED, []), ad.structured

    a, structured = run(go())
    assert a.move == "F" and calls == [True, False] and structured is False


def test_runner_counts_invalid_outputs_and_retries(monkeypatch):
    monkeypatch.setattr(config, "MAX_MOVES", 4)
    monkeypatch.setattr(config, "MAX_RETRIES", 1)

    class Bad:
        simulated = False

        async def call(self, state, recent, ctx=None):
            from race.models import Attempt

            return Attempt(error="malformed", latency=0.001)

    entry = ModelEntry(SPEC_C, Bad())
    from race.cube import apply_moves

    puzzle = {"id": "t-01", "tier": "primary", "scramble_length": 2, "scramble": ["R", "U"], "state": apply_moves(SOLVED, ["R", "U"]), "optimal": 2, "oracle": ["U'", "R'"]}

    async def emit(ev):
        return None

    res = run(play_trial(entry, puzzle, emit))
    assert res["status"] == "RAN_OUT_OF_MOVES" and res["steps"] == 4 and res["invalid_outputs"] == 4
    assert res["retries"] == 4 and res["moves"] == 0 and not res["solved"]


def test_parse_move_json_accepts_wrapped_object_only():
    from race.models import parse_move_json

    assert parse_move_json('{"move": "R"}') == {"move": "R"}
    assert parse_move_json('Sure! {"move": "U2"} done')["move"] == "U2"
    import pytest

    with pytest.raises(ValueError):
        parse_move_json("I would turn R")


def test_substitute_models_are_labeled(monkeypatch):
    import importlib

    monkeypatch.setenv("MODEL_JEV", "meta-llama/llama-3.3-70b-instruct:free")
    monkeypatch.setenv("INTERFACE_JEV", "chat")
    import race.config as cfg

    cfg = importlib.reload(cfg)
    jev = [s for s in cfg.MODEL_SPECS if s["key"] == "jev"][0]
    assert jev["substitute"] and jev["interface"] == "chat" and "substitute" in jev["label"]
    monkeypatch.delenv("MODEL_JEV")
    monkeypatch.delenv("INTERFACE_JEV")
    cfg = importlib.reload(cfg)
    assert not [s for s in cfg.MODEL_SPECS if s["key"] == "jev"][0]["substitute"]
