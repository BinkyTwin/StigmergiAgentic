"""TravelPlanner metrics evaluator aligned with paper constraints."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from core.marker import Marker

from .workspace import TravelPlannerWorkspace


DAY_FIELDS = [
    "current_city",
    "transportation",
    "breakfast",
    "attraction",
    "lunch",
    "dinner",
    "accommodation",
]


@dataclass(slots=True)
class PlanEvaluation:
    """Per-query evaluation payload."""

    delivered: bool
    commonsense: dict[str, bool | None]
    hard: dict[str, bool | None]
    estimated_cost: float

    @property
    def commonsense_macro_pass(self) -> bool:
        return all(value is True for value in self.commonsense.values() if value is not None)

    @property
    def hard_macro_pass(self) -> bool:
        return all(value is True for value in self.hard.values() if value is not None)

    @property
    def final_pass(self) -> bool:
        return self.delivered and self.commonsense_macro_pass and self.hard_macro_pass


class TravelPlannerEvaluator:
    """Evaluate plans with commonsense/hard constraints and paper metrics."""

    def __init__(self, *, workspace: TravelPlannerWorkspace) -> None:
        self.workspace = workspace

    def evaluate_snapshot(self, markers: list[Marker] | list[dict[str, Any]]) -> dict[str, Any]:
        typed_markers = [
            marker if isinstance(marker, Marker) else Marker.from_dict(marker)
            for marker in markers
            if isinstance(marker, (Marker, dict))
        ]

        finalize_candidates = [
            marker
            for marker in typed_markers
            if marker.id.endswith("::finalize")
        ]
        source_markers = finalize_candidates if finalize_candidates else typed_markers

        query_plan_pairs: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        seen_keys: set[str] = set()
        for marker in source_markers:
            payload = dict(marker.payload)
            query_data = payload.get("query_data")
            plan = payload.get("final_plan")
            if not isinstance(plan, list):
                plan = payload.get("plan")
            if not isinstance(query_data, dict):
                continue
            if isinstance(plan, list):
                key = str(query_data.get("query_idx", marker.id))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                query_plan_pairs.append((query_data, plan))

        if not query_plan_pairs:
            return {
                "delivery_rate": 0.0,
                "commonsense_micro": 0.0,
                "commonsense_macro": 0.0,
                "hard_constraint_micro": 0.0,
                "hard_constraint_macro": 0.0,
                "final_pass_rate": 0.0,
                "evaluated_queries": 0,
            }

        evaluations = [
            self.evaluate_plan(query_data=query, plan=plan)
            for query, plan in query_plan_pairs
        ]
        return self.aggregate(evaluations)

    def evaluate_plan(self, *, query_data: dict[str, Any], plan: list[dict[str, Any]]) -> PlanEvaluation:
        delivered = isinstance(plan, list) and len(plan) > 0
        if not delivered:
            commonsense = {
                "valid_info_current_city": False,
                "valid_info_sandbox": False,
                "reasonable_city_route": False,
                "valid_restaurants": False,
                "valid_transportation": False,
                "valid_attractions": False,
                "valid_accommodation": False,
                "not_absent": False,
            }
            hard = {
                "valid_cost": False,
                "valid_room_rule": False,
                "valid_cuisine": False,
                "valid_room_type": False,
                "valid_transportation": False,
            }
            return PlanEvaluation(
                delivered=False,
                commonsense=commonsense,
                hard=hard,
                estimated_cost=0.0,
            )

        normalized_plan = [self._normalize_day(day) for day in plan]
        commonsense = {
            "valid_info_current_city": self._is_valid_information_in_current_city(query_data, normalized_plan),
            "valid_info_sandbox": self._is_valid_information_in_sandbox(normalized_plan),
            "reasonable_city_route": self._is_reasonable_city_route(query_data, normalized_plan),
            "valid_restaurants": self._is_valid_restaurants(normalized_plan),
            "valid_transportation": self._is_valid_transportation_commonsense(normalized_plan),
            "valid_attractions": self._is_valid_attractions(normalized_plan),
            "valid_accommodation": self._is_valid_accommodation(query_data, normalized_plan),
            "not_absent": self._is_not_absent(query_data, normalized_plan),
        }

        estimated_cost = self._estimate_cost(query_data, normalized_plan)
        hard = {
            "valid_cost": estimated_cost <= float(query_data.get("budget", 0)),
            "valid_room_rule": self._is_valid_room_rule(query_data, normalized_plan),
            "valid_cuisine": self._is_valid_cuisine(query_data, normalized_plan),
            "valid_room_type": self._is_valid_room_type(query_data, normalized_plan),
            "valid_transportation": self._is_valid_transportation_hard(query_data, normalized_plan),
        }

        return PlanEvaluation(
            delivered=True,
            commonsense=commonsense,
            hard=hard,
            estimated_cost=float(estimated_cost),
        )

    def aggregate(self, evaluations: list[PlanEvaluation]) -> dict[str, Any]:
        total = len(evaluations)
        if total <= 0:
            return {
                "delivery_rate": 0.0,
                "commonsense_micro": 0.0,
                "commonsense_macro": 0.0,
                "hard_constraint_micro": 0.0,
                "hard_constraint_macro": 0.0,
                "final_pass_rate": 0.0,
                "evaluated_queries": 0,
            }

        delivery_count = sum(1 for eval_ in evaluations if eval_.delivered)
        commonsense_macro = sum(1 for eval_ in evaluations if eval_.commonsense_macro_pass)
        hard_macro = sum(1 for eval_ in evaluations if eval_.hard_macro_pass)
        final_macro = sum(1 for eval_ in evaluations if eval_.final_pass)

        commonsense_true = 0
        commonsense_total = 0
        hard_true = 0
        hard_total = 0

        for eval_ in evaluations:
            for value in eval_.commonsense.values():
                if value is None:
                    continue
                commonsense_total += 1
                if value:
                    commonsense_true += 1
            for value in eval_.hard.values():
                if value is None:
                    continue
                hard_total += 1
                if value:
                    hard_true += 1

        commonsense_micro = 0.0 if commonsense_total == 0 else commonsense_true / commonsense_total
        hard_micro = 0.0 if hard_total == 0 else hard_true / hard_total

        return {
            "delivery_rate": delivery_count / total,
            "commonsense_micro": commonsense_micro,
            "commonsense_macro": commonsense_macro / total,
            "hard_constraint_micro": hard_micro,
            "hard_constraint_macro": hard_macro / total,
            "final_pass_rate": final_macro / total,
            "evaluated_queries": total,
        }

    def failed_constraints(self, evaluation: PlanEvaluation) -> list[str]:
        failed: list[str] = []
        for name, value in evaluation.commonsense.items():
            if value is False:
                failed.append(f"commonsense:{name}")
        for name, value in evaluation.hard.items():
            if value is False:
                failed.append(f"hard:{name}")
        return failed

    def _normalize_day(self, day: dict[str, Any]) -> dict[str, str]:
        normalized = {field: "" for field in DAY_FIELDS}
        if not isinstance(day, dict):
            return normalized
        for field in DAY_FIELDS:
            normalized[field] = str(day.get(field, "")).strip()
        return normalized

    def _is_reasonable_city_route(self, query_data: dict[str, Any], plan: list[dict[str, str]]) -> bool:
        if not plan:
            return False

        city_sequence: list[str] = []
        for day in plan:
            current_city = day.get("current_city", "")
            from_city, to_city = self._extract_from_to(current_city)
            if from_city and to_city:
                city_sequence.extend([from_city, to_city])
            else:
                city = self._normalize_city(current_city)
                if city:
                    city_sequence.append(city)

        if not city_sequence:
            return False

        origin = self._normalize_city(str(query_data.get("org", "")))
        if origin and city_sequence[0] != origin:
            return False
        if origin and city_sequence[-1] != origin:
            return False

        visited_non_origin = {
            city for city in city_sequence if city and city != origin
        }
        target_visits = int(query_data.get("visiting_city_number", 0))
        if target_visits > 0 and len(visited_non_origin) != target_visits:
            return False

        return self._is_valid_city_sequence(city_sequence)

    def _is_valid_city_sequence(self, sequence: list[str]) -> bool:
        if len(sequence) < 2:
            return False

        seen: set[str] = set()
        idx = 0
        while idx < len(sequence):
            city = sequence[idx]
            if city in seen and 0 < idx < len(sequence) - 1:
                return False

            run = 0
            while idx < len(sequence) and sequence[idx] == city:
                run += 1
                idx += 1

            if run == 1 and 0 < idx - 1 < len(sequence) - 1:
                return False

            seen.add(city)
        return True

    def _is_valid_restaurants(self, plan: list[dict[str, str]]) -> bool:
        seen: set[str] = set()
        for day in plan:
            for field in ("breakfast", "lunch", "dinner"):
                value = day.get(field, "")
                if not value or value == "-":
                    continue
                key = value.casefold()
                if key in seen:
                    return False
                seen.add(key)
        return True

    def _is_valid_transportation_commonsense(self, plan: list[dict[str, str]]) -> bool:
        modes: set[str] = set()
        for day in plan:
            mode = self._transport_mode(day.get("transportation", ""))
            if mode:
                modes.add(mode)

        if "self-driving" in modes and "flight" in modes:
            return False
        if "self-driving" in modes and "taxi" in modes:
            return False
        return True

    def _is_valid_attractions(self, plan: list[dict[str, str]]) -> bool:
        seen: set[str] = set()
        for day in plan:
            value = day.get("attraction", "")
            if not value or value == "-":
                continue
            parts = [part.strip() for part in value.split(";") if part.strip()]
            for part in parts:
                key = part.casefold()
                if key in seen:
                    return False
                seen.add(key)
        return True

    def _is_valid_accommodation(
        self,
        query_data: dict[str, Any],
        plan: list[dict[str, str]],
    ) -> bool:
        if not plan:
            return False

        days = int(query_data.get("days", len(plan)))
        relevant = plan[: min(days, len(plan))]
        if not relevant:
            return False

        for index, day in enumerate(relevant):
            value = day.get("accommodation", "")
            if index < len(relevant) - 1 and value in {"", "-"}:
                return False

        consecutive: list[tuple[str, int]] = []
        current = ""
        count = 0
        for day in relevant:
            value = day.get("accommodation", "")
            if value == current:
                count += 1
            else:
                if current:
                    consecutive.append((current, count))
                current = value
                count = 1
        if current:
            consecutive.append((current, count))

        for name_city, stay_length in consecutive:
            if name_city in {"", "-"}:
                continue
            name, city = self._split_name_city(name_city)
            row = self._find_hotel(name=name, city=city)
            if row is None:
                return False
            minimum_nights = float(row.get("minimum nights", 0))
            if stay_length < minimum_nights:
                return False

        return True

    def _is_valid_information_in_current_city(
        self,
        query_data: dict[str, Any],
        plan: list[dict[str, str]],
    ) -> bool:
        days = int(query_data.get("days", len(plan)))
        for idx, day in enumerate(plan[: min(days, len(plan))]):
            current_city = day.get("current_city", "")
            from_city, to_city = self._extract_from_to(current_city)
            cities = [from_city, to_city] if from_city and to_city else [self._normalize_city(current_city)]
            cities = [city for city in cities if city]
            if not cities:
                return False

            city_candidates = [city.casefold() for city in cities]
            meal_fields = ["breakfast", "lunch", "dinner", "attraction", "transportation"]
            for field in meal_fields:
                value = day.get(field, "")
                if not value or value == "-":
                    continue
                value_key = value.casefold()
                if not any(city in value_key for city in city_candidates):
                    return False

            accommodation = day.get("accommodation", "")
            if accommodation and accommodation != "-":
                if cities[-1].casefold() not in accommodation.casefold():
                    return False

            if idx == 0:
                origin = self._normalize_city(str(query_data.get("org", "")))
                if origin and cities[0] != origin:
                    return False

        return True

    def _is_valid_information_in_sandbox(self, plan: list[dict[str, str]]) -> bool:
        for day in plan:
            transportation = day.get("transportation", "")
            if transportation and transportation != "-":
                from_city, to_city = self._extract_from_to(transportation)
                if not (from_city and to_city):
                    from_city, to_city = self._extract_from_to(day.get("current_city", ""))

                if "flight number" in transportation.casefold():
                    match = re.search(r"flight\s*number\s*:\s*([^,]+)", transportation, flags=re.IGNORECASE)
                    if match is None:
                        return False
                    flight_number = match.group(1).strip()
                    frame = self.workspace.flights
                    rows = frame[
                        frame["Flight Number"].astype(str).str.strip().eq(flight_number)
                    ]
                    if from_city:
                        rows = rows[
                            frame.loc[rows.index, "OriginCityName"].astype(str).map(self._normalize_city).str.casefold().eq(from_city.casefold())
                        ]
                    if to_city:
                        rows = rows[
                            frame.loc[rows.index, "DestCityName"].astype(str).map(self._normalize_city).str.casefold().eq(to_city.casefold())
                        ]
                    if rows.empty:
                        return False
                else:
                    mode = self._transport_mode(transportation)
                    if mode in {"self-driving", "taxi"}:
                        if not from_city or not to_city:
                            return False
                        if self.workspace.get_distances(from_city, to_city).empty:
                            return False

            for field in ("breakfast", "lunch", "dinner"):
                value = day.get(field, "")
                if not value or value == "-":
                    continue
                name, city = self._split_name_city(value)
                if self._find_restaurant(name=name, city=city) is None:
                    return False

            attraction_value = day.get("attraction", "")
            if attraction_value and attraction_value != "-":
                parts = [part.strip() for part in attraction_value.split(";") if part.strip()]
                for part in parts:
                    name, city = self._split_name_city(part)
                    if self._find_attraction(name=name, city=city) is None:
                        return False

            accommodation = day.get("accommodation", "")
            if accommodation and accommodation != "-":
                name, city = self._split_name_city(accommodation)
                if self._find_hotel(name=name, city=city) is None:
                    return False

        return True

    def _is_not_absent(self, query_data: dict[str, Any], plan: list[dict[str, str]]) -> bool:
        days = int(query_data.get("days", len(plan)))
        relevant = plan[: min(days, len(plan))]
        if len(relevant) < days:
            return False

        required = [
            "transportation",
            "breakfast",
            "lunch",
            "dinner",
            "attraction",
            "accommodation",
        ]

        non_empty = 0
        total_slots = len(relevant) * len(required)
        for idx, day in enumerate(relevant):
            for field in required:
                if field not in day:
                    return False

            current_city = day.get("current_city", "")
            travel_day = "from " in current_city.casefold() and " to " in current_city.casefold()

            if travel_day and day.get("transportation", "") in {"", "-"}:
                return False
            if (not travel_day) and day.get("attraction", "") in {"", "-"}:
                return False
            if idx < len(relevant) - 1 and day.get("accommodation", "") in {"", "-"}:
                return False

            if not travel_day:
                if day.get("breakfast", "") in {"", "-"}:
                    return False
                if day.get("lunch", "") in {"", "-"}:
                    return False
                if day.get("dinner", "") in {"", "-"}:
                    return False

            for field in required:
                value = day.get(field, "")
                if value and value != "-":
                    non_empty += 1

        if total_slots <= 0:
            return False
        return (non_empty / total_slots) >= 0.5

    def _is_valid_room_rule(self, query_data: dict[str, Any], plan: list[dict[str, str]]) -> bool | None:
        constraint = self._local_constraint(query_data, "house rule")
        if constraint is None:
            return None

        forbidden_map = {
            "smoking": "No smoking",
            "parties": "No parties",
            "children under 10": "No children under 10",
            "visitors": "No visitors",
            "pets": "No pets",
        }
        forbidden = forbidden_map.get(str(constraint).strip().lower())
        if forbidden is None:
            return True

        for day in plan:
            accommodation = day.get("accommodation", "")
            if not accommodation or accommodation == "-":
                continue
            name, city = self._split_name_city(accommodation)
            row = self._find_hotel(name=name, city=city)
            if row is None:
                return False
            house_rules = str(row.get("house_rules", ""))
            if forbidden in house_rules:
                return False
        return True

    def _is_valid_cuisine(self, query_data: dict[str, Any], plan: list[dict[str, str]]) -> bool | None:
        required = self._local_constraint(query_data, "cuisine")
        if required is None or required == "" or required == []:
            return None
        if not isinstance(required, list):
            return None

        origin = self._normalize_city(str(query_data.get("org", "")))
        found: set[str] = set()
        for day in plan:
            for field in ("breakfast", "lunch", "dinner"):
                value = day.get(field, "")
                if not value or value == "-":
                    continue
                name, city = self._split_name_city(value)
                if self._normalize_city(city) == origin:
                    continue
                row = self._find_restaurant(name=name, city=city)
                if row is None:
                    continue
                cuisines = str(row.get("Cuisines", ""))
                for cuisine in required:
                    cuisine_text = str(cuisine).strip()
                    if cuisine_text and cuisine_text in cuisines:
                        found.add(cuisine_text)

        return all(str(cuisine).strip() in found for cuisine in required)

    def _is_valid_room_type(self, query_data: dict[str, Any], plan: list[dict[str, str]]) -> bool | None:
        constraint = self._local_constraint(query_data, "room type")
        if constraint is None:
            return None

        normalized_constraint = str(constraint).strip().lower()
        for day in plan:
            accommodation = day.get("accommodation", "")
            if not accommodation or accommodation == "-":
                continue
            name, city = self._split_name_city(accommodation)
            row = self._find_hotel(name=name, city=city)
            if row is None:
                return False

            room_type = str(row.get("room type", "")).strip().lower()
            if normalized_constraint == "not shared room" and room_type == "shared room":
                return False
            if normalized_constraint == "shared room" and room_type != "shared room":
                return False
            if normalized_constraint == "private room" and room_type != "private room":
                return False
            if normalized_constraint == "entire room" and room_type != "entire home/apt":
                return False
        return True

    def _is_valid_transportation_hard(self, query_data: dict[str, Any], plan: list[dict[str, str]]) -> bool | None:
        constraint = self._local_constraint(query_data, "transportation")
        if constraint is None:
            return None

        normalized = str(constraint).strip().lower()
        for day in plan:
            transportation = day.get("transportation", "")
            if not transportation or transportation == "-":
                continue
            text = transportation.casefold()
            if normalized == "no flight" and "flight" in text:
                return False
            if normalized == "no self-driving" and "self-driving" in text:
                return False
        return True

    def _estimate_cost(self, query_data: dict[str, Any], plan: list[dict[str, str]]) -> float:
        people = max(1, int(query_data.get("people_number", 1)))
        total = 0.0

        for day in plan:
            transportation = day.get("transportation", "")
            current_city = day.get("current_city", "")
            from_city, to_city = self._extract_from_to(transportation)
            if not (from_city and to_city):
                from_city, to_city = self._extract_from_to(current_city)

            if transportation and transportation != "-":
                if "flight number" in transportation.casefold():
                    match = re.search(r"flight\s*number\s*:\s*([^,]+)", transportation, flags=re.IGNORECASE)
                    if match is not None:
                        flight_number = match.group(1).strip()
                        rows = self.workspace.flights[
                            self.workspace.flights["Flight Number"].astype(str).str.strip().eq(flight_number)
                        ]
                        if not rows.empty:
                            total += float(rows.iloc[0].get("Price", 0.0)) * people
                else:
                    mode = self._transport_mode(transportation)
                    if mode in {"self-driving", "taxi"} and from_city and to_city:
                        dist_rows = self.workspace.get_distances(from_city, to_city)
                        if not dist_rows.empty:
                            km = self._parse_distance_km(dist_rows.iloc[0].get("distance", 0))
                            if mode == "self-driving":
                                total += km * 0.05 * math.ceil(people / 5)
                            else:
                                total += km * math.ceil(people / 4)

            for meal in ("breakfast", "lunch", "dinner"):
                name_city = day.get(meal, "")
                if not name_city or name_city == "-":
                    continue
                name, city = self._split_name_city(name_city)
                row = self._find_restaurant(name=name, city=city)
                if row is not None:
                    total += float(row.get("Average Cost", 0.0)) * people

            accommodation = day.get("accommodation", "")
            if accommodation and accommodation != "-":
                name, city = self._split_name_city(accommodation)
                row = self._find_hotel(name=name, city=city)
                if row is not None:
                    price = float(row.get("price", 0.0))
                    occupancy = max(1.0, float(row.get("maximum occupancy", 1.0)))
                    total += price * math.ceil(people / occupancy)

        return float(total)

    def _find_restaurant(self, *, name: str, city: str) -> dict[str, Any] | None:
        frame = self.workspace.search_restaurants(city)
        if frame.empty:
            return None
        mask = frame["Name"].astype(str).str.contains(re.escape(name), case=False, regex=True)
        rows = frame.loc[mask]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def _find_hotel(self, *, name: str, city: str) -> dict[str, Any] | None:
        frame = self.workspace.search_hotels(city)
        if frame.empty:
            return None
        mask = frame["NAME"].astype(str).str.contains(re.escape(name), case=False, regex=True)
        rows = frame.loc[mask]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def _find_attraction(self, *, name: str, city: str) -> dict[str, Any] | None:
        frame = self.workspace.search_attractions(city)
        if frame.empty:
            return None
        mask = frame["Name"].astype(str).str.contains(re.escape(name), case=False, regex=True)
        rows = frame.loc[mask]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def _local_constraint(self, query_data: dict[str, Any], key: str) -> Any:
        raw = query_data.get("local_constraint", {})
        if not isinstance(raw, dict):
            return None
        return raw.get(key)

    def _split_name_city(self, value: str) -> tuple[str, str]:
        text = str(value).strip()
        pattern = r"(.*?),\s*([^,]+)(\([^)]*\))?$"
        match = re.search(pattern, text)
        if match is None:
            return text, ""
        name = match.group(1).strip()
        city = self._normalize_city(match.group(2).strip())
        return name, city

    def _extract_from_to(self, text: str) -> tuple[str, str]:
        pattern = r"from\s+(.+?)\s+to\s+([^,]+)(?=[,\s]|$)"
        match = re.search(pattern, str(text), flags=re.IGNORECASE)
        if match is None:
            return "", ""
        return self._normalize_city(match.group(1)), self._normalize_city(match.group(2))

    def _transport_mode(self, value: str) -> str:
        text = str(value).casefold()
        if "self-driving" in text:
            return "self-driving"
        if "taxi" in text:
            return "taxi"
        if "flight" in text:
            return "flight"
        return ""

    def _normalize_city(self, value: str) -> str:
        text = str(value).strip()
        if "(" in text and ")" in text:
            text = text.split("(", 1)[0].strip()
        return text

    def _parse_distance_km(self, value: Any) -> float:
        text = str(value)
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text.replace(",", ""))
        if match is None:
            return 0.0
        return float(match.group(1))
