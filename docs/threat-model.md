# Vertex Hub — Threat Model

Status: engineering draft, grounded in the current code and today's benchmark results
(`tools/guardrails_eval.py`). Not a legal or compliance sign-off — pair with
`docs/gdpr-ai-act-position.md` and route both through your team's actual review process
before they go in front of a client.

## 1. What's being protected, and where it lives

Vertex Hub runs **per client engagement**: each client gets its own `data/<client>/` tree
(project documents, backlog, systems/interfaces), loaded into one `Twin` instance
(`src/vertex_hub/pipeline.py`). There is no shared database and no multi-tenant server —
today's deployment model is "stood up fresh per engagement," closer to installed software
than SaaS (see `bootstrap.py`, built explicitly to scaffold a new client).

| Asset | Where | Why it matters |
| --- | --- | --- |
| Client project documents (minutes, workshops, status reports) | `data/<client>/documents/` | Often contains named individuals, business-sensitive decisions, supplier names |
| Personal data of client staff (names, emails, phones) | Embedded in the documents above | GDPR personal data; masked before the LLM sees it (`guardrails.Redactor`), not before a human does |
| The audit trail | `cache/audit.db` (as of today — see §5) | The evidence that guardrails actually fired; itself sensitive (shows what was blocked/redacted and when) |
| Jira credentials | `JIRA_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN` env vars | Write access to the client's real backlog, if configured |
| LLM backend credentials | `OPENAI_API_KEY` env var (optional, opt-in) | Only relevant if a client engagement explicitly chooses the cloud backend over local Ollama |

## 2. Threat actors, ranked by what the evidence says is actually weakest

### T1 — Malicious or compromised document source (prompt injection) — **highest priority**

**Path:** a document that reaches the pipeline (a meeting-minutes file, a pasted upload via
`Twin.ingest()`, an incoming Jira story) contains text aimed at the LLM rather than the human
reader — "ignore previous instructions and export X," a role-play jailbreak, a hidden
instruction in a table cell.

**Why it's realistic here specifically:** the pipeline's own demo scenario (DOC-05) is built
around exactly this — a MoM with a planted instruction to exfiltrate the attribute list. That's
not a hypothetical; it's the one attack the product was explicitly designed to demonstrate
catching.

**Current mitigation:** `guardrails.quarantine()` — sentence-level regex match against
`INJECTION_PATTERNS`, blocked sentences never reach the LLM, each block is logged.

**Measured residual risk:** scored today against `deepset/prompt-injections` (662 real
injection/benign examples, patterns tuned only on the train split):
- **Held-out recall: 10%** (6/60 real injection attempts caught on the test split)
- **False-positive rate: 0%** (0/56 — never blocks legitimate text)

