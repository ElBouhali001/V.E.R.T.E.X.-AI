"""Score extractions against data/<client>/expected_extractions.yaml (seen vs holdout)."""
import pandas as pd

from .extract import fact_key


def gold_table(truth):
    rows = []
    for x in truth.get("extractions", []):
        a = x["affects"]
        if "attribute" in a:
            k = (x["doc"], a["attribute"], a["system"], a["property"], str(a["value"]))
        elif x["kind"] == "version_change":
            k = (x["doc"], "version", a["to_profile"].split("_")[-1].upper())
        else:
            continue
        rows.append({"id": x["id"], "doc": x["doc"], "holdout": x.get("holdout", False), "key": k})
    return pd.DataFrame(rows)


def score(facts, gold, name):
    pred = {fact_key(f) for f in facts}
    rows = []
    for split, g in gold.groupby("holdout"):
        gkeys, docs = set(g.key), set(g.doc)
        p = {k for k in pred if k[0] in docs}
        tp = len(p & gkeys)
        rows.append({"extractor": name, "split": "holdout" if split else "seen", "gold": len(gkeys), "predicted": len(p),
                     "correct": tp, "precision": round(tp / len(p), 2) if p else None, "recall": round(tp / len(gkeys), 2)})
    return rows


def misses(facts, gold):
    pred = {fact_key(f) for f in facts}
    return gold[~gold.key.isin(pred)]
