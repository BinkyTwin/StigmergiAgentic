"""Unit tests for TravelPlanner workspace wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.travelplanner.workspace import TravelPlannerWorkspace
from travelplanner_data import sample_query_rows, write_sample_database


@pytest.fixture
def workspace(tmp_path: Path) -> TravelPlannerWorkspace:
    database_root = write_sample_database(tmp_path / "database")
    return TravelPlannerWorkspace(
        database_root=database_root,
        dataset_split="validation",
        query_rows=sample_query_rows(),
    )


def test_list_targets_returns_expected_types(workspace: TravelPlannerWorkspace) -> None:
    assert workspace.list_targets() == [
        "flights",
        "hotels",
        "restaurants",
        "attractions",
        "distances",
    ]


def test_search_flights_filters_origin_destination_date(
    workspace: TravelPlannerWorkspace,
) -> None:
    frame = workspace.search_flights("Washington", "Myrtle Beach", "2022-03-13")
    assert len(frame) == 1
    assert str(frame.iloc[0]["Flight Number"]) == "F3792603"


def test_search_hotels_filters_city(workspace: TravelPlannerWorkspace) -> None:
    frame = workspace.search_hotels("Myrtle Beach")
    assert len(frame) == 2
    assert "Private Room A" in set(frame["NAME"].astype(str))


def test_search_restaurants_filters_city(workspace: TravelPlannerWorkspace) -> None:
    frame = workspace.search_restaurants("Myrtle Beach")
    assert len(frame) == 5
    assert "Exotic India" in set(frame["Name"].astype(str))


def test_search_attractions_filters_city(workspace: TravelPlannerWorkspace) -> None:
    frame = workspace.search_attractions("Myrtle Beach")
    assert len(frame) == 2
    assert "SkyWheel Myrtle Beach" in set(frame["Name"].astype(str))


def test_get_distances_returns_directional_row(workspace: TravelPlannerWorkspace) -> None:
    frame = workspace.get_distances("Washington", "Myrtle Beach")
    assert len(frame) == 1
    assert str(frame.iloc[0]["distance"]) == "693 km"


def test_get_query_parses_constraints_and_dates(workspace: TravelPlannerWorkspace) -> None:
    query = workspace.get_query(0)
    assert query["query_idx"] == 0
    assert query["org"] == "Washington"
    assert query["dest"] == "Myrtle Beach"
    assert query["date"] == ["2022-03-13", "2022-03-14", "2022-03-15"]
    assert isinstance(query["local_constraint"], dict)


def test_get_context_summary_includes_current_query_fields(
    workspace: TravelPlannerWorkspace,
) -> None:
    workspace.get_query(0)
    summary = workspace.get_context_summary()
    assert "TravelPlanner Query Context" in summary
    assert "origin: Washington" in summary
    assert "destination: Myrtle Beach" in summary


def test_missing_database_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        TravelPlannerWorkspace(database_root=tmp_path / "missing")


def test_get_query_out_of_range_raises(workspace: TravelPlannerWorkspace) -> None:
    with pytest.raises(IndexError):
        workspace.get_query(99)
