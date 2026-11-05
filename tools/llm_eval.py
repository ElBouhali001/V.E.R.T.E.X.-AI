"""Run the real model on every document, fill the cache, and score rules vs AI vs hybrid.

Usage (Ollama running, model pulled):
    python tools/llm_eval.py                          # first installed qwen model
    python tools/llm_eval.py --model qwen2.5-coder:7b
Run it once before the demo: afterwards the app reads answers from cache/ and never waits on the model.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import os  # noqa: E402

import pandas as pd  # noqa: E402

if "--model" in sys.argv:
    os.environ["LLM_MODEL"] = sys.argv[sys.argv.index("--model") + 1]

from vertex_hub import llm, run_pipeline  # noqa: E402
from vertex_hub.evaluate import gold_table, misses, score  # noqa: E402

st = llm.status()
print(f"Backend: {st['backend']} | model: {st['model']} | {st['detail']}")
if not st["ok"]:
    sys.exit(1)

t = run_pipeline(ROOT)
gold = gold_table(t.project.truth)
rows, rejected = [], []
for doc in t.sanitized:
    t0 = time.time()
    _, rej, info = t.extract_doc(doc, mode="ai")
    print(f"  {doc:8s} {time.time() - t0:5.1f}s  {info['warning'] or 'ok'}")
    rejected += rej

for mode in ("rules", "ai", "hybrid"):
    acc, _, _ = t.extract(mode=mode)
    rows += score(acc, gold, mode)
pd.set_option("display.width", 160)
print("\n", pd.DataFrame(rows).to_string(index=False))
acc, _, _ = t.extract(mode="hybrid")
print("\nHybrid still misses:\n", misses(acc, gold)[["id", "doc", "key"]].to_string(index=False) or "nothing")
if rejected:
    print("\nRejected by the gate (AI):")
    print(pd.DataFrame(rejected)[["doc", "attribute", "value", "reason"]].to_string(index=False))
