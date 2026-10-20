# Rubik's Cube Race

AI Engineering | Assignment 02 | Urooj Baloch | Roll No. 23K-0071

Can fast System-1 decision models beat a frontier LLM at solving a Rubik's Cube? This project is a repeatable benchmark that compares four models through OpenRouter or local Ollama on speed (per-move latency, total solve time) and thinking quality (solve rate, moves versus the exact shortest solution).

## Demo screen recording

**[Watch the screen recording: demo/demo.mp4](demo/demo.mp4)** (direct link, stored in this repository; real live run on Ollama)

The recording shows: (1) the in-progress stage with all four models playing the same scramble, (2) the completion stage with SOLVED / RAN OUT OF MOVES banners, (3) a final statistical-benchmarks slide, and (4) the student name and roll number visible on screen for the whole recording.

<!-- NOTE:START -->
The screen recording (`demo/demo.mp4`) and the results in the "Live run" section come from a real live run of the models on Ollama (Clef Flash, Qwen 3.5, DeepSeek-R1, Gemma 3), executed on Google Colab T4 GPU hardware, so the speed figures reflect that hardware.
<!-- NOTE:END -->

## Features

- Deterministic cube engine (54-facelet state, 18 moves, validated against known identities) with random scramble generation
- Exact shortest-solution reference: bidirectional BFS meet-in-the-middle, exact up to 6 moves, which covers every warm-up and primary puzzle
- OpenRouter adapters
  - Decisions API (`POST /api/alpha/decisions`) for Jev 1.13, GPT-6 Luna Decisions and Cloudflare Clef, with one shared question wording and option set (only the model id changes)
  - Chat Completions (`POST /api/v1/chat/completions`) for Claude Opus 5.5 with a strict JSON-schema constrained output (`{"move": "R'"}`) and automatic fallback if the route rejects structured output
- Ollama adapters (used for the submitted run): `POST /v1/systemone` for the Clef Flash decision model and `POST /api/chat` with a JSON schema for Qwen 3.5, DeepSeek-R1 and Gemma 3
- Same rules for every model: identical start state per puzzle, 30-move limit, per-call timeout, retry policy, and recent-move history window; malformed or invalid outputs are counted and never silently turned into actions
- Live race UI (FastAPI + plain HTML/JS) with four 3D cubes, running timers, move counts, move history, and a statistics slide
- Headless benchmark runner that writes `report.md`, `summary.json`, `trials.json` and a chart image
- API key stays in a backend environment variable and is never sent to the browser

## Project layout

```
race/cube.py        cube engine, moves, scramble generator
race/solver.py      exact BFS shortest-solution search
race/models.py      Decisions + Chat adapters
race/runner.py      fair trial loop (limits, retries, timing, logging)
race/stats.py       aggregate statistics
race/analysis.py    answers to the five required questions from the data
race/report.py      markdown/JSON/chart output and README injection
race/server.py      FastAPI app and server-sent-event stream
static/             race UI (index.html, app.js, style.css)
benchmark.py        headless benchmark CLI
check_models.py     verifies configured model ids against OpenRouter
demo/demo.mp4       screen recording of the live run
tests/              engine, solver, adapter and runner tests
results/            generated reports (results/live)
```

## Setup

