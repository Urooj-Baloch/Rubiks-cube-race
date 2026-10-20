import statistics


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _agg(trials):
    n = len(trials)
    lat = [x for t in trials for x in t["step_latencies"]]
    solved = [t for t in trials if t["solved"]]
    gaps = [t["opt_gap"] for t in trials if t["opt_gap"] is not None]
    return {
        "trials": n,
        "solved": len(solved),
        "success_rate": 100.0 * len(solved) / n if n else None,
        "avg_move_latency": _mean(lat),
        "median_move_latency": statistics.median(lat) if lat else None,
        "p95_move_latency": _pct(lat, 0.95),
        "avg_total_time": _mean([t["total_time"] for t in trials]),
        "avg_total_moves": _mean([t["moves"] for t in trials]),
        "avg_moves_solved": _mean([t["moves"] for t in solved]),
        "avg_opt_gap": _mean(gaps),
        "gap_trials": len(gaps),
        "optimal_solves": sum(1 for g in gaps if g == 0),
        "invalid_outputs": sum(t["invalid_outputs"] for t in trials),
        "retries": sum(t["retries"] for t in trials),
        "total_steps": sum(t["steps"] for t in trials),
        "out_of_time": sum(1 for t in trials if t["status"] == "OUT_OF_TIME"),
        "ran_out_of_moves": sum(1 for t in trials if t["status"] == "RAN_OUT_OF_MOVES"),
        "cost": sum(t["cost"] for t in trials),
    }


def summarize(results):
    models = []
    seen = {}
    for r in results:
        if r["model"] not in seen:
            seen[r["model"]] = {"label": r["label"], "category": r["category"], "simulated": r["simulated"]}
            models.append(r["model"])
    overall = {}
    by_tier = {}
    for m in models:
        mine = [r for r in results if r["model"] == m]
        overall[m] = dict(seen[m], **_agg(mine))
        for tier in sorted({r["tier"] for r in mine}):
            by_tier.setdefault(tier, {})[m] = dict(
                seen[m], **_agg([r for r in mine if r["tier"] == tier])
            )
    graded = [r for r in results if r["tier"] != "warmup"]
    graded_overall = {}
    for m in models:
        mine = [r for r in graded if r["model"] == m]
        if mine:
            graded_overall[m] = dict(seen[m], **_agg(mine))
    return {
        "models": models,
        "overall": overall,
        "graded_overall": graded_overall,
        "by_tier": by_tier,
        "n_trials": len(results),
        "n_puzzles": len({r["puzzle"] for r in results}),
    }
