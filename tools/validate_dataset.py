"""Validate the synthetic dataset and compute the expected demo results.

Usage: python tools/validate_dataset.py [repo_root]
Checks referential integrity, verifies that every ground-truth quote exists word for word,
computes impacted items per extraction, scans for latent cross-system conflicts,
and writes data/acme/expected_results.json.
"""
import json
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
acme = root / "data" / "acme"
load = lambda p: yaml.safe_load(p.read_text(encoding="utf-8"))

errors, infos = [], []

systems_doc = load(acme / "systems.yaml")
systems = {s["id"]: s for s in systems_doc["systems"]}
interfaces = {i["id"]: i for i in systems_doc["interfaces"]}
attributes = {a["id"]: a for a in load(acme / "attributes.yaml")["attributes"]}
backlog = load(acme / "backlog.yaml")
epics = {e["id"]: e for e in backlog["epics"]}
caps = {c["id"]: c for c in backlog["capabilities"]}
feats = {f["id"]: f for f in backlog["features"]}
stories = {s["id"]: s for s in backlog["user_stories"]}
tests = {t["id"]: t for t in load(acme / "test_cases.yaml")["test_cases"]}
concepts = {c["id"]: c for c in load(acme / "glossary.yaml")["concepts"]}

incoming = {}
for p in sorted((acme / "incoming").glob("*.yaml")):
    item = load(p)
    incoming[item["id"]] = item

docs = {}
for p in sorted((acme / "documents").glob("*.md")):
    text = p.read_text(encoding="utf-8")
    doc_id = yaml.safe_load(text.split("---")[1])["id"]
    docs[doc_id] = text


def need(ref, pool, where):
    if ref not in pool:
        errors.append(f"{where}: unknown reference {ref}")


# --- referential integrity
all_ids = [*systems, *interfaces, *attributes, *epics, *caps, *feats, *stories, *tests, *concepts, *incoming]
dupes = {i for i in all_ids if all_ids.count(i) > 1}
if dupes:
    errors.append(f"duplicate ids: {sorted(dupes)}")

for i in interfaces.values():
    need(i["from"], systems, i["id"])
    need(i["to"], systems, i["id"])
    for a in i["carries"]:
        need(a, attributes, i["id"])
for a in attributes.values():
    for s in a["definitions"]:
        need(s, systems, a["id"])
for c in caps.values():
    need(c["epic"], epics, c["id"])
for f in feats.values():
    need(f["capability"], caps, f["id"])
for s in [*stories.values(), *incoming.values()]:
    need(s["feature"], feats, s["id"])
    for a in s["uses"]:
        need(a, attributes, s["id"])
    for i in s["implements"]:
        need(i, interfaces, s["id"])
for t in tests.values():
    need(t["verifies"], stories, t["id"])
    for a in t["checks"]:
        need(a, attributes, t["id"])
    for i in t["exercises"]:
        need(i, interfaces, t["id"])
for c in concepts.values():
    if "maps_to_attribute" in c:
        need(c["maps_to_attribute"], attributes, c["id"])

tested = {t["verifies"] for t in tests.values()}
untested = sorted(set(stories) - tested)
if untested:
    infos.append(f"stories with no test case: {untested}")


# --- impact computation (mirrors ontology/core.yaml impact_walk)
def impact(attr_id):
    ints = sorted(i for i, v in interfaces.items() if attr_id in v["carries"])
    direct_us = {s for s, v in stories.items() if attr_id in v["uses"]}
    via_int_us = {s for s, v in stories.items() if set(v["implements"]) & set(ints)}
    direct_tc = {t for t, v in tests.items() if attr_id in v["checks"]}
    via_tc = {t for t, v in tests.items() if v["verifies"] in direct_us}
    return {
        "interfaces": ints,
        "systems": sorted(attributes[attr_id]["definitions"]),
        "user_stories_direct": sorted(direct_us),
        "user_stories_via_interface": sorted(via_int_us - direct_us),
        "test_cases_direct": sorted(direct_tc),
        "test_cases_via_story": sorted(via_tc - direct_tc),
    }


def current_value(attr_id, system, prop):
    return attributes[attr_id]["definitions"].get(system, {}).get(prop)


def interface_issues(attr_id, defs):
    """Directional check: data flowing into a shorter field, or across different units."""
    issues = set()
    for i in interfaces.values():
        if attr_id not in i["carries"]:
            continue
        src, dst = defs.get(i["from"], {}), defs.get(i["to"], {})
        if "max_length" in src and "max_length" in dst and src["max_length"] > dst["max_length"]:
            issues.add((i["id"], "truncation", f"{i['from']} {src['max_length']} > {i['to']} {dst['max_length']}"))
        if "unit" in src and "unit" in dst and src["unit"] != dst["unit"]:
            issues.add((i["id"], "unit mismatch", f"{i['from']} {src['unit']} vs {i['to']} {dst['unit']}"))
    return issues


