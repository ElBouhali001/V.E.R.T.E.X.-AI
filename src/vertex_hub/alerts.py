"""Alerts: every cross-system problem, from the data model or from documents, merged, scored and dated.

state "current"    = the problem exists in today's landscape
state "if applied" = a proposal or decision in a document would create it
Severity = base by kind + exposure (items directly affected) + evidence (a failing test already shows it).
"""
from .data import load_yaml
from .decisions import approved_keys
from .extract import fact_key
from .graph import impact
from .impact import assess, assess_fact, definitions, interface_issues

BASE = {"unit mismatch": 4, "truncation": 3, "test data outdated": 2}
DATA_MODEL = {"doc": "data model", "date": None, "quote": "attribute definitions in attributes.yaml"}


def _severity(p, kind, stories, tests):
    score = BASE.get(kind, 2)
    if len(stories) + len(tests) >= 5:
        score += 1
    if any(p.tests[t]["status"] == "Failed" for t in tests):
        score += 1
    return "high" if score >= 4 else "medium" if score == 3 else "low"


def _human(a):
    """'SYS-PLM 80 > SYS-ERP 40' -> 'PLM allows 80 characters, ERP holds only 40: longer values are cut on INT-01.'"""
    import re
    d = a["detail"]
    m = re.match(r"SYS-(\w+) (\d+) > SYS-(\w+) (\d+)", d)
    if a["kind"] == "truncation" and m:
        return f"{m[1]} allows {m[2]} characters, {m[3]} holds only {m[4]}: longer values are cut on {a['interface']}."
    m = re.match(r"SYS-(\w+) (\w+) vs SYS-(\w+) (\w+)", d)
    if a["kind"] == "unit mismatch" and m:
        return f"{m[1]} sends {m[2]}, {m[3]} would store {m[4]}: values off by a factor of 1000 without conversion on {a['interface']}."
    return d + "."


def _doc_ref(p, f):
    d = p.documents.get(f["doc"]) or p.incoming.get(f["doc"]) or {}
    return {"doc": f["doc"], "date": str(d.get("date") or d.get("created") or ""), "quote": f["quote"], "fact": fact_key(f)}


def doc_date(p, doc_id):
    d = p.documents.get(doc_id) or p.incoming.get(doc_id) or {}
    return str(d.get("date") or d.get("created") or "")


def active_facts(twin, facts):
    """Drop facts already decided, and facts superseded by a later approved decision on the same field."""
    p, done = twin.project, twin.decided()
    approved = {(k[1], k[2], k[3]): doc_date(p, k[0]) for k in approved_keys(twin.audit) if len(k) == 5}
    out = []
    for f in facts:
        if fact_key(f) in done:
            continue
        when = approved.get((f.get("attribute"), f.get("system"), f.get("property")))
        if when is not None and doc_date(p, f["doc"]) <= when:
            continue
        out.append(f)
    return out


def build_alerts(twin, facts):
    """Facts already decided are skipped: approved ones are now part of the model, rejected ones are closed."""
    p, G = twin.project, twin.G
    facts = active_facts(twin, facts)
    alerts = {}

    def add(key, kind, state, attr, interface, detail, src, r):
        a = alerts.setdefault(key, {"kind": kind, "state": state, "attribute": attr, "interface": interface, "detail": detail,
                                    "sources": [], "resolutions": [], "stories": r["stories_direct"], "tests": r["tests_direct"]})
        if all((s["doc"], s["quote"]) != (src["doc"], src["quote"]) for s in a["sources"]):
            a["sources"].append(src)

    # 1. today's landscape, no document needed
    for attr in p.attributes:
        for i, kind, d in interface_issues(p, attr, definitions(p, attr)):
            add((i, attr, kind, "current"), kind, "current", attr, i, d, DATA_MODEL, impact(G, attr))

    for t in p.tests.values():
        td = t.get("test_data") or {}
        if "max_length_tested" in td:
            for attr in t["checks"]:
                cur = p.attributes[attr]["definitions"].get(td.get("system", "SYS-PLM"), {}).get("max_length")
                if cur is not None and cur != td["max_length_tested"]:
                    add((t["id"], attr, "test data outdated", "current"), "test data outdated", "current", attr, t["id"],
                        f"{t['id']} still tests {td['max_length_tested']}, model now says {cur}", DATA_MODEL, impact(G, attr))

    # 2. what documents say
    for f in facts:
        if f["property"] == "version":
            path = p.root / "ontology" / "editors" / f"3dexperience_{f['value'].replace('X', 'x')}.yaml"
            diff = load_yaml(path).get("changes", []) if path.exists() else []
            for c in diff:
                for prop, val in c["after"].items():
                    r = assess(p, G, c["attribute"], f["system"], prop, val)
                    for i, kind, d in r["conflicts"]:
                        existing = {(x[0], x[1]) for x in interface_issues(p, c["attribute"], definitions(p, c["attribute"]))}
                        if (i, kind) not in existing:
                            add((i, c["attribute"], kind, "if applied", f["doc"]), kind, "if applied", c["attribute"], i, d, _doc_ref(p, f), r)
            continue
        r = assess_fact(p, G, f)
        if r is None:
            continue
        state = "if applied" if r["current"] != r["new"] else "current"
        for i, kind, d in r["conflicts"]:
            add((i, f["attribute"], kind, state) + ((f["doc"],) if state == "if applied" else ()), kind, state, f["attribute"], i, d, _doc_ref(p, f), r)
        for t in r["outdated_tests"]:
            add((t, f["attribute"], "test data outdated", state, f["doc"]), "test data outdated", state, f["attribute"], t,
                f"{t} tests {f['property']} = {p.tests[t].get('test_data', {}).get('max_length_tested')}, proposal says {f['value']}",
                _doc_ref(p, f), r)
        for i, kind, d in r["resolves"]:
            key = (i, f["attribute"], kind, "current")
            if key in alerts:
                alerts[key]["resolutions"].append({**_doc_ref(p, f), "change": f"{f['system']} {f['property']} {r['current']} -> {r['new']}",
                                                   "side_effects": r["outdated_tests"]})

    out = []
    for a in alerts.values():
        a["severity"] = _severity(p, a["kind"], a["stories"], a["tests"])
        dates = sorted(s["date"] for s in a["sources"] if s["date"])
        a["first_seen"] = dates[0] if dates else None
        a["doc_sources"] = [s["doc"] for s in a["sources"] if s["doc"] != "data model"]
        name = p.attributes[a["attribute"]]["canonical"]
        a["human"] = _human(a)
        a["title"] = {"truncation": f"{name} truncated on {a['interface']}",
                      "unit mismatch": f"{name}: unit mismatch on {a['interface']}",
                      "test data outdated": f"{a['interface']} test data outdated for {name}"}[a["kind"]]
        out.append(a)
    rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda a: (a["state"] != "current", rank[a["severity"]], a["title"]))
    for n, a in enumerate(out, 1):
        a["id"] = f"AL-{n:02d}"
    return out
