"""Run every official DEXPI 1.3 example through the unchanged ingestion pipeline, stage by stage.

    uv run python scripts/ingestion_matrix.py

Writes evals/ingestion/matrix.json and evals/ingestion/matrix.md. Deterministic; no model is
used. This shows ingestion and graph-abstraction compatibility only, not answer quality.
"""

from __future__ import annotations

import collections
import json
import re
import warnings
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "data" / "C01V04-VER.EX01.xml", *sorted((ROOT / "data" / "dexpi-1.3-examples").glob("*.xml"))]
SOURCE = "DEXPI e.V. TrainingTestCases, dexpi 1.3/example pids (CC BY 4.0)"
OUT = ROOT / "evals" / "ingestion"


def header(path: Path) -> dict[str, str | None]:
    text = path.read_text(errors="ignore")[:4000]
    tag = re.search(r"<PlantInformation\b[^>]*>", text)
    attrs = dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', tag.group(0))) if tag else {}
    return {"schema_version": attrs.get("SchemaVersion"), "dexpi_version": attrs.get("ApplicationVersion"), "originating_system": attrs.get("OriginatingSystem")}


def profile(path: Path) -> dict:
    from pydexpi.loaders import GraphAbstractor, GraphLoader, ProteusSerializer

    from pid_agent.graph.normalizer import normalize
    from pid_agent.graph.service import GraphService
    from pid_agent.ingestion.dexpi_loader import LoadedPlant

    row: dict = {"file": path.name, "source": SOURCE, **header(path)}
    stages = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            model = ProteusSerializer().load(str(path.parent), path.name)
            stages["parse"] = "ok"
            plant = GraphLoader().parse_dexpi_to_graph(model)
            stages["graph_loader"] = "ok"
            conceptual = GraphAbstractor.build_conceptual_graph(plant)
            stages["graph_abstractor"] = "ok"
            index = normalize(LoadedPlant(path, plant, conceptual))
            stages["normalize"] = "ok"
            GraphService(index)
            stages["graph_service"] = "ok"
        except Exception as exc:  # recorded per stage; the matrix continues with the next file
            failed = next(s for s in ("parse", "graph_loader", "graph_abstractor", "normalize", "graph_service") if s not in stages)
            stages[failed] = f"failed: {type(exc).__name__}: {str(exc)[:160]}"
            row["stages"] = stages
            return row
    row["stages"] = stages
    entities = list(index.entities.values())
    connections = list(index.connections.values())
    topology = [e for e in entities if e.in_topology]
    graph = nx.Graph()
    graph.add_nodes_from(e.id for e in topology)
    graph.add_edges_from((c.source, c.target) for c in connections if c.source and c.target)
    category = collections.Counter(e.category for e in entities)
    dropped = collections.Counter(re.sub(r".*\((\w+)\)\.?$", r"\1", w) for w in index.warnings if w.startswith("Ignored"))
    row.update({
        "plant_nodes": plant.number_of_nodes(), "plant_edges": plant.number_of_edges(),
        "conceptual_nodes": conceptual.number_of_nodes(), "conceptual_edges": conceptual.number_of_edges(),
        "equipment": category["equipment"], "piping_components": category["piping_component"],
        "instrumentation": category["instrumentation"], "lines": category["piping_line"],
        "tagged": sum(1 for e in topology if e.tag), "untagged": sum(1 for e in topology if not e.tag),
        "connected_components": nx.number_connected_components(graph) if graph.number_of_nodes() else 0,
        "connections": dict(collections.Counter(c.connection_type for c in connections)),
        "dropped_links": dict(dropped),
        "warnings": [w for w in index.warnings if not w.startswith("Ignored")],
    })
    return row


def main() -> None:
    rows = [profile(path) for path in FILES]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "matrix.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    ok = sum(1 for r in rows if all(v == "ok" for v in r["stages"].values()) and len(r["stages"]) == 5)
    lines = [
        "# DEXPI ingestion matrix", "",
        f"All {len(rows)} official DEXPI 1.3 example files, run through the unchanged pipeline "
        "(ProteusSerializer -> GraphLoader -> GraphAbstractor -> normalize -> GraphService). "
        f"{ok} of {len(rows)} complete every stage. This shows ingestion compatibility, not answer quality.", "",
        "| File | Proteus | Stages | Plant n/e | Conceptual n/e | Equip. | Piping | Instr. | Lines | Tagged / untagged | Components | Connections | Dropped links |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        stages = "all ok" if all(v == "ok" for v in r["stages"].values()) and len(r["stages"]) == 5 else "; ".join(f"{k}: {v}" for k, v in r["stages"].items() if v != "ok")
        if "plant_nodes" not in r:
            lines.append(f"| {r['file']} | {r['schema_version']} | {stages} |  |  |  |  |  |  |  |  |  |  |")
            continue
        conns = ", ".join(f"{k} {v}" for k, v in sorted(r["connections"].items())) or "none"
        dropped = ", ".join(f"{k} {v}" for k, v in r["dropped_links"].items()) or "none"
        lines.append(f"| {r['file']} | {r['schema_version']} | {stages} | {r['plant_nodes']} / {r['plant_edges']} | {r['conceptual_nodes']} / {r['conceptual_edges']} | {r['equipment']} | {r['piping_components']} | {r['instrumentation']} | {r['lines']} | {r['tagged']} / {r['untagged']} | {r['connected_components']} | {conns} | {dropped} |")
    lines += ["", f"Source: {SOURCE}. C01 is the file at data/C01V04-VER.EX01.xml (identical to the official copy and to the one shipped with pyDEXPI)."]
    (OUT / "matrix.md").write_text("\n".join(lines) + "\n")
    print(f"{ok} of {len(rows)} files complete every stage")
    for r in rows:
        print(r["file"], r["stages"] if any(v != "ok" for v in r["stages"].values()) else "ok", r.get("dropped_links"), r.get("warnings")[:1] if r.get("warnings") else "")


if __name__ == "__main__":
    main()