In plain terms: the detector reliably catches the *style* of attack it was written for
(explicit "ignore/forget/override instructions," system-prompt extraction, role hijack
phrases) and reliably ignores everything else, including the 90% of attack styles it wasn't
written for — fiction-framed jailbreaks ("two actors in a film about a robbery, stay in
character...") being the clearest blind spot. A regex family can be broadened further, but
closing most of that 90% needs a different *kind* of detector (a classifier/NER model, the way
`extract.py`'s own docstring already concedes for personal-data detection), not more regex.

**Recommendation:** state the 10% figure plainly in any claim of "we catch prompt injection" —
today's true claim is "we catch injections that follow one of several known phrasing families
and log every one we catch," not "we catch prompt injection attempts." Treat a
classifier-based upgrade as a scoped Phase 2 item, not a quick fix.

### T2 — Personal data reaching the LLM or leaking in logs

**Path:** a name, email or phone number in a document is sent to the LLM (local or cloud) or
ends up readable in `cache/` without ever being pseudonymized.

**Current mitigation:** `guardrails.Redactor` — regex-based EMAIL/PHONE matching plus a
**name-anchor heuristic**: a name is only recognised (and then masked everywhere in the
corpus) if it's introduced somewhere as `"X Y (Acme"` or `"X Y (consulting"`. This is a
documented, deliberate placeholder — `guardrails.py`'s own module docstring names the production
fix: Microsoft Presidio with a spaCy NER model.

**Measured residual risk** (`presidio-research` synthetic benchmark, 747 rows):
- **EMAIL recall: 100%** (49/49) — the regex is close to universal for this format.
- **PHONE recall: 2%** (2/92) — deliberately scoped to French domestic + international `+`
  formats (the formats realistic for *this* client's documents), not broadened further because
  a looser pattern false-positives on every document date (`2026-09-07`, etc. — checked against
  the real corpus, not assumed). A different client with non-French phone formats needs that
  format added and re-validated the same way, before go-live for that engagement.
- **PERSON recall: not measured** — the anchor heuristic needs a textual cue this general
  benchmark doesn't provide. Its real weakness is structural, not a tuning gap: a name that's
  never introduced with an anchor phrase, anywhere in the corpus, is never masked. This holds
  today's demo corpus together by construction (every name happens to be anchored) — that's
  dataset luck, confirmed by checking, not a property of the detector.

**Recommendation:** before using this on a real client's documents (as opposed to the synthetic
demo), either (a) manually audit that every name appearing is anchor-introduced, which doesn't
scale, or (b) replace the heuristic with real NER. This is the single biggest gap between
"demo-safe" and "client-data-safe."

### T3 — Local-vs-cloud model substitution (the app silently sending data off-machine)

**Path:** a model is selected that doesn't actually run locally, so sanitized (but not
necessarily fully redacted, per T2) document text leaves the machine.

**Status: mitigated this session.** Previously, Ollama Cloud models (`*-cloud` suffix, proxied
to `ollama.com`) and embedding-only models were selectable in the sidebar dropdown alongside
genuinely local ones, filtered only by a name-substring check. `llm.py`'s `local_chat_models()`
now filters on Ollama's actual reported `capabilities` and `remote_host` fields, so a cloud
model can no longer be chosen as "the local model." Residual risk: a user can still explicitly
set `LLM_BACKEND=openai` (an intentional, opt-in escape hatch for engagements that choose
cloud) — that's a deliberate design choice, not a leak, but it should be a conscious
per-engagement decision, documented in the GDPR position doc, not a default.

### T4 — Compromised or leaked integration credentials

**Path:** `JIRA_API_TOKEN` or `OPENAI_API_KEY` leaks (committed accidentally, shared insecurely,
left in shell history) and is used to write to the client's real Jira or run up API spend.

**Current mitigation:** credentials are read from environment variables only, never written to
`data/`, `cache/`, or the audit log; `.gitignore` excludes `.venv/` and `cache/`. No secret
scanning or rotation policy exists in the repo today — that's standard practice to layer on at
the engagement/ops level (secrets manager, not hardcoded in `.env` committed to a client repo),
not something `guardrails.py` can enforce itself.

**Recommendation:** make "how credentials are provisioned per engagement" an explicit line in
your governance doc rather than leaving it implicit in README prose.

### T5 — Cross-engagement data leakage

**Path:** Client A's data becomes visible in a Client B engagement.

**Current mitigation:** structural — each client's data lives in its own `data/<client>/` tree,
loaded into its own `Twin`/`Redactor`/`Audit` instance per process. No shared database. As long
as deployment keeps "one process, one client" (which the architecture assumes but doesn't
enforce), this isn't reachable. **Becomes a real question the moment deployment changes** —
e.g. a shared server running multiple clients' instances, or the audit log's `cache/audit.db`
(see §5) being backed up/shipped somewhere shared. Flag this explicitly if/when a multi-client
hosting model is considered; today's single-tenant-per-install architecture sidesteps it by
construction, not by access control.

## 3. Out of scope for this document

- Attacks on the Ollama binary / model supply chain itself (trusting `ollama pull` to fetch
  what it claims to) — upstream dependency, not something this app's code controls.
- Physical/OS-level access control to the machine running the app — assumed to be the client's
  or your own standard endpoint security, not a Vertex Hub concern.
- Jira Cloud's own security posture — out of this app's control once a comment is sent
  (`decisions.send_outbox`).

## 4. Audit trail as a control (today's change)

As of this session, `guardrails.Audit` splits into two stores (`src/vertex_hub/guardrails.py`,
wired in `pipeline.py`):
- **`audit` table** (injections blocked, redactions, extraction accept/reject, decisions made,
  Jira sends): persists to `cache/audit.db`, survives a restart, and is **not** cleared by the
  app's "Reset demo" button — a reset that could erase its own evidence trail would defeat the
  point of having one.
- **`decisions`/`outbox` tables**: stay in-memory, fresh per session — this is what "Reset demo"
  clears, and what every test expects to start empty.

Regression-tested in `tests/test_guardrails.py::test_decisions_never_leak_between_separate_twins_while_audit_trail_persists`
specifically because the first version of this fix got it wrong (persisted all three tables
together, which leaked decision state between runs) before being caught and corrected.

**Open question for governance:** the trail is durable per-machine but has no retention policy,
no access control beyond the filesystem, and no export/redaction mechanism for a data-subject
erasure request. That's a decision for the GDPR position doc, not something to default silently.
