"""Ask Vertex and the setup assistant, with and without a model (the model is faked)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vertex_hub import run_pipeline  # noqa: E402
from vertex_hub.assistant import answer, retrieve, setup_profile  # noqa: E402
from vertex_hub.bootstrap import bootstrap  # noqa: E402

T = run_pipeline()


def test_retrieval_maps_client_words_and_finds_the_alert():
    ctx, m = retrieve(T, "Que se passe-t-il si on change la désignation article ?")
    assert "ATT-DESC" in m["attributes"]
    assert "AL-01" in ctx and "DOC-03" in ctx and "40" in ctx["ATT-DESC"]


def test_glossary_question_without_model():
    r = answer(T, "What is a Plant BOM?", use_llm=False)
    assert r["engine"] == "graph" and "C-PBOM" in r["cited"] and "Process BOM" in r["answer"]


def test_pending_decisions_question():
    r = answer(T, "Which decisions are waiting?", use_llm=False)
    assert "Pending decision" in r["answer"]


def test_model_answer_citations_are_checked():
    def fake(prompt, *a, **kw):
        return "PLM allows 80 characters but SAP holds 40 [AL-01], raised in the ERP workshop [DOC-03]. Budget is 2M [DOC-99]."
    r = answer(T, "Why are part descriptions truncated?", use_llm=True, call_fn=fake)
    assert r["engine"] == "ai:test"
    assert r["cited"] == ["AL-01", "DOC-03"] and r["unverified"] == ["DOC-99"]


def test_model_down_falls_back_to_graph():
    def down(*a, **kw):
        raise ConnectionError
    r = answer(T, "What is impacted if the mass unit changes?", use_llm=True, call_fn=down)
    assert r["engine"] == "graph" and "ATT-WEIGHT" in r["cited"]


def test_unknown_question_says_so():
    r = answer(T, "xyzzy", use_llm=False)
    assert r["cited"] == [] or "project graph" in r["answer"]


def test_setup_from_a_sentence_rules_only():
    prof = setup_profile("Nordwind Aero builds aircraft seats, runs Teamcenter, works in SAFe and has no MES yet", use_llm=False)
    assert (prof["industry"], prof["landscape"]["plm"]["product"], prof["delivery_framework"]) == ("aerospace", "Teamcenter", "SAFe")
    assert prof["landscape"]["mes"]["editor"] == "none"
    backlog = bootstrap(T.project.root, prof)
    assert len(backlog) > 10 and any("Change Notice" in f for f in backlog.feature)


def test_setup_model_output_is_validated():
    def fake(prompt, *a, **kw):
        return '{"name": "Helix", "industry": "space mining", "plm": "Windchill", "framework": "Scrum", "has_mes": false}'
    prof = setup_profile("Helix fabrique des pompes à perfusion sous Windchill, en Scrum", use_llm=True, call_fn=fake)
    assert prof["name"] == "Helix" and prof["industry"] == "medtech"      # invalid model value replaced by rules
    assert prof["landscape"]["plm"]["product"] == "Windchill"


if __name__ == "__main__":
    for k, v in dict(globals()).items():
        if k.startswith("test_"):
            v()
            print("PASS", k)


def test_delivery_method_changes_framework():
    from pathlib import Path
    from vertex_hub.bootstrap import bootstrap, delivery_plan, frame_backlog
    from vertex_hub.data import load_yaml
    root = Path(__file__).resolve().parents[1]
    c = load_yaml(root / "data" / "medtech" / "client_profile.yaml")["client"]
    b = bootstrap(root, c)
    plans = {}
    for m in ("SAFe", "Scrum", "Waterfall"):
        plans[m] = delivery_plan(b, {**c, "delivery_framework": m})
    assert "PI Planning" in plans["SAFe"]["events"] and "increment" in plans["SAFe"]["calendar"]
    assert plans["Scrum"]["length_weeks"] == 3
    assert plans["Waterfall"]["calendar"]["gate_or_event"].iloc[-1] == "Go-live gate"
    assert list(frame_backlog(b, {**c, "delivery_framework": "Waterfall"}).columns)[:2] == ["Phase", "Work package"]
