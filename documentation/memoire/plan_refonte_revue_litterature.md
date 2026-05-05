# Plan de refonte de la revue de littérature

> **Auteur** : Abdelatif DJEDDOU
> **Mémoire** : Master EMLV — *Orchestration stigmergique de systèmes multi-agents LLM*
> **Méthodologie** : Design Science Research (Hevner et al. 2004 ; Peffers et al. 2007)
> **Date du plan** : 2026-05-05
> **Volume cible revue de littérature** : **25 à 35 pages**
> **Fichier cible** : `documentation/memoire/latex/chapitres/chap_02_revue_litterature.tex`
> **État source** : revue actuelle ≈ 30-35 p., 1 678 lignes, héritée du DSR `consigne/revue_litterature_v2_DSR.tex`

---

## 1. Contexte et déclencheur du plan

Le 2026-05-05, retour oral de la superviseure (transcript :
`/Users/lotfi/Downloads/112_Rue_du_Ge_ne_ral_de_Gaulle_6.m4a.transcript.txt`).
Quatre instructions structurantes en sortent et orientent cette refonte :

1. **Densité** : la revue est jugée *« trop dense, encyclopédique »*. Une revue
   de littérature n'est pas un panorama exhaustif, c'est un argumentaire orienté.
   On condense le matériau existant et on resserre l'argumentaire — sans
   chercher à descendre sous 25 pages, qui est le plancher cible.
2. **Pas de cours sur la stigmergie** : les sections actuelles « Fondements
   théoriques de la stigmergie » et « Coordination multi-agents et systèmes
   computationnels » sont rédigées sur un ton pédagogique. Les reformuler en
   mode argumentaire : problème → solutions → gap.
3. **Pivot GenAI en entreprise** : ajouter explicitement une couche sur les
   *usages, l'adoption et la gouvernance de la GenAI agentique en entreprise*.
   Le sujet est managérial avant d'être technique ; le fil rouge de la revue
   doit le refléter.
4. **Suppression des entretiens** : la méthodologie DSR n'exige pas
   d'entretiens. Toutes les mentions d'entretiens, de panel qualitatif au sens
   FEDS-collecte, de grille d'évaluation associée, sont à retirer de la revue
   et du chapitre 3 (méthodologie).

**Hors scope explicite** : le rééquilibrage global management/technique du
mémoire (la superviseure a noté un ratio actuel 25/75 jugé risqué) sera traité
dans une passe ultérieure. Ne pas le mentionner comme objectif de cette
refonte. La pivot GenAI suffira à amorcer naturellement le rééquilibrage.

---

## 2. Stratégie générale

**Option retenue** : pivot partiel (Option 2). On garde l'investissement DSR
existant comme matériau, mais on ré-articule la revue autour d'un nouveau fil
rouge :

> *Comment l'entreprise adopte et gouverne des écologies d'agents LLM à grande
> échelle, et pourquoi les architectures hiérarchiques actuelles n'y suffisent
> pas — ce qui motive l'exploration d'un mécanisme de coordination indirecte
> (la stigmergie) comme réponse organisationnelle.*

La stigmergie n'est plus l'objet d'étude principal de la revue. Elle devient
**la réponse technique à un problème managérial préalablement posé**. Cette
inversion narrative est la transformation centrale de la refonte.

---

## 3. Structure cible (7 sections)

| # | Section | Pages cibles | Statut |
|---|---|---|---|
| 2.1 | Le défi managérial de la GenAI agentique en entreprise | 4-5 | **NOUVELLE** |
| 2.2 | Gouvernance, auditabilité et conformité dans les écologies agentiques | 5-6 | RENFORCÉE |
| 2.3 | Théorie de la coordination organisationnelle et apport au management des SI | 4-5 | RECYCLÉE + condensée |
| 2.4 | La stigmergie comme mécanisme de coordination indirecte | 5-6 | FUSION + condensation forte (cours retiré) |
| 2.5 | Transformation de code et workflows agentiques en pratique | 3-4 | CONDENSÉE |
| 2.6 | Évaluation des systèmes agentiques et frontière coût-précision | 2-3 | CONDENSÉE |
| 2.7 | Cadre conceptuel et identification du gap | 2-3 | RÉÉCRITE |
| **Total** | | **25-32** | |

---

## 4. Détail par section, ce qui se garde, ce qui se coupe, ce qui s'ajoute

### 2.1 Le défi managérial de la GenAI agentique en entreprise *(NOUVELLE)*

**Objectif** : poser le problème **côté entreprise** avant tout détour technique.

