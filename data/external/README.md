# External datasets

Files in these folders are loaded at start-up into the **Library**: cut into passages, quarantined and masked
like project documents, indexed for search, and cited by Ask Vertex as `EXT-<DATASET>-0001`.
Nothing here is sent anywhere: the local model reads only the passages a question retrieves.

## 1. PURE: public requirements documents

79 real requirements documents collected from the web (Ferrari, Spagnolo, Gnesi, RE 2017).

- Page: https://zenodo.org/records/7118517
- Put the documents **in `data/external/pure/`** (subfolders are fine). Supported: `.pdf` (needs `pypdf`), `.xml`,
  `.html`/`.htm`, `.txt`, `.md`, and legacy `.doc`/`.rtf` (read through macOS `textutil`; skipped, and listed in the
  doctor, on a machine without it).
- The first load reads every file and takes about a minute. The result is kept in `cache/library/`, so later
  start-ups are instant; a changed file is re-read automatically.

## 2. PROMISE NFR: labelled requirements

625 requirements from 15 projects, each labelled functional or by quality type
(performance, security, usability, availability...).

- Page: https://zenodo.org/records/268542
- Put `nfr.arff` **in `data/external/promise/`** (a subfolder is fine). A CSV with a requirement-text column and a
  class column also works. The per-project `*_trace.arff` files carry trace links, not requirement text, and are ignored.
- Licence: CC BY-NC-SA 4.0 (non-commercial use with attribution): fine for the hackathon demo.

## After adding files

```bash
python tools/doctor.py
```
The "Datasets" line should list both folders with their passage counts. In the app, press **Reset demo**
(sidebar), then open **Library** to search, or ask in **Ask Vertex**, for example
"Which requirements talk about availability?" or "What does the ground station spec say about telemetry?".

Any other folder here works too: `.txt`, `.md`, `.pdf` and `.xml` documents are read as plain text.
