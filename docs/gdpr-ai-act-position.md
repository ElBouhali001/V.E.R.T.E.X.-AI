# Vertex Hub — GDPR / EU AI Act Position

Status: engineering-grounded draft for your team to review, edit, and own. **This is not legal
advice** — it describes what the software actually does and doesn't do, so your legal/DPO
function can reach a defensible position faster than starting from a blank page. The positions
below are *recommended defaults* that fit the current architecture; several are explicitly
flagged as decisions your team needs to confirm, not facts.

Companion document: `docs/threat-model.md` (the technical gaps referenced below).

## 1. Controller vs. processor — recommended default, needs sign-off

**Recommended position: your firm acts as processor, the client remains controller**, for data
processed during an engagement.

Why this fits the architecture, not just the paperwork: Vertex Hub has no central database and
no multi-tenant backend. Each engagement runs as its own local process against its own
`data/<client>/` tree; the default AI backend (`LLM_BACKEND=ollama`) runs entirely on the
machine where it's installed (verified this session — see `docs/threat-model.md` §T3); nothing
is sent to a third party unless a client engagement *explicitly* opts into `LLM_BACKEND=openai`
or a real Jira Cloud connector. That's a materially easier processor story than a typical SaaS
tool, because there's no "your data sits on our servers" claim to make at all in the default
configuration.

**Confirm before using externally:** does any engagement currently (or plan to) use the OpenAI
backend or a shared/hosted deployment? If yes, that specific engagement's processor story
changes (data now reaches a named sub-processor) and needs its own data processing agreement
language — don't let the general local-first claim cover a deployment that isn't actually
local-first.

## 2. Legal basis for processing

Not this document's call — the client, as controller, determines their own legal basis
(typically legitimate interest or contract performance, for employee names appearing in
internal project minutes). **Recommended stance: your firm doesn't need to assert or track the
client's legal basis**, because the architecture's default is "we don't retain this data beyond
the engagement, on infrastructure the client controls" — the processor doesn't need the
controller's legal basis to do its job, only to confirm one exists.

## 3. What the software actually does with personal data — the factual basis for any claim

| Stage | What happens | Code reference |
| --- | --- | --- |
| Ingestion | Document text loaded from `data/<client>/documents/` or pasted via the app | `pipeline.py: Twin.ingest` |
| Quarantine | Sentences matching known prompt-injection phrasings are stripped before anything else happens | `guardrails.quarantine` |
| Pseudonymization | Names (anchor-heuristic only — see gap below), emails, phone numbers replaced with stable tokens (`<PERSON_1>`, etc.) before the LLM ever sees the text | `guardrails.Redactor` |
| AI processing | Pseudonymized text sent to the configured backend — local Ollama by default, verified this session to exclude cloud-proxied models from the "local" option | `llm.py` |
| Audit | Every redaction and injection-block logged with a timestamp, persisted to `cache/audit.db` | `guardrails.Audit` (see threat model §4) |
| Re-identification | Pseudonyms reversed only for display to the authorised user viewing the app | `Redactor.reveal` |

**The honest caveat, stated plainly rather than buried:** pseudonymization happens *before the
AI*, not before a human using the cockpit — anyone with access to the app sees real names,
emails and phones by design (that's the product: a human reviewing project decisions needs to
know who said what). The data-protection claim here is "minimised third-party/AI exposure," not
"anonymised from all users." Don't let a pitch deck slide blur that distinction.

**Known technical gap, inherited from `docs/threat-model.md` §T2:** the name-detection heuristic
only masks names that are introduced with a specific textual pattern somewhere in the corpus. On
the synthetic demo data this holds by construction (checked, not assumed). On a real client's
documents, an unanchored name would reach the LLM unmasked. **This is the limiting factor on any
claim stronger than "we pseudonymize personal data we can detect."** Until the detector is
upgraded (Presidio/NER, as the code already names as the intended path), any client-facing
commitment should either name this limitation explicitly or require a one-time manual check of
the client's document set before go-live.

