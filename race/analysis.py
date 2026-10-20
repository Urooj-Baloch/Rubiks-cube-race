def _fmt(x, nd=2, suffix=""):
    return "n/a" if x is None else ("%.*f%s" % (nd, x, suffix))


def _pick(table, key, best="min", skip_none=True):
    items = [(m, v[key]) for m, v in table.items() if (v[key] is not None or not skip_none)]
    if not items:
        return None
    fn = min if best == "min" else max
    target = fn(v for _, v in items)
    return [m for m, v in items if v == target], target


def _names(table, keys):
    return " and ".join(table[k]["label"] for k in keys)


def answers(summary):
    graded = summary["graded_overall"] or summary["overall"]
    primary = summary["by_tier"].get("primary") or graded
    out = []

    fast = _pick(graded, "avg_move_latency", "min")
    slow = _pick(graded, "avg_move_latency", "max")
    ratio = slow[1] / fast[1] if fast and fast[1] else None
    q1 = "%s was fastest per decision at %s s on average" % (_names(graded, fast[0]), _fmt(fast[1], 3))
    if ratio:
        q1 += "; the slowest model (%s) averaged %s s, a %sx difference." % (
            _names(graded, slow[0]),
            _fmt(slow[1], 3),
            _fmt(ratio, 1),
        )
    out.append(("Which model is fastest in terms of making decisions?", q1))

    rate = _pick(primary, "success_rate", "max")
    rate_all = _pick(graded, "success_rate", "max")
    q2 = "On the primary benchmark %s achieved the highest solve rate (%s%%); across all graded puzzles %s led with %s%%." % (
        _names(primary, rate[0]),
        _fmt(rate[1], 1),
        _names(graded, rate_all[0]),
        _fmt(rate_all[1], 1),
    )
    out.append(("Which model achieved the highest solve rate?", q2))

    gap = _pick(primary, "avg_opt_gap", "min")
    if gap:
        details = "; ".join(
            "%s: mean gap %s over %d solved puzzles (%d optimal)"
            % (v["label"], _fmt(v["avg_opt_gap"]), v["gap_trials"], v["optimal_solves"])
            for m, v in primary.items()
            if v["avg_opt_gap"] is not None
        )
        unsolved = [v["label"] for v in primary.values() if v["avg_opt_gap"] is None]
        q3 = "%s found the shortest solutions (mean optimality gap %s moves). %s." % (
            _names(primary, gap[0]),
            _fmt(gap[1]),
            details,
        )
        if unsolved:
            q3 += " No optimality gap exists for %s because it solved none of the primary puzzles." % ", ".join(unsolved)
    else:
        q3 = "No model solved a primary puzzle, so no optimality gap could be computed."
    out.append(("Which model found the shortest solutions, and how close were they to the known optimum?", q3))

    fastest_keys = fast[0]
    if gap:
        same = bool(set(fastest_keys) & set(gap[0]))
        if same:
            q4 = "Yes. %s was both the fastest per decision and among the best on solution length (gap %s)." % (
                _names(graded, fastest_keys),
                _fmt(gap[1]),
            )
        else:
            q4 = "No. %s was fastest but %s found the shortest solutions (gap %s versus %s)." % (
                _names(graded, fastest_keys),
                _names(primary, gap[0]),
                _fmt(gap[1]),
                _fmt(primary[fastest_keys[0]]["avg_opt_gap"]),
            )
    else:
        q4 = "Not determinable: no primary puzzle was solved."
    out.append(("Did the fastest model also achieve the best solution quality?", q4))

    llm = [k for k, v in graded.items() if v["category"] == "Frontier LLM"]
    dec = [k for k, v in graded.items() if v["category"] != "Frontier LLM"]
    if llm and dec:
        best_llm = max(llm, key=lambda k: (graded[k]["success_rate"], -(graded[k]["avg_move_latency"] or 1e9)))
        l = graded[best_llm]
        best_dec = max(dec, key=lambda k: (graded[k]["success_rate"], -(graded[k]["avg_move_latency"] or 1e9)))
        d = graded[best_dec]
        speedup = (l["avg_move_latency"] / d["avg_move_latency"]) if d["avg_move_latency"] else None
        lt = l["avg_total_time"]
        dt = d["avg_total_time"]
        evidence = (
            "Evidence: the best LLM, %s, solved %s%% of graded puzzles in %s s average total time, versus %s%% in %s s for the best decision model (%s), "
            "which decides %sx faster per move; invalid outputs were %d for that LLM and %d for that decision model."
            % (
                l["label"],
                _fmt(l["success_rate"], 1),
                _fmt(lt, 1),
                _fmt(d["success_rate"], 1),
                _fmt(dt, 1),
                d["label"],
                _fmt(speedup, 1),
                l["invalid_outputs"],
                d["invalid_outputs"],
            )
        )
        if l["success_rate"] > d["success_rate"] and speedup and speedup > 3:
            rec = (
                "A hybrid agent. The LLM is more reliable, but the decision model is far cheaper in latency, "
                "so use the decision model for routine low-latency steps and escalate to the LLM when its confidence is low or progress stalls."
            )
        elif l["success_rate"] > d["success_rate"]:
            rec = "The LLM, because its reliability advantage is not offset by a large latency penalty."
        else:
            rec = (
                "The fast decision model, because it matched or beat the LLMs on solve rate while responding far faster; "
                "keep an LLM only as a fallback for stalled cases."
            )
        q5 = rec + " " + evidence
    else:
        q5 = "Both a decision model and an LLM are required in the run to answer this question."
    out.append(
        (
            "Would you use the fastest decision model, the frontier LLM, or a hybrid agent in a real-world application? What evidence supports your choice?",
            q5,
        )
    )
    return out
