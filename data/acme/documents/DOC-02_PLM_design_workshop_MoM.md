---
id: DOC-02
type: MoM
title: PLM data model workshop
date: 2026-09-21
language: en
classification: confidential
---

# Minutes of Meeting: PLM data model workshop

**Date:** 21 September 2026
**Attendees:** Claire Martin (Acme, PLM product owner), Thomas Leroy (Acme, design office), Karim Haddad (consulting)

## 1. Part description

The part description in 3DEXPERIENCE (V_description) is confirmed at a maximum of 80 characters. The naming rule is NOUN, MODIFIER, then size, for example "SHAFT, OUTPUT, D32 L210".

**Decision:** descriptions are mandatory in both French and English before a part can be released.

## 2. Mass

Mass is stored in kilograms with 3 decimals. CAD-computed mass overrides manual entry when available.

## 3. Maturity states

Parts follow Private, In Work, Frozen, Released, Obsolete. Only Released parts may be published to SAP.

## Action items

| Owner | Action | Due |
| --- | --- | --- |
| Thomas Leroy | Provide 20 sample parts with FR and EN descriptions | 2 Oct 2026 |
