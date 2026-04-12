"""Workspace wrapper for TravelPlanner dataset and CSV databases."""

from __future__ import annotations

import ast
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from adapters.base import Workspace


QUERY_DATASET_ID = "osunlp/TravelPlanner"


class TravelPlannerWorkspace(Workspace):
    """TravelPlanner workspace backed by local CSV databases and HF queries."""

    _query_cache: dict[str, list[dict[str, Any]]] = {}
    flight_columns = (
        "Flight Number",
        "Price",
        "DepTime",
        "ArrTime",
        "ActualElapsedTime",
        "FlightDate",
        "OriginCityName",
        "DestCityName",
        "Distance",
    )
    hotel_columns = (
        "NAME",
        "price",
        "room type",
        "house_rules",
        "minimum nights",
        "maximum occupancy",
        "review rate number",
        "city",
    )
    restaurant_columns = (
        "Name",
        "Average Cost",
        "Cuisines",
        "Aggregate Rating",
        "City",
    )
    attraction_columns = (
        "Name",
        "Latitude",
        "Longitude",
        "Address",
        "Phone",
        "Website",
        "City",
    )
    distance_columns = (
        "origin",
        "destination",
        "duration",
        "distance",
    )

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
        self.city_state_map = self._load_city_state_map()
        self.city_lookup = {
            city.casefold(): city
            for city in sorted(self.city_state_map)
        }
        self.state_lookup = {
            state.casefold(): state
            for state in sorted(set(self.city_state_map.values()))
        }
        self.inventory_counts = self._build_inventory_counts()
        self.full_inventory_cities = {
            city
            for city, counts in self.inventory_counts.items()
            if counts["hotels"] > 0
            and counts["restaurants"] > 0
            and counts["attractions"] > 0
        }
        self.state_city_map = self._build_state_city_map()
        self.distance_km_by_route = self._build_distance_index()

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

    def search_ground_transport(self, origin: str, dest: str) -> pd.DataFrame:
        route = self.get_distances(origin, dest)
        if route.empty:
            return pd.DataFrame(
                columns=[
                    "mode",
                    "origin",
                    "destination",
                    "duration",
                    "distance",
                    "cost",
                    "transportation",
                ]
            )

        options: list[dict[str, Any]] = []
        for _, row in route.iterrows():
            origin_name = self._normalize_city(str(row.get("origin", origin)))
            dest_name = self._normalize_city(str(row.get("destination", dest)))
            duration = str(row.get("duration", "")).strip()
            distance = str(row.get("distance", "")).strip()
            distance_km = self._parse_distance_km(distance)
            if not duration or not distance or distance_km is None:
                continue

            driving_cost = int(distance_km * 0.05)
            taxi_cost = int(distance_km)
            options.extend(
                [
                    {
                        "mode": "Self-driving",
                        "origin": origin_name,
                        "destination": dest_name,
                        "duration": duration,
                        "distance": distance,
                        "cost": driving_cost,
                        "transportation": (
                            f"Self-driving, from {origin_name} to {dest_name}, "
                            f"duration: {duration}, distance: {distance}, cost: {driving_cost}"
                        ),
                    },
                    {
                        "mode": "Taxi",
                        "origin": origin_name,
                        "destination": dest_name,
                        "duration": duration,
                        "distance": distance,
                        "cost": taxi_cost,
                        "transportation": (
                            f"Taxi, from {origin_name} to {dest_name}, "
                            f"duration: {duration}, distance: {distance}, cost: {taxi_cost}"
                        ),
                    },
                ]
            )

        return pd.DataFrame(options)

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
            f"- city_sequence: {query.get('city_sequence', [])}\n"
            f"- days: {query.get('days')}\n"
            f"- people: {query.get('people_number')}\n"
            f"- budget: {query.get('budget')}\n"
            f"- dates: {dates}\n"
            f"- local_constraint: {constraints}\n"
            f"- query: {query.get('query')}"
        )

    def build_city_sequence(self, query: dict[str, Any]) -> list[str]:
        requested_cities = max(1, int(query.get("visiting_city_number", 0) or 0))
        origin = self._resolve_city_name(query.get("org"))
        destination = str(query.get("dest", "")).strip()
        query_text = str(query.get("query", "")).strip()
        dates = query.get("date", [])
        route_dates = self._build_leg_dates(dates=dates, city_count=requested_cities)
        target_state, anchor_city = self._resolve_destination_scope(
            destination=destination,
            query_text=query_text,
            requested_cities=requested_cities,
        )

        candidate_pool = self._build_destination_candidates(
            origin=origin,
            target_state=target_state,
            anchor_city=anchor_city,
            requested_cities=requested_cities,
        )
        if not candidate_pool:
            fallback_city = anchor_city or self._resolve_city_name(destination)
            return [fallback_city] if fallback_city else []

        flight_counts = self._build_query_flight_counts(dates=dates)
        transport_constraint = self._extract_transport_constraint(query)
        best_sequence = self._search_city_sequence(
            origin=origin,
            candidate_pool=candidate_pool,
            requested_cities=requested_cities,
            route_dates=route_dates,
            flight_counts=flight_counts,
            transport_constraint=transport_constraint,
            anchor_city=anchor_city,
        )
        if best_sequence:
            return best_sequence

        return self._fallback_city_sequence(
            origin=origin,
            candidate_pool=candidate_pool,
            requested_cities=requested_cities,
            route_dates=route_dates,
            flight_counts=flight_counts,
            transport_constraint=transport_constraint,
            anchor_city=anchor_city,
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

        self.flights = self._prepare_inventory(
            self.flights,
            required_columns=self.flight_columns,
        )
        self.hotels = self._prepare_inventory(
            self.hotels,
            required_columns=self.hotel_columns,
        )
        self.restaurants = self._prepare_inventory(
            self.restaurants,
            required_columns=self.restaurant_columns,
        )
        self.attractions = self._prepare_inventory(
            self.attractions,
            required_columns=self.attraction_columns,
        )
        self.distances = self._prepare_inventory(
            self.distances,
            required_columns=self.distance_columns,
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

        normalized = {
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
        normalized["city_sequence"] = self.build_city_sequence(normalized)
        normalized["leg_dates"] = self._build_leg_dates(
            dates=normalized["date"],
            city_count=len(normalized["city_sequence"]),
        )
        return normalized

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

    def _resolve_city_name(self, value: Any) -> str:
        normalized = self._normalize_city(str(value or ""))
        return self.city_lookup.get(normalized.casefold(), normalized)

    def _resolve_state_name(self, value: Any) -> str:
        text = str(value or "").strip()
        return self.state_lookup.get(text.casefold(), text)

    def _series_equals(self, series: pd.Series, expected: str) -> pd.Series:
        expected_key = self._normalize_city(expected).casefold()
        normalized = series.astype(str).map(self._normalize_city).str.casefold()
        return normalized.eq(expected_key)

    def _prepare_inventory(
        self,
        frame: pd.DataFrame,
        *,
        required_columns: tuple[str, ...],
    ) -> pd.DataFrame:
        missing = [column for column in required_columns if column not in frame.columns]
        if missing:
            raise ValueError(
                "TravelPlanner inventory is missing required columns: "
                + ", ".join(missing)
            )
        prepared = frame.loc[:, list(required_columns)].copy()
        prepared = prepared.dropna(subset=list(required_columns)).reset_index(drop=True)
        return prepared

    def _parse_distance_km(self, value: str) -> int | None:
        text = str(value).strip()
        if not text:
            return None
        match = re.search(r"([0-9][0-9,]*\.?[0-9]*)", text)
        if match is None:
            return None
        try:
            return int(math.floor(float(match.group(1).replace(",", ""))))
        except ValueError:
            return None

    def _load_city_state_map(self) -> dict[str, str]:
        path = self.database_root / "background" / "citySet_with_states.txt"
        if not path.exists():
            return {}

        mapping: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            if "\t" not in raw_line:
                continue
            city_raw, state_raw = raw_line.split("\t", 1)
            city = self._normalize_city(city_raw)
            state = str(state_raw).strip()
            if city and state:
                mapping[city] = state
        return mapping

    def _build_inventory_counts(self) -> dict[str, dict[str, int]]:
        counts: defaultdict[str, dict[str, int]] = defaultdict(
            lambda: {
                "hotels": 0,
                "restaurants": 0,
                "attractions": 0,
            }
        )
        sources = (
            ("hotels", self.hotels, "city"),
            ("restaurants", self.restaurants, "City"),
            ("attractions", self.attractions, "City"),
        )
        for label, frame, column in sources:
            for city in frame[column].astype(str):
                normalized_city = self._resolve_city_name(city)
                if normalized_city:
                    counts[normalized_city][label] += 1
        return dict(counts)

    def _build_state_city_map(self) -> dict[str, list[str]]:
        grouped: defaultdict[str, list[str]] = defaultdict(list)
        for city, state in self.city_state_map.items():
            if city not in self.inventory_counts:
                continue
            grouped[state].append(city)
        return {
            state: sorted(cities)
            for state, cities in grouped.items()
        }

    def _build_distance_index(self) -> dict[tuple[str, str], int]:
        index: dict[tuple[str, str], int] = {}
        for _, row in self.distances.iterrows():
            origin = self._resolve_city_name(row.get("origin"))
            destination = self._resolve_city_name(row.get("destination"))
            distance_km = self._parse_distance_km(str(row.get("distance", "")))
            if not origin or not destination or distance_km is None:
                continue
            index[(origin, destination)] = distance_km
        return index

    def _resolve_destination_scope(
        self,
        *,
        destination: str,
        query_text: str,
        requested_cities: int,
    ) -> tuple[str | None, str | None]:
        normalized_destination = self._resolve_city_name(destination)
        destination_state = self._resolve_state_name(destination)
        lowered_query = query_text.casefold()
        destination_key = str(destination or "").strip().casefold()
        state_scope = (
            requested_cities > 1
            and (
                destination_state in self.state_city_map
                or f"cities in {destination_key}" in lowered_query
                or f"city in {destination_key}" in lowered_query
                or f"in the state of {destination_key}" in lowered_query
            )
        )
        if state_scope:
            return destination_state, None

        if normalized_destination in self.city_state_map:
            return self.city_state_map.get(normalized_destination), normalized_destination

        if destination_state in self.state_city_map:
            return destination_state, None

        return None, normalized_destination or None

    def _build_destination_candidates(
        self,
        *,
        origin: str,
        target_state: str | None,
        anchor_city: str | None,
        requested_cities: int,
    ) -> list[str]:
        preferred_pool: list[str] = []
        if target_state:
            preferred_pool.extend(self.state_city_map.get(target_state, []))

        if anchor_city and anchor_city not in preferred_pool:
            preferred_pool.insert(0, anchor_city)

        pool = [
            city
            for city in preferred_pool
            if city and city != origin
        ]
        full_inventory_pool = [city for city in pool if city in self.full_inventory_cities]
        if len(full_inventory_pool) >= requested_cities:
            pool = full_inventory_pool
        elif full_inventory_pool:
            pool = full_inventory_pool + [city for city in pool if city not in full_inventory_pool]

        if len(pool) >= requested_cities:
            return self._unique_preserving_order(pool)

        fallback_pool = [
            city
            for city in sorted(self.full_inventory_cities)
            if city != origin and city not in pool
        ]
        return self._unique_preserving_order(pool + fallback_pool)

    def _build_query_flight_counts(self, *, dates: list[Any]) -> Counter[tuple[str, str, str]]:
        date_values = {
            str(date).strip()
            for date in dates
            if str(date).strip()
        }
        if not date_values:
            return Counter()

        filtered = self.flights.loc[
            self.flights["FlightDate"].astype(str).str.strip().isin(date_values)
        ]
        counts: Counter[tuple[str, str, str]] = Counter()
        for _, row in filtered.iterrows():
            origin = self._resolve_city_name(row.get("OriginCityName"))
            destination = self._resolve_city_name(row.get("DestCityName"))
            date_value = str(row.get("FlightDate", "")).strip()
            if origin and destination and date_value:
                counts[(origin, destination, date_value)] += 1
        return counts

    def _extract_transport_constraint(self, query: dict[str, Any]) -> str:
        constraints = query.get("local_constraint")
        if not isinstance(constraints, dict):
            return ""
        return str(constraints.get("transportation") or "").strip().casefold()

    def _route_score(
        self,
        *,
        origin: str,
        destination: str,
        date_value: str,
        flight_counts: Counter[tuple[str, str, str]],
        transport_constraint: str,
    ) -> float | None:
        if not origin or not destination:
            return None

        flight_count = 0
        if transport_constraint != "no flight" and date_value:
            flight_count = int(flight_counts.get((origin, destination, date_value), 0))
        distance_km = self.distance_km_by_route.get((origin, destination))
        if flight_count <= 0 and distance_km is None:
            return None

        score = 0.0
        if flight_count > 0:
            score += 100.0 + min(float(flight_count), 12.0) * 10.0

        if distance_km is not None:
            ground_bonus = max(1.0, 35.0 - (float(distance_km) / 120.0))
            if transport_constraint == "no flight":
                ground_bonus += 15.0
            score += ground_bonus

        return score

    def _city_inventory_score(self, city: str) -> float:
        counts = self.inventory_counts.get(city, {})
        return (
            float(counts.get("hotels", 0))
            + float(counts.get("restaurants", 0)) * 0.5
            + float(counts.get("attractions", 0)) * 0.75
        )

    def _search_city_sequence(
        self,
        *,
        origin: str,
        candidate_pool: list[str],
        requested_cities: int,
        route_dates: list[str],
        flight_counts: Counter[tuple[str, str, str]],
        transport_constraint: str,
        anchor_city: str | None,
    ) -> list[str]:
        ordered_candidates = sorted(
            self._unique_preserving_order(candidate_pool),
            key=lambda city: (
                city == anchor_city,
                self._route_score(
                    origin=origin,
                    destination=city,
                    date_value=route_dates[0] if route_dates else "",
                    flight_counts=flight_counts,
                    transport_constraint=transport_constraint,
                )
                or -1.0,
                self._city_inventory_score(city),
            ),
            reverse=True,
        )

        best_sequence: list[str] = []
        best_score = float("-inf")

        def backtrack(
            current_origin: str,
            remaining: list[str],
            depth: int,
            sequence: list[str],
            accumulated_score: float,
        ) -> None:
            nonlocal best_score, best_sequence

            if depth >= requested_cities:
                if anchor_city and anchor_city not in sequence:
                    return
                return_date = route_dates[min(depth, len(route_dates) - 1)] if route_dates else ""
                return_score = self._route_score(
                    origin=current_origin,
                    destination=origin,
                    date_value=return_date,
                    flight_counts=flight_counts,
                    transport_constraint=transport_constraint,
                )
                if return_score is None:
                    return

                total_score = accumulated_score + return_score
                total_score += sum(self._city_inventory_score(city) for city in sequence)
                if total_score > best_score:
                    best_score = total_score
                    best_sequence = list(sequence)
                return

            for index, city in enumerate(remaining):
                if anchor_city and anchor_city not in sequence:
                    slots_left = requested_cities - depth
                    if anchor_city not in remaining[: index + 1] and slots_left <= 1:
                        continue

                route_date = route_dates[min(depth, len(route_dates) - 1)] if route_dates else ""
                leg_score = self._route_score(
                    origin=current_origin,
                    destination=city,
                    date_value=route_date,
                    flight_counts=flight_counts,
                    transport_constraint=transport_constraint,
                )
                if leg_score is None:
                    continue

                anchor_bonus = 12.0 if city == anchor_city else 0.0
                backtrack(
                    city,
                    remaining[:index] + remaining[index + 1 :],
                    depth + 1,
                    sequence + [city],
                    accumulated_score + leg_score + anchor_bonus,
                )

        backtrack(origin, ordered_candidates, 0, [], 0.0)
        return best_sequence

    def _fallback_city_sequence(
        self,
        *,
        origin: str,
        candidate_pool: list[str],
        requested_cities: int,
        route_dates: list[str],
        flight_counts: Counter[tuple[str, str, str]],
        transport_constraint: str,
        anchor_city: str | None,
    ) -> list[str]:
        ordered = sorted(
            self._unique_preserving_order(candidate_pool),
            key=lambda city: (
                city == anchor_city,
                self._route_score(
                    origin=origin,
                    destination=city,
                    date_value=route_dates[0] if route_dates else "",
                    flight_counts=flight_counts,
                    transport_constraint=transport_constraint,
                )
                or -1.0,
                self._city_inventory_score(city),
                city,
            ),
            reverse=True,
        )
        if anchor_city and anchor_city in ordered:
            ordered = [anchor_city] + [city for city in ordered if city != anchor_city]
        return ordered[:requested_cities]

    def _build_leg_dates(self, *, dates: list[Any], city_count: int) -> list[str]:
        normalized_dates = [
            str(value).strip()
            for value in dates
            if str(value).strip()
        ]
        if not normalized_dates:
            return [""] * max(city_count + 1, 2)

        leg_dates: list[str] = []
        leg_count = max(city_count + 1, 2)
        for leg_index in range(leg_count):
            source_index = min(leg_index * 2, len(normalized_dates) - 1)
            leg_dates.append(normalized_dates[source_index])
        return leg_dates

    def _unique_preserving_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered
