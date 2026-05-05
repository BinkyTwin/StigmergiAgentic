# Mémoire de Master EMLV — projet LaTeX

Sources LaTeX du mémoire **« Orchestration stigmergique de systèmes
multi-agents LLM »** (Abdelatif Djeddou, EMLV, 2026).

## Compilation

Toolchain : **XeLaTeX** + **biber** + **biblatex-apa**.

```bash
cd documentation/memoire/latex
xelatex -interaction=nonstopmode main.tex
biber main
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

ou avec `latexmk` :

```bash
latexmk -xelatex -interaction=nonstopmode main.tex
```

Le PDF produit est `main.pdf`.

## Structure

```
.
├── main.tex                    # fichier maître
├── preambule.tex               # packages, fontspec, geometry, biblatex
├── meta.tex                    # \title, \author, mots-clés PDF
├── bibliography.bib            # base APA (à enrichir)
├── liminaires/                 # page de titre, déclarations, résumés, glossaire
├── chapitres/                  # chap_01 à chap_09
├── annexes/                    # annexe_a à annexe_j
└── images/                     # logo EMLV, schémas, courbes
```

## Conformité format EMLV

| Exigence              | Implémentation                                  |
|-----------------------|-------------------------------------------------|
| Times New Roman 12 pt | `fontspec` + `\setmainfont{Times New Roman}`    |
| Marges 2,5 cm         | `geometry` left/right=2.5cm                     |
| Interligne 1,5        | `setspace` + `\onehalfspacing`                  |
| Texte justifié        | défaut LaTeX                                    |
| Numéros de page       | `\pagestyle{plain}`                             |
| Table des matières    | `\tableofcontents`                              |
| Bibliographie APA     | `biblatex` + `style=apa` + `biber`              |

## Pré-requis

- TeX Live ≥ 2022 (ou MacTeX) avec packages `fontspec`, `babel-french`,
  `biblatex-apa`, `biber`.
- Police **Times New Roman** installée (sinon fallback automatique sur
  TeX Gyre Termes).

## État de rédaction

Voir `../plan_memoire_detaille.md` pour le statut de chaque chapitre et
la stratégie de séquençage.
