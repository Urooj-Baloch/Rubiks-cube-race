const COLORS = { U: "#f8fafc", R: "#dc2626", F: "#16a34a", D: "#facc15", L: "#f97316", B: "#2563eb" };
const FACE_ORDER = ["U", "R", "F", "D", "L", "B"];
const $ = (id) => document.getElementById(id);

const S = { models: [], panels: {}, source: null, summary: null, answers: [], mode: "sim", puzzleTotal: 0, puzzleIndex: 0, timers: {} };

function buildCube() {
  const scene = document.createElement("div");
  scene.className = "scene";
  const rank = document.createElement("div");
  rank.className = "rank";
  scene.appendChild(rank);
  const cube = document.createElement("div");
  cube.className = "cube";
  const stickers = [];
  FACE_ORDER.forEach((f) => {
    const face = document.createElement("div");
    face.className = "face " + f;
    for (let i = 0; i < 9; i++) {
      const s = document.createElement("div");
      s.className = "sticker";
      face.appendChild(s);
      stickers.push(s);
    }
    cube.appendChild(face);
  });
  scene.appendChild(cube);
  return { scene, stickers, rank };
}

function paint(panel, state) {
  for (let i = 0; i < 54; i++) panel.stickers[i].style.background = COLORS[state[i]] || "#888";
}

function fmtTime(sec) {
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return m + ":" + s.toFixed(2).padStart(5, "0");
}

function buildPanels(models) {
  const arena = $("arena");
  arena.innerHTML = "";
  S.panels = {};
  models.forEach((m) => {
    const el = document.createElement("div");
    el.className = "panel";
    const llm = m.category === "Frontier LLM";
    el.innerHTML =
      '<div class="panel-head"><span>' + m.label + '</span><span class="chip ' + (llm ? "llm" : "dec") + '">' + (llm ? "LLM" : "Decision model") + "</span></div>" +
      '<div class="panel-body"><div class="cubeslot"></div><div class="readout">' +
      '<div class="stat"><small>TIME</small><b class="t">0:00.00</b></div>' +
      '<div class="stat"><small>MOVES</small><b class="mv-count">0</b></div>' +
      '<div class="status">waiting</div><div class="result"></div></div></div><div class="history"></div>';
    const cube = buildCube();
    el.querySelector(".cubeslot").replaceWith(cube.scene);
    arena.appendChild(el);
    S.panels[m.key] = {
      el, stickers: cube.stickers, rank: cube.rank,
      t: el.querySelector(".t"), mv: el.querySelector(".mv-count"), status: el.querySelector(".status"),
      result: el.querySelector(".result"), history: el.querySelector(".history"), start: null,
    };
    paint(S.panels[m.key], "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB");
  });
}

function resetPanels(state) {
  Object.values(S.panels).forEach((p) => {
    p.el.className = "panel";
    p.rank.textContent = "";
    p.t.textContent = "0:00.00";
    p.mv.textContent = "0";
    p.status.className = "status";
    p.status.textContent = "ready";
    p.result.textContent = "";
    p.history.innerHTML = "";
    p.start = null;
    paint(p, state);
  });
}

function tick() {
  const now = performance.now();
  Object.values(S.panels).forEach((p) => {
    if (p.start !== null) p.t.textContent = fmtTime((now - p.start) / 1000);
  });
  requestAnimationFrame(tick);
}

