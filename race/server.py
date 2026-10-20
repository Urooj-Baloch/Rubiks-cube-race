import asyncio
import json
import os
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .analysis import answers
from .preflight import check_backend
from .report import write_outputs
from .runner import run_experiment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "static")
PUZZLE_PAUSE = float(os.getenv("UI_PUZZLE_PAUSE_SECONDS", "3.0"))

app = FastAPI(title="Rubik's Cube Race")
RUNS = {}


class RunRequest(BaseModel):
    mode: str = "sim"
    seed: str = "a02"
    warmup: int = 0
    primary: int = 3
    extension: int = 0
    models: list[str] = []


@app.get("/api/config")
async def get_config():
    return {
        "student_name": config.STUDENT_NAME,
        "student_roll": config.STUDENT_ROLL,
        "live_available": config.live_ready(),
        "backend": config.BACKEND,
        "live_name": config.live_name(),
        "max_moves": config.MAX_MOVES,
        "trial_time_limit": config.TRIAL_TIME_LIMIT,
        "tiers": config.TIERS,
        "models": [
            {"key": s["key"], "label": s["label"], "category": s["category"], "model_id": s["id"]}
            for s in config.MODEL_SPECS
        ],
    }


@app.post("/api/runs")
async def start_run(req: RunRequest):
    if req.mode not in ("live", "sim"):
        raise HTTPException(400, "mode must be live or sim")
    if req.mode == "live":
        problem = await asyncio.get_running_loop().run_in_executor(None, check_backend)
        if problem:
            raise HTTPException(400, problem)
    plan = {}
    for tier in ("warmup", "primary", "extension"):
        count = max(0, min(50, getattr(req, tier)))
        if count:
            plan[tier] = dict(config.TIERS[tier], count=count)
    if not plan:
        raise HTTPException(400, "select at least one puzzle")
    run_id = uuid.uuid4().hex[:10]
    queue = asyncio.Queue()
    RUNS[run_id] = queue

    async def emit(ev):
        await queue.put(ev)
        if ev["type"] == "puzzle_finished":
            await asyncio.sleep(PUZZLE_PAUSE)

    async def job():
        try:
            puzzles, results, summary = await run_experiment(req.mode, plan, req.seed, emit, req.models or None)
            await queue.put({"type": "analysis", "answers": answers(summary)})
            meta = {
                "mode": req.mode,
                "mode_label": ("LIVE (%s)" % config.live_name()) if req.mode == "live" else "SIMULATED (not real model outputs)",
                "seed": req.seed,
                "max_moves": config.MAX_MOVES,
                "call_timeout": config.CALL_TIMEOUT,
                "max_retries": config.MAX_RETRIES,
                "trial_limit": config.TRIAL_TIME_LIMIT,
                "backend": config.BACKEND,
                "substitutes": {sp["label"]: sp["id"] for sp in config.MODEL_SPECS if sp["substitute"]},
            }
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, write_outputs, os.path.join(ROOT, "results", "ui_" + req.mode), summary, results, puzzles, meta
            )
        except Exception as exc:
            await queue.put({"type": "error", "message": "%s: %s" % (type(exc).__name__, exc)})
        finally:
            await queue.put(None)

    asyncio.create_task(job())
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str):
    queue = RUNS.get(run_id)
    if queue is None:
        raise HTTPException(404, "unknown run")

    async def stream():
        while True:
            try:
                ev = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            if ev is None:
                yield "event: end\ndata: {}\n\n"
                RUNS.pop(run_id, None)
                return
            yield "data: %s\n\n" % json.dumps(ev)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC), name="static")
