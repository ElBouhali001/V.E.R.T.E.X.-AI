---
id: DOC-06
type: MoM
title: Integration test review
date: 2026-10-30
language: en
classification: confidential
holdout: true
---

# Minutes of Meeting: Integration test review

**Date:** 30 October 2026
**Attendees:** Inès Garcia (Acme, MES engineer), Lucas Petit (Acme, planning), Karim Haddad (consulting)

## 1. Findings from the test campaign

SAP cannot hold a material short text beyond forty characters, so anything longer is cut at transfer.

Côté MES, le code du poste ne doit pas dépasser huit caractères.

Operation names authored in 3DEXPERIENCE may run up to 60 characters.

## 2. Requests

Going forward, planners want weights in SAP expressed in grams for every part, not only fasteners.

## Action items

| Owner | Action | Due |
| --- | --- | --- |
| Inès Garcia | Re-run TC-405 with short work center codes | 6 Nov 2026 |
