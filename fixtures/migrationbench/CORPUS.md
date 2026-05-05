# MigrationBench Corpus Fixtures

Source dataset: `AmazonScience/migration-bench-java-selected`, split `test`, read on 2026-04-27.

These fixtures are not synthetic evidence. They are deterministic subsets of the official selected dataset and use the repository-level fields exposed by the Hugging Face dataset:

- `repo`
- `base_commit`
- `num_java_files`
- `num_loc`
- `num_pom_xml`
- `num_src_test_java_files`
- `num_test_cases`
- `license`

The project-local schema deliberately standardizes on `repo_url`, not `github_url`, to avoid runner/evaluator drift. The official evaluator wrapper maps `repo_url` back to the official CLI argument `--github_url`.

Subset policy:

- `smoke_5.jsonl` selects very small concrete official repositories for fast preflight and adapter debugging.
- `pilot_20.jsonl` and `main_30.jsonl` use deterministic round-robin stratification across repository size and build complexity buckets.
- `dependency_age` is set to `unknown` until an official or reproducible dependency-age analysis is implemented.

Important: these subsets still require the official preflight. If clone/checkout/evaluator setup mortality exceeds 10% on the selected subset, rebuild and re-register the subset before treating `main_30` as the study denominator.