function handle(ev) {
  const p = S.panels[ev.model];
  switch (ev.type) {
    case "run_started":
      S.models = ev.models;
      S.puzzleTotal = ev.puzzles.length;
      S.puzzleIndex = 0;
      buildPanels(ev.models);
      $("modeBadge").textContent = ev.mode === "sim" ? "SIMULATED" : "LIVE \u00b7 " + (ev.backend === "ollama" ? "OLLAMA" : "OPENROUTER");
      $("modeBadge").className = "badge " + (ev.mode === "sim" ? "sim" : "live");
      break;
    case "puzzle_started":
      S.puzzleIndex += 1;
      resetPanels(ev.state);
      $("pzLabel").textContent = "Puzzle " + S.puzzleIndex + "/" + S.puzzleTotal + " - " + ev.puzzle;
      $("pzMeta").textContent = "scramble (" + ev.scramble_length + "): " + ev.scramble.join(" ") + " | exact optimum: " + (ev.optimal === null ? "unknown (<= 20)" : ev.optimal + " moves");
      $("pzProgress").textContent = "tier: " + ev.tier;
      break;
    case "trial_started":
      p.start = performance.now();
      p.status.textContent = "starting";
      break;
    case "loading":
      p.status.className = "status thinking";
      p.status.textContent = "loading model...";
      break;
    case "thinking":
      p.status.className = "status thinking";
      p.status.textContent = "thinking...";
      break;
    case "step": {
      p.status.className = "status";
      p.status.textContent = ev.move ? "move " + ev.move + (ev.confidence ? " (conf " + ev.confidence.toFixed(2) + ")" : "") + " - " + ev.latency.toFixed(2) + " s" : "invalid output (" + ev.errors.join(",") + ")";
      p.mv.textContent = ev.applied;
      const chip = document.createElement("span");
      chip.className = "mv" + (ev.move ? "" : " bad");
      chip.textContent = ev.move || "x";
      p.history.appendChild(chip);
      p.history.scrollTop = p.history.scrollHeight;
      paint(p, ev.state);
      break;
    }
    case "trial_finished": {
      const r = ev.result;
      p.start = null;
      p.t.textContent = fmtTime(r.total_time);
      p.mv.textContent = r.moves;
      p.status.className = "status";
      p.status.textContent = r.solved && r.opt_gap !== null ? "optimality gap " + r.opt_gap : "";
      p.el.classList.add("done", r.solved ? "solved" : "failed");
      p.result.className = "result " + (r.solved ? "ok" : "bad");
      p.result.textContent = r.solved ? "SOLVED ✓" : r.status === "OUT_OF_TIME" ? "OUT OF TIME • NOT SOLVED" : "RAN OUT OF MOVES • NOT SOLVED";
      paint(p, r.final_state);
      break;
    }
    case "puzzle_finished": {
      const order = ev.results.slice().sort((a, b) => (b.solved - a.solved) || (a.total_time - b.total_time));
      order.forEach((r, i) => {
        const pn = S.panels[r.model];
        pn.rank.textContent = ["1st", "2nd", "3rd", "4th"][i] || String(i + 1);
        pn.rank.style.background = r.solved ? "#eab308" : "#94a3b8";
        pn.el.classList.add("ranked");
      });
      break;
    }
    case "run_finished":
      S.summary = ev.summary;
      $("showStats").disabled = false;
      $("run").disabled = false;
      $("pzProgress").textContent = "run complete";
      break;
    case "analysis":
      S.answers = ev.answers;
      renderSlide();
      showSlide(true);
      break;
    case "error":
      $("notice").textContent = ev.message;
      $("run").disabled = false;
      break;
  }
}

function barChart(title, rows, fmt, color) {
  const max = Math.max(...rows.map((r) => r.v), 1e-9);
  const div = document.createElement("div");
  div.className = "chart";
  div.innerHTML = "<h4>" + title + "</h4>" + rows.map((r) =>
    '<div class="bar-row"><span>' + r.label + '</span><div class="bar-track"><div class="bar-fill" style="width:' + (100 * r.v / max) + "%;background:" + (r.llm ? "#b45309" : "#1d4ed8") + '"></div></div><span>' + fmt(r.v) + "</span></div>"
  ).join("");
  return div;
}

