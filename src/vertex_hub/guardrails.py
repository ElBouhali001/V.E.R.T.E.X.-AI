"""Guardrails applied before any AI sees a text: injection quarantine, personal-data masking, audit log.

The name detector is a lightweight heuristic (a capitalised name followed by a role in brackets,
then propagated across the corpus). Production: Microsoft Presidio with a spaCy NER model.
"""
import datetime as dt
import json
import re
import sqlite3

import pandas as pd


class Audit:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS audit (ts TEXT, step TEXT, doc TEXT, detail TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS decisions (id TEXT, ts TEXT, status TEXT, doc TEXT, quote TEXT, change TEXT, "
                        "option TEXT, approver TEXT, note TEXT, impacted TEXT, fact_key TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS outbox (decision TEXT, jira_key TEXT, item TEXT, comment TEXT, "
                        "status TEXT, ts TEXT, target TEXT)")

    def log(self, step, doc, detail):
        self.db.execute("INSERT INTO audit VALUES (?,?,?,?)",
                        (dt.datetime.now().isoformat(timespec="seconds"), step, doc, json.dumps(detail, ensure_ascii=False)))
        self.db.commit()

    def df(self, table="audit"):
        return pd.read_sql(f"SELECT * FROM {table}", self.db)


INJECTION_PATTERNS = [
    r"ignore (all )?(the )?(previous|prior|above) instructions",
    r"disregard (all )?(previous|prior) instructions",
    r"note for the ai", r"you are now", r"system prompt",
    r"(send|email|forward|export|upload)\b.{0,80}\b(to|vers)\s+\S+@\S+",
    r"ignore[rz]? (toutes )?les instructions",
]
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+\d{1,3}(?:[ .]\d{1,2}){4,5}")
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
