"""Human decisions. Nothing reaches Jira, and nothing changes in the model, without a person's approval.

approved -> the change is applied to the project model (the twin updates itself), Jira comments are drafted
            into the outbox; they are sent only when someone presses Send.
rejected -> logged with the reason; the fact stops raising alerts.
"""
import datetime as dt
import json

from .extract import fact_key
from .impact import assess_fact


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


def decide(p, G, audit, fact, status, option="", approver="", note=""):
    assert status in ("approved", "rejected")
    r = assess_fact(p, G, fact)
    n = audit.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] + 1
    dec_id = f"DEC-{n:03d}"
    impacted = (r["stories_direct"] + r["tests_direct"]) if r else []
    change = f"{fact.get('attribute') or ''} {fact['system']} {fact['property']} {r['current'] if r else ''} -> {fact['value']}".strip()
    audit.db.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (dec_id, _now(), status, fact["doc"], fact["quote"], change, option, approver, note,
                      ",".join(impacted), json.dumps(fact_key(fact), ensure_ascii=False)))
    drafts = []
    if status == "approved" and r:
        before = r["current"]
        p.attributes[fact["attribute"]]["definitions"].setdefault(fact["system"], {})[fact["property"]] = fact["value"]
        G.add_edge(fact["attribute"], fact["system"], rel="DEFINED_IN", **p.attributes[fact["attribute"]]["definitions"][fact["system"]])
        label = p.attributes[fact["attribute"]]["canonical"]
        for i in impacted:
            comment = (f"[{dec_id}] {label} {fact['property']} changes {before} -> {fact['value']} in {fact['system']} "
                       f"(source {fact['doc']}, approved by {approver}). Please review acceptance criteria / test data.")
            drafts.append({"jira_key": p.item(i)["jira_key"], "item": i, "comment": comment})
            audit.db.execute("INSERT INTO outbox VALUES (?,?,?,?,?,?,?)", (dec_id, p.item(i)["jira_key"], i, comment, "drafted", _now(), ""))
    audit.db.commit()
    audit.log(f"decision_{status}", fact["doc"], {"decision": dec_id, "approver": approver, "note": note})
    return dec_id, drafts


def approve(p, G, audit, fact, option, approver):
    return decide(p, G, audit, fact, "approved", option, approver)


def approved_keys(audit):
    return [tuple(json.loads(k)) for (k,) in audit.db.execute("SELECT fact_key FROM decisions WHERE status='approved'")]


def decided_keys(audit):
    return {tuple(json.loads(k)) for (k,) in audit.db.execute("SELECT fact_key FROM decisions")}


def decision_of(audit, fact):
    k = json.dumps(fact_key(fact), ensure_ascii=False)
    row = audit.db.execute("SELECT id, status, approver, note FROM decisions WHERE fact_key=? ORDER BY ts DESC", (k,)).fetchone()
    return dict(zip(("id", "status", "approver", "note"), row)) if row else None


def send_outbox(audit, connector):
    """Send every drafted comment through the connector (mock or real Jira). Returns (sent, errors)."""
    rows = audit.db.execute("SELECT rowid, jira_key, comment FROM outbox WHERE status='drafted'").fetchall()
    sent, errors = 0, []
    for rowid, key, comment in rows:
        try:
            connector.add_comment(key, comment)
            audit.db.execute("UPDATE outbox SET status='sent', ts=?, target=? WHERE rowid=?", (_now(), connector.name, rowid))
            sent += 1
        except Exception as e:
            errors.append(f"{key}: {e}")
    audit.db.commit()
    audit.log("jira_sent", None, {"sent": sent, "errors": errors[:5], "target": connector.name})
    return sent, errors