function renderSlide() {
  const sum = S.summary;
  if (!sum) return;
  const table = Object.keys(sum.graded_overall).length ? sum.graded_overall : sum.overall;
  const primary = sum.by_tier.primary || table;
  const n = (x, d) => (x === null || x === undefined ? "n/a" : x.toFixed(d));
  const keys = Object.keys(table);
  $("slideMode").textContent = S.models.length && S.models[0].label.includes("(sim)") ? "SIMULATED DATA" : "LIVE DATA";
  $("slideMode").className = "badge " + ($("slideMode").textContent.startsWith("SIM") ? "sim" : "live");
  $("statsTable").innerHTML =
    '<table class="stats"><thead><tr><th>Model</th><th>Per-move avg latency</th><th>Total solve time (avg)</th><th>Total moves (avg)</th><th>Success rate</th><th>Optimal gap (avg, primary)</th><th>Invalid outputs</th></tr></thead><tbody>' +
    keys.map((k) => {
      const v = table[k];
      const g = primary[k] ? primary[k].avg_opt_gap : null;
      return "<tr><td>" + v.label + "</td><td>" + n(v.avg_move_latency, 3) + " s</td><td>" + fmtTime(v.avg_total_time) + "</td><td>" + n(v.avg_total_moves, 1) + "</td><td>" + n(v.success_rate, 1) + "% (" + v.solved + "/" + v.trials + ")</td><td>" + n(g, 2) + "</td><td>" + v.invalid_outputs + "</td></tr>";
    }).join("") + "</tbody></table>";
  const rows = (f) => keys.map((k) => ({ label: table[k].label.split(" ")[0], v: f(k) || 0, na: f(k) === null || f(k) === undefined, llm: table[k].category === "Frontier LLM" }));
  const ch = $("statsCharts");
  ch.innerHTML = "";
  ch.appendChild(barChart("Avg latency per move (s)", rows((k) => table[k].avg_move_latency), (x) => x.toFixed(2)));
  ch.appendChild(barChart("Success rate (%)", rows((k) => table[k].success_rate), (x) => x.toFixed(0)));
  ch.appendChild(barChart("Avg total moves", rows((k) => table[k].avg_total_moves), (x) => x.toFixed(1)));
  ch.appendChild(barChart("Avg optimality gap (primary)", rows((k) => primary[k] && primary[k].avg_opt_gap), (x) => x.toFixed(1)));
  $("answers").innerHTML = "<ol>" + S.answers.map((a) => "<li><b>" + a[0] + "</b><br>" + a[1] + "</li>").join("") + "</ol>";
}

function showSlide(on) {
  $("slide").classList.toggle("hidden", !on);
}

async function start() {
  $("notice").textContent = "";
  $("run").disabled = true;
  $("showStats").disabled = true;
  showSlide(false);
  const body = {
    mode: $("mode").value,
    seed: $("seed").value || "a02",
    warmup: +$("nWarmup").value,
    primary: +$("nPrimary").value,
    extension: +$("nExtension").value,
  };
  const res = await fetch("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    $("notice").textContent = j.detail || "could not start";
    $("run").disabled = false;
    return;
  }
  const { run_id } = await res.json();
  if (S.source) S.source.close();
  S.source = new EventSource("/api/runs/" + run_id + "/events");
  S.source.onmessage = (m) => handle(JSON.parse(m.data));
  S.source.addEventListener("end", () => S.source.close());
  S.source.onerror = () => {};
}

async function init() {
  const cfg = await (await fetch("/api/config")).json();
  $("studentName").textContent = cfg.student_name;
  $("studentRoll").textContent = cfg.student_roll;
  $("mode").querySelector('option[value="live"]').textContent = "Live (" + cfg.live_name + ")";
  if (!cfg.live_available) {
    $("mode").querySelector('option[value="live"]').disabled = true;
    $("notice").textContent = "Live mode disabled: set OPENROUTER_API_KEY in .env, or set BACKEND=ollama to use local models";
  }
  const params = new URLSearchParams(location.search);
  if (params.get("mode")) $("mode").value = params.get("mode");
  S.models = cfg.models.map((m) => ({ key: m.key, label: m.label, category: m.category }));
  buildPanels(S.models);
  $("run").addEventListener("click", start);
  $("showStats").addEventListener("click", () => { renderSlide(); showSlide(true); });
  $("closeSlide").addEventListener("click", () => showSlide(false));
  requestAnimationFrame(tick);
}

init();
