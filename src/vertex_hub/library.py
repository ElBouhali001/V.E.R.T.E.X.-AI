"""Library: external datasets dropped in data/external/, cut into passages, masked, and searchable (BM25).

Supported, by folder:
  data/external/pure/      PURE requirements documents: .xml (the 19-document XML subset), .pdf (needs pypdf), .txt, .md
  data/external/promise/   PROMISE NFR: .arff (original) or .csv (columns with the requirement text and its class)
  data/external/<other>/   any .txt / .md / .pdf / .xml documents
Each passage gets an id like EXT-PURE-0001 or EXT-NFR-0001, which Ask Vertex cites.
"""
import csv
import io
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from .ontology import norm

NFR_CLASSES = {"F": "Functional", "A": "Availability", "L": "Legal", "LF": "Look and feel", "MN": "Maintainability",
               "O": "Operational", "PE": "Performance", "SC": "Scalability", "SE": "Security", "US": "Usability",
               "FT": "Fault tolerance", "PO": "Portability"}
STOP = set("""a an the and or of to in on for with by is are be was were it this that these those as at from shall should must will
can may not no all any each its their there which who what when where how why do does le la les un une des de du et ou en au aux
pour par sur dans est sont ce cette ces qui que quoi quand comment pourquoi il elle ils elles on nous vous""".split())


def stem(t):
    """Light suffix stripping: processing -> process, requirements -> requirement, frames -> frame, processes -> process."""
    if len(t) <= 4 or t.endswith(("ss", "us", "is")):
        return t
    for suf, rep in (("ations", "ate"), ("ation", "ate"), ("ings", ""), ("ing", ""), ("ies", "y"), ("sses", "ss"),
                     ("xes", "x"), ("ches", "ch"), ("shes", "sh"), ("ed", ""), ("s", "")):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)] + rep
    return t


def tokens(text):
    return [stem(t) for t in re.findall(r"[a-z0-9][a-z0-9_-]+", norm(text)) if t not in STOP]


def _chunks(text, size=700):
    """Paragraph-aware chunks of about `size` characters."""
    text = re.sub(r"[ \t]+", " ", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=\d+(?:\.\d+)*\s)", text) if p.strip()]
    out, cur = [], ""
    for p in paras:
        if len(cur) + len(p) > size and cur:
            out.append(cur)
            cur = ""
        cur = (cur + "\n" + p).strip()
        while len(cur) > size * 1.6:
            cut = cur.rfind(". ", 0, size) + 1 or size
            out.append(cur[:cut].strip())
            cur = cur[cut:].strip()
    if cur:
        out.append(cur)
    return [c for c in out if len(c) > 40]


# ------------------------------------------------------------------ readers
def read_xml(path):
    root = ET.parse(path).getroot()
    strip = lambda t: t.split("}")[-1].lower()
    title = next((" ".join(e.itertext()).strip() for e in root.iter() if "title" in strip(e.tag) and "".join(e.itertext()).strip()), Path(path).stem)
    reqs = [e for e in root.iter() if strip(e.tag) in ("req", "requirement")]
    if reqs:
        texts = [" ".join(" ".join(e.itertext()).split()) for e in reqs]
        return title, [t for t in texts if len(t) > 20]
    return title, _chunks("\n".join(" ".join(t.split()) for t in root.itertext() if t.strip()))


def read_pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, []
    try:
        text = "\n\n".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    except Exception:
        return None, []
    return Path(path).stem, _chunks(text)


def read_text(path):
    return Path(path).stem, _chunks(Path(path).read_text(encoding="utf-8", errors="ignore"))


def read_arff(path):
    """PROMISE NFR .arff: @attribute lines, then @data rows like 1,'The system shall ...',PE"""
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().lower() == "@data") + 1
    attrs = [l.split()[1].strip("'\"").lower() for l in lines[:start] if l.lower().startswith("@attribute")]
    rows = []
    for row in csv.reader(io.StringIO("\n".join(l for l in lines[start:] if l.strip() and not l.startswith("%"))),
                          quotechar="'", escapechar="\\", skipinitialspace=True):
        rows.append(dict(zip(attrs, row)))
    return rows


