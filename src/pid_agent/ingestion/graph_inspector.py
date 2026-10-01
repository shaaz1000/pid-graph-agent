"""Print a structural summary of the pyDEXPI graphs.

    uv run python -m pid_agent.ingestion.graph_inspector
"""

from __future__ import annotations

from collections import Counter

import networkx as nx

from pid_agent.config import load_settings
from pid_agent.ingestion.dexpi_loader import load_plant


def summarize(graph: nx.MultiDiGraph) -> dict:
    return {
        "type": type(graph).__name__,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "weakly_connected_components": nx.number_weakly_connected_components(graph),
        "node_labels": dict(Counter(d.get("label") for _, d in graph.nodes(data=True))),
        "edge_labels": dict(Counter(d.get("label") for *_, d in graph.edges(data=True))),
    }


def main() -> None:
    plant = load_plant(load_settings().data_file)
    for name, graph in (("plant", plant.plant_graph), ("conceptual", plant.conceptual_graph)):
        info = summarize(graph)
        print(f"== {name}: {info['type']} nodes={info['nodes']} edges={info['edges']} "
              f"components={info['weakly_connected_components']}")
        print("   node labels:", info["node_labels"])
        print("   edge labels:", info["edge_labels"])


if __name__ == "__main__":
    main()