def conflicts_for(attr_id, system, prop, value):
    before = {k: dict(v) for k, v in attributes[attr_id]["definitions"].items()}
    after = {k: dict(v) for k, v in before.items()}
    after.setdefault(system, {})[prop] = value
    issues_before, issues_after = interface_issues(attr_id, before), interface_issues(attr_id, after)
    out = [{"interface": i, "issue": kind, "detail": d} for i, kind, d in sorted(issues_after)]
    resolved = [{"interface": i, "issue": kind, "detail": d} for i, kind, d in sorted(issues_before - issues_after)]
    if prop == "max_length":
        for t in tests.values():
            limit = (t.get("test_data") or {}).get("max_length_tested")
            if attr_id in t["checks"] and limit and limit != value:
                out.append({"test_case": t["id"], "issue": "test data outdated", "detail": f"tests {limit}, new value {value}"})
    return out, resolved


# --- ground truth checks
gt = load(acme / "expected_extractions.yaml")
results = {"extractions": [], "latent_conflicts": [], "injections": gt["injections"], "personal_data": gt["personal_data"]}

for x in gt["extractions"]:
    source = docs.get(x["doc"])
    if source is None and x["doc"] in incoming:
        source = yaml.safe_dump(incoming[x["doc"]], allow_unicode=True, width=10_000)
    if source is None:
        errors.append(f"{x['id']}: unknown document {x['doc']}")
        continue
    if x["quote"] not in " ".join(source.split()):
        errors.append(f"{x['id']}: quote not found verbatim in {x['doc']}")
    row = {k: x[k] for k in ("id", "doc", "kind", "status", "quote", "affects")}
    a = x["affects"]
    if "attribute" in a:
        need(a["attribute"], attributes, x["id"])
        row["current_value"] = current_value(a["attribute"], a["system"], a["property"])
        row["conflicts"], row["resolves"] = conflicts_for(a["attribute"], a["system"], a["property"], a["value"])
        row["changes_current_value"] = row["current_value"] != a["value"]
        row["impact"] = impact(a["attribute"])
        has_conflict = bool(row["conflicts"]) or row["changes_current_value"]
        if has_conflict != x.get("expected_conflict", False):
            errors.append(f"{x['id']}: expected_conflict={x.get('expected_conflict')} but computed {has_conflict}")
    if x["kind"] == "version_change":
        diff = load(root / "ontology" / "editors" / f"{a['to_profile']}.yaml")["changes"]
        row["profile_diff"] = diff
        row["impact"] = {c["attribute"]: impact(c["attribute"]) for c in diff}
    for k in ("risk", "why"):
        if k in x:
            row[k] = x[k]
    results["extractions"].append(row)

for inj in gt["injections"]:
    if inj["quote"] not in " ".join(docs[inj["doc"]].split()):
        errors.append(f"injection quote not found in {inj['doc']}")
all_text = " ".join(docs.values())
for kind, items in gt["personal_data"].items():
    for item in items:
        if item not in all_text:
            errors.append(f"personal data {kind} '{item}' not present in any document")

# --- latent conflicts: an interface carries an attribute into a system with a tighter limit or other unit
for i in interfaces.values():
    for a in i["carries"]:
        d = attributes[a]["definitions"]
        src, dst = d.get(i["from"], {}), d.get(i["to"], {})
        if "max_length" in src and "max_length" in dst and src["max_length"] > dst["max_length"]:
            results["latent_conflicts"].append({"interface": i["id"], "attribute": a, "issue": "truncation",
                                                "from": [i["from"], src["max_length"]], "to": [i["to"], dst["max_length"]]})
        if "unit" in src and "unit" in dst and src["unit"] != dst["unit"]:
            results["latent_conflicts"].append({"interface": i["id"], "attribute": a, "issue": "unit mismatch",
                                                "from": [i["from"], src["unit"]], "to": [i["to"], dst["unit"]]})

out = acme / "expected_results.json"
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

counts = dict(systems=len(systems), interfaces=len(interfaces), attributes=len(attributes), epics=len(epics),
              capabilities=len(caps), features=len(feats), user_stories=len(stories), test_cases=len(tests),
              concepts=len(concepts), documents=len(docs), incoming=len(incoming), extractions=len(gt["extractions"]))
print("counts:", counts)
for msg in infos:
    print("info:", msg)
print(f"latent conflicts found: {len(results['latent_conflicts'])}")
for c in results["latent_conflicts"]:
    print("  ", c)
if errors:
    print(f"\n{len(errors)} ERROR(S):")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"\nOK, wrote {out.relative_to(root)}")
