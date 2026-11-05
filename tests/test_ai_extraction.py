"""AI path tested with a fake model that makes the mistakes small local models really make:
names instead of ids, spelled-out numbers, slightly paraphrased quotes, and one invented fact."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vertex_hub import llm, run_pipeline  # noqa: E402
from vertex_hub.evaluate import gold_table, score  # noqa: E402

FAKE_DOC06 = {"facts": [
    {"quote": "SAP cannot hold a material short text beyond forty characters", "attribute": "Part Description",
     "system": "SAP", "property": "max length", "value": "forty", "kind": "constraint"},
    {"quote": "Cote MES, le code du poste ne doit pas depasser huit caracteres.",          # accents dropped
     "attribute": "ATT-WORKCENTER", "system": "MES", "property": "max_length", "value": "huit", "kind": "constraint"},
    {"quote": "Operation names authored in 3DEXPERIENCE may run up to 60 characters", "attribute": "Operation Label",
     "system": "3DEXPERIENCE", "property": "max_length", "value": 60, "kind": "fact"},
    {"quote": "planners want weights in SAP expressed in grams for every part", "attribute": "Mass",
     "system": "ERP", "property": "unit", "value": "grams", "kind": "proposal"},
    {"quote": "MES accepts part descriptions of 500 characters.", "attribute": "ATT-DESC",   # invented
     "system": "SYS-MES", "property": "max_length", "value": 500, "kind": "fact"},
]}


def fake_model(prompt, backend, model):
    return json.dumps(FAKE_DOC06) if "DOCUMENT DOC-06" in prompt else "Sure! Here is the JSON: {\"facts\": []}"


def make_twin():
    t = run_pipeline()
    t.cache = llm.Cache(tempfile.mkdtemp())
    return t


def test_normalisation_repair_and_gate():
    t = make_twin()
    acc, rej, info = t.extract_doc("DOC-06", mode="ai", call_fn=fake_model)
    assert info["mode_used"] == "ai"
    assert len(acc) == 4, acc
    assert len(rej) == 1 and "verbatim" in rej[0]["reason"]          # the invented fact is stopped
    by_attr = {f["attribute"]: f for f in acc}
    assert by_attr["ATT-DESC"]["value"] == 40 and by_attr["ATT-DESC"]["system"] == "SYS-ERP"
    assert by_attr["ATT-WORKCENTER"]["value"] == 8 and by_attr["ATT-WORKCENTER"]["repaired"]
    assert by_attr["ATT-WEIGHT"]["value"] == "g"


def test_hybrid_scores_on_holdout():
    t = make_twin()
    acc, _, _ = t.extract(mode="hybrid", call_fn=fake_model)
    s = {r["split"]: r for r in score(acc, gold_table(t.project.truth), "hybrid")}
    assert s["seen"]["recall"] == 1.0          # rules keep the seen documents
    assert s["holdout"]["recall"] == 1.0       # the model brings the paraphrases
    assert s["holdout"]["precision"] == 1.0    # the gate keeps the invention out


def test_cache_means_no_second_call():
    t = make_twin()
    calls = []

    def counting(prompt, b, m):
        calls.append(1)
        return fake_model(prompt, b, m)

    t.extract_doc("DOC-06", mode="ai", call_fn=counting)
    t._facts.clear()
    t.extract_doc("DOC-06", mode="ai", call_fn=counting)
    assert len(calls) == 1


def test_model_down_falls_back_to_rules():
    t = make_twin()

    def down(*a):
        raise ConnectionError("ollama not running")

    acc, _, info = t.extract_doc("DOC-03", mode="ai", call_fn=down)
    assert info["mode_used"] == "rules" and "unavailable" in info["warning"] and acc


def test_parse_json_tolerates_prose_and_think_tags():
    assert llm.parse_json('<think>hmm</think> ```json\n{"facts": [{"quote": "x"}]}\n```') == [{"quote": "x"}]
    assert llm.parse_json("[]") == []
    assert llm.parse_json("no json here") == []


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print("PASS", fn.__name__)
