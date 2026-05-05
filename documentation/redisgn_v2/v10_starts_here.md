# V10 starts here

**Date :** 2026-05-03  
**Statut :** borne de depart implementation V10  
**Plan source :** `documentation/redisgn_v2/plan_v10_framework_rebuild.md`

---

## Pourquoi cette borne existe

Les resultats V6/V7.1/V7.2 sur MigrationBench ont montre que le probleme
n'est plus seulement un bug local de boucle de reparation. Le framework peut
produire des patches qui s'appliquent sans produire des succes stricts, et il
peut consommer beaucoup d'appels LLM sans rendre l'echec plus explicable.

V10 marque donc un changement de regime :

- V6, V7.1 et V7.2 restent des artefacts historiques ;
- les resultats negatifs restent conserves ;
- les comparaisons futures doivent signaler que V10 change l'architecture ;
- le nouveau coeur doit etre plug-and-play, verifie, rejouable et
  benchmark-agnostic.

## Regle de lecture des anciens resultats

Les anciennes metriques restent utiles comme diagnostic, mais elles ne doivent
pas etre melangees avec les metriques V10 sans mention explicite.

| Ancienne lecture | Lecture V10 |
|---|---|
| `patch_applies` | Signal intermediaire seulement. |
| `artifact_delivery` | Contrat de sortie, pas succes benchmark. |
| `local_valid` | Validation adapter locale. |
| `official_valid` | Validation officielle si disponible. |
| `strict_success` | Succes complet du benchmark, impossible sans verifier. |

## Frontiere d'implementation

La V10 commence dans un nouveau namespace :

```text
core_v10/
tests/unit/v10/
```

Le runtime V3/V7 reste consultable, mais il n'est pas la contrainte
architecturale du nouveau coeur. Les composants existants peuvent etre
recuperes seulement s'ils respectent les nouveaux contrats.

## Premier jalon

Le premier jalon executable est volontairement petit :

```text
DomainAdapterV10
  -> observe
  -> apply
  -> validate
  -> diagnose
  -> finalize
  -> score
```

Un fake adapter doit pouvoir passer ce chemin sans importer Maven,
TravelPlanner, MigrationBench ni l'ancien orchestrateur.
