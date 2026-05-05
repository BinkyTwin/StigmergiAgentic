# Prompt détaillé — Génération de poster scientifique via ImageGen / DALL-E / ChatGPT

## Notice préliminaire

**Réalisme à connaître avant de coller le prompt :** les générateurs d'images type DALL-E / ImageGen produisent rarement un poster scientifique avec du texte parfaitement lisible et bien composé en une seule passe. Trois stratégies possibles :

1. **Recommandée** : utiliser le prompt ci-dessous pour générer **uniquement les éléments visuels** (illustration centrale, palette, ambiance, composition) puis assembler le texte dans Canva, Figma, ou PowerPoint A0.
2. **Tout-en-un** : coller le prompt long ci-dessous, en acceptant que le texte généré soit partiellement illisible ou approximatif (à corriger ensuite manuellement).
3. **Itératif** : générer d'abord la composition globale, puis demander à ChatGPT de produire chaque section comme image séparée, puis assembler.

Je fournis ci-dessous **trois variantes** : (A) prompt complet pour générer le poster d'un coup, (B) prompt visuel pur (sans texte) pour l'assemblage manuel, (C) prompt de composition pour ChatGPT (qui génère un canevas Figma ou un SVG textuel).

---

## Variante A — Prompt complet (poster autoportant)

