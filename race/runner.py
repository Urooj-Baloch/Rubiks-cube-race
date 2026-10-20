import asyncio
import random
import time

import httpx

from . import config
from .cube import SOLVED, apply_move, apply_moves, inverse_sequence, is_solved, random_scramble
from .models import build_entries, update_oracle
from .solver import EXACT_LIMIT, optimal_solution
from .stats import summarize


def make_puzzles(plan, seed):
    puzzles = []
    for tier, spec in plan.items():
        for i in range(spec["count"]):
            rng = random.Random("%s:%s:%d" % (seed, tier, i))
            length = rng.randint(spec["min"], spec["max"])
            scramble = random_scramble(length, rng)
            state = apply_moves(SOLVED, scramble)
            optimal = None
            oracle = inverse_sequence(scramble)
            if length <= EXACT_LIMIT:
                sol = optimal_solution(state)
                if sol is not None:
                    optimal = len(sol)
                    oracle = sol
            puzzles.append(
                {
                    "id": "%s-%02d" % (tier, i + 1),
                    "tier": tier,
                    "scramble_length": length,
                    "scramble": scramble,
                    "state": state,
                    "optimal": optimal,
                    "oracle": oracle,
                }
            )
    return puzzles


async def _decide(entry, state, recent, ctx):
    started = time.perf_counter()
    attempts = 0
    errors = []
    cost = 0.0
    last = None
    for _ in range(config.MAX_RETRIES + 1):
        attempts += 1
        last = await entry.adapter.call(state, recent, ctx)
        cost += last.cost
        if last.move:
            break
        errors.append(last.error)
        if last.error == "http_429":
            await asyncio.sleep(config.BACKOFF_SECONDS)
    return {
        "move": last.move if last and last.move else None,
        "latency": time.perf_counter() - started,
        "attempts": attempts,
        "errors": errors,
        "confidence": last.confidence if last else None,
        "probabilities": last.probabilities if last else None,
        "cost": cost,
    }


async def play_trial(entry, puzzle, emit):
    state = puzzle["state"]
    ctx = {"oracle": list(puzzle["oracle"])} if entry.simulated else None
    history = []
    latencies = []
    steps = 0
    invalid = 0
    retries = 0
    cost = 0.0
    status = None
    started = time.perf_counter()
    await emit({"type": "trial_started", "model": entry.key, "puzzle": puzzle["id"], "state": state})
    while True:
        if is_solved(state):
            status = "SOLVED"
            break
        if steps >= config.MAX_MOVES:
            status = "RAN_OUT_OF_MOVES"
            break
        remaining = config.TRIAL_TIME_LIMIT - (time.perf_counter() - started)
        if remaining <= 0:
            status = "OUT_OF_TIME"
            break
        await emit({"type": "thinking", "model": entry.key, "puzzle": puzzle["id"], "step": steps + 1})
        recent = [h["move"] for h in history if h["move"]][-config.RECENT_MOVES:]
        try:
            res = await asyncio.wait_for(_decide(entry, state, recent, ctx), timeout=remaining)
        except asyncio.TimeoutError:
            status = "OUT_OF_TIME"
            break
        steps += 1
        retries += res["attempts"] - 1
        cost += res["cost"]
        latencies.append(res["latency"])
        if res["move"]:
            state = apply_move(state, res["move"])
            if ctx is not None:
                ctx["oracle"] = update_oracle(ctx["oracle"], res["move"])
        else:
            invalid += 1
        record = {
            "step": steps,
            "move": res["move"],
            "latency": round(res["latency"], 4),
            "attempts": res["attempts"],
            "errors": res["errors"],
            "confidence": res["confidence"],
        }
        history.append(record)
        await emit(
            {
                "type": "step",
                "model": entry.key,
                "puzzle": puzzle["id"],
                "state": state,
                "elapsed": time.perf_counter() - started,
                "applied": sum(1 for h in history if h["move"]),
                **record,
            }
        )
    total_time = time.perf_counter() - started
    applied = sum(1 for h in history if h["move"])
    solved = status == "SOLVED"
    gap = None
    if solved and puzzle["optimal"] is not None:
        gap = applied - puzzle["optimal"]
    result = {
        "model": entry.key,
        "label": entry.label,
        "category": entry.category,
        "simulated": entry.simulated,
        "puzzle": puzzle["id"],
        "tier": puzzle["tier"],
        "scramble_length": puzzle["scramble_length"],
        "scramble": puzzle["scramble"],
        "optimal": puzzle["optimal"],
        "status": status,
        "solved": solved,
        "moves": applied,
        "steps": steps,
        "invalid_outputs": invalid,
        "retries": retries,
        "total_time": round(total_time, 4),
        "avg_latency": round(sum(latencies) / len(latencies), 4) if latencies else None,
        "step_latencies": [round(x, 4) for x in latencies],
        "opt_gap": gap,
        "cost": round(cost, 6),
        "history": history,
        "final_state": state,
    }
    await emit({"type": "trial_finished", "model": entry.key, "puzzle": puzzle["id"], "result": result})
    return result


async def _run_entry(entry, puzzle, emit):
    prep = getattr(entry.adapter, "prepare", None)
    if prep is not None:
        await emit({"type": "loading", "model": entry.key, "puzzle": puzzle["id"]})
        await prep()
    return await play_trial(entry, puzzle, emit)


async def run_experiment(mode, plan, seed, emit, keys=None):
    puzzles = make_puzzles(plan, seed)
    results = []
    async with httpx.AsyncClient() as client:
        entries = build_entries(mode, client, seed, keys)
        await emit(
            {
                "type": "run_started",
                "mode": mode,
                "backend": config.BACKEND,
                "seed": seed,
                "puzzles": [{k: p[k] for k in ("id", "tier", "scramble_length", "optimal")} for p in puzzles],
                "models": [
                    {"key": e.key, "label": e.label, "category": e.category, "model_id": e.spec["id"]}
                    for e in entries
                ],
            }
        )
        for puzzle in puzzles:
            await emit(
                {
                    "type": "puzzle_started",
                    "puzzle": puzzle["id"],
                    "tier": puzzle["tier"],
                    "scramble": puzzle["scramble"],
                    "scramble_length": puzzle["scramble_length"],
                    "state": puzzle["state"],
                    "optimal": puzzle["optimal"],
                }
            )
            if config.SEQUENTIAL:
                batch = []
                for e in entries:
                    batch.append(await _run_entry(e, puzzle, emit))
            else:
                batch = list(await asyncio.gather(*[_run_entry(e, puzzle, emit) for e in entries]))
            results.extend(batch)
            await emit({"type": "puzzle_finished", "puzzle": puzzle["id"], "results": batch})
        summary = summarize(results)
        await emit({"type": "run_finished", "mode": mode, "summary": summary})
    return puzzles, results, summary
