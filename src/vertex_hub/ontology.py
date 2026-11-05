"""Ontology reconciliation: one concept, many names (consultant, editor, client, French)."""
import difflib
import re
import unicodedata

SKIP_FIELDS = {"current", "revision", "classification"}  # field names too generic to match in prose


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("’", "'")
    return " ".join(s.split())


class Glossary:
    def __init__(self, p):
        self.p = p
        self.terms = {}            # normalized term -> (concept id, party)
        for c in p.concepts.values():
            self.terms[norm(c["canonical"])] = (c["id"], "canonical")
            for party, terms in c["terms"].items():
                for t in terms:
                    self.terms.setdefault(norm(t), (c["id"], party))
        self.attr_aliases = {}     # normalized alias -> attribute id
        for a in p.attributes.values():
            self.attr_aliases[norm(a["canonical"])] = a["id"]
            for d in a["definitions"].values():
                f = d.get("field")
                if f and len(f) >= 4 and norm(f) not in SKIP_FIELDS:
                    self.attr_aliases[norm(f)] = a["id"]
        for c in p.concepts.values():
            if "maps_to_attribute" in c:
                for terms in c["terms"].values():
                    for t in terms:
                        self.attr_aliases[norm(t)] = c["maps_to_attribute"]

    def lookup(self, term):
        key = norm(term)
        if key in self.terms:
            cid, party = self.terms[key]
            return {"term": term, "concept": cid, "canonical": self.p.concepts[cid]["canonical"], "matched_as": party, "status": "known"}
        close = difflib.get_close_matches(key, self.terms, n=1, cutoff=0.75)
        if close:
            cid, _ = self.terms[close[0]]
            return {"term": term, "concept": cid, "canonical": self.p.concepts[cid]["canonical"],
                    "matched_as": f"fuzzy: {close[0]}", "status": "proposed, needs validation"}
        return {"term": term, "concept": None, "canonical": None, "matched_as": None, "status": "new term, add to glossary?"}

    def find_attributes(self, sentence):
        """Longest alias first, whole words only, each span used once."""
        text, found = norm(sentence), []
        for alias in sorted(self.attr_aliases, key=len, reverse=True):
            m = re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", text)
            if m:
                found.append(self.attr_aliases[alias])
                text = text[:m.start()] + " " * len(alias) + text[m.end():]
        return list(dict.fromkeys(found))

    def catalogue(self):
        """Attribute list with all their names, for the LLM prompt."""
        lines = []
        for a in self.p.attributes.values():
            names = sorted({al for al, aid in self.attr_aliases.items() if aid == a["id"]})
            lines.append(f"- {a['id']}: {', '.join(names)}")
        return "\n".join(lines)
