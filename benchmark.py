import argparse
import asyncio
import os
import sys

from race import config
from race.preflight import check_backend
from race.report import inject_readme, write_outputs
from race.runner import run_experiment


def parse():
    p = argparse.ArgumentParser(description="Run the Rubik's Cube Race benchmark headlessly")
    p.add_argument("--mode", choices=["live", "sim"], default="live")
    p.add_argument("--seed", default="a02")
    p.add_argument("--warmup", type=int, default=config.TIERS["warmup"]["count"])
    p.add_argument("--primary", type=int, default=config.TIERS["primary"]["count"])
    p.add_argument("--extension", type=int, default=config.TIERS["extension"]["count"])
    p.add_argument("--models", default="")
    p.add_argument("--out", default="")
    p.add_argument("--update-readme", action="store_true")
    return p.parse_args()


async def main():
    args = parse()
    if args.mode == "live":
        problem = check_backend()
        if problem:
            print(problem)
            sys.exit(2)
    plan = {
        "warmup": dict(config.TIERS["warmup"], count=args.warmup),
        "primary": dict(config.TIERS["primary"], count=args.primary),
        "extension": dict(config.TIERS["extension"], count=args.extension),
    }
    plan = {k: v for k, v in plan.items() if v["count"] > 0}
    keys = [k for k in args.models.split(",") if k] or None
    out_dir = args.out or os.path.join("results", args.mode)

    async def emit(ev):
        t = ev["type"]
        if t == "puzzle_started":
            print("puzzle %s  scramble=%s  optimal=%s" % (ev["puzzle"], " ".join(ev["scramble"]), ev["optimal"]))
        elif t == "trial_finished":
            r = ev["result"]
            print(
                "  %-24s %-17s moves=%-2d steps=%-2d time=%7.2fs gap=%s invalid=%d"
                % (r["label"], r["status"], r["moves"], r["steps"], r["total_time"], r["opt_gap"], r["invalid_outputs"])
            )

    puzzles, results, summary = await run_experiment(args.mode, plan, args.seed, emit, keys)
    meta = {
        "mode": args.mode,
        "mode_label": ("LIVE (%s)" % config.live_name()) if args.mode == "live" else "SIMULATED (offline pipeline validation, not real model outputs)",
        "seed": args.seed,
        "max_moves": config.MAX_MOVES,
        "call_timeout": config.CALL_TIMEOUT,
        "max_retries": config.MAX_RETRIES,
        "trial_limit": config.TRIAL_TIME_LIMIT,
        "model_ids": {s["key"]: s["id"] for s in config.MODEL_SPECS},
        "backend": config.BACKEND,
        "substitutes": {s["label"]: s["id"] for s in config.MODEL_SPECS if s["substitute"]},
    }
    md = write_outputs(out_dir, summary, results, puzzles, meta)
    print("wrote", out_dir)
    if args.update_readme:
        inject_readme("README.md", "LIVE" if args.mode == "live" else "SIM", md.replace("](benchmarks.png)", "](%s/benchmarks.png)" % out_dir))
        print("README.md updated")


if __name__ == "__main__":
    asyncio.run(main())
