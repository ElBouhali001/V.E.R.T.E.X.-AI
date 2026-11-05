"""Regression tests for the demo scenarios. Run: pytest   (or: python tests/test_pipeline.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vertex_hub import run_pipeline  # noqa: E402
from vertex_hub.bootstrap import bootstrap  # noqa: E402
from vertex_hub.data import load_yaml  # noqa: E402
from vertex_hub.decisions import approve  # noqa: E402
from vertex_hub.evaluate import gold_table, score  # noqa: E402
from vertex_hub.impact import assess, latent_conflicts, version_upgrade  # noqa: E402

T = run_pipeline()
P = T.project
FACTS, REJECTED, _ = T.extract(mode="rules")


def test_no_personal_data_reaches_the_llm():
    for kind, values in P.truth["personal_data"].items():
        for v in values:
            assert not any(v in t for t in T.sanitized.values()), f"{kind} leaked: {v}"


def test_injection_is_quarantined():
    assert sum(len(b) for b in T.blocked.values()) == 1
    assert "ignore all previous instructions" not in T.sanitized["DOC-05"]


def test_glossary_reconciles_names():
    assert T.glossary.lookup("Plant BOM")["concept"] == "C-PBOM"
    assert T.glossary.lookup("BOP")["concept"] == "C-PBOM"
    assert T.glossary.find_attributes("la désignation article à 40 caractères") == ["ATT-DESC"]


def test_every_accepted_fact_is_quoted_verbatim():
    assert FACTS and not REJECTED


def test_gate_rejects_invented_quote_and_unknown_id():
    from vertex_hub.extract import gate
    bad = [{"doc": "DOC-03", "kind": "x", "quote": "SAP accepts 500 characters", "attribute": "ATT-DESC", "system": "SYS-ERP", "property": "max_length", "value": 500},
           {"doc": "DOC-03", "kind": "x", "quote": "MAKTX", "attribute": "ATT-NOPE", "system": "SYS-ERP", "property": "max_length", "value": 40}]
    accepted, rejected = gate(P, T.sanitized, bad)
    assert not accepted and len(rejected) == 2


def test_baseline_scores():
    s = {r["split"]: r for r in score(FACTS, gold_table(P.truth), "baseline")}
    assert s["seen"]["recall"] == 1.0
    assert s["holdout"]["recall"] == 0.0   # the honest number: rules don't generalise


def test_latent_conflicts():
    assert [c[:2] for c in latent_conflicts(P)] == [("INT-01", "truncation"), ("INT-02", "truncation")]


def test_erp_proposal_tradeoff():
    r = assess(P, T.G, "ATT-DESC", "SYS-PLM", "max_length", 40)
    assert r["current"] == 80 and not r["conflicts"]
    assert [x[0] for x in r["resolves"]] == ["INT-01"]
    assert r["outdated_tests"] == ["TC-205"]
    assert len(r["stories_direct"]) == 5 and len(r["tests_direct"]) == 4


def test_mes_story_flags_plm_to_mes_tests():
    f = next(f for f in FACTS if f["doc"] == "US-412")
    r = assess(P, T.G, f["attribute"], f["system"], f["property"], f["value"])
    assert r["tests_direct"] == ["TC-401", "TC-402"]


def test_version_upgrade_flags_new_truncations():
    diff = load_yaml(P.root / "ontology" / "editors" / "3dexperience_R2026x.yaml")["changes"]
    rows = version_upgrade(P, T.G, diff)
    assert sum(r["conflicts after upgrade"].count(">") for r in rows) == 3


def test_approval_logs_decision_and_drafts_jira():
    f = next(f for f in FACTS if f["doc"] == "DOC-03" and f["system"] == "SYS-PLM")
    dec_id, drafts = approve(P, T.G, T.audit, f, "accept", "tester")
    assert dec_id.startswith("DEC-") and len(drafts) == 9


def test_bootstrapper_adapts_to_industry_and_editor():
    med = bootstrap(P.root, load_yaml(P.root / "data" / "medtech" / "client_profile.yaml")["client"])
    assert "Verification and validation management" in set(med.capability)
    assert any("Change Notice" in f for f in med.feature)   # Windchill vocabulary


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
