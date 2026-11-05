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
