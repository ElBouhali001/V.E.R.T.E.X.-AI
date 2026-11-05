"""Alerts, decisions, Jira outbox and the impact map."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vertex_hub import run_pipeline  # noqa: E402
from vertex_hub.connectors import JiraMock  # noqa: E402
from vertex_hub.decisions import send_outbox  # noqa: E402
from vertex_hub.impact import assess  # noqa: E402
from vertex_hub.viz import impact_map  # noqa: E402


def fresh():
    t = run_pipeline()
    t.jira = JiraMock(t.project, Path(tempfile.mkdtemp()) / "jira.json")
    return t


def titles(alerts, state):
    return [a["title"] for a in alerts if a["state"] == state]


def test_alerts_before_any_decision():
    a = fresh().alerts()
    cur = [x for x in a if x["state"] == "current"]
    assert titles(a, "current") == ["Part Description truncated on INT-01", "Work Center truncated on INT-02"]
    desc = cur[0]
    assert desc["first_seen"] == "2026-09-21"                       # 14 days before the ERP workshop
    assert {s["doc"] for s in desc["sources"]} == {"data model", "DOC-02", "DOC-03"}
    assert [r["doc"] for r in desc["resolutions"]] == ["DOC-03"]
    assert all(x["severity"] == "high" for x in cur)
    assert "factor of 1000" in next(x for x in a if x["kind"] == "unit mismatch")["human"]


def test_approve_updates_the_model_and_alerts():
    t = fresh()
    f, r = next((f, r) for f, r in t.pending() if f["doc"] == "DOC-03")
    dec_id, drafts = t.decide(f, "approved", "accept 40", "PLM PO")
    assert t.project.attributes["ATT-DESC"]["definitions"]["SYS-PLM"]["max_length"] == 40
    a = t.alerts()
    assert "Part Description truncated on INT-01" not in titles(a, "current")
    assert "TC-205 test data outdated for Part Description" in titles(a, "current")   # side effect is now real
    assert not any(f["doc"] in ("DOC-02", "DOC-03") for f, _ in t.pending())           # DOC-02 superseded
    assert len(drafts) == 9


def test_reject_closes_the_proposal_without_changing_the_model():
    t = fresh()
    f, _ = next((f, r) for f, r in t.pending() if f["doc"] == "DOC-04")
    t.decide(f, "rejected", "keep kg", "ERP lead", "conversion in middleware instead")
    assert t.project.attributes["ATT-WEIGHT"]["definitions"]["SYS-ERP"]["unit"] == "kg"
    assert not any(a["kind"] == "unit mismatch" for a in t.alerts())
    assert t.decision_of(f)["status"] == "rejected"


def test_outbox_goes_to_jira_only_when_sent():
    t = fresh()
    f, _ = next((f, r) for f, r in t.pending() if f["doc"] == "DOC-03")
    t.decide(f, "approved", "accept 40", "PLM PO")
    assert t.jira.comments() == {}                                   # drafted, not sent
    sent, errors = send_outbox(t.audit, t.jira)
    assert sent == 9 and not errors
    assert len(t.jira.comments("ACME-501")) == 1
    assert send_outbox(t.audit, t.jira)[0] == 0                       # nothing sent twice


def test_impact_map_marks_fix_and_outdated_test():
    t = fresh()
    r = assess(t.project, t.G, "ATT-DESC", "SYS-PLM", "max_length", 40)
    svg, h = impact_map(t.project, t.G, "ATT-DESC", r)
    assert svg.startswith("<svg") and ">fixed<" in svg and ">outdated<" in svg and h > 200


if __name__ == "__main__":
    for k, v in dict(globals()).items():
        if k.startswith("test_"):
            v()
            print("PASS", k)
