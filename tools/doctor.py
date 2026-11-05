"""Vertex Hub doctor: checks everything the demo needs, in order, and says how to fix what fails.

Usage:  python tools/doctor.py            (full check, calls the local model)
        python tools/doctor.py --warm     (also reads every document with the model so the demo never waits)
"""
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RESULTS = []


def report(status, name, detail="", fix=""):
    RESULTS.append(status)
    mark = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[status]
    print(f"{mark}  {name}" + (f"  ({detail})" if detail else ""))
    if fix and status != "PASS":
        print(f"      fix: {fix}")


print("Vertex Hub doctor\n")

# 1. python and packages
ok = sys.version_info >= (3, 10)
report("PASS" if ok else "FAIL", "Python 3.10 or newer", sys.version.split()[0], "uv venv --python 3.11 .venv && source .venv/bin/activate")
missing = [m for m in ("yaml", "pandas", "networkx", "pydantic", "streamlit", "matplotlib") if importlib.util.find_spec(m) is None]
report("FAIL" if missing else "PASS", "Python packages", ", ".join(missing) or "all installed", "uv pip install -r requirements.txt")
if missing:
    sys.exit(1)
report("PASS" if importlib.util.find_spec("pypdf") else "WARN", "PDF reading (pypdf)", "" if importlib.util.find_spec("pypdf") else "PDF datasets will be skipped",
       "uv pip install pypdf")

from vertex_hub import llm, run_pipeline  # noqa: E402
from vertex_hub.assistant import answer  # noqa: E402

# 2. project data
t0 = time.time()
try:
    twin = run_pipeline(ROOT)
    report("PASS", "Project loads", f"{len(twin.sanitized)} documents, {len(twin.project.attributes)} attributes, {time.time() - t0:.1f}s")
except Exception as e:
    report("FAIL", "Project loads", repr(e)[:120], "python tools/validate_dataset.py, then fix the file it names")
    sys.exit(1)

# 3. datasets
if len(twin.library):
    det = "; ".join(f"{s['dataset']}: {s['passages']} passages from {s['files read']} files" + (f", skipped {s['skipped']}" if s["skipped"] else "")
                    for s in twin.library_summary)
    report("PASS", "Datasets in data/external", det)
else:
    report("WARN", "Datasets in data/external", "none found", "see data/external/README.md for links and folders")

# 4. local model
st = llm.status()
report("PASS" if st["ok"] else "FAIL", "Local model", f"{st['backend']} {st['model']}: {st['detail']}",
       "open the Ollama app, then: ollama pull qwen2.5:7b")
if st["ok"]:
    t0 = time.time()
    try:
        reply = llm.call("Reply with the single word OK.", st["backend"], st["model"], json_mode=False, timeout=120)
        dt = time.time() - t0
        report("PASS" if "ok" in reply.lower() else "WARN", "Model answers", f"{dt:.1f}s, said: {reply.strip()[:30]!r}",
               "a first call loads the model into memory; run the doctor again")
        if dt > 30:
            report("WARN", "Model speed", f"{dt:.0f}s for one word", "close other apps, or use a smaller model: ollama pull qwen2.5:3b")
    except Exception as e:
        report("FAIL", "Model answers", repr(e)[:120], "restart the Ollama app; check `curl http://localhost:11434`")

    # 5. extraction on one real document
    t0 = time.time()
    acc, rej, info = twin.extract_doc("DOC-03", "ai", allow_calls=True)
    report("PASS" if acc and info["mode_used"] == "ai" else "WARN", "AI extraction on DOC-03 (French minutes)",
           f"{len(acc)} facts accepted, {len(rej)} stopped by the source check, {time.time() - t0:.1f}s, {info['warning'] or 'ok'}",
           "try another model: ollama pull qwen2.5:7b, then restart; hybrid mode keeps the rules as a safety net")

    # 6. cache coverage
    if "--warm" in sys.argv:
        for d in twin.sanitized:
            t0 = time.time()
            twin.extract_doc(d, "ai", allow_calls=True)
            print(f"      read {d} in {time.time() - t0:.1f}s")
    cached = sum(twin.ai_ready(d) for d in twin.sanitized)
    report("PASS" if cached == len(twin.sanitized) else "WARN", "Documents already read by the model (cache)",
           f"{cached}/{len(twin.sanitized)}", "python tools/doctor.py --warm   (so the live demo never waits)")

# 7. assistant
t0 = time.time()
r = answer(twin, "What is a Plant BOM?")
report("PASS" if "C-PBOM" in r["cited"] and not r["unverified"] else "WARN", "Ask Vertex",
       f"{r['engine']}, cited {r['cited']}, {time.time() - t0:.1f}s", "if engine is 'graph', the model is not reachable from the app")
if len(twin.library):
    r = answer(twin, "Which requirements talk about availability?")
    report("PASS" if any(c.startswith("EXT-") for c in r["cited"]) else "WARN", "Ask Vertex over the datasets",
           f"{r['engine']}, cited {r['cited'][:4]}", "check the dataset files are in data/external/<name>/")

fails, warns = RESULTS.count("FAIL"), RESULTS.count("WARN")
print(f"\n{'READY' if not fails else 'NOT READY'}: {RESULTS.count('PASS')} pass, {warns} warning(s), {fails} failure(s)")
sys.exit(1 if fails else 0)
