"""Build notebooks/01_pipeline_check.ipynb: a thin notebook that imports src/vertex_hub, runs every step,
shows the results and checks them. The logic lives in src/; the notebook only calls it.

Usage: python tools/build_notebook.py          -> writes the notebook
       python tools/build_notebook.py --test   -> also runs every code cell in order (no Jupyter needed)
You can also edit the notebook directly; this script just regenerates the default version.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELLS = []
md = lambda t: CELLS.append(("markdown", t.strip("\n")))
code = lambda t: CELLS.append(("code", t.strip("\n")))

md(r"""
# Vertex Hub: pipeline check notebook

Runs **in parallel with the project**: every cell calls the real code in `src/vertex_hub/` (the same code the Streamlit app uses), shows the result, and checks it with `check(...)`.
If someone breaks a module, the matching cell turns red. The last cell is the health report.

| § | Step | Module |
|---|---|---|
| 1 | Load project + graph | `data`, `graph` |
| 2 | Ontology reconciliation | `ontology` |
| 3 | Guardrails (injection, personal data) | `guardrails` |
| 4 | Extraction + gate | `extract` |
| 5 | Evaluation (seen vs holdout) | `evaluate` |
| 6 | Impact, conflicts, trade-off | `impact`, `graph` |
| 7 | Version upgrade + incoming Jira story | `impact` |
| 8 | Alerts, decisions, Jira outbox | `alerts`, `decisions`, `connectors` |
| 9 | Bootstrapper + impact map | `bootstrap`, `viz` |
| 10 | Health report | |

Local AI: start the Ollama app and `ollama pull qwen2.5:7b` (or set `LLM_MODEL`). Without it, the AI cells are skipped and everything else still runs.
""")

md("## 0. Setup")
code(r"""
%load_ext autoreload
%autoreload 2

import sys
from pathlib import Path
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "src" / "vertex_hub").exists())
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
pd.set_option("display.max_colwidth", 110)

from vertex_hub import run_pipeline
from vertex_hub import llm
from vertex_hub.evaluate import gold_table, score, misses
from vertex_hub.impact import assess, assess_fact, latent_conflicts, tradeoff, version_upgrade
from vertex_hub.graph import impact_subgraph
from vertex_hub.decisions import send_outbox
from vertex_hub.connectors import JiraMock
from vertex_hub.viz import impact_map
from IPython.display import SVG
from vertex_hub.bootstrap import bootstrap
from vertex_hub.data import load_yaml

CHECKS = []
def check(name, condition, detail=""):
    CHECKS.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})
    print(("PASS " if condition else "FAIL ") + name + (f"  ({detail})" if detail else ""))

LLM = llm.status()
print("Repo:", ROOT, "| AI:", LLM["backend"], LLM["model"], "->", LLM["detail"])
""")

md("## 1. Load the project and build the knowledge graph")
code(r"""
twin = run_pipeline(ROOT)      # loads data, builds the graph, glossary, guardrails
p, G = twin.project, twin.G
display(pd.Series(p.counts(), name="count").to_frame())
display(pd.Series(nx.get_node_attributes(G, "kind")).value_counts().rename("graph nodes").to_frame())
check("graph has every backlog item", all(s in G for s in [*p.stories, *p.tests]))
check("every test verifies an existing story", all(t["verifies"] in p.stories for t in p.tests.values()))
""")

md("## 2. Ontology reconciliation")
code(r"""
terms = ["Plant BOM", "BOP", "PBOM", "gamme de fabrication", "désignation article", "ordre de modif", "Plant BOMs", "jig"]
display(pd.DataFrame([twin.glossary.lookup(t) for t in terms]))
check("PBOM = BOP = Plant BOM", {twin.glossary.lookup(t)["concept"] for t in ["PBOM", "BOP", "Plant BOM"]} == {"C-PBOM"})
check("French term maps to the attribute", twin.glossary.find_attributes("la désignation article à 40 caractères") == ["ATT-DESC"])
check("unknown term is flagged, not guessed", twin.glossary.lookup("jig")["concept"] is None)
""")

md("## 3. Guardrails before any AI sees the text")
code(r"""
display(pd.DataFrame(twin.guard_rows))
leaks = [v for vals in p.truth["personal_data"].values() for v in vals if any(v in t for t in twin.sanitized.values())]
check("no personal data in LLM input", not leaks, f"{len(leaks)} leaks")
check("injection quarantined", sum(map(len, twin.blocked.values())) == 1, str(twin.blocked.get("DOC-05")))
print("\nWhat the AI sees, DOC-03 excerpt:\n" + twin.sanitized["DOC-03"][:500])
""")

md("## 4. Extraction and the anti-hallucination gate")
code(r"""
facts, rejected, _ = twin.extract(mode="rules")        # rules, always available
display(pd.DataFrame(facts)[["doc", "attribute", "system", "property", "value", "quote"]])
check("baseline facts all pass the gate", facts and not rejected, f"{len(facts)} accepted")