**À rédiger** :
- 2.1.1 Industrialisation de la GenAI dans l'entreprise — chiffres d'adoption
  récents, état du marché (banque, secteurs régulés en priorité, cohérent avec
  le terrain professionnel de l'auteur).
- 2.1.2 Tension architecturale héritée — monolithes vs microservices vs
  modernisation incrémentale (mention explicite par la superviseure).
- 2.1.3 Promesse et limites des architectures multi-agents centralisées —
  recyclage condensé de l'actuelle 2.3 (MAST, Agentless, Gao 2025), mais sous
  l'angle *« pourquoi cette approche déçoit en production »*, pas
  *« panorama des frameworks »*.
- 2.1.4 Pourquoi le problème est d'abord managérial — les modes d'échec
  documentés sont des problèmes de **coordination, gouvernance et coût
  d'orchestration**, pas seulement des problèmes de modèles.

**Sources existantes à recycler** :
- Sections actuelles 2.3 (Limites des approches MAS centralisées) et 2.4.1
  (Migration à grande échelle, validation industrielle).
- Chiffres Ziftci 2025, Amazon 2024, IBM, Cemri 2025, Gao 2025, Xia 2024
  déjà cités.

**Sources à ajouter (à fournir à l'auteur, ne pas chercher seul)** :
- Études adoption GenAI en entreprise 2024-2026 (McKinsey, BCG, Gartner,
  Stanford AI Index).
- Travaux MIS sur l'adoption des SI complexes (Davis TAM, UTAUT, post-adoption
  fatigue).
- Cas industriels banque/assurance documentés sur l'IA générative.

---

### 2.2 Gouvernance, auditabilité et conformité dans les écologies agentiques *(RENFORCÉE)*

**Objectif** : ancrer le mémoire dans la dimension **management des systèmes
d'information**, en insistant sur ce qui est validé par la superviseure
(*« la partie gouvernance, c'est bien »*).

**À garder du chap. 2 actuel (sect. 2.5)** :
- Guardrails pour écologies agentiques.
- Perspective principal-agent.
- EU AI Act Article 14, traçabilité, contrôle humain effectif.
- Meaningful Human Control.
- Responsabilité morale distribuée.
- Sécurité des systèmes agentiques.

**À condenser fortement** :
- Sous-section actuelle « Dimensions organisationnelles : résistance et
  adoption » (l. 1251-1386 du DSR) — beaucoup trop longue, à ramener à
  l'essentiel et à intégrer dans la nouvelle 2.1 plutôt qu'ici.

**À ajouter** :
- Lien explicite avec le secteur bancaire et les contraintes de régulation
  qu'y ajoute le terrain (RGPD, DORA, supervision ACPR/EBA pour la banque, et
  EU AI Act pour les agents).
- Articulation entre gouvernance externe (régulateur) et gouvernance interne
  (DSI, comité IA, audit), inspirée du retour oral de la superviseure.

---

### 2.3 Théorie de la coordination organisationnelle et apport au management des SI *(RECYCLÉE + condensée)*

**Objectif** : asseoir le cadre **théorique managérial** qui justifie la
stigmergie comme mécanisme de coordination organisationnelle, pas seulement
biologique.

**À garder du chap. 2 actuel (sect. 2.1 Ancrage managérial)** :
- Théorie de la coordination de Malone et Crowston (1994) — pivot central.
- Capacités dynamiques (Teece 2007).
- Routines organisationnelles et évolution du code (Feldman & Pentland 2003).
- Affordances technologiques (Strong et al. 2014).

**Inflexion** : ces 4 sous-sections existent déjà dans l'actuelle 2.1, mais
elles sont placées en fin de section sur la stigmergie. **Les remonter en
section 2.3 dédiée**, comme cadre théorique managérial à part entière, et non
plus comme appendice à la stigmergie.

**À condenser** :
- Chaque sous-section actuelle fait 30-40 lignes, on vise 15-25 lignes.

---

### 2.4 La stigmergie comme mécanisme de coordination indirecte *(FUSION + condensation forte)*

**Objectif** : présenter la stigmergie en **3-4 pages condensées**, sans
ton de cours, comme mécanisme de coordination organisationnelle pertinent
pour le problème posé en 2.1-2.3.

**Fusion des sections actuelles** :
- 2.1 (Fondements théoriques de la stigmergie) — sauf le bloc managérial déjà
  remonté en 2.3.
- 2.2 (Coordination multi-agents et systèmes computationnels).

**À garder** :
- Origine Grassé 1959 — paragraphe court, pas plus.
- Formalisation Bonabeau, Dorigo, Theraulaz 1999 — paragraphe court.
- Extension numérique Heylighen 2016 — paragraphe court.
- Stigmergie cognitive Ricci 2007 — paragraphe court, important pour le pivot
  vers les agents LLM.
- **Stigmergie empirique en open source et Git (Bolici 2016)** — à mettre en
  avant car c'est le pivot terrain vers le mémoire.
- Phéromones numériques, espaces de tuples, auto-organisation —
  fortement condensés en un seul paragraphe synthétique.
- Panorama frameworks (MetaGPT, CrewAI, AutoGen, LangGraph) — réduit à un
  tableau ou une liste, pas une section.

**À couper** :
- L'épistémologie stigmergique et cognition distribuée, sauf si nécessaire
  pour articuler avec la stigmergie cognitive de Ricci.
- Tout passage à ton pédagogique du type *« la stigmergie, c'est… »* :
  reformuler en *« l'apport de X est de montrer que… »*.
- La figure `images/stigmergic_feedback_loop.png` peut être conservée si elle
  sert directement l'argument, sinon retirée. Ne pas réintroduire la figure
  termite.

---

### 2.5 Transformation de code et workflows agentiques en pratique *(CONDENSÉE)*

**Objectif** : justifier le **cas d'application principal** du mémoire (la
transformation de code, MigrationBench).

