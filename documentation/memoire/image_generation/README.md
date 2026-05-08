# Génération de figures du mémoire avec PaperBanana + FranceStudent

Ce dossier est un poste de travail local pour produire des figures académiques
du mémoire. Il est volontairement séparé du framework expérimental : il ne
sert ni aux benchmarks, ni à V10/V11, ni aux claims scientifiques.

## Principe

- PaperBanana fournit le pipeline agentique de figure :
  `Retriever -> Planner -> Stylist -> Visualizer -> Critic`.
- FranceStudent fournit l'API OpenAI-compatible :
  - texte via `POST /responses` avec `gpt-5.5`,
  - images via `POST /images/generations` avec `gpt-image-2`.
- La clé est lue depuis `.env` ou l'environnement, dans cet ordre pratique :
  `IMAGEN`, `FRANCESTUDENT_API_KEY`, `OPENAI_API_KEY`.
- Le proxy FranceStudent testé ici exige `size=1024x1024` pour
  `gpt-image-2`. Le patch local PaperBanana force donc cette taille même si le
  prompt demande un ratio large ; PaperBanana exporte ensuite une image
  redimensionnée utilisable en LaTeX.

Aucun secret ne doit être écrit dans ce dossier.

## Installation locale

Depuis la racine du repo :

```bash
python3 documentation/memoire/image_generation/setup_paperbanana_francestudent.py
```

Le script clone PaperBanana dans `documentation/memoire/image_generation/vendor/`
si nécessaire, applique le patch FranceStudent, puis écrit une config locale
sans secret.

Installe ensuite les dépendances PaperBanana dans son environnement local :

```bash
cd documentation/memoire/image_generation/vendor/PaperBanana
uv python install 3.12
uv venv --python 3.12
uv pip install -r requirements.txt
```

## Générer une figure

Exemple simple, sans téléchargement du dataset PaperBananaBench :

```bash
python3 documentation/memoire/image_generation/run_paperbanana_figure.py \
  --name boucle_stigmergique \
  --content-file documentation/memoire/image_generation/prompts/template_method.md \
  --caption "Schéma académique clair montrant une boucle de coordination indirecte : traces partagées, lecture par agents, décision influencée, validation, puis nouveau signal." \
  --retrieval-setting none \
  --max-critic-rounds 1
```

Exemple complet déjà validé localement :

```bash
python3 documentation/memoire/image_generation/run_paperbanana_figure.py \
  --name paperbanana_francestudent_pipeline_clean \
  --content-file documentation/memoire/image_generation/prompts/paperbanana_francestudent_pipeline.md \
  --caption "Diagramme du pipeline local PaperBanana-FranceStudent pour générer des figures du mémoire. Ne pas écrire cette phrase dans l'image." \
  --retrieval-setting none \
  --exp-mode demo_full \
  --max-critic-rounds 1 \
  --num-candidates 1 \
  --aspect-ratio 16:9
```

Sortie par défaut :

```text
documentation/memoire/latex/images/<name>.png
documentation/memoire/image_generation/records/<name>.json
```

Dans LaTeX :

```latex
\begin{figure}[H]
  \centering
  \includegraphics[width=0.92\linewidth]{boucle_stigmergique.png}
  \caption{Boucle de coordination indirecte par traces partagées.}
\end{figure}
```

## Modes utiles

- `--exp-mode demo_full` : Planner + Stylist + Visualizer + Critic.
- `--exp-mode demo_planner_critic` : plus léger, sans Stylist.
- `--retrieval-setting none` : pas de dataset externe, plus simple.
- `--retrieval-setting auto` : utilise PaperBananaBench si téléchargé, plus proche
  du PaperBanana complet.
- `--diagram-ref-limit 40` : limite locale pour garder le prompt de retrieval
  sous la limite FranceStudent observée. Le défaut PaperBanana de 200 références
  produisait environ 3 MB de payload et dépassait le plafond fournisseur.
- `--skip-cyber-references 1` : filtre les exemples PaperBananaBench contenant
  des termes cyber-sensibles sans rapport avec le mémoire, afin d'éviter les
  refus de sécurité sur le prompt de retrieval.
- `--max-critic-rounds 0` : désactive la critique image si le proxy refuse les
  entrées multimodales dans `/responses`.

Les figures générées doivent être relues et éventuellement redessinées : pour
un mémoire, les flèches, libellés et relations causales doivent rester exacts.
