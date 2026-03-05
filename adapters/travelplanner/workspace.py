"""Workspace wrapper for TravelPlanner dataset and CSV databases."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pandas as pd

from adapters.base import Workspace


QUERY_DATASET_ID = "osunlp/TravelPlanner"


class TravelPlannerWorkspace(Workspace):
    """TravelPlanner workspace backed by local CSV databases and HF queries."""

    _query_cache: dict[str, list[dict[str, Any]]] = {}

    def __init__(
        self,
        *,
        database_root: str | Path,
        dataset_split: str = "validation",
        query_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.database_root = Path(database_root).expanduser().resolve()
        if not self.database_root.exists():
            raise FileNotFoundError(
                f"TravelPlanner database directory not found: {self.database_root}. "
                "Run `uv run python scripts/setup_travelplanner.py`."
            )

        self.dataset_split = str(dataset_split).strip() or "validation"
        self._query_rows_override = query_rows
        self.current_query: dict[str, Any] | None = None

        self.flights = self._load_csv(
            "flights",
            candidates=[
                "flights/clean_Flights_2022.csv",
                "clean_Flights_2022.csv",
            ],
        )
        self.hotels = self._load_csv(
            "hotels",
            candidates=[
                "accommodations/clean_accommodations_2022.csv",
                "hotels/clean_Accommodations.csv",
                "clean_Accommodations.csv",
            ],
        )
        self.restaurants = self._load_csv(
            "restaurants",
            candidates=[
                "restaurants/clean_restaurant_2022.csv",
                "restaurants/clean_Restaurants.csv",
                "clean_Restaurants.csv",
            ],
        )
        self.attractions = self._load_csv(
            "attractions",
            candidates=[
                "attractions/attractions.csv",
                "attractions/clean_Attractions.csv",
                "clean_Attractions.csv",
            ],
        )
        self.distances = self._load_csv(
            "distances",
            candidates=[
                "googleDistanceMatrix/distance.csv",
                "distances/google_distances.csv",
                "distances/distance.csv",
                "distance.csv",
            ],
        )

        self._normalize_columns()

    def list_targets(self) -> list[str]:
        return ["flights", "hotels", "restaurants", "attractions", "distances"]

    def search_flights(self, origin: str, dest: str, date: str) -> pd.DataFrame:
        origin_name = self._normalize_city(origin)
        dest_name = self._normalize_city(dest)
        date_value = str(date).strip()

        frame = self.flights
        mask = (
            self._series_equals(frame["OriginCityName"], origin_name)
            & self._series_equals(frame["DestCityName"], dest_name)
            & frame["FlightDate"].astype(str).str.strip().eq(date_value)
        )
        return frame.loc[mask].reset_index(drop=True)

    def search_hotels(self, city: str) -> pd.DataFrame:
        city_name = self._normalize_city(city)
        frame = self.hotels
        mask = self._series_equals(frame["city"], city_name)
        return frame.loc[mask].reset_index(drop=True)

    def search_restaurants(self, city: str) -> pd.DataFrame:
        city_name = self._normalize_city(city)
        frame = self.restaurants
        mask = self._series_equals(frame["City"], city_name)
        return frame.loc[mask].reset_index(drop=True)

    def search_attractions(self, city: str) -> pd.DataFrame:
        city_name = self._normalize_city(city)
        frame = self.attractions
        mask = self._series_equals(frame["City"], city_name)
        return frame.loc[mask].reset_index(drop=True)

    def get_distances(self, origin: str, dest: str) -> pd.DataFrame:
        origin_name = self._normalize_city(origin)
        dest_name = self._normalize_city(dest)
        frame = self.distances
        mask = (
            self._series_equals(frame["origin"], origin_name)
            & self._series_equals(frame["destination"], dest_name)
        )
        return frame.loc[mask].reset_index(drop=True)

    def get_query(self, idx: int) -> dict[str, Any]:
        query_rows = self._load_queries(split=self.dataset_split)
        index = int(idx)
        if index < 0 or index >= len(query_rows):
            raise IndexError(f"query index out of range: {index}")

        raw = dict(query_rows[index])
        parsed = self._normalize_query_row(raw=raw, idx=index)
        self.current_query = parsed
        return parsed

    def get_context_summary(self) -> str:
        if self.current_query is None:
            city_count = len(
                set(self.flights["OriginCityName"].astype(str)).union(
                    set(self.flights["DestCityName"].astype(str))
                )
            )
            return (
                "TravelPlanner workspace loaded. "
                f"Cities={city_count}, flights={len(self.flights)}, hotels={len(self.hotels)}, "
                f"restaurants={len(self.restaurants)}, attractions={len(self.attractions)}."
            )

        query = self.current_query
        constraints = query.get("local_constraint", {})
        dates = query.get("date", [])
        return (
            "TravelPlanner Query Context\n"
            f"- query_idx: {query.get('query_idx')}\n"
            f"- origin: {query.get('org')}\n"
            f"- destination: {query.get('dest')}\n"
            f"- days: {query.get('days')}\n"
            f"- people: {query.get('people_number')}\n"
            f"- budget: {query.get('budget')}\n"
            f"- dates: {dates}\n"
            f"- local_constraint: {constraints}\n"
            f"- query: {query.get('query')}"
        )

    def _load_csv(self, label: str, candidates: list[str]) -> pd.DataFrame:
        for relative in candidates:
            candidate = self.database_root / relative
            if candidate.exists() and candidate.is_file():
                return pd.read_csv(candidate)
        joined = ", ".join(candidates)
        raise FileNotFoundError(
            f"Missing TravelPlanner {label} CSV in {self.database_root}. Tried: {joined}"
        )

    def _normalize_columns(self) -> None:
        self.flights = self.flights.copy()
        self.hotels = self.hotels.copy()
        self.restaurants = self.restaurants.copy()
        self.attractions = self.attractions.copy()
        self.distances = self.distances.copy()

        self.hotels.rename(
            columns={
                "house_rules": "house_rules",
                "room type": "room type",
                "maximum occupancy": "maximum occupancy",
                "minimum nights": "minimum nights",
            },
            inplace=True,
        )

        self.distances.rename(
            columns={
                "Origin": "origin",
                "Destination": "destination",
                "Distance": "distance",
                "Duration": "duration",
            },
            inplace=True,
        )

    def _load_queries(self, *, split: str) -> list[dict[str, Any]]:
        if self._query_rows_override is not None:
            return [dict(row) for row in self._query_rows_override]

        split_name = str(split).strip() or "validation"
        if split_name in self._query_cache:
            return [dict(row) for row in self._query_cache[split_name]]

        try:
            from datasets import load_dataset  # lazy import for optional dependency
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "datasets package is required to load TravelPlanner queries. "
                "Install dependencies: `uv pip install -r requirements.txt`."
            ) from exc

        loaded = load_dataset(QUERY_DATASET_ID, split_name)
        if split_name not in loaded:
            raise ValueError(f"Unknown dataset split: {split_name}")

        rows = [dict(row) for row in loaded[split_name]]
        self._query_cache[split_name] = rows
        return [dict(row) for row in rows]

    def _normalize_query_row(self, *, raw: dict[str, Any], idx: int) -> dict[str, Any]:
        local_constraint = self._safe_literal(raw.get("local_constraint"), default={})
        if not isinstance(local_constraint, dict):
            local_constraint = {}

        dates = self._safe_literal(raw.get("date"), default=[])
        if not isinstance(dates, list):
            dates = []

        return {
            "query_idx": int(idx),
            "query": str(raw.get("query", "")).strip(),
            "org": str(raw.get("org", "")).strip(),
            "dest": str(raw.get("dest", "")).strip(),
            "days": int(raw.get("days", 0)),
            "visiting_city_number": int(raw.get("visiting_city_number", 0)),
            "date": [str(item) for item in dates],
            "people_number": int(raw.get("people_number", 1)),
            "budget": int(raw.get("budget", 0)),
            "level": str(raw.get("level", "")).strip(),
            "local_constraint": local_constraint,
            "reference_information": str(raw.get("reference_information", "")).strip(),
        }

    def _safe_literal(self, value: Any, *, default: Any) -> Any:
        if isinstance(value, (dict, list, tuple, int, float, bool)):
            return value
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return default

    def _normalize_city(self, value: str) -> str:
        text = str(value).strip()
        if "(" in text and ")" in text:
            return text.split("(", 1)[0].strip()
        return text

    def _series_equals(self, series: pd.Series, expected: str) -> pd.Series:
        expected_key = self._normalize_city(expected).casefold()
        normalized = series.astype(str).map(self._normalize_city).str.casefold()
        return normalized.eq(expected_key)
