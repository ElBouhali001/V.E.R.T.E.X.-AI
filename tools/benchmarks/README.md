# Guardrail benchmarks

External, fully-synthetic eval sets used only to measure `src/vertex_hub/guardrails.py` against
something harder than the 6 demo documents in `data/acme/documents/`. Never mixed into the demo
corpus; `is_injection` and `Redactor` are not tuned against these sets, so the scores in
`tools/guardrails_eval.py` are an honest out-of-sample read, not a fit metric.

| File | Source | License | Rows | Note |
| --- | --- | --- | --- | --- |
| `injection/prompt_injections.json` | [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections) (HF) | Apache-2.0 | 662 | `{text, label, split}`; label 1 = injection attempt |
| `pii/synth_pii.json` | [presidio-research](https://github.com/data-privacy-stack/presidio-research) `data/synth_dataset_v2.json` (Microsoft, now data-privacy-stack), filtered to PERSON/EMAIL_ADDRESS/PHONE_NUMBER spans + 50 PII-free negatives | MIT | 747 of 1500 | Faker-generated identities; no real person's data |

Run: `python tools/guardrails_eval.py`

## Known, deliberate gaps (not chased further)

- **Phone redaction (2% recall on the benchmark).** `PHONE` in guardrails.py covers `+<country code> ...`
  and French domestic `0X XX XX XX XX` -- the formats realistic for this client engagement (Acme
  Mobility: French/international PLM project). The benchmark's other 90 misses are US/UK/Swedish/etc.
  locale formats from Faker. A looser digit-group pattern that would catch them also matches every
  document date in the real corpus (`2026-09-07`, etc. -- verified, not a guess) and attribute lengths
  like "40 characters". Broadening here trades a redaction win for a redaction-storm false-positive risk
  on information that has to stay readable (dates, max-length rules). If a client engagement needs other
  locales, add that locale's format explicitly and re-run the false-positive check against the real corpus
  first, the same way this one was validated.
- **Injection recall (12% held-out).** `INJECTION_PATTERNS` catches explicit phrasing families
  (ignore/forget/override + role-hijack cues). It structurally cannot catch injection-via-fiction
  ("two actors in a film about a robbery, stay in character...") or other semantically-disguised attacks
  without either false positives or a real classifier (NER/embedding-based, e.g. a fine-tuned
  injection-detection model). That's a bigger change than a regex tune -- see the threat model doc.