**Fusion des sections actuelles** :
- 2.4 (Migration de code et transformation avec LLM).
- 2.6 (Agentic BPM et workflows).

**À garder** :
- Validation industrielle Google (Ziftci 2025), Amazon Q, IBM COBOL.
- Coordination multi-agents pour le codage autonome.
- Définition Agentic BPM, du RPA à l'automatisation cognitive.
- CAS appliqués aux processus, Process Mining et LLM (un seul paragraphe).

**À condenser** :
- Traduction cross-language et modernisation, refactoring incrémental :
  un seul paragraphe synthétique.
- Transformation du rôle développeur : à raccourcir ou déplacer en discussion
  (chap. 8).

---

### 2.6 Évaluation des systèmes agentiques et frontière coût-précision *(CONDENSÉE)*

**Objectif** : préparer le protocole d'évaluation du chap. 5 sans en faire
un panorama.

**À garder, en très court** :
- MultiAgentBench, REALM-Bench, TravelPlanner — un paragraphe par benchmark.
- Métriques de génération de code — un paragraphe.
- Coût-efficacité, frontières de Pareto Kapoor 2024 — un paragraphe.

**À couper** :
- Détails de scoring qui appartiennent au chap. 5.

---

### 2.7 Cadre conceptuel et identification du gap *(RÉÉCRITE)*

**Objectif** : poser un **gap explicitement managérial**, pas seulement
technique.

**Reformulation centrale** :
- Le gap actuel est rédigé comme *« aucun cadre n'opérationnalise la
  stigmergie pour les agents LLM »* — c'est un gap technique.
- Le gap reformulé doit être : *« la coordination stigmergique, identifiée
  par la théorie de la coordination organisationnelle (Malone & Crowston
  1994) comme mécanisme à part entière, n'est pas opérationnalisée pour la
  gouvernance d'écologies agentiques en entreprise, alors même que les
  exigences d'adoption, d'auditabilité et de conformité (EU AI Act Art. 14,
  régulation sectorielle) la rendent nécessaire ».*

