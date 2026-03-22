# TravelPlanner Official Evaluation (Vendored)

This directory vendors the official TravelPlanner evaluation/constraint code from:
- Repository: `OSU-NLP-Group/TravelPlanner`
- URL: https://github.com/OSU-NLP-Group/TravelPlanner

Vendored files are used to avoid re-implementing evaluation logic.

## Included upstream components
- `evaluation/eval.py`
- `evaluation/commonsense_constraint.py`
- `evaluation/hard_constraint.py`
- `tools/{flights,accommodations,restaurants,attractions,googleDistanceMatrix}/apis.py`
- `utils/func.py`

## Database path
The runtime creates/uses `third_party/travelplanner_official/database` as a symlink to the configured TravelPlanner database root (for example `data/travelplanner/database`).

## Note
Do not modify vendored upstream files unless strictly required for compatibility.
