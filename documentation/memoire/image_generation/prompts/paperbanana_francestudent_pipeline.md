# Figure à générer

Représenter un atelier local de production de figures académiques pour un
mémoire de master.

## Composants obligatoires

- À gauche : sources du mémoire, avec deux entrées nommées "texte de méthode"
  et "caption / intention visuelle".
- Au centre : pipeline agentique PaperBanana composé de Planner, Stylist,
  Visualizer et Critic. Montrer ces modules comme des blocs distincts, reliés
  par des flèches simples.
- Sous le Visualizer : appel API FranceStudent vers `gpt-image-2`, sans
  afficher de clé API.
- À droite : sortie locale vers `documentation/memoire/latex/images/figure.png`
  puis inclusion dans LaTeX.
- En bas : un petit bloc "records" indiquant que le prompt, la configuration et
  le résultat sont tracés pour reproductibilité.

## Style

Diagramme académique clair, fond blanc, palette sobre bleu/vert/gris avec un
accent orange très discret, flèches nettes, labels courts, pas de titre dans
l'image, pas de texte décoratif. L'image doit être lisible dans un mémoire A4.