> Crée un poster scientifique académique format **A0 vertical (841 × 1189 mm, ratio 1:1.414)**, style sobre et élégant adapté à un Research Day universitaire en sciences de gestion. Le poster doit présenter une recherche intitulée **« Apprendre par traces : la stigmergie agentique comme médium d'apprentissage organisationnel hybride »**.
>
> **Palette de couleurs** : fond blanc cassé ou ivoire très clair (#F8F6F0). Couleur principale bleu nuit profond (#1B2A4E). Accents cuivre / ambre (#C77B3F) pour les éléments saillants. Texte secondaire gris ardoise (#3A4452). Aucun dégradé criard, aucune couleur fluo. Esthétique inspirée du design éditorial des revues *Harvard Business Review* et *MIT Sloan Management Review*.
>
> **Typographie** : titres en serif moderne (type Playfair Display ou EB Garamond), corps de texte en sans-serif humaniste (type Inter ou Source Sans Pro). Hiérarchie typographique nette. Crénage et interlignage généreux. Pas de WordArt, pas d'effet 3D.
>
> **Composition générale** (de haut en bas) :
>
> 1. **Bandeau en-tête (10% de la hauteur)** : à gauche, logos EMLV et De Vinci Research Center alignés. À droite, mention « Research Day — Learning in the Age of AI — 11 juin 2026 ». Filet horizontal cuivre fin séparant l'en-tête.
>
> 2. **Titre principal (8% hauteur)** : « Apprendre par traces » en très grands caractères serif bleu nuit. Sous-titre : « La stigmergie agentique comme médium d'apprentissage organisationnel hybride ». Encore en dessous, en plus petit et italique : « Une lecture managériale de l'équilibre exploration / exploitation entre agents IA ». Auteur : « Abdelatif Djeddou — EMLV ».
>
> 3. **Section 1 — Question de recherche (12% hauteur, en bandeau)** : encadré sobre fond ivoire avec filet cuivre. Texte court en italique : « À quelles conditions la matérialisation de l'apprentissage collectif des agents IA dans des traces persistantes peut-elle constituer un médium organisationnel évaluable et gouvernable, plutôt qu'une boîte noire de coordination automatisée ? ».
>
> 4. **Section centrale visuelle (35% hauteur)** : illustration conceptuelle élégante d'un **réseau de traces stigmergiques** — un graphe organique où des nœuds (markers) sont reliés par des arcs d'intensité variable. Certains nœuds brillent (renforcés), d'autres s'estompent en fondu (decay). Quelques nœuds en cuivre représentent la promotion en compétences persistantes. Petites silhouettes humaines minimalistes en marge supervisent le réseau (gouvernance par traces). Style : illustration vectorielle minimaliste à la croisée de l'infographie *Information is Beautiful* et des schémas organisationnels du *Journal of Decision Systems*. Pas de fourmis dessinées explicitement (éviter le biomimétisme naïf).
>
> 5. **Section « Huit traductions »** (20% hauteur, en deux colonnes) : présenter un tableau ou huit petites cartes alignées, chacune contenant : (a) icône minimaliste, (b) mécanisme stigmergique, (c) flèche cuivre, (d) concept managérial. Les huit paires :
>    - Markers persistants → Mémoire transactive (Walsh & Ungson)
>    - Évaporation (decay) → Désapprentissage organisationnel (Akgün)
>    - Renforcement → Apprentissage simple boucle (Argyris & Schön)
>    - Lesson → Skill → Codification SECI (Nonaka & Takeuchi)
>    - Protocoles + garde-fous → Encapsulation de routines (Feldman & Pentland)
>    - Pressions ACO → Arbitrage exploration/exploitation (March ; Dorigo)
>    - Adaptation dynamique → Apprentissage double boucle (Argyris)
>    - Audit append-only → Gouvernance par traçabilité (EU AI Act)
>
> 6. **Section « Tensions et paradoxes »** (10% hauteur, en quatre cartouches verticaux) : (i) Support / dépendance ; (ii) Piège de compétence ; (iii) Paradoxe d'automation déplacé ; (iv) Liminalité de la trace. Pictogrammes minimalistes en cuivre.
>
> 7. **Pied de poster (5% hauteur)** : références clés (Yan et al. 2026 ; Raisch & Krakowski 2021 ; Kefi et al. 2025 ; March 1991 ; Nonaka & Takeuchi 1995). À droite, QR code factice (placeholder) renvoyant vers le résumé étendu. Mention : « Soumis au Research Day DVRC × CEROS, La Défense, juin 2026 ».
>
> **Style graphique global** : sobre, scientifique, lisible à 1m de distance pour les titres, à 30cm pour le corps. Aucune image générique de robot, aucun cliché « IA » (cerveau bleu, code matrix, etc.). Esthétique académique haut de gamme. Marges généreuses, blanc respiré, hiérarchie visuelle claire.
>
> **À éviter absolument** : fourmis dessinées littéralement, métaphores biomimétiques naïves, dégradés saturés, couleurs vives, polices fantaisistes, icônes 3D, images stock de personnes en costume devant un écran.

---

## Variante B — Prompt visuel pur (pour assemblage Canva/Figma)

> Crée une illustration vectorielle minimaliste et élégante, format A0 vertical, montrant un **réseau organique de traces lumineuses** sur fond ivoire (#F8F6F0). Les traces sont des nœuds circulaires reliés par des arcs d'intensité variable. Trois zones se distinguent dans le réseau :
>
> - **Zone gauche** : nœuds en bleu nuit (#1B2A4E) brillants, densément connectés (exploitation, routines validées).
> - **Zone droite** : nœuds plus pâles, dispersés, certains s'estompent en fondu (exploration, traces fraîches en cours d'évaluation).
> - **Zone basse centrale** : nœuds cuivre/ambre (#C77B3F) plus grands, surélevés, représentant des compétences cristallisées et persistantes.
>
> Au-dessus du réseau, deux silhouettes humaines minimalistes (style pictogramme contemporain) supervisent en regardant vers le bas, sans intervenir directement. De fines lignes pointillées cuivre les relient à des « curseurs » virtuels en marge du réseau (méta-paramètres : taux d'évaporation, seuil de promotion, budget exploratoire).
>
> Aucun texte. Composition aérée, marges généreuses, esthétique éditoriale type *MIT Sloan Management Review* ou *Long Range Planning*. Inspiré des illustrations de Giorgia Lupi (data humanism) et Federica Fragapane.

---

## Variante C — Prompt de composition pour ChatGPT (génération SVG / canevas)

À coller dans ChatGPT (GPT-4 / GPT-4o avec capacité de générer du SVG ou du HTML/CSS) :

> Génère-moi le **code SVG complet** d'un poster scientifique format A0 vertical (841 × 1189 mm) pour la recherche suivante :
>
> **Titre :** Apprendre par traces : la stigmergie agentique comme médium d'apprentissage organisationnel hybride
> **Auteur :** Abdelatif Djeddou (EMLV)
> **Conférence :** Research Day « Learning in the Age of AI », DVRC × CEROS, La Défense, 11 juin 2026.
>
> **Palette obligatoire :** fond #F8F6F0, primaire #1B2A4E, accent #C77B3F, texte secondaire #3A4452.
>
> **Sections requises (de haut en bas) :**
> 1. Bandeau en-tête avec emplacement réservé pour logos EMLV / DVRC (rectangles vides étiquetés).
> 2. Titre principal + sous-titre + auteur.
> 3. Encadré « Question de recherche » avec filet cuivre.
> 4. Schéma central : réseau de nœuds (markers) avec arcs d'intensité variable, trois clusters (exploitation, exploration, compétences cristallisées) et deux silhouettes superviseurs en marge.
> 5. Tableau à 8 lignes / 3 colonnes : « Mécanisme stigmergique » | « Concept managérial » | « Référence ». Remplir avec les 8 paires :
>    - Markers persistants | Mémoire transactive | Walsh & Ungson 1991
>    - Decay | Désapprentissage organisationnel | Akgün et al. 2003
>    - Renforcement | Apprentissage simple boucle | Argyris & Schön 1978
>    - Lesson → Skill | Codification SECI | Nonaka & Takeuchi 1995
>    - Protocoles + garde-fous | Encapsulation de routines | Feldman & Pentland 2003
>    - Pressions ACO | Arbitrage exploration/exploitation | March 1991 ; Dorigo 2004
>    - Adaptation dynamique | Apprentissage double boucle | Argyris 1977
>    - Audit append-only | Gouvernance par traçabilité | EU AI Act 2024
> 6. Quatre cartouches « Tensions et paradoxes » : Support/dépendance ; Piège de compétence ; Paradoxe d'automation déplacé ; Liminalité de la trace.
> 7. Pied de poster avec 5 références clés et placeholder QR code.
>
> **Typographie :** titres en serif (Playfair Display ou similaire serif via @import Google Fonts), corps en sans-serif (Inter ou similaire). Hiérarchie typographique nette. Marges 80px. Interlignage 1.4.
>
> **Sortie attendue :** un fichier SVG complet, valide, avec viewBox="0 0 841 1189", convertible en PDF haute résolution. Inclure tous les textes en `<text>` (pas en image). Les illustrations vectorielles (réseau, silhouettes) doivent être codées en `<path>` ou `<circle>`/`<line>`.

---

## Recommandation de workflow

1. **Lance d'abord la variante B** dans ChatGPT/ImageGen pour obtenir l'illustration centrale propre. Itère 2-3 fois jusqu'à un visuel satisfaisant.
2. **Lance la variante C** dans ChatGPT pour obtenir un squelette SVG du poster complet.
3. **Importe le SVG dans Figma ou Inkscape**, remplace l'illustration centrale par le rendu de l'étape 1, ajuste les textes si la génération SVG a tronqué.
4. **Exporte en PDF A0** pour impression.

Si tu veux quelque chose de plus rapide et fiable, je peux aussi te générer directement un **template Canva** (lien à créer manuellement) ou un fichier `.tex` Beamer poster. Dis-moi.
