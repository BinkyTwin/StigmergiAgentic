Proposition d'Amélioration Architecturale : Intégration des Modèles de Langage Récursifs (RLM) dans un Cadre Stigmergique

Auteur : Abdelatif DJEDDOU + GEMINI

Source à consulter: 
https://discuss.google.dev/t/recursive-language-models-in-adk/323523?utm_source=twitter&utm_medium=unpaidsoc&utm_campaign=fy26q1-googlecloudtech-web-ai-in_feed-no-brand-global&utm_content=-&utm_term=-&linkId=48424260

https://arxiv.org/pdf/2512.24601

Contexte : Thèse "Orchestration stigmergique de systèmes multi-agents LLM"

Date : Février 2026

1. Synthèse de la Problématique et du Gap

Les architectures multi-agents actuelles (CrewAI, MetaGPT) souffrent de deux limitations majeures pour la migration de code à grande échelle :

Fragmentation du Contexte : Les agents perdent la "vision globale" lorsqu'ils traitent de multiples fichiers interdépendants (Yan, 2025).

Surcharge Cognitive : Tenter de charger tout le contexte dans le prompt d'un seul agent mène à des hallucinations ou des dépassements de fenêtre.

Proposition : Hybrider la Coordination Stigmergique (gestion macro des interactions via l'environnement) avec les Modèles de Langage Récursifs (RLM) (gestion micro de la profondeur de raisonnement).

2. Architecture Conceptuelle : Le Modèle "Stigmergic RLM"

L'architecture repose sur la séparation claire entre la Coordination (Inter-Agents) et le Raisonnement (Intra-Agent).

A. Le Principe Fondamental

Macro-Niveau (Stigmergie) : Les agents ne communiquent pas directement. Ils interagissent via un Artéfact de Coordination (le "Shadow Blackboard").

Micro-Niveau (RLM) : Chaque agent est une unité récursive. Face à une tâche complexe, il ne la traite pas en une passe, mais instancie des sous-processus (récursion) pour résoudre des sous-problèmes, en utilisant l'artéfact comme mémoire cache.

3. L'Artéfact Central : Le "Shadow Blackboard"

Conformément au paradigme Agents & Artifacts (Ricci et al., 2007), nous introduisons un artéfact actif situé à côté du code source (ex: .shadow/blackboard.json). Il agit comme une "carte dynamique du territoire".

Structure de Données Proposée (JSON Schema)

{
  "territory_map": {
    "src/main.py": {
      "status": "PENDING_MIGRATION",
      "complexity": 0.8,
      "dependencies": ["src/utils.py", "src/config.py"]
    }
  },
  "pheromones": [
    {
      "id": "task_101",
      "type": "MIGRATE_SYNTAX",
      "target": "src/utils.py",
      "priority_score": 10.0,
      "deposited_by": "Agent_Scanner_Alpha",
      "timestamp": "2026-02-10T14:00:00Z"
    }
  ],
  "rlm_knowledge_cache": {
    "src/utils.py::hash123": {
      "summary": "Module utilitaire. Contient des fonctions 'time' dépréciées.",
      "migration_strategy": "Remplacer time.clock() par time.perf_counter()",
      "validity_period": "24h"
    }
  }
}


Rôle de l'Artéfact

Médiateur : Centralise les demandes (Phéromones).

Mémoire Partagée (Tuple Space) : Stocke les résultats des sous-agents RLM dans le knowledge_cache pour éviter les calculs redondants.

Guardrail Structurel : Peut être configuré pour rejeter des mises à jour invalides (ex: interdiction de passer en VALIDATED sans lien vers un log de test réussi).

4. L'Agent : Unité de Raisonnement Récursif (RLM)

Contrairement à un agent standard "plat", l'agent RLM suit un cycle d'exécution inspiré des travaux de Zhang et al. (2026).

Le Cycle d'Exécution RLM

Observation (Peek) : L'agent lit le Shadow Blackboard. Il identifie une phéromone (tâche) prioritaire.

Planification & Décomposition :

Si la tâche est simple -> Exécution directe.

Si la tâche est complexe (ex: migrer un fichier avec 10 dépendances) -> Appel Récursif.

Récursion (Spawn) :

L'agent crée un contexte enfant pour traiter une dépendance.

Exemple : "Va d'abord analyser src/utils.py et écris le résultat dans le knowledge_cache".

Synthèse & Action :

L'agent parent récupère les infos du cache.

Il génère le code final.

Il met à jour le Blackboard (dépose une phéromone TO_TEST).

5. Scénario de Migration : Exemple Concret

Cas d'usage : Migration Python 2 vers 3 de main.py qui dépend de utils.py.

Étape

Acteur

Action

Impact sur le Shadow Blackboard

1

Agent Scanner

Analyse le dépôt Git.

Crée l'entrée territory_map et dépose la phéromone MIGRATE sur main.py.

2

Agent RLM (Worker)

Prise de tâche main.py. Détecte la dépendance utils.py.

Lit l'état. Vérifie si utils.py est déjà connu dans le knowledge_cache.

3

Agent RLM (Enfant)

(Récursion) Analyse utils.py. Identifie les changements nécessaires.

Écrit le résumé technique dans rlm_knowledge_cache. Ne touche pas au code source.

4

Agent RLM (Worker)

(Retour Récursion) Utilise le cache pour migrer main.py en cohérence avec utils.py.

Modifie le fichier main.py (Git). Change le statut dans le Blackboard à TO_TEST.

5

Agent Testeur

Détecte la phéromone TO_TEST.

Lance les tests. Si OK, change statut à DONE. Si KO, remet MIGRATE avec un log d'erreur.

6. Justification Scientifique et Avantages

Cette architecture répond spécifiquement aux limitations identifiées dans la revue de littérature :

Réponse à la "Context Fragmentation" (Yan, 2025) :

L'agent ne charge pas tout le projet. Il charge uniquement ce qui est pertinent via des appels récursifs et stocke le contexte dans le Blackboard.

Alignement avec "Agentless" (Xia et al., 2024) :

On garde la simplicité de l'interface (fichiers plats, étapes claires) mais on ajoute la profondeur d'analyse via RLM.

Conformité Stigmergique (Heylighen, 2016) :

La coordination reste indirecte. Si l'Agent Worker plante au milieu, un autre peut reprendre en lisant le knowledge_cache du Blackboard.

Gouvernance & AI Act (Fink, 2025) :

Le Shadow Blackboard fournit une trace d'audit parfaite ("Tracing"). On sait quel agent a fait quoi, pourquoi, et sur la base de quelle information (cache).

7. Conclusion pour le POC

Pour le prototype expérimental, l'implémentation se limitera à :

Un script Python gérant le Shadow Blackboard (JSON).

Une classe RLMAgent capable d'exécuter des outils et de s'instancier elle-même (profondeur max = 3).

Un ensemble de Phéromones simples : TODO, IN_PROGRESS, REVIEW, DONE.