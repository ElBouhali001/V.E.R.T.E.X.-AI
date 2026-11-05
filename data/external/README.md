# External datasets

Files in these folders are loaded at start-up into the **Library**: cut into passages, quarantined and masked
like project documents, indexed for search, and cited by Ask Vertex as `EXT-<DATASET>-0001`.
Nothing here is sent anywhere: the local model reads only the passages a question retrieves.

## 1. PURE: public requirements documents

79 real requirements documents collected from the web (Ferrari, Spagnolo, Gnesi, RE 2017).

- Page: https://zenodo.org/records/7118517
- Download **requirements-xml.zip** (about 380 kB, 19 documents in XML) and unzip it **into `data/external/pure/`**.
- Optional: the large zip with all 79 PDFs (about 34 MB) also works; unzip it into the same folder.
  PDFs need `pypdf` (in requirements.txt) and make start-up slower.

## 2. PROMISE NFR: labelled requirements

625 requirements from 15 projects, each labelled functional or by quality type
(performance, security, usability, availability...).

- Page: https://zenodo.org/records/268542
- Download the **.arff** file and put it **in `data/external/promise/`**. A CSV with a requirement-text
  column and a class column also works.
- Licence: CC BY-NC-SA 4.0 (non-commercial use with attribution): fine for the hackathon demo.

## After adding files

```bash
python tools/doctor.py
```
The "Datasets" line should list both folders with their passage counts. In the app, press **Reset demo**
(sidebar), then open **Library** to search, or ask in **Ask Vertex**, for example
"Which requirements talk about availability?" or "What does the ground station spec say about telemetry?".

Any other folder here works too: `.txt`, `.md`, `.pdf` and `.xml` documents are read as plain text.
