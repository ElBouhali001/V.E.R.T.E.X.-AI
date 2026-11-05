<p><img src="app/assets/vertex-wordmark.png" alt="Vertex Hub" width="520"></p>

**V.E.R.T.E.X. AI**: Value Extraction and Reconciliation for Technical Excellence.
Built for the Capgemini DPM & PLM Hackathon (project P1, AI-driven Project Accelerator).

Vertex Hub keeps a PLM project's knowledge connected across PLM, ERP, MES and the backlog. It reads
meeting minutes, tickets and documents, maps every client's vocabulary to one ontology, and shows what a
decision breaks before anyone applies it. The AI reads, the graph reasons, a human decides.

All data in `data/` is synthetic: every company, person, email and phone number is invented.

## Project layout

```
src/vertex_hub/          THE PROJECT: all logic lives here
  data.py              load a client project
  graph.py             knowledge graph + impact walk
  ontology.py          glossary, term reconciliation, attribute aliases
  guardrails.py        injection quarantine, personal-data masking, audit log
  llm.py               local AI (Ollama by default), status check, disk cache
  extract.py           rules / AI / hybrid extraction, normalisation, quote repair, anti-hallucination gate
  impact.py            conflicts, trade-offs, version upgrades
  alerts.py            alerts merged across sources, severity, first-seen date
  assistant.py         Ask Vertex (grounded Q&A with checked citations) + setup assistant
  library.py           external datasets: loaders, masking, BM25 search
  decisions.py         approve / reject, model update, Jira outbox
  connectors.py        Jira mock + Jira Cloud (env vars)
  viz.py               impact map (SVG)
  evaluate.py          scoring vs ground truth
  bootstrap.py         starter backlog for a new client
  pipeline.py          Twin: wires everything, used by app, notebook and tests
app/                   the cockpit (streamlit_app.py + ui.py + assets/ logo), imports src
.streamlit/config.toml theme
notebooks/01_pipeline_check.ipynb   parallel check notebook (imports src, 27 checks)
tests/                 44 automated tests (incl. a fake imperfect model)
tools/                 doctor, validator, notebook builder, app smoke test, llm_eval, guardrails_eval + benchmarks/
docs/                  threat model, GDPR and AI Act position (drafts for review)
data/ ontology/ catalog/            the inputs
cache/                 AI answers + Jira mock (git-ignored, safe to delete)
```

Rule: logic goes in `src/`. The app and the notebook only call it.

## Run it

```bash
cd plm-accelerator
source .venv/bin/activate
pip install -r requirements.txt

python tools/validate_dataset.py   # data is consistent  -> OK
pytest                             # logic works         -> 44 passed
```

Then two terminal tabs (each runs until Ctrl+C):

```bash
jupyter lab notebooks/01_pipeline_check.ipynb   # tab 1: Run All -> "27/27 checks passed"
streamlit run app/streamlit_app.py              # tab 2: the cockpit, http://localhost:8501
```

The notebook uses `%autoreload`: edit a file in `src/`, re-run the cell, it picks up the change.
After changing app code, Streamlit offers "Rerun" in the browser. Before every push: `pytest`.

## Pitch

`pitch/index.html` is the 3-slide presentation: open it in a browser, no server needed. Arrow keys or
space to move, F for full screen. Slide 2 has a clickable pipeline, a live what-if slider and a button to
the running cockpit. Put the official Capgemini logo next to it as
`pitch/capgemini-logo.png`. Orange `[__]` values are placeholders: fill them from `tools/llm_eval.py` and the team.

## Datasets and the AI check

Public datasets go in `data/external/` (links and folders in `data/external/README.md`): PURE in
`data/external/pure/`, PROMISE NFR in `data/external/promise/`. They appear in the **Library** page and Ask Vertex
cites them.

Before any demo, run:
```bash
python tools/doctor.py --warm
```
It checks Python, packages, data, datasets, the local model, AI extraction on a French document, the cache and
Ask Vertex, and prints the fix for anything that fails. `--warm` reads every document once so the demo never waits.

## Security evaluation

`python tools/guardrails_eval.py` scores the guardrails on public benchmarks (prompt injection, synthetic personal
data). Current held-out injection recall is 12% with 0 false positives, and 0 of 18 project-language sentences are
wrongly blocked (`tests/test_guardrails.py`). The regex layer is the first of several: the model has no tools, its
output is schema-checked, every fact must quote its source, and nothing changes without a person's approval.
See `docs/threat-model.md`.

## Partner logo

The sidebar shows any file in `app/assets/` whose name contains `partner-logo` or `capgemini` (.svg or .png).
The pitch embeds the logo directly.

## Local AI (Ollama)

1. Install Ollama from https://ollama.com (Mac app) and open it.
2. `ollama pull qwen2.5:7b` (about 5 GB; good at JSON and French). Without `LLM_MODEL`, the app picks
   the first suitable installed model (qwen2.5:7b, then qwen2.5-coder:7b, then others).
