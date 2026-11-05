"""Score guardrails.py against public out-of-sample benchmarks (see tools/benchmarks/README.md).

Usage: python tools/guardrails_eval.py

Injection: precision/recall of is_injection() against deepset/prompt-injections (662 labelled rows),
reported separately for the train and test split. INJECTION_PATTERNS in guardrails.py was tuned by
reading train-split misses only (see git history); the test-split number is the honest, held-out one
-- quote that one, not train, in any report of how well this detects real injection attempts.
Redaction: recall of Redactor against presidio-research's synthetic PERSON/EMAIL/PHONE spans (747 rows).
Both sets are untouched by the detectors' own design, so this is a generalisation check, not the
"does it find the planted demo scenarios" check tests/test_guardrails.py already covers.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vertex_hub.guardrails import EMAIL, PHONE, is_injection  # noqa: E402

BENCH = ROOT / "tools" / "benchmarks"


def eval_injection():
    rows = json.loads((BENCH / "injection" / "prompt_injections.json").read_text())
    for split in ("train", "test"):
        sub = [r for r in rows if r["split"] == split]
        tp = sum(1 for r in sub if r["label"] == 1 and is_injection(r["text"]))
        fp = sum(1 for r in sub if r["label"] == 0 and is_injection(r["text"]))
        pos = sum(r["label"] for r in sub)
        neg = len(sub) - pos
        tag = "(tuned on this split)" if split == "train" else "(held-out -- the honest number)"
        print(f"Injection  {split:5s} {tag}: recall {tp / pos:.0%} ({tp}/{pos})  "
              f"false-positive rate {fp / neg:.1%} ({fp}/{neg})")


def eval_redaction():
    """EMAIL/PHONE have standalone regexes we can test directly against each labelled span. PERSON
    needs the anchor heuristic (name followed by "(Acme"/"(consulting)") which this general-purpose
    benchmark doesn't provide, so PERSON recall isn't measurable here -- see benchmarks/README.md."""
    rows = json.loads((BENCH / "pii" / "synth_pii.json").read_text())
    counts = {"EMAIL_ADDRESS": [0, 0], "PHONE_NUMBER": [0, 0]}
    for r in rows:
        for s in r["spans"]:
            kind = s["entity_type"]
            if kind not in counts:
                continue
            ok = bool((EMAIL if kind == "EMAIL_ADDRESS" else PHONE).search(s["entity_value"]))
            counts[kind][int(ok)] += 1
    for kind, (miss, hit) in counts.items():
        total = hit + miss
        print(f"Redaction  {kind:14s} recall {hit / total:.0%}  ({hit}/{total})")
    print("Redaction  PERSON          recall n/a -- the anchor heuristic (name + \"(Acme\"/\"(consulting)\") "
          "has no equivalent signal in this benchmark; see tools/benchmarks/README.md")


if __name__ == "__main__":
    eval_injection()
    eval_redaction()
