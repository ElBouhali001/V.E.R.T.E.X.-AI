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