from vertex_hub.extract import gate
fake = [{"doc": "DOC-03", "kind": "x", "quote": "SAP accepts 500 characters", "attribute": "ATT-DESC",
         "system": "SYS-ERP", "property": "max_length", "value": 500}]
check("gate rejects an invented quote", not gate(p, twin.sanitized, fake)[0])
""")
code(r"""
# Local AI (first run calls the model and fills cache/; later runs are instant)
llm_facts, hybrid_facts, model = [], [], LLM["model"]
if LLM["ok"]:
    llm_facts, llm_rejected, infos = twin.extract(mode="ai", allow_calls=True)
    hybrid_facts, _, _ = twin.extract(mode="hybrid", allow_calls=False)
    display(pd.DataFrame(llm_facts)[["doc", "attribute", "system", "property", "value", "repaired", "quote"]])
    if llm_rejected:
        print("Rejected by the gate:"); display(pd.DataFrame(llm_rejected)[["doc", "attribute", "value", "reason"]])
    check("AI ran on every document", all(i["mode_used"] == "ai" for i in infos.values()))
else:
    print("AI skipped:", LLM["detail"])
""")

md("## 5. Evaluation against ground truth\n**Seen** = documents the rules were written against. **Holdout** = DOC-06 (paraphrases). The holdout row is the honest number.")
code(r"""
gold = gold_table(p.truth)
scores = score(facts, gold, "rules") + (score(llm_facts, f"AI ({model})") + score(hybrid_facts, "hybrid") if llm_facts else [])
display(pd.DataFrame(scores))
display(misses(facts, gold)[["id", "doc", "holdout", "key"]])
base = {r["split"]: r["recall"] for r in score(facts, gold, "b")}
check("baseline recall on seen docs = 1.0", base["seen"] == 1.0)
if hybrid_facts:
    hy = {r["split"]: r for r in score(hybrid_facts, gold, "h")}
    check("hybrid holdout recall >= 0.75 (target)", hy["holdout"]["recall"] >= 0.75, f"{hy['holdout']['recall']}")
    check("hybrid precision = 1.0 on seen docs", hy["seen"]["precision"] == 1.0, f"{hy['seen']['precision']}")
""")

md("## 6. Impact, conflicts and the trade-off card")
code(r"""
latent = latent_conflicts(p)
display(pd.DataFrame(latent, columns=["interface", "issue", "detail"]))
check("2 latent conflicts found with no document", len(latent) == 2)

rows = []
for f in llm_facts or facts:
    r = assess_fact(p, G, f)
    if r:
        rows.append({"doc": f["doc"], "attribute": f["attribute"], "system": f["system"], "change": f"{r['current']} -> {r['new']}",
                     "conflicts": len(r["conflicts"]), "resolves": len(r["resolves"]),
                     "stories_direct": len(r["stories_direct"]), "tests_direct": len(r["tests_direct"])})
display(pd.DataFrame(rows))
""")
code(r"""
card = tradeoff(p, G, "ATT-DESC", "SYS-PLM", "max_length", [
    ("A. Accept: PLM limited to 40", 40, "naming rule (US-501) must change"),
    ("B. Keep 80, truncate in SAP", 80, "data silently truncated at transfer")])
display(pd.DataFrame(card).set_index("option").T)
r = assess(p, G, "ATT-DESC", "SYS-PLM", "max_length", 40)
check("option A resolves the INT-01 truncation", [x[0] for x in r["resolves"]] == ["INT-01"])
check("option A flags outdated test TC-205", r["outdated_tests"] == ["TC-205"])
check("direct impact = 5 stories + 4 tests", (len(r["stories_direct"]), len(r["tests_direct"])) == (5, 4))

display(SVG(impact_map(p, G, "ATT-DESC", r, "If PLM Part Description becomes 40 characters")[0]))
""")

md("## 7. Version upgrade and an incoming Jira story")
code(r"""
diff = load_yaml(ROOT / "ontology" / "editors" / "3dexperience_R2026x.yaml")["changes"]
up = version_upgrade(p, G, diff)
display(pd.DataFrame(up))
check("R2026x upgrade flags 3 new truncations", sum(x["conflicts after upgrade"].count(">") for x in up) == 3)

