# Governance and billing model

Answers point 7 of the brief: who owns the framework once it is live, how it changes safely, and how it is paid for across build, run and support.

## 1. Who owns what

| Role | Side | Owns | Decides |
|---|---|---|---|
| Framework owner | Integrator | Capability catalogue, editor profiles, connectors, release of new Vertex versions | What goes into a release |
| Ontology steward | Client (PLM key user) | Glossary and attribute mapping for this client | Accepts or rejects proposed terms |
| Change board | Client (PLM lead, architects) | Approve / reject decisions raised by Vertex | Every change to the project model |
| Data protection officer | Client | Masking rules, retention of the audit trail, where the model runs | What data may leave the client network (default: none) |
| PMO / RTE / Scrum Master | Client | Delivery framework settings (cadence, levels, ceremonies) | When the framework is re-generated |

The AI never decides. It proposes; a named person approves, and the approval is logged.

## 2. How things change

| What changes | Path | Safety check |
|---|---|---|
| A new term in the glossary | Proposed in the app or detected in a document → steward validates → new glossary version | Unvalidated terms are shown as "proposed", never used as facts |
| A fact extracted from a document | Lands in "Decisions" → change board approves or rejects | Quote must exist verbatim in the source, IDs must exist in the ontology |
| The local model or its prompt | Run `tools/llm_eval.py` on the ground truth and holdout | Release blocked if holdout recall drops or a hallucinated quote passes the gate |
| Injection / masking rules | Run `tools/guardrails_eval.py` and the project-language test set | Release blocked if false positives on project language rise above 0 |
| PLM editor version (e.g. R2025x → R2026x) | New editor profile → upgrade impact report | Interfaces and tests to rerun listed before the upgrade is planned |

Cadence: glossary and decisions continuously; model and rules at each release; a quarterly review of alerts that turned out wrong.

## 3. Billing model (figures are working assumptions, to be validated with the partner)

| Phase | What the client gets | Proposed price | Basis |
|---|---|---|---|
| Build (once per client) | Connectors to their backlog and document store, editor vocabulary, tailored catalogue, framework in their delivery method, first ground truth | Fixed fee, ~€15k | ~15 consultant days |
| Run (monthly, per project) | Local model hosted on client hardware or sovereign cloud, document ingestion, alerts, decision log, audit trail | ~€1.5k per project per month | Compute + ~1 analyst day a month |
| Support (yearly) | New connectors, ontology extensions, model upgrades re-measured on the holdout, editor version profiles | ~15% of build per year, new connector quoted separately | Standard maintenance ratio |

Why it is sustainable: the catalogue, editor profiles and guardrails are built once and reused for every client, so build cost falls with each new project while run revenue grows with the number of live projects. For the integrator it also shortens project start-up, which protects margin on fixed-price PLM deals.

Value argument to the client: one integration defect caught before testing (the 80 → 40 character truncation in the demo, flagged 14 days early) avoids a rework cycle across interface, tests and data migration. A few such catches per year cover the run fee.
