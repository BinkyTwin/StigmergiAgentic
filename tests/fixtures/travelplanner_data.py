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
        {
            "org": "Washington",
            "dest": "South Carolina",
            "days": 7,
            "visiting_city_number": 3,
            "date": (
                "['2022-03-13', '2022-03-14', '2022-03-15', "
                "'2022-03-16', '2022-03-17', '2022-03-18', '2022-03-19']"
            ),
            "people_number": 1,
            "local_constraint": "{'house rule': None, 'cuisine': None, 'room type': None, 'transportation': None}",
            "budget": 3500,
            "query": (
                "Please create a 7-day travel plan from Washington covering "
                "3 cities in South Carolina."
            ),
            "level": "medium",
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
            {
                "Flight Number": "F4001001",
                "Price": 110,
                "DepTime": "08:15",
                "ArrTime": "09:05",
                "ActualElapsedTime": "50 minutes",
                "FlightDate": "2022-03-15",
                "OriginCityName": "Myrtle Beach",
                "DestCityName": "Charleston",
                "Distance": 95.0,
            },
            {
                "Flight Number": "F4001002",
                "Price": 118,
                "DepTime": "09:40",
                "ArrTime": "10:30",
                "ActualElapsedTime": "50 minutes",
                "FlightDate": "2022-03-17",
                "OriginCityName": "Charleston",
                "DestCityName": "Greenville",
                "Distance": 203.0,
            },
            {
                "Flight Number": "F4001003",
                "Price": 142,
                "DepTime": "17:20",
                "ArrTime": "18:40",
                "ActualElapsedTime": "1 hours 20 minutes",
                "FlightDate": "2022-03-19",
                "OriginCityName": "Greenville",
                "DestCityName": "Washington",
                "Distance": 408.0,
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
            {
                "NAME": "Charleston Loft",
                "price": 150.0,
                "room type": "Private room",
                "house_rules": "No smoking",
                "minimum nights": 1,
                "maximum occupancy": 2,
                "review rate number": 4.7,
                "city": "Charleston",
            },
            {
                "NAME": "Greenville Retreat",
                "price": 130.0,
                "room type": "Private room",
                "house_rules": "No parties",
                "minimum nights": 1,
                "maximum occupancy": 2,
                "review rate number": 4.5,
                "city": "Greenville",
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
            {
                "Name": "Charleston Grill",
                "Average Cost": 52,
                "Cuisines": "American",
                "Aggregate Rating": 4.6,
                "City": "Charleston",
            },
            {
                "Name": "Greenville Bistro",
                "Average Cost": 36,
                "Cuisines": "French",
                "Aggregate Rating": 4.4,
                "City": "Greenville",
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
            {
                "Name": "Charleston City Market",
                "Latitude": 32.781153,
                "Longitude": -79.931602,
                "Address": "188 Meeting St",
                "Phone": "(843) 937-0920",
                "Website": "https://thecharlestoncitymarket.com/",
                "City": "Charleston",
            },
            {
                "Name": "Falls Park on the Reedy",
                "Latitude": 34.844458,
                "Longitude": -82.401171,
                "Address": "601 S Main St",
                "Phone": "(864) 467-4350",
                "Website": "https://www.greenvillesc.gov/parks/falls-park",
                "City": "Greenville",
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
            {
                "origin": "Myrtle Beach",
                "destination": "Charleston",
                "cost": 8,
                "duration": "2 hours 5 mins",
                "distance": "157 km",
            },
            {
                "origin": "Charleston",
                "destination": "Greenville",
                "cost": 11,
                "duration": "3 hours 10 mins",
                "distance": "344 km",
            },
            {
                "origin": "Greenville",
                "destination": "Washington",
                "cost": 20,
                "duration": "7 hours 54 mins",
                "distance": "822 km",
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
        "Myrtle Beach\tSouth Carolina\n"
        "Charleston\tSouth Carolina\n"
        "Greenville\tSouth Carolina",
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
