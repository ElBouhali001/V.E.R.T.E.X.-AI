---
id: DOC-03
type: MoM
title: Atelier ERP, données article
date: 2026-10-05
language: fr
classification: confidential
---

# Compte rendu de réunion : atelier ERP, données article

**Date :** 5 octobre 2026, site de Lyon
**Participants :** Javier Ruiz (Acme, responsable ERP, javier.ruiz@acme-mobility.example), Claire Martin (Acme, PO PLM), Lucas Petit (Acme, planification), Karim Haddad (consulting, chef de projet)

## 1. Désignation article

Javier Ruiz rappelle que dans SAP le champ MAKTX est limité à 40 caractères. Plusieurs désignations de test ont été tronquées lors des premiers transferts.

L'équipe ERP propose de limiter la désignation article à 40 caractères côté PLM, plutôt que de tronquer à l'interface. Claire Martin indique que la règle de nommage actuelle produit des désignations plus longues. Point à confirmer avec l'équipe PLM avant la fin du sprint.

## 2. Postes de charge

Les codes poste de charge (ARBPL) sont sur 8 caractères maximum dans SAP. Les noms de ressources dans la gamme usine doivent donc utiliser le code court.

## 3. Formation

La formation des planificateurs à SAP aura lieu en semaine 46.

## Actions

| Responsable | Action | Échéance |
| --- | --- | --- |
| Claire Martin | Évaluer l'impact d'une limite à 40 caractères sur la règle de nommage | 16 oct. 2026 |
| Lucas Petit | Lister les désignations tronquées | 9 oct. 2026 |