3. `python tools/llm_eval.py` (or `--model qwen2.5-coder:7b`): runs the model on every document, fills `cache/`, prints
   rules vs AI vs hybrid scores. After that the cockpit reads from cache and never waits.

If Ollama is not running, everything still works on rules; the sidebar shows the AI status.
Cloud option: `LLM_BACKEND=openai` + `OPENAI_API_KEY` (any OpenAI-compatible endpoint via `OPENAI_BASE_URL`).
The model can also be switched live in the app sidebar; answers are cached per model.

## Jira

Default is a mock (comments stored in `cache/jira_mock.json`). For a real Jira Cloud site set
`JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` (untested against a live site), and make sure the
issue keys in `data/acme/backlog.yaml` exist there.

## Data

| Path | Content |
| --- | --- |
| `data/acme/client_profile.yaml` | Acme Mobility: automotive e-axles, 3DEXPERIENCE R2025x, SAP S/4HANA, DELMIA Apriso, SAFe, Jira |
| `data/acme/systems.yaml` | 5 systems, 4 interfaces (PLM to ERP, PLM to MES, ERP to MES, CAD to PLM) and the attributes each carries |
| `data/acme/attributes.yaml` | 15 canonical attributes with their field, type, length and unit in each system |
| `data/acme/glossary.yaml` | 15 concepts with consultant, editor, client and French terms (PBOM = BOP = Plant BOM) |
| `data/acme/backlog.yaml` | 4 epics, 5 capabilities, 9 features, 16 user stories with Jira keys and attribute links |
| `data/acme/test_cases.yaml` | 16 test cases linked to stories, attributes and interfaces (2 currently failing) |
| `data/acme/documents/` | 6 documents: kickoff, PLM workshop, ERP workshop (in French), status report, steering committee, and DOC-06, a **holdout** written with paraphrases to test extraction honestly |
| `data/acme/incoming/US-412...yaml` | New MES user story arriving from Jira: operation label renamed and cut to 40 characters |
| `data/acme/expected_extractions.yaml` | Ground truth: 10 facts the AI must extract, 1 injection to block, personal data to mask |
| `data/acme/expected_results.json` | Generated: impact sets, conflicts, resolved conflicts, latent conflicts |
| `data/medtech/client_profile.yaml` | Second client (infusion pumps, Windchill, Scrum, no MES) for the bootstrapper |
| `ontology/core.yaml` | Graph schema: node types, edge types, impact walk |
| `ontology/editors/` | Editor vocabularies: 3DEXPERIENCE R2025x, R2026x (diff is ILLUSTRATIVE), Windchill |
| `catalog/capabilities.yaml` | Capability catalogue from the brief, by family and industry, for the bootstrapper |

## Planted scenarios (what the demo must show)

| # | Trigger | What the system must find |
| --- | --- | --- |
| 1 | DOC-03, French ERP workshop: limit the part description to 40 characters in PLM | Maps "désignation article" to Part Description. Proposal resolves the INT-01 truncation but breaks TC-205 and the naming rule (US-501). Impact: 5 stories and 4 tests directly. This is the trade-off card. |
| 2 | DOC-02, PLM workshop confirms 80 characters | Conflict with SAP MAKTX (40) on INT-01. **Detectable on 21 Sept, two weeks before anyone raised it.** |
| 3 | DOC-03 + DOC-04: work centers are 8 characters in SAP; TC-405 failed | Explains a failing test: PLM resource names (40) are truncated into MES (8) on INT-02. |
| 4 | DOC-04: ERP moves fastener weight to grams | Unit mismatch kg vs g on INT-01; US-502 and TC-206 affected. |
| 5 | US-412 from Jira: MES label cut to 40 characters | PLM-to-MES tests TC-401, TC-402 flagged before they fail. |
| 6 | DOC-05: upgrade to R2026x | Editor profile diff becomes a change; interfaces carrying the changed attributes flagged for retest. |
| 7 | DOC-05, "any other business" | Prompt injection: quarantined, logged, nothing extracted from that line. |
| 8 | All documents | 7 names, 3 emails, 1 phone number masked before the LLM sees the text. |
| 9 | Medtech profile | Bootstrapper adds requirements, V&V and AML; skips MES publication; uses Windchill terms. |

Show "direct" impact first; "via interface" lists are long and belong in a second, collapsed ring.

## To validate with the PLM lead (Houssam) before Wednesday 18:00

- [ ] 3DEXPERIENCE type names in `ontology/editors/3dexperience_R2025x.yaml` (VPMReference, Manufacturing Item, Header Operation...)
- [ ] Windchill type names (WTPart, Change Notice, Change Task, MPMLink process plan)
- [ ] PLM field names in `attributes.yaml` (V_description, V_mass, V_Name): illustrative, fix if wrong
- [ ] Glossary client terms in French: do they sound like a real plant?
- [ ] Whether the INT-01 trigger "Change Action released" matches how you have seen it done
- [ ] Any scenario a PLM judge would find naive
