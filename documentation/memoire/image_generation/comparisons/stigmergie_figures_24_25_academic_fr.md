# Comparaison — figures 2.4 et 2.5 en français académique

## Objectif

Refaire les figures de la section 2.4 en évitant les libellés bilingues et en
visant un rendu plus académique, sérieux et exploitable dans le mémoire.

## Figures générées

| Figure | Workflow | Fichier | Durée | Prompts/appels utiles |
| --- | --- | --- | ---: | ---: |
| 2.4 Boucle stigmergique | Direct `gpt-image-2` | `documentation/memoire/latex/images/stigmergic_feedback_loop_direct_fr_academic.png` | 83.5 s | 1 image |
| 2.4 Boucle stigmergique | PaperBanana réel `demo_full`, `auto`, ref40 filtré | `documentation/memoire/latex/images/stigmergic_feedback_loop_paperbanana_auto_ref40_filtered_fr_academic.png` | 300.9 s | 4 texte + 1 image |
| 2.5 Principes auto-organisés | Direct `gpt-image-2` | `documentation/memoire/latex/images/self_organizing_principles_direct_fr_academic.png` | 93.8 s | 1 image |
| 2.5 Principes auto-organisés | PaperBanana réel `demo_full`, `auto`, ref40 filtré | `documentation/memoire/latex/images/self_organizing_principles_paperbanana_auto_ref40_filtered_fr_academic.png` | 243.7 s | 4 texte + 1 image |

Note : un essai technique direct en `1536x1024` pour la figure 2.4 a reçu un
`HTTP 400`. Les générations utiles ont ensuite utilisé le format stable
`1024x1024`.

## Détail coût / prompts

| Figure | Direct prompt | Direct approx. tokens | PaperBanana retriever approx. tokens | PaperBanana refs |
| --- | ---: | ---: | ---: | --- |
| 2.4 | 2 645 caractères | ~661 | ~149 717 | 10 refs récupérées, 59 refs cyber filtrées |
| 2.5 | 2 758 caractères | ~690 | ~149 754 | 10 refs récupérées, 59 refs cyber filtrées |

Le comptage PaperBanana utile correspond à :

1. Retriever text call (`/responses`)
2. Planner text call (`/responses`)
3. Stylist text call (`/responses`)
4. Visualizer image call (`/images/generations`)
5. Critic text+image call (`/responses`)

Les deux runs PaperBanana se sont arrêtés après le premier critic round avec
`No changes needed`, donc il n'y a pas eu de deuxième génération image.

## Verdict visuel

### Figure 2.4

Le direct `gpt-image-2` produit une boucle circulaire plus lisible, plus proche
d'un schéma d'article, avec des libellés français propres et une bonne
explication visuelle de dépôt, renforcement et évaporation. PaperBanana est plus
explicite sur l'absence de message direct, mais le rendu est plus bloc/pédagogie
que figure académique.

Choix recommandé : direct `gpt-image-2`.

### Figure 2.5

Le direct `gpt-image-2` donne une grille 2x2 très claire et homogène, avec des
labels français courts et une bonne comparaison entre communication directe et
traces partagées. PaperBanana est propre mais plus illustratif et moins sobre.

Choix recommandé : direct `gpt-image-2`.

## Leçon pour le site de l'association

Pour des visuels de site ou des schémas éditoriaux courts, le direct
`gpt-image-2` paraît plus rentable : un seul prompt, moins de temps, et un rendu
déjà propre lorsque la structure est bien spécifiée. PaperBanana devient
intéressant si le texte source est flou, si l'on veut une chaîne agentique avec
retrieval/critique, ou si l'on produit des figures académiques en série avec un
besoin de traçabilité.
