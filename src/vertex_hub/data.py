"""Load a client project (YAML + Markdown) into one object."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def find_root(start=None):
    """Repo root = first parent containing data/acme. Works from notebooks/, app/ or the root."""
    for base in [Path(start or Path.cwd()).resolve(), Path(__file__).resolve()]:
        for p in [base, *base.parents]:
            if (p / "data" / "acme").exists():
                return p
    raise FileNotFoundError("repo root with data/acme not found")


def read_document(path):
    _, front, body = Path(path).read_text(encoding="utf-8").split("---", 2)
    meta = yaml.safe_load(front)
    meta["text"] = body.strip()
    return meta


@dataclass
class Project:
    root: Path
    client_dir: Path
    profile: dict
    systems: dict
    interfaces: dict
    attributes: dict
    epics: dict
    capabilities: dict
    features: dict
    stories: dict
    tests: dict
    concepts: dict
    documents: dict
    incoming: dict
    truth: dict = field(default_factory=dict)

    def corpus(self):
        """Every text the pipeline ingests: documents + incoming Jira items."""
        texts = {d: doc["text"] for d, doc in self.documents.items()}
        for k, v in self.incoming.items():
            texts[k] = v["text"].strip() + "\n" + "\n".join(v.get("acceptance", []))
        return texts

    def title_of(self, doc_id):
        if doc_id in self.documents:
            return self.documents[doc_id]["title"]
        if doc_id in self.incoming:
            return self.incoming[doc_id].get("team", "")
        return ""

    def item(self, item_id):
        return self.stories.get(item_id) or self.tests.get(item_id)

    def counts(self):
        return {"systems": len(self.systems), "interfaces": len(self.interfaces), "attributes": len(self.attributes),
                "epics": len(self.epics), "capabilities": len(self.capabilities), "features": len(self.features),
                "user stories": len(self.stories), "test cases": len(self.tests), "glossary concepts": len(self.concepts),
                "documents": len(self.documents), "incoming Jira items": len(self.incoming)}


def load_project(root=None, client="acme"):
    root = find_root(root)
    d = root / "data" / client
    sys_doc = load_yaml(d / "systems.yaml")
    backlog = load_yaml(d / "backlog.yaml")
    incoming = {}
    for p in sorted((d / "incoming").glob("*.yaml")):
        item = load_yaml(p)
        incoming[item["id"]] = item
    truth_file = d / "expected_extractions.yaml"
    return Project(
        root=root,
        client_dir=d,
        profile=load_yaml(d / "client_profile.yaml")["client"],
        systems={s["id"]: s for s in sys_doc["systems"]},
        interfaces={i["id"]: i for i in sys_doc["interfaces"]},
        attributes={a["id"]: a for a in load_yaml(d / "attributes.yaml")["attributes"]},
        epics={e["id"]: e for e in backlog["epics"]},
        capabilities={c["id"]: c for c in backlog["capabilities"]},
        features={f["id"]: f for f in backlog["features"]},
        stories={s["id"]: s for s in backlog["user_stories"]},
        tests={t["id"]: t for t in load_yaml(d / "test_cases.yaml")["test_cases"]},
        concepts={c["id"]: c for c in load_yaml(d / "glossary.yaml")["concepts"]},
        documents={m["id"]: m for m in map(read_document, sorted((d / "documents").glob("*.md")))},
        incoming=incoming,
        truth=load_yaml(truth_file) if truth_file.exists() else {},
    )