def read_csv(path):
    with open(path, encoding="utf-8", errors="ignore", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample else csv.excel
        return [{k.strip().lower(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f, dialect=dialect)]


def _requirement_rows(rows, prefix):
    out = []
    for n, r in enumerate(rows, 1):
        text = next((r[k] for k in r if k in ("requirementtext", "requirement", "text", "requirement_text", "description")), None)
        if not text:
            continue
        cls = next((r[k] for k in r if k in ("class", "label", "type", "_class_")), "")
        project = next((r[k] for k in r if k in ("projectid", "project", "project_id")), "")
        label = NFR_CLASSES.get(cls.strip().upper(), cls)
        out.append({"id": f"EXT-{prefix}-{n:04d}", "source": "PROMISE NFR", "title": f"Requirement, project {project}, {label}".strip(),
                    "text": f"[{label}] {text.strip()}", "label": label})
    return out


# ------------------------------------------------------------------ loading
def load_external(root):
    """All passages found under data/external/, plus a per-dataset summary."""
    base = Path(root) / "data" / "external"
    passages, summary = [], []
    if not base.exists():
        return passages, summary
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        prefix = "NFR" if folder.name.lower().startswith("promise") else folder.name.upper()[:8].replace("-", "")
        before, files, skipped = len(passages), 0, []
        for f in sorted(folder.rglob("*")):
            if not f.is_file() or f.name.startswith("."):
                continue
            ext = f.suffix.lower()
            try:
                if ext in (".arff", ".csv"):
                    rows = read_arff(f) if ext == ".arff" else read_csv(f)
                    new = _requirement_rows(rows, prefix)
                    for k, p in enumerate(new, len(passages) - before + 1):
                        p["id"] = f"EXT-{prefix}-{k:04d}"
                    passages += new
                    files += 1
                    continue
                if ext == ".xml":
                    title, parts = read_xml(f)
                elif ext == ".pdf":
                    title, parts = read_pdf(f)
                    if title is None:
                        skipped.append(f.name)
                        continue
                elif ext in (".txt", ".md"):
                    title, parts = read_text(f)
                else:
                    continue
            except Exception as e:  # a broken file must not stop the app
                skipped.append(f"{f.name} ({type(e).__name__})")
                continue
            files += 1
            for part in parts:
                k = len(passages) - before + 1
                passages.append({"id": f"EXT-{prefix}-{k:04d}", "source": folder.name, "title": title, "text": part, "file": f.name})
        summary.append({"dataset": folder.name, "files read": files, "passages": len(passages) - before, "skipped": ", ".join(skipped[:5])})
    return passages, summary


class Library:
    """BM25 over passages. Built once at start-up."""

    def __init__(self, passages, k1=1.5, b=0.75):
        self.passages = passages
        self.by_id = {p["id"]: p for p in passages}
        self.toks = [tokens(p["title"] + " " + p["text"]) for p in passages]
        self.df = Counter(t for ts in self.toks for t in set(ts))
        self.avg = sum(map(len, self.toks)) / len(self.toks) if self.toks else 0
        self.k1, self.b = k1, b

    def __len__(self):
        return len(self.passages)

    def search(self, query, k=5, source=None):
        q = tokens(query)
        if not q or not self.passages:
            return []
        n = len(self.passages)
        scores = []
        for i, ts in enumerate(self.toks):
            if source and self.passages[i]["source"] != source:
                continue
            tf = Counter(ts)
            s = 0.0
            for t in q:
                if t in tf:
                    idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                    s += idf * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * len(ts) / (self.avg or 1)))
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        return [{**self.passages[i], "score": round(s, 2)} for s, i in scores[:k]]