## 4. Data subject rights

No built-in mechanism today to locate-and-purge a specific person's data from `cache/` on
request (access/erasure requests under GDPR Arts. 15/17). **Recommended default position:**
since the client is controller and the data stays on infrastructure they control, fulfilling a
data-subject request is the client's operational responsibility, same as it would be for their
own email archive or SharePoint — your firm's commitment is that nothing has been copied
elsewhere (true today, structurally, not as an operational promise someone has to remember to
keep). **Needs confirmation:** does any engagement retain a copy of `cache/` outside the
client's own infrastructure (e.g., for your team's QA, or backups)? If so, that copy needs its
own answer to this question.

## 5. EU AI Act position — recommended tier, needs sign-off

**Recommended position: limited-risk.** The system extracts facts and surfaces conflicts from
project documents to inform a human decision-maker; it does not itself decide, act
autonomously, or fall into an Annex III high-risk category (no biometric identification, no
safety component in a regulated product, no employment/credit/law-enforcement decisioning). The
product's own framing — "the AI reads, the graph reasons, a person decides" (`pitch/index.html`)
— is also the right compliance framing: a human approves or rejects every proposed change
(`decisions.decide`), nothing is auto-applied.

**Primary obligation this implies: transparency** — users must know they're interacting with an
AI system. The app already does this structurally (the "Local AI" mode label, the model/backend
status shown in the sidebar, `LLM["detail"]` surfaced in the UI) rather than disclosing it only
in a terms-of-service document nobody reads.

**Needs your team's re-confirmation per engagement, not a one-time global answer:** risk tier is
a function of *use case*, not just the tool. The demo client (Acme Mobility, automotive e-axles)
is unambiguously limited-risk. The second synthetic profile already in the repo
(`data/medtech/client_profile.yaml` — infusion pumps) edges toward a safety-adjacent vertical;
if a real engagement in medical devices, automotive safety systems, or another regulated
vertical comes up, **reassess the tier for that engagement specifically** before reusing the
blanket "limited-risk" claim. Recommend a one-paragraph risk-tier check as a standard step in
your engagement kickoff, not a decision made once in this document and forgotten.

## 6. Security measures as GDPR Art. 25/32 evidence

These map directly to the "privacy by design" and "security of processing" obligations, with
the honest caveat (from the threat model) attached to each:

| Measure | Article 25/32 relevance | Caveat |
| --- | --- | --- |
| Local-first AI processing (no third party by default) | Data minimisation, Art. 32 confidentiality | Only true while the engagement stays on the default Ollama backend |
| Pseudonymization before AI exposure | Art. 25(1) privacy by design | Name detection is heuristic, not NER — see §3 |
| Prompt-injection quarantine | Art. 32 integrity (prevents a document from exfiltrating other data via the AI) | 12% held-out recall against a public benchmark, 0 false positives on project language — see threat model §T1 |
| Durable audit trail of redactions/blocks/decisions | Art. 30-style accountability records | No retention policy or erasure tooling defined yet — see §4 |
| Credentials via environment variables only, never committed | Art. 32 confidentiality | No secrets-manager integration or rotation policy defined — operational, not code |

## 7. Decisions this document is explicitly deferring to your team

1. Confirm the processor/controller framing in §1, and whether any current engagement already
   breaks the "local-first" assumption it rests on.
2. Confirm the limited-risk AI Act position in §5, and commit to the per-engagement reassessment
   step for regulated verticals.
3. Decide a retention/erasure policy for `cache/audit.db` (§4) — this is the one area where "the
   architecture handles it structurally" doesn't apply, because the whole point of an audit log
   is that it's retained.
4. Decide whether the name-detection gap (§3) is acceptable to disclose to clients as a known
   limitation, or is a blocker for any real (non-synthetic) client document set until upgraded.