**À garder** :
- Synthèse croisée (sect. 2.8.1 actuelle).
- Relations conceptuelles entre blocs.
- Complexity Leadership Theory (à reconnecter au pivot managérial).
- Cadre conceptuel proposé (figure récapitulative s'il y en a une).

**À retirer** :
- Toute formulation positionnant le gap comme purement technique.

---

## 5. Suppression des entretiens

À traiter dans deux fichiers, en plus de la revue elle-même.

### 5.1 Dans `chap_02_revue_litterature.tex`
- Toute mention de panel qualitatif comme **méthode de collecte**.
- Toute mention de grille Likert ou questionnaire comme **données primaires**.

### 5.2 Dans `chap_03_methodologie.tex`
- Section actuelle « Évaluation par experts » (équivalent du chap. 7 du plan
  global) à reformuler comme **test d'utilité de l'artefact** au sens FEDS,
  pas comme étude qualitative.
- Activité 5 du DSRM (Évaluation) : retirer toute mention d'entretiens
  semi-directifs.
- Si une grille d'entretien est mentionnée, la retirer ou la déplacer en
  annexe à titre purement illustratif (matériau exploratoire personnel, hors
  méthodologie formelle).

### 5.3 Dans le plan global `plan_memoire_detaille.md`
- Chapitre 7 « Évaluation par experts et validation OC5 » : reformuler en
  test d'utilité, sans entretiens.

---

## 6. Méthode de travail (séquencée)

### Étape 1 — Préparation
1. Lire intégralement le transcript supervision.
2. Lire la revue actuelle, le plan détaillé, les fichiers managériaux
   (`documentation/implications_manageriales_et_pratiques.md`,
   `documentation/managerial_playbook.md`,
   `documentation/memoire/framework_pedagogique.md`).
3. Marquer dans la revue actuelle, par numéros de lignes, ce qui se garde,
   se déplace, se condense, se coupe.

### Étape 2 — Validation du plan détaillé
1. Lister à l'auteur, avant rédaction :
   - Les passages à supprimer (avec lignes).
   - Les passages à déplacer (avec source et destination).
   - Les nouveaux contenus à introduire (sections 2.1 et 2.7
     principalement).
   - Les sources externes à ajouter — **lister, ne pas chercher seul**.
2. Attendre validation explicite avant de toucher au fichier `.tex`.

### Étape 3 — Rédaction section par section
1. Réécrire dans l'ordre 2.7 → 2.1 → 2.4 → 2.3 → 2.2 → 2.5 → 2.6.
   Justification : commencer par le gap (2.7) clarifie le fil rouge ; finir
   par les sections d'évaluation (2.6) qui dépendent le moins du nouveau
   fil rouge.
2. Après chaque section, lancer
   `cd documentation/memoire/latex && latexmk -xelatex -interaction=nonstopmode main.tex`
   pour vérifier que la compilation reste propre.
3. Compter les pages section par section pour rester dans la fourchette
   25-35.

### Étape 4 — Suppression des entretiens
1. Passer dans `chap_03_methodologie.tex` une fois la revue stabilisée.
2. Mettre à jour `plan_memoire_detaille.md` (chapitre 7).

### Étape 5 — Mise à jour du plan global
1. Section « Chapitre 2 » dans `plan_memoire_detaille.md` à réécrire pour
   refléter la nouvelle structure 2.1-2.7.
2. Ajouter en fin de plan global un changelog daté 2026-05-05 listant la
   refonte (sections supprimées, fusionnées, créées).

### Étape 6 — Vérification finale
1. Recompiler complètement (`latexmk -C && latexmk -xelatex main.tex`).
2. Vérifier le nombre de pages PDF de la revue (compteur via texcount
   `texcount -inc -sum chapitres/chap_02_revue_litterature.tex`).
3. Pas de warning d'erreur LaTeX bloquant.

---

## 7. Contraintes de forme

- Français, orthographe complète avec diacritiques.
- Style académique sobre, pas de tournure pédagogique *« voici ce qu'est X »*.
- Citations APA inline `(Auteur, année)` conservées telles quelles, **pas de
  conversion BibTeX** dans cette passe.
- LaTeX classe `book` : conserver `\chapter{Revue de la littérature}` et
  `\label{chap:revue}` en tête, garder les niveaux `\section` /
  `\subsection` / `\subsubsection` cohérents.
- Pas de modification du fichier source `consigne/revue_litterature_v2_DSR.tex`
  (archive).
- Pas de réécriture de `liminaires/bibliographie_manuelle.tex` dans cette
  passe ; consigner les nouvelles entrées à ajouter dans une liste à part
  remise à l'auteur.

---

## 8. Livrables attendus

1. `chap_02_revue_litterature.tex` refondu, structure 7 sections, 25-35 p.
2. `chap_03_methodologie.tex` mis à jour pour retirer les entretiens du
   protocole d'évaluation.
3. `plan_memoire_detaille.md` mis à jour (chap. 2 et chap. 7) + changelog.
4. Liste des sources externes à ajouter, organisée par section, remise à
   l'auteur.
5. PDF compilé propre, vérifié pour le nombre de pages cible.

---

## 9. Périmètre exclu (ne pas faire)

- Pas de modification du chapitre 1 (Introduction).
- Pas de rééquilibrage management/technique global au-delà de ce que la pivot
  GenAI implique naturellement.
- Pas d'ajout d'entretiens, panel qualitatif, grille Likert dans la revue ou
  la méthodologie.
- Pas de conversion BibTeX.
- Pas de modification de `consigne/revue_litterature_v2_DSR.tex`.
- Pas d'ajout de nouvelles entrées biblio par recherche autonome — uniquement
  signaler ce qu'il faudrait ajouter.

---

## 10. Risques et garde-fous

| Risque | Garde-fou |
|---|---|
| Réécriture qui casse la cohérence avec le chap. 1 et les chap. 4-9 | Lire l'intro et le plan détaillé avant de réécrire le gap (2.7). |
| Section 2.1 trop spéculative faute de sources | Lister les sources à ajouter, ne pas inventer de chiffres. |
| Pivot GenAI qui dilue la stigmergie | Garder la stigmergie comme **réponse au problème**, pas comme objet d'étude éliminé. Section 2.4 reste centrale. |
| Perte de la rigueur DSR existante en condensant | Conserver Hevner 2004, Peffers 2007, Gregor & Hevner 2013, Venable 2016 dans 2.6 ou 2.7. |
| Compilation cassée par les éditions massives | Compiler après chaque section réécrite, pas en bout de chaîne. |
