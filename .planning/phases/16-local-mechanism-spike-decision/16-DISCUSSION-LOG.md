# Phase 16: Local Mechanism Spike & Decision - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-28
**Phase:** 16-Local Mechanism Spike & Decision
**Areas discussed:** Scripts de sonde — disposition; Conditions d'arrêt & verdicts; Consentement & exécution des sondes

**Carried context (locked in earlier discussions, not re-asked):** real target albums
(100–500) as probe targets with 600+ synthetic fallback; share links redacted in
committed docs / full links untracked / created by the user via Google UI; dedicated
Chrome profile, untracked 0600 cookies, structural denylist, throwaway album for the
browser probe; fidelity via standing assets with hard reject on mismatch; re-auth
cadence accepted unknown; decision record at `16-DECISION-RECORD.md` with verdict table
and user's final call.

---

## Scripts de sonde — disposition

### Q1: Où vivent les scripts de sonde, et que survit en Phase 17 ?

| Option | Description | Selected |
|--------|-------------|----------|
| Commités dans le repo | `probes/` commité — réutilisable, auditable, Phase 17 repart du code validé. | ✓ |
| Éphémères hors git | Jetables après enregistrement des résultats; Phase 17 réécrit tout. | |
| Manuel sans script | curl + notes; insuffisant pour le RPC batchexecute. | |

**User's choice:** Commités dans le repo (Recommandé)

### Q2: Si le plafond ~500 se confirme, que devient le code de sonde du lien partagé ?

| Option | Description | Selected |
|--------|-------------|----------|
| Parser commité, plafond documenté | Parseur AF_initDataCallback + download =d réutilisables en Phase 17; verdict documente le plafond mesuré. | ✓ |
| Tout jetable | Sonde rejetée, code non réutilisé. | |

**User's choice:** Parser commité, plafond documenté (Recommandé)

---

## Conditions d'arrêt & verdicts

### Q1: Le bootstrap cookie navigateur échoue. Verdict de la sonde navigateur ?

| Option | Description | Selected |
|--------|-------------|----------|
| Rejeté sauf preuve contraire | Mécanisme non prouvé = rejeté avec raison « bootstrap non reproductible » — jamais par optimisme. | ✓ |
| Inconclus = re-jouable | Verdict « inconclusif », décision reportée pour retenter. | |

**User's choice:** Rejeté sauf preuve contraire (Recommandé)

### Q2: Le plafond du lien partagé ne peut pas être mesuré précisément. Verdict ?

| Option | Description | Selected |
|--------|-------------|----------|
| Plafond = risque documenté, choix quand même | Risque borné (borne inférieure = plus grand album mesuré); pas de blocage pour une mesure parfaite. | ✓ |
| Album synthétique 600+ obligatoire | Mesure précise prime sur la rapidité. | |

**User's choice:** Plafond = risque documenté, choix quand même (Recommandé)

### Q3: Et si les DEUX mécanismes échouent leurs sondes ?

| Option | Description | Selected |
|--------|-------------|----------|
| Pause jalon | Pas de choix du moins-mauvais; fidélité octets et énumération complète non négociables; réévaluation avant de continuer. | ✓ |
| Choisir le moins mauvais | Mécanisme le plus proche des critères, limitations acceptées documentées. | |

**User's choice:** Pause jalon (Recommandé)

---

## Consentement & exécution des sondes

### Q1: Consentement pour la récolte de cookies (portée v4.0, refondée depuis le 26-09) ?

| Option | Description | Selected |
|--------|-------------|----------|
| Confirmé | Le consentement du 26-09 s'applique tel quel: profil dédié, lecture seule, stockage sécurisé, album jetable. | ✓ |
| Révoqué pour v4.0 | Sonde navigateur marquée « non sondée »; décision sans cette preuve. | |

**User's choice:** Confirmé (Recommandé)
**Notes:** Consentement explicite de l'opérateur, sélectionné directement (pas relayé par
un agent) — re-affirmation de la portée du 26-09 pour le jalon v4.0. Portée: récolte en
lecture seule + sonde décrite; les actions live significatives gardent leurs propres
portes (précédent Phase 11).

### Q2: Qui exécute les sondes live ?

| Option | Description | Selected |
|--------|-------------|----------|
| Agent exécute, gates aux étapes sensibles | Gates avant: (1) récolte de cookies, (2) toute écriture cadre, (3) upload d'un actif de test. | ✓ |
| Tout manuel de votre côté | Vous lancez chaque script et collez les sorties. | |
| Agent sans gates | Exécution de bout en bout sans pauses (déconseillé — précédent Phase 11). | |

**User's choice:** Agent exécute, gates aux étapes sensibles (Recommandé)

### Q3: Quel navigateur/moteur d'automatisation pour la sonde navigateur ?

| Option | Description | Selected |
|--------|-------------|----------|
| Playwright + Chromium | API Python mature, navigateur géré, recommandation de BROWSER-AUTOMATION.md. | ✓ |
| chromedriver + Selenium | Classique, plus de friction d'installation. | |
| Autre / à décider au plan | Seule contrainte verrouillée: charger le profil Chrome dédié. | |

**User's choice:** Playwright + Chromium (Recommandé)

---

## Claude's Discretion

- Evidence file layout — precedent `11-LIVE-FINDINGS.md` (archivé: raw HTTP, mechanism
  table, re-read confirmation)
- Détails de comparaison LGS-06 — choix des actifs, taille d'échantillon, ordre
  mécanisme/fidélité
- Structure des scripts de sonde — layout `probes/`, forme CLI, généralisation du
  parseur shared-link
- Compilation de l'enregistrement de décision — l'agent compile avec recommandation;
  l'utilisateur fait l'appel final

## Deferred Ideas

None — discussion stayed within phase scope.
