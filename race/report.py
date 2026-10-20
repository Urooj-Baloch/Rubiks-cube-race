import json
import os

from .analysis import answers


def _f(x, nd=2):
    return "n/a" if x is None else "%.*f" % (nd, x)


def _secs(x):
    if x is None:
        return "n/a"
    m, s = divmod(x, 60)
    return "%d:%05.2f" % (m, s) if m else "%.2f s" % s


def stats_table(table):
    head = (
        "| Model | Category | Trials | Success rate | Avg latency / move (s) | Median (s) | P95 (s) | Avg total time | "
        "Avg total moves | Avg moves (solved) | Avg optimality gap | Optimal solves | Invalid outputs | Retries | Cost (USD) |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for m, v in table.items():
        rows.append(
            "| %s | %s | %d | %s%% (%d/%d) | %s | %s | %s | %s | %s | %s | %s | %d/%d | %d | %d | %s |"
            % (
                v["label"],
                v["category"],
                v["trials"],
                _f(v["success_rate"], 1),
                v["solved"],
                v["trials"],
                _f(v["avg_move_latency"], 3),
                _f(v["median_move_latency"], 3),
                _f(v["p95_move_latency"], 3),
                _secs(v["avg_total_time"]),
                _f(v["avg_total_moves"], 2),
                _f(v["avg_moves_solved"], 2),
                _f(v["avg_opt_gap"], 2),
                v["optimal_solves"],
                v["gap_trials"],
                v["invalid_outputs"],
                v["retries"],
                _f(v["cost"], 4),
            )
        )
    return head + "\n".join(rows) + "\n"


def trial_table(results):
    head = (
        "| Puzzle | Scramble | Optimal | Model | Status | Moves | Steps | Gap | Total time | Avg latency (s) | Invalid |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for r in results:
        rows.append(
            "| %s | %s | %s | %s | %s | %d | %d | %s | %s | %s | %d |"
            % (
                r["puzzle"],
                " ".join(r["scramble"]),
                "?" if r["optimal"] is None else r["optimal"],
                r["label"],
                r["status"],
                r["moves"],
                r["steps"],
                "n/a" if r["opt_gap"] is None else r["opt_gap"],
                _secs(r["total_time"]),
                _f(r["avg_latency"], 3),
                r["invalid_outputs"],
            )
        )
    return head + "\n".join(rows) + "\n"


def render_markdown(summary, results, meta, chart_path=None):
    parts = []
    parts.append(
        "Run: **%s** | seed `%s` | %d puzzles | %d model-puzzle trials | move limit %d | per-call timeout %ss | retries %d | trial time cap %ss\n"
        % (
            meta["mode_label"],
            meta["seed"],
            summary["n_puzzles"],
            summary["n_trials"],
            meta["max_moves"],
            meta["call_timeout"],
            meta["max_retries"],
            meta["trial_limit"],
        )
    )
    if meta.get("substitutes"):
        parts.append(
            "**Substitute models were used instead of the assigned ones:** "
            + "; ".join("%s ran as `%s`" % (k, v) for k, v in meta["substitutes"].items())
            + ". These results do not describe the assigned models.\n"
        )
    if chart_path:
        parts.append("![Benchmark charts](%s)\n" % chart_path)
    parts.append("### Benchmark statistics (all graded puzzles: primary + extension)\n")
    parts.append(stats_table(summary["graded_overall"] or summary["overall"]))
    for tier in ("warmup", "primary", "extension"):
        if tier in summary["by_tier"]:
            parts.append("### Tier: %s\n" % tier)
            parts.append(stats_table(summary["by_tier"][tier]))
    parts.append("### Answers to the required questions\n")
    for i, (q, a) in enumerate(answers(summary), 1):
        parts.append("%d. **%s** %s\n" % (i, q, a))
    parts.append("### Every trial\n")
    parts.append(trial_table(results))
    return "\n".join(parts)


def render_chart(summary, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    table = summary["graded_overall"] or summary["overall"]
    labels = [v["label"] for v in table.values()]
    colors = ["#2b6cb0" if v["category"] != "Frontier LLM" else "#c05621" for v in table.values()]
    panels = [
        ("Avg latency per move (s)", [v["avg_move_latency"] or 0 for v in table.values()]),
        ("Success rate (%)", [v["success_rate"] or 0 for v in table.values()]),
        ("Avg total moves", [v["avg_total_moves"] or 0 for v in table.values()]),
        ("Avg optimality gap (solved, primary)", None),
    ]
    primary = summary["by_tier"].get("primary", {})
    gaps = [(primary.get(m, {}).get("avg_opt_gap") or 0) for m in table.keys()]
    panels[3] = (panels[3][0], gaps)
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.2))
    for ax, (title, vals) in zip(axes, panels):
        bars = ax.bar(range(len(vals)), vals, color=colors)
        ax.set_title(title, fontsize=11)
        ax.set_xticks(range(len(vals)))
        ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), "%.2f" % v, ha="center", va="bottom", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def write_outputs(out_dir, summary, results, puzzles, meta):
    os.makedirs(out_dir, exist_ok=True)
    chart = os.path.join(out_dir, "benchmarks.png")
    render_chart(summary, chart)
    md = render_markdown(summary, results, meta, chart_path=os.path.basename(chart))
    with open(os.path.join(out_dir, "report.md"), "w") as fh:
        fh.write(md)
    with open(os.path.join(out_dir, "summary.json"), "w") as fh:
        json.dump({"meta": meta, "summary": summary}, fh, indent=2)
    with open(os.path.join(out_dir, "trials.json"), "w") as fh:
        json.dump(results, fh, indent=1)
    with open(os.path.join(out_dir, "puzzles.json"), "w") as fh:
        json.dump(
            [{k: p[k] for k in ("id", "tier", "scramble_length", "scramble", "state", "optimal")} for p in puzzles],
            fh,
            indent=1,
        )
    return md


def inject_readme(readme_path, block_name, markdown):
    start = "<!-- RESULTS:%s:START -->" % block_name
    end = "<!-- RESULTS:%s:END -->" % block_name
    with open(readme_path) as fh:
        text = fh.read()
    a = text.index(start) + len(start)
    b = text.index(end)
    text = text[:a] + "\n" + markdown + "\n" + text[b:]
    with open(readme_path, "w") as fh:
        fh.write(text)
