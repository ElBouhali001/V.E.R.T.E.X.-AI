"""One object that wires every step together. Used identically by the Streamlit app, the notebook and the tests."""
from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .alerts import build_alerts
from .connectors import get_jira
from .data import Project, load_project
from .decisions import decide, decided_keys, decision_of
from .extract import baseline_extract, fact_key, gate, llm_extract, merge
from .graph import build_graph
from .guardrails import Audit, Redactor, quarantine, sanitize
from .library import Library, load_external
from .ontology import Glossary

MODES = ("rules", "ai", "hybrid")


@dataclass
class Twin:
    project: Project
    audit: Audit = field(default_factory=Audit)

    def __post_init__(self):
        p = self.project
        # decisions/outbox (audit.db, in-memory) stay session-scoped -- tests, notebook re-runs and
        # "Reset demo" all expect a clean decision slate. The audit trail (audit.log_db) is a durable
        # evidence log that must survive both a restart and a reset, so it gets its own file.
        self.audit = Audit(log_path=str(Path(p.root) / "cache" / "audit.db"))
        self.G = build_graph(p)
        self.glossary = Glossary(p)
        self.redactor = Redactor(p.corpus())
        self.cache = llm.Cache(p.root)
        self.sanitized, self.guard_rows, self.blocked = {}, [], {}
        self._facts = {}          # (doc_id, mode) -> (accepted, rejected, info)
        self.jira = get_jira(p)
        for doc_id, raw in p.corpus().items():
            self._sanitize(doc_id, raw)
        self.load_library()

    # -------------------------------------------------------------- library (external datasets)
    def load_library(self):
        """Datasets in data/external/: quarantined and masked like everything else, then indexed for search."""
        passages, self.library_summary = load_external(self.project.root)
        masked = blocked = 0
        for ps in passages:
            kept, bl = quarantine(ps["id"], ps["text"])
            ps["text"], counts = self.redactor.redact(ps["id"], kept)
            masked += sum(counts.values())
            blocked += len(bl)
        self.library = Library(passages)
        if passages:
            self.audit.log("library_loaded", None, {"passages": len(passages), "masked": masked, "blocked": blocked,
                                                    "datasets": [x["dataset"] for x in self.library_summary]})
        self.refresh_doc_index()

    def refresh_doc_index(self):
        self.doc_index = Library([{"id": d, "source": "project", "title": self.project.title_of(d), "text": t}
                                  for d, t in self.sanitized.items()])

    # -------------------------------------------------------------- ingestion
    def _sanitize(self, doc_id, raw):
        clean, row, blocked = sanitize(doc_id, raw, self.redactor, self.audit)
        self.sanitized[doc_id] = clean
        self.guard_rows = [r for r in self.guard_rows if r["doc"] != doc_id] + [row]
        self.blocked[doc_id] = blocked
        self._facts = {k: v for k, v in self._facts.items() if k[0] != doc_id}
        return clean, row, blocked

    def ingest(self, doc_id, raw_text, title="", date=None):
        """A new document (pasted in the app, or arriving from a connector)."""
        self.project.documents[doc_id] = {"id": doc_id, "title": title, "text": raw_text, "date": date, "type": "upload"}
        self.redactor.learn(raw_text)
        out = self._sanitize(doc_id, raw_text)
        self.refresh_doc_index()
        return out

    # -------------------------------------------------------------- extraction
    def ai_ready(self, doc_id):
        _, model = llm.config()
        return self.cache.has(model, doc_id, self.sanitized[doc_id])

    def extract_doc(self, doc_id, mode="rules", allow_calls=True, call_fn=None):
        """(accepted, rejected, info). info.mode_used may fall back to 'rules' if the AI is unavailable."""
        key = (doc_id, mode, llm.config()[1] if mode != "rules" else "")
        if key in self._facts:
            return self._facts[key]
        text = self.sanitized[doc_id]
        info = {"mode": mode, "mode_used": mode, "warning": None}
        rules_acc, rules_rej = gate(self.project, self.sanitized, baseline_extract(self.project, self.glossary, doc_id, text),
                                    "rules", self.audit)
        if mode == "rules":
            result = (rules_acc, rules_rej, info)
        else:
            ai_acc, ai_rej = [], []
            if allow_calls or self.ai_ready(doc_id):
                try:
                    raw = llm_extract(self.project, self.glossary, doc_id, text, self.cache, call_fn=call_fn)
                    ai_acc, ai_rej = gate(self.project, self.sanitized, raw, None, self.audit, repair=True)
                except Exception as e:  # model down, timeout, bad JSON...
                    info.update(mode_used="rules", warning=f"AI unavailable ({type(e).__name__}): rules used")
            else:
                info.update(mode_used="rules", warning="not yet analysed by the AI (cache empty)")
            if info["mode_used"] == "rules":
                result = (rules_acc, rules_rej, info)
            elif mode == "ai":
                result = (ai_acc, ai_rej, info)
            else:
                result = (merge(ai_acc, rules_acc), ai_rej + rules_rej, info)
        if not info["warning"]:          # never memoise a fallback: retry the AI next time
            self._facts[key] = result
        return result

    def extract(self, doc_ids=None, mode="rules", allow_calls=True, call_fn=None):
        """All documents (or a subset). Returns (accepted, rejected, infos per doc)."""
        acc, rej, infos = [], [], {}
        for d in doc_ids or list(self.sanitized):
            a, r, i = self.extract_doc(d, mode, allow_calls, call_fn)
            acc += a
            rej += r
            infos[d] = i
        return acc, rej, infos


    # -------------------------------------------------------------- alerts + decisions
    def alerts(self, mode="rules", allow_calls=False):
        facts, _, _ = self.extract(mode=mode, allow_calls=allow_calls)
        return build_alerts(self, facts)

    def decided(self):
        return decided_keys(self.audit)

    def decision_of(self, fact):
        return decision_of(self.audit, fact)

    def decide(self, fact, status, option="", approver="", note=""):
        return decide(self.project, self.G, self.audit, fact, status, option, approver, note)

    def pending(self, mode="rules"):
        """Facts that would change the model and have no decision yet."""
        from .impact import assess_fact
        from .alerts import active_facts
        facts, _, _ = self.extract(mode=mode, allow_calls=False)
        out = []
        for f in active_facts(self, facts):
            r = assess_fact(self.project, self.G, f)
            if r and r["current"] != r["new"]:
                out.append((f, r))
        return out


def run_pipeline(root=None, client="acme"):
    return Twin(load_project(root, client))
