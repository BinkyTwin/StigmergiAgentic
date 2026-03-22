"""Shared fixtures for TravelPlanner unit/integration tests."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pandas as pd


def sample_query_rows() -> list[dict[str, Any]]:
    return [
        {
            "org": "Washington",
            "dest": "Myrtle Beach",
            "days": 3,
            "visiting_city_number": 1,
            "date": "['2022-03-13', '2022-03-14', '2022-03-15']",
            "people_number": 1,
            "local_constraint": "{'house rule': None, 'cuisine': None, 'room type': None, 'transportation': None}",
            "budget": 2000,
            "query": "Please create a travel plan from Washington to Myrtle Beach for 3 days.",
            "level": "easy",
            "reference_information": "[]",
        },
        {
            "org": "Washington",
            "dest": "Myrtle Beach",
            "days": 3,
            "visiting_city_number": 1,
            "date": "['2022-03-13', '2022-03-14', '2022-03-15']",
            "people_number": 1,
            "local_constraint": "{'house rule': 'smoking', 'cuisine': ['Indian'], 'room type': 'private room', 'transportation': 'no self-driving'}",
            "budget": 500,
            "query": "Query 1",
            "level": "hard",
            "reference_information": "[]",
        },
    ]


def write_sample_database(database_root: Path) -> Path:
    (database_root / "flights").mkdir(parents=True, exist_ok=True)
    (database_root / "accommodations").mkdir(parents=True, exist_ok=True)
    (database_root / "restaurants").mkdir(parents=True, exist_ok=True)
    (database_root / "attractions").mkdir(parents=True, exist_ok=True)
    (database_root / "googleDistanceMatrix").mkdir(parents=True, exist_ok=True)
    (database_root / "background").mkdir(parents=True, exist_ok=True)

    flights = pd.DataFrame(
        [
            {
                "Flight Number": "F3792603",
                "Price": 164,
                "DepTime": "09:19",
                "ArrTime": "10:59",
                "ActualElapsedTime": "1 hours 40 minutes",
                "FlightDate": "2022-03-13",
                "OriginCityName": "Washington",
                "DestCityName": "Myrtle Beach",
                "Distance": 372.0,
            },
            {
                "Flight Number": "F3791200",
                "Price": 87,
                "DepTime": "11:36",
                "ArrTime": "13:06",
                "ActualElapsedTime": "1 hours 30 minutes",
                "FlightDate": "2022-03-15",
                "OriginCityName": "Myrtle Beach",
                "DestCityName": "Washington",
                "Distance": 372.0,
            },
        ]
    )

    hotels = pd.DataFrame(
        [
            {
                "NAME": "Private Room A",
                "price": 120.0,
                "room type": "Private room",
                "house_rules": "No parties",
                "minimum nights": 1,
                "maximum occupancy": 2,
                "review rate number": 4.8,
                "city": "Myrtle Beach",
            },
            {
                "NAME": "Shared Room B",
                "price": 80.0,
                "room type": "Shared room",
                "house_rules": "No smoking",
                "minimum nights": 1,
                "maximum occupancy": 2,
                "review rate number": 4.1,
                "city": "Myrtle Beach",
            },
            {
                "NAME": "Filtered Hotel",
                "price": 99.0,
                "room type": "Private room",
                "house_rules": None,
                "minimum nights": 1,
                "maximum occupancy": 2,
                "review rate number": 4.0,
                "city": "Myrtle Beach",
            },
        ]
    )

    restaurants = pd.DataFrame(
        [
            {
                "Name": "Exotic India",
                "Average Cost": 40,
                "Cuisines": "Indian, BBQ, Fast Food",
                "Aggregate Rating": 4.1,
                "City": "Myrtle Beach",
            },
            {
                "Name": "Seafood Place",
                "Average Cost": 30,
                "Cuisines": "Seafood",
                "Aggregate Rating": 4.0,
                "City": "Myrtle Beach",
            },
            {
                "Name": "Cafe Blue",
                "Average Cost": 22,
                "Cuisines": "Cafe, Desserts",
                "Aggregate Rating": 4.0,
                "City": "Myrtle Beach",
            },
            {
                "Name": "BBQ Dock",
                "Average Cost": 35,
                "Cuisines": "BBQ, American",
                "Aggregate Rating": 4.3,
                "City": "Myrtle Beach",
            },
            {
                "Name": "Pasta Corner",
                "Average Cost": 28,
                "Cuisines": "Italian",
                "Aggregate Rating": 4.2,
                "City": "Myrtle Beach",
            },
        ]
    )

    attractions = pd.DataFrame(
        [
            {
                "Name": "SkyWheel Myrtle Beach",
                "Latitude": 33.694026,
                "Longitude": -78.877372,
                "Address": "1110 N Ocean Blvd",
                "Phone": "(843) 839-9200",
                "Website": "http://skywheelmb.com/",
                "City": "Myrtle Beach",
            },
            {
                "Name": "Broadway at the Beach",
                "Latitude": 33.715617,
                "Longitude": -78.881949,
                "Address": "1325 Celebrity Cir",
                "Phone": "(843) 444-3200",
                "Website": "https://www.broadwayatthebeach.com/",
                "City": "Myrtle Beach",
            },
        ]
    )

    distances = pd.DataFrame(
        [
            {
                "origin": "Washington",
                "destination": "Myrtle Beach",
                "cost": 34,
                "duration": "6 hours 47 mins",
                "distance": "693 km",
            },
            {
                "origin": "Myrtle Beach",
                "destination": "Washington",
                "cost": 34,
                "duration": "6 hours 45 mins",
                "distance": "693 km",
            },
        ]
    )

    flights.to_csv(database_root / "flights" / "clean_Flights_2022.csv", index=False)
    hotels.to_csv(database_root / "accommodations" / "clean_accommodations_2022.csv", index=False)
    restaurants.to_csv(database_root / "restaurants" / "clean_restaurant_2022.csv", index=False)
    attractions.to_csv(database_root / "attractions" / "attractions.csv", index=False)
    distances.to_csv(database_root / "googleDistanceMatrix" / "distance.csv", index=False)
    (database_root / "background" / "citySet_with_states.txt").write_text(
        "Washington\tDistrict of Columbia\n"
        "Myrtle Beach\tSouth Carolina",
        encoding="utf-8",
    )
    return database_root


def sample_valid_plan() -> list[dict[str, str]]:
    return [
        {
            "current_city": "from Washington to Myrtle Beach",
            "transportation": "Flight Number: F3792603, from Washington to Myrtle Beach",
            "breakfast": "-",
            "attraction": "SkyWheel Myrtle Beach, Myrtle Beach",
            "lunch": "-",
            "dinner": "-",
            "accommodation": "Private Room A, Myrtle Beach",
        },
        {
            "current_city": "Myrtle Beach",
            "transportation": "-",
            "breakfast": "Exotic India, Myrtle Beach",
            "attraction": "Broadway at the Beach, Myrtle Beach",
            "lunch": "Seafood Place, Myrtle Beach",
            "dinner": "Cafe Blue, Myrtle Beach",
            "accommodation": "Private Room A, Myrtle Beach",
        },
        {
            "current_city": "from Myrtle Beach to Washington",
            "transportation": "Flight Number: F3791200, from Myrtle Beach to Washington",
            "breakfast": "-",
            "attraction": "-",
            "lunch": "-",
            "dinner": "-",
            "accommodation": "-",
        },
    ]


def clone_plan(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return copy.deepcopy(plan)
