import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rubiks_cube_race_colab.ipynb")

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)})


def code(text):
    cells.append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": text.strip("\n").splitlines(True),
        }
    )



md(
    """
# Rubik's Cube Race on Colab

Choose **Runtime > Change runtime type > T4 GPU** and press Save. Then run the cells from top to bottom, one at a time. Upload the project zip `rubiks-cube-race.zip` when asked.
"""
)

code(
    """
import os
import re
import shutil
import subprocess
import sys
import time

gpu = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout
print(gpu or "NO GPU FOUND")
if "GPU" not in gpu:
    raise RuntimeError("No GPU. Use Runtime > Change runtime type > T4 GPU, then run this cell again.")
"""
)

code(
    """
import glob
import zipfile

from google.colab import files

os.chdir("/content")
uploaded = files.upload()
archive = next(n for n in uploaded if n.lower().endswith(".zip"))
shutil.rmtree("/content/project_extract", ignore_errors=True)
zipfile.ZipFile(archive).extractall("/content/project_extract")
found = glob.glob("/content/project_extract/**/benchmark.py", recursive=True)
assert found, "benchmark.py not found inside the zip. Upload the project zip, not a single file."
PROJECT = "/content/rubiks-cube-race"
shutil.rmtree(PROJECT, ignore_errors=True)
shutil.copytree(os.path.dirname(found[0]), PROJECT)
print("project ready:", PROJECT)
"""
)

code(
    """
!pip install -q fastapi "uvicorn[standard]" httpx python-dotenv matplotlib
!apt-get install -y -q zstd pciutils > /dev/null
!curl -fsSL https://ollama.com/install.sh | sh
"""
)

code(
    """
import httpx

ollama_server = subprocess.Popen(
    ["ollama", "serve"],
    env=dict(os.environ, OLLAMA_HOST="127.0.0.1:11434", OLLAMA_KEEP_ALIVE="30m"),
    stdout=open("/content/ollama.log", "w"),
    stderr=subprocess.STDOUT,
)
version = None
for _ in range(90):
    try:
        version = httpx.get("http://127.0.0.1:11434/api/version", timeout=2).json()["version"]
        break
    except Exception:
        time.sleep(1)
print("Ollama version:", version)
parts = tuple(int(x) for x in re.findall(r"\\d+", version or "0")[:3])
if not version or parts < (0, 35, 1):
    raise RuntimeError("Ollama is missing or older than 0.35.1, which Clef Flash needs. See /content/ollama.log")
"""
)

code(
    """
for tag in ["clef-flash", "qwen3.5", "deepseek-r1", "gemma3"]:
    print("downloading", tag, flush=True)
    if subprocess.run(["ollama", "pull", tag]).returncode != 0:
        raise RuntimeError("could not download " + tag)
print("all models downloaded")
"""
)

code(
    """
STUDENT_NAME = "Urooj Baloch"
STUDENT_ROLL = "23K-0071"

os.chdir(PROJECT)
out = []
for line in open(".env.ollama.example").read().splitlines():
    if line.startswith("STUDENT_NAME="):
        line = "STUDENT_NAME=" + STUDENT_NAME
    elif line.startswith("STUDENT_ROLL="):
        line = "STUDENT_ROLL=" + STUDENT_ROLL
    out.append(line)
open(".env", "w").write("\\n".join(out) + "\\n")
print(open(".env").read())
!python check_models.py
"""
)

md("## Benchmark (results and README). Wait until it prints `README.md updated`. It takes about 30 to 45 minutes.")

code(
    """
!python benchmark.py --mode live --seed a02 --warmup 0 --primary 3 --extension 0 --out results/live --update-readme
"""
)

md("## Race page (for the screen recording). Run only after the benchmark has finished. Open the page, choose Live, set Warm-up 0, Primary 3, Extension 0, start your screen recording, then press Run.")

code(
    """
ui_server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "race.server:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=PROJECT,
    env=dict(os.environ, UI_PUZZLE_PAUSE_SECONDS="3"),
)
time.sleep(5)
from google.colab import output

output.serve_kernel_port_as_window(8000)
"""
)

md("## Download the finished project. Run after the benchmark and your recording are done.")

code(
    """
readme_path = os.path.join(PROJECT, "README.md")
text = open(readme_path).read()
a = text.index("<!-- NOTE:START -->") + len("<!-- NOTE:START -->")
b = text.index("<!-- NOTE:END -->")
note = (
    "\\nThe recording and the results in the \\"Live run\\" section come from a real live run of the models on Ollama "
    "(Clef Flash, Qwen 3.5, DeepSeek-R1, Gemma 3), executed on Google Colab GPU hardware, so the speed figures reflect that hardware. "
    "The results in the \\"Simulated run\\" section are scripted and only validate the pipeline.\\n"
)
open(readme_path, "w").write(text[:a] + note + text[b:])
shutil.make_archive("/content/rubiks-cube-race-final", "zip", "/content", "rubiks-cube-race")
files.download("/content/rubiks-cube-race-final.zip")
"""
)

nb = {
    "cells": cells,
    "metadata": {
        "colab": {"provenance": [], "gpuType": "T4"},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

with open(OUT, "w") as fh:
    json.dump(nb, fh, indent=1)
print("wrote", OUT)
