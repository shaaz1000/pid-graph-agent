"""Load a Proteus XML P&ID through pyDEXPI into NetworkX graphs.

    XML -> ProteusSerializer -> DEXPI model -> GraphLoader -> plant graph
                                                 GraphAbstractor -> conceptual graph
"""

from __future__ import annotations

import logging
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from pid_agent.errors import DataFileNotFoundError, DexpiParseError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedPlant:
    """The pyDEXPI artefacts for one P&ID file."""

    source_file: Path
    plant_graph: nx.MultiDiGraph
    conceptual_graph: nx.MultiDiGraph


def load_plant(xml_file: Path | str) -> LoadedPlant:
    """Parse ``xml_file`` and build the plant and conceptual graphs.

    Raises
    ------
    DataFileNotFoundError
        If the file does not exist.
    DexpiParseError
        If pyDEXPI cannot turn the file into a non-empty graph.
    """
    path = Path(xml_file)
    if not path.is_file():
        raise DataFileNotFoundError(f"P&ID file not found: {path}")

    # Imported lazily so that a missing file is reported before the heavy import.
    from pydexpi.loaders import GraphAbstractor, GraphLoader, ProteusSerializer

    started = time.perf_counter()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ProteusSerializer().load(str(path.parent), path.name)
            plant_graph = GraphLoader().parse_dexpi_to_graph(model)
            conceptual_graph = GraphAbstractor.build_conceptual_graph(plant_graph)
    except Exception as exc:  # pyDEXPI raises a variety of types for bad input
        raise DexpiParseError(f"Could not parse {path.name} as a DEXPI/Proteus P&ID: {exc}") from exc

    if plant_graph.number_of_nodes() == 0 or conceptual_graph.number_of_nodes() == 0:
        raise DexpiParseError(f"{path.name} produced an empty graph.")

    logger.info(
        "loaded_plant file=%s plant_nodes=%d plant_edges=%d conceptual_nodes=%d "
        "conceptual_edges=%d duration_ms=%.0f",
        path.name,
        plant_graph.number_of_nodes(),
        plant_graph.number_of_edges(),
        conceptual_graph.number_of_nodes(),
        conceptual_graph.number_of_edges(),
        (time.perf_counter() - started) * 1000,
    )
    return LoadedPlant(path, plant_graph, conceptual_graph)