```bash
git clone <your-repo-url>
cd rubiks-cube-race
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `OPENROUTER_API_KEY` (create one at https://openrouter.ai/settings/keys), plus `STUDENT_NAME` and `STUDENT_ROLL`, which are shown on screen. Do not commit `.env`.

Environment variables (see `.env.example`): model ids, `MAX_MOVES=30`, `CALL_TIMEOUT_SECONDS=60`, `MAX_RETRIES=2`, `TRIAL_TIME_LIMIT_SECONDS=300`, `RECENT_MOVES=6`.

Verify model ids before running, as the assignment instructs (names and routing can change):

```bash
python check_models.py
```

## Running the real experiment

```bash
python benchmark.py --mode live --seed a02 --update-readme
```

This runs 2 warm-up, 10 primary and 3 extension puzzles on all four models (60 trials), writes `results/live/`, and replaces the "Live run" section below with the real statistics, charts and answers. Use `--primary 5` for the minimum sample, or change `--seed` to repeat the experiment on fresh puzzles.

## Running with local Ollama models (free, approved by the instructor)

The instructor approved Ollama as the way to run the experiment without an OpenRouter key: Clef Flash as the System-1 decision model, and open models (Qwen 3.5, DeepSeek-R1, Gemma 3) as the language models. Switch the whole app to this backend with `BACKEND=ollama`.

| Slot | Ollama model (default tag) | Download size | Interface |
|---|---|---|---|
| Decision model | Clef Flash (`clef-flash`, 9B) | about 11-12 GB | Ollama `POST /v1/systemone`, same request and response shape as the OpenRouter Decisions API |
| Language model | Qwen 3.5 (`qwen3.5`) | about 7 GB | Ollama `POST /api/chat` with a JSON-schema constrained reply `{"move": "R'"}` |
| Language model | DeepSeek-R1 (`deepseek-r1`, 8B) | about 5 GB | same |
| Language model | Gemma 3 (`gemma3`, 4B) | about 3.4 GB | same |

Jev 1.13, GPT-6 Luna Decisions and Claude Opus 5.5 are not available on Ollama, so they are not part of this run. Qwen, DeepSeek and Gemma stand in for the frontier-LLM slot, and `report.md` and the README results state that substitute models were used.

Setup:

1. Install Ollama (https://ollama.com/download) and make sure it is running. Clef Flash needs Ollama 0.35.1 or newer.
2. Download the models (about 27 GB in total; the largest, Clef Flash, needs roughly 12 GB of free memory when it runs):
   ```
   ollama pull clef-flash
   ollama pull qwen3.5
   ollama pull deepseek-r1
   ollama pull gemma3
   ```
3. Copy `.env.ollama.example` to `.env` (no key needed). The tags can be changed with `OLLAMA_MODEL_*` if you use different sizes.
4. Check everything is ready: `python check_models.py`
5. Run a small test and then the full experiment:
   ```
   python benchmark.py --mode live --warmup 1 --primary 1 --extension 0
   python benchmark.py --mode live --seed a02 --update-readme
   ```

Fairness on one machine: models take turns on each puzzle (no two models compete for the same CPU/GPU), and each model is loaded into memory before its trial starts, so load time is not counted in its latency. The Ollama template uses 60 s per call and 300 s per puzzle, and loading a model into memory has its own separate 15-minute allowance that is not part of any measured time.

## Running on Google Colab (free GPU)

If your own computer is too slow for the Ollama models, `colab/rubiks_cube_race_colab.ipynb` runs the same project on a free Colab GPU. Upload the notebook to https://colab.research.google.com, choose Runtime > Change runtime type > T4 GPU, and run the cells in order. The notebook installs Ollama, downloads the four models, runs the benchmark and writes the results into this README, then opens the race page so you can screen-record it. Speed numbers then reflect Colab hardware, which the results section states.

## Running the race UI

```bash
uvicorn race.server:app --port 8000
```

Open http://127.0.0.1:8000, choose Live, pick the number of puzzles per tier, and press Run benchmark. When the race finishes, the statistics slide opens automatically (Show benchmarks reopens it).

## Recording the demo (for submission)

Record the browser tab with any screen recorder (for example Win + Alt + R on Windows). Keep the name and roll number badge visible, show the race in progress and after it finishes, and end on the statistics slide. Save the file as `demo/demo.mp4`.

## Method

State and action space: the state sent to every model is the 54-character facelet string (U, R, F, D, L, B faces, nine stickers each) plus the last six moves; the action space is the 18 moves `U U' U2 R R' R2 F F' F2 D D' D2 L L' L2 B B' B2`. The engine applies the chosen move and checks that all six faces are uniform.

Fairness: for each puzzle all four models start from the identical scrambled state and run under the same limits (one after another on a single GPU with Ollama, concurrently through OpenRouter). Reaching 30 moves counts as unsuccessful. A failed or invalid response is retried up to `MAX_RETRIES` times and then recorded as an invalid output that consumes a step without changing the cube.

Metrics:

- Per-move latency: wall time from sending a request to receiving a valid move, including retries, averaged over every move; median and P95 also reported
- Total solve time: wall time from the first request to solved or move limit
- Success rate: solved trials / total trials
- Optimality gap = model moves - exact shortest moves, computed for solved trials of puzzles with a known exact distance (warm-up and primary tiers)

Test sets: warm-up (3-4 turns), primary (4-5 turns, exact optimum), extension (15-20 turns, optimum not computed because the exact distance is beyond the BFS range).

## Tests

```bash
python -m pytest -q
```

22 tests cover move definitions (including a reference U-turn permutation, move orders and inverses), scramble round trips, the exact solver, both OpenRouter adapters and both Ollama adapters against mocked HTTP, and invalid-output / retry accounting. One test runs the whole benchmark against a fake local Ollama server (`tests/fake_ollama.py`).

## Results

### Live run (real models)

<!-- RESULTS:LIVE:START -->
**Environment.** Real models served by Ollama on a Google Colab free T4 GPU (15 GB). Seed `a02`, three primary puzzles (scrambles of 4, 4 and 5 moves, exact optimum 4, 4 and 5), 30-move limit, 60 s per call, 300 s per puzzle, up to 2 retries. Models run one after another so each has the GPU to itself, and model loading time is not counted in any figure below.

Substitute models were used because OpenRouter credits were not available; the instructor approved the Ollama alternatives. Clef Flash (`clef-flash`) is the decision model. Qwen 3.5 (`qwen3.5`), DeepSeek-R1 (`deepseek-r1`) and Gemma 3 (`gemma3`) stand in for the frontier LLM.

#### Run A: race page run (the run shown in the screen recording)

| Model | Per-move avg latency | Total solve time (avg) | Total moves (avg) | Success rate | Optimality gap (avg) | Invalid outputs |
|---|---|---|---|---|---|---|
| Clef Flash (clef-flash) | 0.726 s | 0:21.79 | 30.0 | 0.0% (0/3) | n/a | 0 |
| Qwen (qwen3.5) | 0.883 s | 0:26.49 | 30.0 | 0.0% (0/3) | n/a | 0 |
| DeepSeek (deepseek-r1) | 49.481 s | 5:00.00 | 0.0 | 0.0% (0/3) | n/a | 18 |
| Gemma (gemma3) | 2.912 s | 1:27.36 | 30.0 | 0.0% (0/3) | n/a | 0 |

![Benchmark charts](results/live/benchmarks.png)

#### Run B: headless benchmark (`python benchmark.py --mode live --seed a02 --warmup 0 --primary 3 --extension 0`), per puzzle

| Puzzle | Scramble | Optimum | Clef Flash | Qwen | DeepSeek | Gemma |
|---|---|---|---|---|---|---|
| primary-01 | D B' R2 B' | 4 | 30 moves, 19.00 s, not solved | 30 moves, 58.52 s, not solved | 0 moves, 300.00 s, out of time (6 invalid) | 30 moves, 99.94 s, not solved |
| primary-02 | D' U' L2 F' | 4 | 30 moves, 22.07 s, not solved | 30 moves, 26.42 s, not solved | 0 moves, 300.00 s, out of time (6 invalid) | 30 moves, 86.50 s, not solved |
| primary-03 | D' U B' L D' | 5 | 30 moves, 21.80 s, not solved | 30 moves, 26.78 s, not solved | 0 moves, 300.00 s, out of time (6 invalid) | 30 moves, 87.68 s, not solved |
| Average total time | | | 20.96 s | 37.24 s | 300.00 s | 91.37 s |

Both runs agree: no model solved any puzzle, and the speed ranking is Clef Flash, then Qwen, then Gemma, then DeepSeek.

#### Notes on the data

- The raw per-trial JSON files from the Colab session were lost when the Colab runtime disconnected, so the tables above are copied from the on-screen statistics slide (Run A) and the benchmark console output (Run B). The chart is drawn from the Run A values. Running `python benchmark.py --mode live --update-readme` regenerates the files and tables.
- Clef Flash, Qwen and Gemma made only valid moves (0 invalid outputs). On every puzzle they used all 30 moves and ended unsolved, repeating the same few moves (for example U and U', or R) instead of working towards a solution.
- DeepSeek-R1 produced no valid move in any of its 18 attempts; each attempt waited the 60 s limit, so each puzzle hit the 300 s limit. This is most likely a mismatch between this reasoning model and the strict JSON-only output format used for all language models, so it says little about its real cube-solving ability.
- Optimality gap is not available because no puzzle was solved.

#### Answers to the required questions

1. **Which model is fastest in terms of making decisions?** Clef Flash, at 0.726 s per decision on average. The slowest model, DeepSeek-R1, averaged 49.481 s, a 68.1x difference. Qwen needed 0.883 s and Gemma 2.912 s.
2. **Which model achieved the highest solve rate?** None. All four models solved 0 of 3 primary puzzles (0.0%), so they tie.
3. **Which model found the shortest solutions, and how close were they to the known optimum?** None. No model solved a primary puzzle, so no optimality gap could be computed. The known optima were 4, 4 and 5 moves.
4. **Did the fastest model also achieve the best solution quality?** Not determinable: no puzzle was solved, so solution quality is tied at zero for every model.
5. **Would you use the fastest decision model, the frontier LLM, or a hybrid agent in a real-world application?** The fast decision model. It matched the language models on solve rate (all 0%) while responding far faster: Clef Flash averaged 21.8 s per puzzle against 26.5 s for the best language model, Qwen, and decided about 1.2x faster per move, with 0 invalid outputs for both. The evidence is mostly about speed, because the quality results are tied at zero. For a real application I would use the decision model as the fast first step and keep a language model only as a fallback for cases it cannot handle, and I would not rely on any of these models alone to solve a cube.

<!-- RESULTS:LIVE:END -->

