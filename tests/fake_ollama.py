import json
import sys

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from race.cube import MOVES
from race.solver import optimal_solution

app = FastAPI()
MODELS = ["clef-flash:latest", "qwen3.5:latest", "deepseek-r1:latest", "gemma3:latest"]
CALLS = {"systemone": 0, "chat": 0, "load": 0}


def best_move(state):
    sol = optimal_solution(state)
    return sol[0] if sol else MOVES[0]


@app.get("/api/tags")
async def tags():
    return {"models": [{"name": m} for m in MODELS]}


@app.get("/calls")
async def calls():
    return CALLS


@app.post("/v1/systemone")
async def systemone(req: Request):
    body = await req.json()
    if "next_move" not in body["questions"]:
        CALLS["load"] += 1
        return {"model": body["model"], "answers": {"ready": {"type": "noul", "noul": 1.0}}, "usage": {}}
    CALLS["systemone"] += 1
    state = body["state"]["cube_facelets"]
    move = best_move(state)
    probs = {m: 0.01 for m in body["questions"]["next_move"]["criteria"]}
    probs[move] = 0.9
    return {
        "model": body["model"],
        "answers": {"next_move": {"type": "choice", "choice": move, "confidence": 0.9, "probabilities": probs}},
        "usage": {"input_tokens": 100, "output_tokens": 5},
    }


@app.post("/api/generate")
async def generate(req: Request):
    body = await req.json()
    CALLS["load"] += 1
    return {"model": body["model"], "response": "", "done": True}


@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    if not body["messages"]:
        CALLS["load"] += 1
        return {"model": body["model"], "message": {"role": "assistant", "content": ""}, "done": True}
    CALLS["chat"] += 1
    if body["model"] == "deepseek-r1" and "think" in body:
        return JSONResponse({"error": "\"deepseek-r1:8b\" does not support thinking"}, status_code=400)
    user = json.loads(body["messages"][1]["content"])
    move = best_move(user["cube_facelets"])
    content = json.dumps({"move": move})
    if body["model"] == "deepseek-r1":
        content = "<think>try {\"move\": \"R\"} maybe</think>" + content
    if body["model"] == "gemma3" and CALLS["chat"] % 5 == 0:
        content = "I would turn the right face"
    return {"model": body["model"], "message": {"role": "assistant", "content": content}, "done": True}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
