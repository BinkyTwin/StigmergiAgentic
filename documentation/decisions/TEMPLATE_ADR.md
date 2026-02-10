# [Numéro] Titre de la Décision

**Date** : YYYY-MM-DD

**Statut** : [Proposé | Accepté | Rejeté | Déprécié | Supersédé par ADR-XXX]

**Contexte** : Décideurs principaux (ex: Lotfi + Claude Code)

---

## Contexte

Décrire la situation qui nécessite une décision architecturale. Inclure :
- Le problème à résoudre
- Les contraintes techniques
- Les contraintes du mémoire (ex: démonstrabilité, traçabilité)
- Les références bibliographiques pertinentes

## Alternatives Considérées

### Alternative 1 : [Nom]

**Description** :  
Explication détaillée de cette approche.

**Avantages** :
- ✅ Avantage 1
- ✅ Avantage 2

**Inconvénients** :
- ❌ Inconvénient 1
- ❌ Inconvénient 2

---

### Alternative 2 : [Nom]

**Description** :  
Explication détaillée de cette approche.

**Avantages** :
- ✅ Avantage 1
- ✅ Avantage 2

**Inconvénients** :
- ❌ Inconvénient 1
- ❌ Inconvénient 2

---

### Alternative 3 : [Nom]

*(Ajouter autant d'alternatives que nécessaire)*

---

## Décision

**Choix retenu** : [Alternative X]

**Justification** :  
Expliquer pourquoi cette alternative a été choisie. Inclure :
- Alignement avec les objectifs du POC
- Compatibilité avec l'état de l'art (Grassé, Ricci et al., etc.)
- Compromis coût/bénéfice
- Facilité d'implémentation vs robustesse

**Citation académique (si applicable)** :
> "Quote pertinent d'un article de recherche"  
> — Auteur, Année

---

## Conséquences

### Positives
- ✅ Conséquence positive 1
- ✅ Conséquence positive 2

### Négatives
- ⚠️ Conséquence négative 1 (à surveiller)
- ⚠️ Conséquence négative 2 (mitigation possible : ...)

### Impacts sur le Code
- Fichiers modifiés : `chemin/fichier1.py`, `chemin/fichier2.py`
- Nouveaux modules : `nouveau_module.py`
- Dépendances ajoutées : `package==version`

### Impacts sur la Méthodologie
- Influence sur les tests : ...
- Influence sur les métriques : ...
- Influence sur la thèse : ...

---

## Validation

**Critères de succès** :
1. [ ] Critère 1 (ex: tests passent avec cette implémentation)
2. [ ] Critère 2 (ex: gain de X% sur la métrique Y)
3. [ ] Critère 3 (ex: code conforme à PEP 8)

**Tests à effectuer** :
```bash
pytest tests/test_feature.py -v
python metrics/pareto.py --compare-baseline
```

**Résultat après implémentation** :  
*(À remplir après avoir codé et testé)*

- [ ] Tous les critères validés
- [ ] Décision confirmée / Décision à revoir

---

## Références

- [Lien vers issue GitHub si applicable]
- [Référence académique 1]
- [Référence académique 2]
- [Autre ADR lié : ADR-XXX]

---

## Métadonnées

- **ADR créé par** : [Nom]
- **ADR validé par** : [Nom / "Auto-validé par IA"]
- **Version** : 1.0
- **Dernière modification** : YYYY-MM-DD
