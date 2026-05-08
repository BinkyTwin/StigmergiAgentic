# Comparaison — définitions opératoires agent / MAS / orchestration / médium

## Passage

Section `2.3.5 Définitions opératoires : agent LLM, système multi-agent,
orchestration`.

## Générations

| Chemin | Fichier | Durée |
| --- | --- | ---: |
| Direct `gpt-image-2` | `documentation/memoire/latex/images/definitions_operatoires_direct.png` | 102 s |
| PaperBanana `demo_full` | `documentation/memoire/latex/images/definitions_operatoires_paperbanana.png` | 305 s |
| PaperBanana `demo_full`, `retrieval_setting=auto` | `documentation/memoire/latex/images/definitions_operatoires_paperbanana_auto.png` | 247 s |
| PaperBanana `demo_full`, dataset extrait, `retrieval_setting=auto` | `documentation/memoire/latex/images/definitions_operatoires_paperbanana_auto_real.png` | 530 s |
| PaperBanana `demo_full`, `auto`, 40 refs, filtre cyber | `documentation/memoire/latex/images/definitions_operatoires_paperbanana_auto_ref40_filtered.png` | 255 s |

Note : le premier run `auto` a basculé en `none` car le dataset HuggingFace est
publié sous forme de `PaperBananaBench.zip` et non de fichiers `diagram/*`
directement accessibles. Après extraction du zip, le Retriever a bien tenté de
sélectionner des références, mais FranceStudent a renvoyé cinq `HTTP 502` sur
le gros prompt de retrieval. L'image finale a donc encore été produite sans
références effectives.

Run corrigé : `definitions_operatoires_paperbanana_auto_ref40_filtered` limite
le retrieval à 40 références, filtre 59 références PaperBananaBench contenant
des marqueurs cyber-sensibles (`attack`, `jailbreak`, `malware`, `red-team`,
etc.), et récupère bien 10 références : `ref_26`, `ref_23`, `ref_7`, `ref_5`,
`ref_3`, `ref_10`, `ref_50`, `ref_34`, `ref_2`, `ref_52`.

## Verdict

La génération directe est plus riche et plus détaillée : elle montre davantage
d'agents, d'objectifs, de sous-rôles et de liens. Elle est cependant plus
dense, donc moins immédiatement pédagogique.

La génération PaperBanana est plus sobre et plus lisible : elle distingue mieux
les quatre niveaux du passage pour une lecture de mémoire. Elle conserve
clairement l'axe `Agent LLM -> système multi-agents -> orchestration -> médium
partagé`, avec moins de bruit visuel.

Pour ce passage précis, la version PaperBanana est le meilleur candidat
éditorial, tandis que la version directe est le meilleur candidat pour une
annexe ou une figure plus détaillée.

Le run `auto_real` montre que l'activation du Retriever tel quel n'est pas
exploitable avec FranceStudent : le prompt de sélection des références dépasse
largement la limite fournisseur observée. Le run `auto_ref40_filtered` est le
premier run PaperBanana `auto` réellement valide dans ce contexte : prompt sous
la limite, références récupérées, et génération complète.

## Leçon méthodologique

Le direct `gpt-image-2` gagne souvent lorsque le prompt fixe déjà strictement
la structure et les labels. PaperBanana devient plus intéressant lorsque la
figure doit interpréter un passage conceptuel, simplifier le rendu, ou produire
une image plus pédagogique à partir d'un texte moins directement diagrammatique.
