"""Download and verify TravelPlanner data assets for Sprint 6 adapter."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
from datasets import load_dataset


SPACE_BASE = "https://huggingface.co/spaces/osunlp/TravelPlannerEnvironment/resolve/main"

FILES = {
    "flights/clean_Flights_2022.csv": f"{SPACE_BASE}/database/flights/clean_Flights_2022.csv",
    "accommodations/clean_accommodations_2022.csv": f"{SPACE_BASE}/database/accommodations/clean_accommodations_2022.csv",
    "restaurants/clean_restaurant_2022.csv": f"{SPACE_BASE}/database/restaurants/clean_restaurant_2022.csv",
    "attractions/attractions.csv": f"{SPACE_BASE}/database/attractions/attractions.csv",
    "googleDistanceMatrix/distance.csv": f"{SPACE_BASE}/database/googleDistanceMatrix/distance.csv",
    "background/citySet_with_states.txt": f"{SPACE_BASE}/database/background/citySet_with_states.txt",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Setup TravelPlanner dataset/database files")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/travelplanner/database"),
        help="Directory that will contain TravelPlanner CSV files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-download files even if present",
    )
    return parser.parse_args()


def download_file(*, url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=60) as response:
        data = response.read()
    destination.write_bytes(data)


def verify_csv(path: Path) -> None:
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"CSV is empty: {path}")


def verify_dataset_split() -> None:
    dataset = load_dataset("osunlp/TravelPlanner", "validation")
    if "validation" not in dataset or len(dataset["validation"]) <= 0:
        raise ValueError("Validation split unavailable for osunlp/TravelPlanner")


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="travelplanner_setup_") as tmp_dir:
        tmp_root = Path(tmp_dir)

        for relative_path, url in FILES.items():
            final_path = output_dir / relative_path
            if final_path.exists() and not args.force:
                print(f"skip {relative_path} (already exists)")
                continue

            temp_path = tmp_root / relative_path
            print(f"download {relative_path}")
            download_file(url=url, destination=temp_path)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp_path), str(final_path))

    for relative_path in FILES:
        final_path = output_dir / relative_path
        if final_path.suffix.lower() == ".csv":
            verify_csv(final_path)

    verify_dataset_split()

    print("TravelPlanner setup complete")
    print(f"database_dir={output_dir}")
    print("dataset=osunlp/TravelPlanner (validation) OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
