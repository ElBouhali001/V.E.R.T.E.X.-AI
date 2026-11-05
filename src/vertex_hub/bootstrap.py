"""Bootstrapper: client profile + capability catalogue + editor vocabulary -> starter backlog."""
import pandas as pd

from .data import load_yaml

EDITOR_PROFILES = {"Windchill": "windchill.yaml", "3DEXPERIENCE": "3dexperience_R2025x.yaml", "Teamcenter": "teamcenter.yaml"}


def bootstrap(root, client):
    catalog = load_yaml(root / "catalog" / "capabilities.yaml")
    editor = load_yaml(root / "ontology" / "editors" / EDITOR_PROFILES[client["landscape"]["plm"]["product"]])
    words = {"Change order": editor["types"]["C-CO"].get("label", "Change Order"),
             "Change action": editor["types"]["C-CA"].get("label", "Change Action")}
    has_mes = client["landscape"]["mes"]["editor"] != "none"
    rows = []
    for fam in catalog["families"]:
        persona = catalog["personas_by_family"][fam["id"]]
        for cap in fam["capabilities"]:
            rel = cap["relevance"]
            if not (rel == "core" or client["industry"] in rel):
                continue
            for feat in cap["features"]:
                if "MES" in feat and not has_mes:
                    continue
                for k, v in words.items():
                    feat = feat.replace(k, v)
                goal = feat if feat[:2].isupper() else feat[0].lower() + feat[1:]
                rows.append({"epic": fam["name"], "capability": cap["title"], "feature": feat,
                             "story": catalog["story_template"].format(persona=persona, feature_goal=goal,
                                                                       benefit="<benefit to refine with the client>")})
    return pd.DataFrame(rows)


# Delivery method -> backlog levels, cadence and ceremonies. Same content, organised the way the client works.
METHODS = {
    "SAFe": {"levels": {"epic": "Epic", "capability": "Capability", "feature": "Feature", "story": "Story"},
             "unit": "Iteration", "default_weeks": 2, "per_increment": 5,
             "events": ["PI Planning", "Iteration planning", "System demo", "Inspect and adapt"],
             "roles": ["Release Train Engineer", "Product Management", "System Architect", "Business Owners"]},
    "Scrum": {"levels": {"epic": "Epic", "capability": "Theme", "feature": "Product backlog item", "story": "User story"},
              "unit": "Sprint", "default_weeks": 2, "per_increment": 1,
              "events": ["Sprint planning", "Daily scrum", "Sprint review", "Sprint retrospective"],
              "roles": ["Product Owner", "Scrum Master", "Developers"]},
    "Waterfall": {"levels": {"epic": "Phase", "capability": "Work package", "feature": "Deliverable", "story": "Requirement"},
                  "unit": "Phase", "default_weeks": 6, "per_increment": 1,
                  "events": ["Requirements review", "Design review", "Test readiness review", "Go-live gate"],
                  "roles": ["Project Manager", "Solution Architect", "Steering committee"]},
}


def method_of(client):
    m = str(client.get("delivery_framework", "Scrum"))
    return next((k for k in METHODS if k.lower() == m.lower()), "Scrum")


def frame_backlog(backlog, client):
    """Rename the backlog levels to the client's delivery method (export-ready)."""
    return backlog.rename(columns=METHODS[method_of(client)]["levels"])


def delivery_plan(backlog, client):
    """First delivery calendar: one slot per epic/phase, sized by feature count, with the method's ceremonies."""
    m = method_of(client)
    spec = METHODS[m]
    weeks = int((client.get("framework_settings") or {}).get(
        "sprint_length_weeks" if m == "Scrum" else "iteration_length_weeks", spec["default_weeks"]))
    rows, start = [], 0
    for i, (epic, grp) in enumerate(backlog.groupby("epic", sort=False), 1):
        if m == "Waterfall":
            dur = weeks
            slot = f"Phase {i}"
        else:
            n = max(1, round(len(grp) / 3))
            dur = n * weeks
            slot = f"{spec['unit']}s {start // weeks + 1}-{start // weeks + n}" if n > 1 else f"{spec['unit']} {start // weeks + 1}"
        rows.append({"slot": slot, "scope": epic, "items": len(grp), "start_week": start + 1, "end_week": start + dur,
                     "gate_or_event": spec["events"][-1] if m == "Waterfall" else spec["events"][2]})
        start += dur
    if m == "Waterfall":
        for r in rows[:-1]:
            r["gate_or_event"] = "Phase gate review"
    if m == "SAFe":
        for r in rows:
            r["increment"] = f"PI {(r['start_week'] - 1) // (weeks * spec['per_increment']) + 1}"
    return {"method": m, "levels": spec["levels"], "unit": spec["unit"], "length_weeks": weeks,
            "events": spec["events"], "roles": spec["roles"], "calendar": pd.DataFrame(rows), "total_weeks": start}