f412 = next(f for f in facts if f["doc"] == "US-412")
r412 = assess_fact(p, G, f412)
print("US-412:", f412["quote"])
check("MES story flags TC-401 and TC-402", r412["tests_direct"] == ["TC-401", "TC-402"])
""")

md("## 8. Alerts, decisions and the Jira outbox\nAlerts merge every source of the same problem and keep the date it first became visible. Approving a decision updates the model; alerts follow.")
code(r"""
twin.jira = JiraMock(p, ROOT / "cache" / "jira_notebook.json"); twin.jira.reset()
alerts = twin.alerts(mode="hybrid" if hybrid_facts else "rules")
display(pd.DataFrame(alerts)[["id", "severity", "state", "title", "human", "first_seen", "doc_sources"]])
cur = [a for a in alerts if a["state"] == "current"]
check("2 open alerts today", len(cur) == 2, ", ".join(a["title"] for a in cur))
check("description conflict visible since 21 Sept", cur[0]["first_seen"] == "2026-09-21")
""")
code(r"""
f03 = next(f for f, r in twin.pending() if f["doc"] == "DOC-03")
dec_id, drafts = twin.decide(f03, "approved", "A. Accept: PLM limited to 40", "PLM product owner")
f04 = next(f for f, r in twin.pending() if f["doc"] == "DOC-04")
twin.decide(f04, "rejected", "keep kg", "ERP lead", "convert in middleware")
after = twin.alerts()
display(pd.DataFrame(after)[["id", "severity", "state", "title"]])
check("approval closes the INT-01 alert", not any(a["title"] == "Part Description truncated on INT-01" and a["state"] == "current" for a in after))
check("side effect TC-205 becomes a current alert", any(a["title"].startswith("TC-205") and a["state"] == "current" for a in after))
check("rejection removes the unit-mismatch risk", not any(a["kind"] == "unit mismatch" for a in after))
display(twin.audit.df("decisions").drop(columns="fact_key"))
sent, errors = send_outbox(twin.audit, twin.jira)
check("9 Jira comments sent only after the explicit send", sent == 9 and not errors)
""")

md("## 9. Bootstrapper for a new client")
code(r"""
med = load_yaml(ROOT / "data" / "medtech" / "client_profile.yaml")["client"]
starter = bootstrap(ROOT, med)
print(f"{med['name']}: {starter.epic.nunique()} epics, {starter.capability.nunique()} capabilities, {len(starter)} features")
display(starter.head(10))
check("medtech gets V&V", "Verification and validation management" in set(starter.capability))
check("Windchill vocabulary used", any("Change Notice" in x for x in starter.feature))
""")
code(r"""
svg, _ = impact_map(p, G, "ATT-OPLABEL", assess(p, G, "ATT-OPLABEL", "SYS-MES", "max_length", 40), "If MES Operation Label becomes 40 characters (US-412)")
display(SVG(svg))
check("impact map renders", svg.startswith("<svg"))
""")

md("## 10. Health report")
code(r"""
report = pd.DataFrame(CHECKS)
display(report)
n_fail = (report.status == "FAIL").sum()
print(f"{len(report) - n_fail}/{len(report)} checks passed" + ("" if not n_fail else "  <-- FIX BEFORE DEMO"))
""")


def build():
    nb = {"cells": [], "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                    "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    for n, (kind, src) in enumerate(CELLS):
        lines = [l + "\n" for l in src.split("\n")]
        lines[-1] = lines[-1].rstrip("\n")
        cell = {"cell_type": kind, "id": f"c{n:02d}", "metadata": {}, "source": lines}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        nb["cells"].append(cell)
    out = ROOT / "notebooks" / "01_pipeline_check.ipynb"
    out.parent.mkdir(exist_ok=True)
    old = ROOT / "notebooks" / "01_end_to_end.ipynb"
    if old.exists():
        old.unlink()
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", out.relative_to(ROOT), f"({len(CELLS)} cells)")


if __name__ == "__main__":
    build()
    if "--test" in sys.argv:
        import os
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.show = lambda: plt.close("all")
        os.chdir(ROOT / "notebooks")
        import types
        sys.modules["IPython"] = types.ModuleType("IPython")
        sys.modules["IPython.display"] = types.SimpleNamespace(SVG=lambda x: "<svg>")
        ns = {"display": lambda x: print(x.to_string() if hasattr(x, "to_string") else str(x)[:80])}
        for n, (kind, src) in enumerate(CELLS):
            if kind == "code":
                body = "\n".join(l for l in src.split("\n") if not l.startswith("%"))
                exec(compile(body, f"cell{n}", "exec"), ns)
        fails = [c for c in ns["CHECKS"] if c["status"] == "FAIL"]
        print(f"\nNOTEBOOK TEST: {len(ns['CHECKS']) - len(fails)}/{len(ns['CHECKS'])} checks passed")
        sys.exit(1 if fails else 0)
