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


# Two tiers, because project documents are full of "ignore the previous revision", "act as the master system",
# "new instructions for station 3" and "disregard previous guidelines on naming": dropping those sentences
# would silently hide real decisions from the AI.
# STRONG phrasings are attacks on their own. WEAK verbs ("ignore/forget/override ... previous ...") only count
# when the same sentence also addresses an AI (you, your, assistant, model, prompt...).
STRONG_PATTERNS = [
    r"\b(ignore|disregard|forget|override)\b.{0,15}\b(all|any|every)\b.{0,25}\b(instructions|prompts?|directions)\b",
    r"\b(ignore|disregard|forget|override)\b.{0,20}\b(your|the assistant'?s?|the model'?s?|the ai'?s?)\b.{0,15}\b(instructions|rules|guidelines|prompt)\b",
    r"\bsystem prompt\b", r"\bnote for the ai\b", r"\bjailbreak|\bdeveloper mode\b|\bDAN\b",
    r"\b(show|reveal|print|repeat|display)\b.{0,30}\b(your|the|all)\b.{0,15}\b(prompt|prompts|instructions)\b(?! sheet)",
    r"\b(act as|pretend (that )?you are|you are now|now you are|from now on you are)\s+(an? |the )?(\w+ ){0,2}(ai|assistant|chatbot|bot|model|llm|unrestricted|unfiltered|evil|hacker)\b",
    r"\b(new|updated) instructions\s*:", r"\b(here are|these are|follow) (your |the |my )?new instructions\b",
    r"(send|email|forward|export|upload)\b.{0,80}\b(to|vers)\s+\S+@\S+",
    r"ignore[rz]? (toutes )?les instructions", r"oublie[rz]? (toutes )?les instructions (pr[ée]c[ée]dentes|pr[ée]alables)",
    r"vergiss (alle |alles )?(vorherigen?|bisherigen?)",
    # role-play openers and prompt extraction (benchmark train-split families)
    r"\b(i want you to|now you)\s+act as\b",
    r"\bact as (an? |the )?(\w+ ){0,2}(interpreter|terminal|translator|storyteller|debater|interviewer|character|persona)\b",
    r"\byou are now \w*bot\b", r"\bnew (instructions|tasks?) follow", r"\bignore (the )?above\b(?! (drawing|revision|version|figure|table|list|section))",
    r"\b(print|show|repeat|spell-?check)\b.{0,25}\babove prompt\b", r"\b(beginning|start) of (this|the) prompt\b",
    r"\bwhat (were|are|was) your (initial |original |first )?(instructions|prompt)\b",
    r"\bforget (about )?(all|everything)\b.{0,20}\b(previous|prior|above|assignments|instructions|tasks|information)\b",
]
WEAK_PATTERNS = [
    r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier)\b.{0,30}\b(instructions|guidelines|rules|tasks|prompts|assignments|information)\b",
]
AI_ADDRESS = r"\b(you|your|yourself|assistant|chatbot|ai|model|llm|prompt|respond|reply|answer freely)\b"
ROLEPLAY = r"\b(now you are|you are now)\b.{0,80}\b(role|character|pretend|chatgpt|bot|how do you answer)\b"
INJECTION_PATTERNS = STRONG_PATTERNS + WEAK_PATTERNS  # kept for tools that list them


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
    if any(re.search(p, sentence, re.I) for p in STRONG_PATTERNS):
        return True
    if re.search(ROLEPLAY, sentence, re.I):
        return True
    return any(re.search(p, sentence, re.I) for p in WEAK_PATTERNS) and bool(re.search(AI_ADDRESS, sentence, re.I))


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
