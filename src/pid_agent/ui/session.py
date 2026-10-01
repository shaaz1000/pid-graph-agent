"""Builds what the chat interface needs: the loaded graph and the existing agent, unchanged."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pid_agent.agent.tools import GraphTools
from pid_agent.agent.workflow import PidAgent
from pid_agent.config import Settings
from pid_agent.graph.normalizer import normalize
from pid_agent.graph.service import GraphService
from pid_agent.ingestion.dexpi_loader import load_plant
from pid_agent.llm import create_llm
from pid_agent.ui.view_model import graph_facts


@dataclass
class GraphSession:
    tools: GraphTools
    facts: dict[str, Any]


def load_graph(settings: Settings) -> GraphSession:
    loaded = load_plant(settings.data_file)
    service = GraphService(normalize(loaded), settings.max_traversal_depth)
    return GraphSession(GraphTools(service), graph_facts(service, loaded))


def build_agent(settings: Settings, tools: GraphTools) -> PidAgent:
    """Raises ConfigError when the selected provider has no key or model configured."""
    return PidAgent(create_llm(settings), tools)
