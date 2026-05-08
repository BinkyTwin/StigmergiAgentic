# Sources externes à ajouter à la revue de littérature refondue

> **Auteur** : Abdelatif DJEDDOU
> **Date** : 2026-05-05
> **Contexte** : refonte de la revue de littérature selon
> `documentation/memoire/plan_refonte_revue_litterature.md`. Cette liste
> recense les sources qu'il **reste à introduire** dans le chapitre 2
> refondu. Aucune recherche autonome n'a été menée pour ces sources :
> elles sont proposées comme inventaire à valider et compléter par
> l'auteur, qui dispose des accès académiques et professionnels
> appropriés (notamment sur le terrain bancaire).
>
> **Périmètre des entrées biblio** : aucune nouvelle entrée n'a été
> ajoutée à `liminaires/bibliographie_manuelle.tex` lors de cette passe.
> Les sources listées ci-dessous, une fois sélectionnées, devront être
> ajoutées à la bibliographie au format APA texte cohérent avec
> l'existant, ou converties à BibTeX dans une passe ultérieure.

---

## Section 2.1 — Le défi managérial de la GenAI agentique en entreprise

### 2.1.1 Industrialisation de la GenAI : adoption récente

Sources actuellement citées dans la refonte : Peng et al. (2023), Barke
et al. (2023), OpenAI (2026), Anthropic (2025b).

