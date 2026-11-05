"""Guardrails applied before any AI sees a text: injection quarantine, personal-data masking, audit log.

The name detector is a lightweight heuristic (a capitalised name followed by a role in brackets,
then propagated across the corpus). Production: Microsoft Presidio with a spaCy NER model.
"""
import datetime as dt
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd


class Audit:
    """Two separate stores on purpose, not one:

    - `audit` (injections blocked, redactions, gate accept/reject, decisions, Jira sends): an
      append-only evidence trail. Durable by default (log_path), and NOT wiped by "Reset demo" --
      a reset button that could erase its own evidence trail would defeat the point of having one.
    - `decisions` / `outbox`: this session's working state (what's been approved/rejected, what's
      queued to Jira). In-memory by default and deliberately NOT durable across a fresh Twin: every
      test, notebook re-run and "Reset demo" click expects to start from a clean decision slate.

    A previous version of this class persisted all three tables to one file, which made decisions
    leak between separate run_pipeline() calls and silently broke "Reset demo". Keep them split.
    """

    def __init__(self, path=":memory:", log_path=None):
        log_path = log_path if log_path is not None else path
        for p in {path, log_path}:
            if p != ":memory:":
                Path(p).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS decisions (id TEXT, ts TEXT, status TEXT, doc TEXT, quote TEXT, change TEXT, "
                        "option TEXT, approver TEXT, note TEXT, impacted TEXT, fact_key TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS outbox (decision TEXT, jira_key TEXT, item TEXT, comment TEXT, "
                        "status TEXT, ts TEXT, target TEXT)")
        self.log_db = self.db if log_path == path else sqlite3.connect(log_path, check_same_thread=False)
        self.log_db.execute("CREATE TABLE IF NOT EXISTS audit (ts TEXT, step TEXT, doc TEXT, detail TEXT)")

    def log(self, step, doc, detail):
        self.log_db.execute("INSERT INTO audit VALUES (?,?,?,?)",
                            (dt.datetime.now().isoformat(timespec="seconds"), step, doc, json.dumps(detail, ensure_ascii=False)))
        self.log_db.commit()

    def df(self, table="audit"):
        return pd.read_sql(f"SELECT * FROM {table}", self.log_db if table == "audit" else self.db)


INJECTION_PATTERNS = [
    # Each family below was checked against this project's real document corpus (zero hits except the
    # one planted DOC-05 scenario) and against the negative class of an external injection benchmark
    # (tools/benchmarks/injection/) before being added -- see tools/guardrails_eval.py.
    r"ignore (all |the )?(above|previous|prior)\b",
    r"disregard (all )?(previous|prior|above) (instructions|guidelines|rules)",
    r"override (your|the) (instructions|guidelines|rules)",
    r"forget (all |about all )?(the )?(previous|prior|above)?\s*(tasks|instructions|assignments|information|prompts)",
    r"new instructions\b", r"note for the ai", r"system prompt",
    r"\b(act as|pretend (that )?you are|now you are|you are now)\b",
    r"(show|reveal|print)\b.{0,20}\b(prompt|system prompt)",
    r"(send|email|forward|export|upload)\b.{0,80}\b(to|vers)\s+\S+@\S+",
    r"ignore[rz]? (toutes )?les instructions",
    r"oublie[rz]? (toutes )?les instructions (pr[ée]c[ée]dentes|pr[ée]alables)",
    r"vergiss (alle |alles )?(vorherigen?|bisherigen?)",
]
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+\d{1,3}(?:[ .]\d{1,2}){4,5}|\b0\d(?:[ .]\d{2}){4}\b")
NAME_ANCHOR = re.compile(r"\b([A-ZÀ-Ý][a-zà-ÿ]+ [A-ZÀ-Ý][a-zà-ÿ]+) \((?:Acme|consulting)")


def split_sentences(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            out.extend(s for s in re.split(r"(?<=[^\d\s][.!?])\s+(?=[A-ZÀ-Ý*<|#])", line) if s.strip())
    return out


def is_injection(sentence):
    return any(re.search(p, sentence, re.I) for p in INJECTION_PATTERNS)


def quarantine(doc_id, text, audit=None):
    kept, blocked = [], []
    for s in split_sentences(text):
        (blocked if is_injection(s) else kept).append(s)
    if audit:
        for s in blocked:
            audit.log("injection_blocked", doc_id, {"sentence": s})
    return "\n".join(kept), blocked


class Redactor:
    """Stable pseudonyms across the whole corpus; the mapping never leaves the perimeter."""

    def __init__(self, corpus):
        self.names = sorted({m for t in corpus.values() for m in NAME_ANCHOR.findall(t)}, key=len, reverse=True)
        self.mapping = {}

    def _pseudo(self, kind, value):
        key = (kind, value)
        if key not in self.mapping:
            self.mapping[key] = f"<{kind}_{sum(k == kind for k, _ in self.mapping) + 1}>"
        return self.mapping[key]

    def learn(self, text):
        """Pick up names from a newly pasted document."""
        new = set(NAME_ANCHOR.findall(text)) - set(self.names)
        self.names = sorted(set(self.names) | new, key=len, reverse=True)

    def redact(self, doc_id, text, audit=None):
        counts = {"PERSON": 0, "EMAIL": 0, "PHONE": 0}

        def sub(kind):
            def f(m):
                counts[kind] += 1
                return self._pseudo(kind, m.group(0))
            return f

        text = EMAIL.sub(sub("EMAIL"), text)
        text = PHONE.sub(sub("PHONE"), text)
        for name in self.names:
            text = re.sub(rf"\b{re.escape(name)}\b", sub("PERSON"), text)
        if audit:
            audit.log("redaction", doc_id, counts)
        return text, counts

    def reveal(self, text):
        """Re-identify for display to authorised users only."""
        for (kind, value), token in self.mapping.items():
            text = text.replace(token, value)
        return text


def sanitize(doc_id, raw, redactor, audit=None):
    kept, blocked = quarantine(doc_id, raw, audit)
    clean, counts = redactor.redact(doc_id, kept, audit)
    return clean, {"doc": doc_id, "injections_blocked": len(blocked), **counts}, blocked
