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
