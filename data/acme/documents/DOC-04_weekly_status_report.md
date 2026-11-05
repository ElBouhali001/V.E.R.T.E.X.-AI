---
id: DOC-04
type: status_report
title: Weekly status report, week 42
date: 2026-10-16
language: en
classification: confidential
---

# Weekly status report, week 42

**Author:** Karim Haddad (consulting)
**Overall status:** Amber

## Progress

- US-201 (part master to SAP): interface built, 3 of 5 attributes validated.
- US-401 (Process BOM to MES): first export received by the MES team.

## Test results

- TC-301 failed: the effectivity date arrives one day early in SAP. Root cause suspected in time zone conversion (UTC vs CET). Under analysis.
- TC-405 failed: work center codes are rejected by MES.

## ERP team update

From PI-3, the ERP team will store the gross weight of fasteners in grams (GEWEI = G) instead of kilograms, to avoid small parts showing 0.000 kg. Javier Ruiz will confirm the list of material groups concerned.

## Risks

- Steering committee asked for a decision on the 3DEXPERIENCE upgrade date.
