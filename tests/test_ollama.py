import asyncio
import importlib
import json
import os
import subprocess
import sys
import time

import httpx
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def ollama_config(monkeypatch):
    import race.config as cfg

    monkeypatch.setenv("BACKEND", "ollama")
    cfg = importlib.reload(cfg)
    yield cfg
    monkeypatch.delenv("BACKEND")
    importlib.reload(cfg)


def test_ollama_specs_use_clef_and_three_llms(ollama_config):
    specs = {s["key"]: s for s in ollama_config.MODEL_SPECS}
    assert list(specs) == ["clef", "qwen", "deepseek", "gemma"]
    assert specs["clef"]["interface"] == "decisions" and not specs["clef"]["substitute"]
    assert all(specs[k]["interface"] == "chat" and specs[k]["substitute"] for k in ("qwen", "deepseek", "gemma"))
    assert ollama_config.SEQUENTIAL and ollama_config.live_ready()
    assert ollama_config.OLLAMA_SYSTEMONE_URL.endswith("/v1/systemone")


def test_parse_move_json_ignores_think_block():
    from race.models import parse_move_json

    assert parse_move_json('<think>maybe {"move": "R"} first</think>{"move": "U2"}')["move"] == "U2"
    assert parse_move_json('text {"move": "B"} more {"other": 1}')["move"] == "B"


def test_ollama_chat_adapter_think_and_format_fallback(ollama_config):
    from race.cube import SOLVED
    from race.models import OllamaChatAdapter

    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(("think" in body, "format" in body))
        if "think" in body:
            return httpx.Response(400, json={"error": "does not support thinking"})
        return httpx.Response(200, json={"message": {"content": '{"move": "F2"}'}})

    spec = {"key": "gemma", "id": "gemma3"}

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            ad = OllamaChatAdapter(spec, c)
            return await ad.call(SOLVED, []), ad

    att, ad = asyncio.run(go())
    assert att.move == "F2" and seen == [(True, True), (False, True)] and ad.think_off is False


def test_decisions_adapter_targets_local_endpoint_without_key(ollama_config):
    from race.cube import SOLVED
    from race.models import DecisionsAdapter

    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        body = json.loads(request.content)
        seen["model"] = body["model"]
        seen["keep_alive"] = body.get("keep_alive")
        return httpx.Response(200, json={"answers": {"next_move": {"choice": "R", "confidence": 0.5}}})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await DecisionsAdapter({"key": "clef", "id": "clef"}, c).call(SOLVED, [])

    att = asyncio.run(go())
    assert att.move == "R" and seen["url"].endswith("/v1/systemone") and seen["auth"] is None
    assert seen["model"] == "clef" and seen["keep_alive"]


def test_preflight_reports_unreachable_and_missing(ollama_config, monkeypatch):
    from race import preflight

    monkeypatch.setattr(ollama_config, "OLLAMA_TAGS_URL", "http://127.0.0.1:9/api/tags")
    assert "Cannot reach Ollama" in preflight.check_ollama(timeout=1)


def test_end_to_end_against_fake_ollama(tmp_path):
    port = 18765
    server = subprocess.Popen(
        [sys.executable, "-m", "tests.fake_ollama", str(port)],
        cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=ROOT),
    )
    try:
        for _ in range(50):
            try:
                if httpx.get("http://127.0.0.1:%d/api/tags" % port, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        env = dict(os.environ, BACKEND="ollama", OLLAMA_URL="http://127.0.0.1:%d" % port, PYTHONPATH=ROOT)
        out = tmp_path / "res"
        run = subprocess.run(
            [sys.executable, "benchmark.py", "--mode", "live", "--warmup", "1", "--primary", "2", "--extension", "0", "--out", str(out)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert run.returncode == 0, run.stdout + run.stderr
        summary = json.load(open(out / "summary.json"))
        overall = summary["summary"]["overall"]
        assert set(overall) == {"clef", "qwen", "deepseek", "gemma"}
        assert overall["clef"]["success_rate"] == 100.0
        assert overall["qwen"]["success_rate"] == 100.0
        assert overall["deepseek"]["success_rate"] == 100.0
        assert overall["gemma"]["invalid_outputs"] == 0
        assert summary["meta"]["backend"] == "ollama" and summary["meta"]["substitutes"]
        report = (out / "report.md").read_text()
        assert "Substitute models were used" in report and "Qwen (qwen3.5)" in report
        calls = httpx.get("http://127.0.0.1:%d/calls" % port).json()
        assert calls["load"] >= 9 and calls["systemone"] > 0 and calls["chat"] > 0
    finally:
        server.terminate()
        server.wait(timeout=10)