Sources à ajouter (statistiques d'adoption GenAI 2024-2026) :

- **McKinsey & Company** — *State of AI* annuel (2024, 2025), notamment
  les chapitres consacrés aux services financiers et à la GenAI
  agentique. Référence usuelle pour les chiffres d'adoption en
  entreprise.
- **Boston Consulting Group (BCG)** — *AI Reality Check* / études
  sectorielles 2024-2026. À privilégier les éditions traitant de la
  banque.
- **Gartner** — *Hype Cycle for Generative AI* (2024, 2025), *Magic
  Quadrant for AI Code Assistants*. Donne une cartographie validée
  par les directions techniques.
- **Stanford AI Index Report** (édition 2025 ou 2026, selon
  disponibilité) — chiffres d'adoption, productivité et investissement
  validés académiquement.
- **OECD AI Observatory** — indicateurs d'adoption transverse en
  Europe.

Périmètre conseillé : choisir une source par catégorie (consulting,
analyste, académique) plutôt que de toutes les citer, pour conserver
un appareil critique compact.

### 2.1.2 Tensions architecturales héritées

Sources actuellement citées : Sneed (2010), IBM (2023).

Sources à ajouter :

- **Études sur la modernisation de monolithes legacy en banque** :
  rapports Deloitte, KPMG, Capgemini sur les programmes de
  modernisation des core banking systems, avec chiffres de coût et
  durée des projets.
- **Newman, S. — *Building Microservices***, 2nd ed., O'Reilly, 2021.
  Référence canonique pour les arbitrages monolithes vs
  microservices. À ne citer que si nécessaire à l'argument.
- **Bass, Weber, Zhu — *DevOps: A Software Architect's Perspective***,
  Addison-Wesley, 2015. Pour l'angle modernisation incrémentale.

### 2.1.3 Pourquoi le problème est managérial

Sources actuellement citées : Markus (1983), Kim & Kankanhalli
(2009), Lee & See (2004), Dietvorst et al. (2015, 2018), Turel & Kalhan
(2023), García-Ruiz & Rocchi (2025).

Sources MIS classiques à valider/ajouter :

- **Davis, F. D. (1989)** — Technology Acceptance Model (TAM),
  *MIS Quarterly*. Référence fondatrice mobilisable si l'on souhaite
  étoffer l'angle adoption.
- **Venkatesh et al. (2003)** — UTAUT (Unified Theory of Acceptance
  and Use of Technology), *MIS Quarterly*. Extension multi-facteurs
  de TAM.
- **Bhattacherjee, A. (2001)** — *post-adoption fatigue / IS
  continuance*, *MIS Quarterly*. Pour l'angle « après le pilote, que
  reste-t-il ? ».
- **Orlikowski, W. (2000)** — *Using Technology and Constituting
  Structures*, *Organization Science*. Pour l'angle structuration et
  technologie.

Le choix entre TAM, UTAUT et IS continuance dépend de l'angle
narratif retenu : profondeur d'adoption (TAM/UTAUT) ou pérennité de
l'usage (Bhattacherjee).

---

## Section 2.2 — Gouvernance, auditabilité et conformité

### 2.2.5 Régulation sectorielle banque

Section actuellement écrite avec mention générique de RGPD, DORA,
ACPR/EBA. **Sources à ajouter pour étayer concrètement chaque texte
réglementaire** :

- **RGPD** : Règlement (UE) 2016/679 du Parlement européen et du
  Conseil. À citer directement, articles pertinents pour la
  traçabilité des traitements automatisés (art. 22 décisions
  individuelles automatisées, art. 30 registre des traitements).
- **DORA** : Règlement (UE) 2022/2554 (Digital Operational Resilience
  Act). Texte officiel disponible sur EUR-Lex. À citer pour les
  obligations de gouvernance des risques informatiques.
- **EBA Guidelines on outsourcing arrangements** (EBA/GL/2019/02) :
  applicable à l'utilisation d'IA tierces dans les processus
  bancaires.
- **ACPR — Documents de réflexion sur l'intelligence artificielle**
  (notamment sur l'explicabilité des modèles en banque, 2020-2024) :
  à compléter avec les communications les plus récentes.
- **Comité de Bâle (BCBS)** — publications sur la gouvernance des
  modèles, applicables aux modèles de score et de risque.

**Article scientifique** :

- **Veale, M., & Borgesius, F. Z. (2021)** — *Demystifying the Draft
  EU Artificial Intelligence Act*, *Computer Law Review
  International*. Si encore d'actualité après l'entrée en vigueur
  effective.

### 2.2 — Cas industriels banque (illustrations)

Sources à fournir par l'auteur depuis son terrain professionnel ou
depuis la littérature spécialisée :

- Études de cas publiées sur l'adoption de copilotes ou d'agents IA
  dans des établissements bancaires (BNP Paribas, Société Générale,
  HSBC, JPMorgan, Goldman Sachs).
- *Case studies* publiés par Microsoft Azure, Google Cloud, AWS sur
  des déploiements GenAI en banque (à utiliser avec discernement, ce
  sont des sources commerciales).
- Articles de presse spécialisée (*L'Usine Digitale*, *Les Échos
  Tech*, *American Banker*, *Banking Technology*) pour des
  illustrations concrètes.

---

## Section 2.3 — Théorie de la coordination organisationnelle et MIS

Sources actuellement citées : Malone & Crowston (1994), Teece (2007),
Feldman & Pentland (2003), Strong et al. (2014), Cemri et al. (2025),
Gao et al. (2025), Kapoor et al. (2024), Cursor (2025).

Sources à valider en complément :

- **Crowston, K. (1997)** — *A Coordination Theory Approach to
  Organizational Process Design*, *Organization Science*. Extension
  appliquée par l'un des auteurs de la théorie originale.
- **Eisenhardt, K. M., & Martin, J. A. (2000)** — *Dynamic
  Capabilities: What Are They?*, *Strategic Management Journal*.
  Souvent cité conjointement à Teece pour cadrer le concept.

---

## Section 2.4 — Stigmergie

La couverture est déjà dense (Grassé, Bonabeau, Theraulaz, Heylighen,
Ricci, Marsh & Onof, Bolici, Parunak, Gelernter, Mamei & Zambonelli,
Serugendo, Weyns, Chari, Zhang, Rodriguez, Rahman). Aucune source
critique manquante identifiée pour cette passe.

Vérification ponctuelle conseillée :

- **Dorigo, Birattari, Stützle (2006)** — *Ant Colony Optimization*,
  *IEEE Computational Intelligence Magazine*. Si l'on souhaite étayer
  ACO comme exemple de stigmergie quantitative.
- **Theraulaz, Bonabeau, Deneubourg (1998)** — formalisation de la
  stigmergie qualitative dans la construction de nids de guêpes. Déjà
  référencé via Theraulaz & Bonabeau (1999).

---

## Section 2.5 — Transformation de code et workflows agentiques

Couverture actuelle : Ziftci (2025), Sneed (2010), IBM (2023), Diggs
(2025), Amazon (2024), Rozière (2020), CodeRosetta (2024), Lamothe
(2021), Dig & Johnson (2005), Vu (2026), Dumas (2026), Berti (2024),
Vidgof (2023).

Sources à valider en complément :

- **Études sectorielles bancaires sur la modernisation COBOL** :
  références internes à l'auteur si publiables, sinon Forrester,
  IDC.
- **Référence sur les outils académiques de migration** :
  *AutoCodeRover* (NeurIPS 2024 ou ICSE 2025), *DocAgent* —
  candidates pour la comparaison MigrationBench du chap. 6, à
  introduire dans 2.5 si elles servent l'argument.

---

## Section 2.6 — Évaluation et frontière coût-précision

Couverture : Zhu (2025) MultiAgentBench, Geng & Chang (2025)
REALM-Bench, Jimenez (2024) SWE-bench, Scale AI (2025) SWE-bench Pro,
Ghosh Paul (2024), RACE (2025), Xie (2024) TravelPlanner, Kapoor
(2024), Desai (2025).

Aucune source critique manquante identifiée. Vérifier seulement la
référence exacte de **MigrationBench** (à confirmer : Wang et al.
2025 ? Liu et al. 2024 ? La référence exacte n'a pas été insérée
dans la nouvelle version, seulement une mention générique à
préciser).

---

## Section 2.7 — Cadre conceptuel et gap

Couverture : reprend les sources des sections précédentes + Uhl-Bien
et al. (2007), Shrestha et al. (2019). Aucune nouvelle source
nécessaire.

---

## Récapitulatif synthétique

| Section | Priorité | Sources prioritaires à introduire |
|---|---|---|
| 2.1 | haute | McKinsey ou BCG (adoption GenAI) ; TAM ou UTAUT (adoption SI) |
| 2.2 | haute | Textes RGPD/DORA + EBA/GL/2019/02 + ACPR (citations directes) ; un cas industriel banque |
| 2.3 | basse | Eisenhardt & Martin (2000) si étoffement dynamic capabilities |
| 2.4 | non bloquante | aucune addition critique |
| 2.5 | moyenne | référence MigrationBench exacte ; AutoCodeRover si pertinent |
| 2.6 | basse | aucune addition critique |
| 2.7 | non bloquante | aucune addition critique |

**Effort estimé** : 2-3 jours de travail bibliographique pour
identifier les références exactes (2-3 sources prioritaires par
section) et les insérer dans la revue refondue + dans
`liminaires/bibliographie_manuelle.tex`.

---

## Note méthodologique

Lors de l'ajout de chaque source, vérifier la cohérence APA texte avec
le format de `liminaires/bibliographie_manuelle.tex` (auteurs,
année, titre en italique pour les ouvrages, *MIS Quarterly*, *vol.*,
*p.*). Aucune conversion BibTeX prévue dans cette passe : l'objectif
est la qualité argumentaire de la revue, pas l'automatisation de la
bibliographie.
