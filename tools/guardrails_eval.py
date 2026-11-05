"""Score guardrails.py against public out-of-sample benchmarks (see tools/benchmarks/README.md).

Usage: python tools/guardrails_eval.py

Injection: precision/recall of is_injection() against deepset/prompt-injections (662 labelled rows).
Redaction: recall of Redactor against presidio-research's synthetic PERSON/EMAIL/PHONE spans (747 rows).
Both sets are untouched by the detectors' own design, so this is an honest generalisation check,
not the "does it find the planted demo scenarios" check tests/test_guardrails.py already covers.
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
    tp = fp = tn = fn = 0
    for r in rows:
        pred = is_injection(r["text"])
        actual = bool(r["label"])
        tp += pred and actual
        fp += pred and not actual
        tn += not pred and not actual
        fn += not pred and actual
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    print(f"Injection  ({len(rows)} rows, {tp + fn} positive): "
          f"precision {precision:.0%}  recall {recall:.0%}  (tp={tp} fp={fp} tn={tn} fn={fn})")
    return recall


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
