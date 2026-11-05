"""Impact and conflict engine (deterministic). A conflict is directional: data flowing into a
shorter field (truncation) or across different units."""
from .graph import impact


def definitions(p, attr_id):
    return {s: dict(d) for s, d in p.attributes[attr_id]["definitions"].items()}


def interface_issues(p, attr_id, defs):
    issues = set()
    for i in p.interfaces.values():
        if attr_id not in i["carries"]:
            continue
        src, dst = defs.get(i["from"], {}), defs.get(i["to"], {})
        if "max_length" in src and "max_length" in dst and src["max_length"] > dst["max_length"]:
            issues.add((i["id"], "truncation", f"{i['from']} {src['max_length']} > {i['to']} {dst['max_length']}"))
        if "unit" in src and "unit" in dst and src["unit"] != dst["unit"]:
            issues.add((i["id"], "unit mismatch", f"{i['from']} {src['unit']} vs {i['to']} {dst['unit']}"))
    return issues


def assess(p, G, attr_id, system, prop, value):
    """What happens if attribute.system.prop becomes value: conflicts left, conflicts resolved, impact."""
    before = definitions(p, attr_id)
    after = {k: dict(v) for k, v in before.items()}
    after.setdefault(system, {})[prop] = value
    ib, ia = interface_issues(p, attr_id, before), interface_issues(p, attr_id, after)
    outdated = [t["id"] for t in p.tests.values()
                if attr_id in t["checks"] and prop == "max_length"
                and (t.get("test_data") or {}).get("system", system) == system
                and (t.get("test_data") or {}).get("max_length_tested") not in (None, value)]
    return {"attribute": attr_id, "system": system, "property": prop,
            "current": before.get(system, {}).get(prop), "new": value,
            "conflicts": sorted(ia), "resolves": sorted(ib - ia), "outdated_tests": outdated, **impact(G, attr_id)}


def assess_fact(p, G, fact):
    if fact.get("property") not in ("max_length", "unit"):
        return None
    return assess(p, G, fact["attribute"], fact["system"], fact["property"], fact["value"])


def latent_conflicts(p):
    """Conflicts already present in today's landscape, with no document needed."""
    return sorted({c for a in p.attributes for c in interface_issues(p, a, definitions(p, a))})


def tradeoff(p, G, attr_id, system, prop, options):
    """options: list of (name, value, risk text). Returns one row per option."""
    rows = []
    for name, value, risk in options:
        r = assess(p, G, attr_id, system, prop, value)
        rows.append({"option": name,
                     "conflicts left": "; ".join(f"{i} {k}" for i, k, _ in r["conflicts"]) or "none",
                     "conflicts resolved": "; ".join(f"{i} {k}" for i, k, _ in r["resolves"]) or "none",
                     "tests to update": ", ".join(r["outdated_tests"]) or "none",
                     "stories to review": ", ".join(r["stories_direct"]),
                     "risk": risk})
    return rows


def version_upgrade(p, G, diff, system="SYS-PLM"):
    rows = []
    for c in diff:
        for prop, val in c["after"].items():
            r = assess(p, G, c["attribute"], system, prop, val)
            rows.append({"attribute": c["attribute"], "field": c["field"], "change": f"{r['current']} -> {val}",
                         "conflicts after upgrade": "; ".join(d for *_, d in r["conflicts"]) or "none",
                         "interfaces to retest": ", ".join(r["interfaces"]), "tests to rerun": ", ".join(r["tests_direct"])})
    return rows
