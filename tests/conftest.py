"""Shared fixtures. The C01 reference P&ID is loaded once per test session."""

from __future__ import annotations

import pytest

from pid_agent.agent.tools import GraphTools
from pid_agent.config import DEFAULT_DATA_FILE
from pid_agent.graph.normalizer import PlantIndex, normalize
from pid_agent.graph.service import GraphService
from pid_agent.ingestion.dexpi_loader import LoadedPlant, load_plant


@pytest.fixture(scope="session")
def loaded() -> LoadedPlant:
    return load_plant(DEFAULT_DATA_FILE)


@pytest.fixture(scope="session")
def index(loaded: LoadedPlant) -> PlantIndex:
    return normalize(loaded)


@pytest.fixture(scope="session")
def service(index: PlantIndex) -> GraphService:
    return GraphService(index)


@pytest.fixture(scope="session")
def tools(service: GraphService) -> GraphTools:
    return GraphTools(service)


def ids(result) -> list[str]:
    return [e["id"] for e in result.entities]
