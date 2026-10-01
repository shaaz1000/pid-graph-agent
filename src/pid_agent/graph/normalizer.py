"""Turn the raw pyDEXPI graphs into normalized entities and connections.

Authority rules (established by inspecting C01, see README):

* Topology comes from the conceptual graph. Its piping edges run DEXPI
  sourceItem -> targetItem (Proteus FromID -> ToID), which is the process-flow direction.
* Piping attributes on conceptual *edges* are trustworthy; piping attributes copied onto
  conceptual *nodes* are not (first writer wins during abstraction), so entity properties
  and line context are always re-read from the plant graph.
* Pipes with a missing end are dropped by GraphAbstractor. They are recovered from the
  plant graph and kept clearly separate as ``open_end`` connections.
* NetworkX node ids are random per load. Public ids are Proteus ids, or a deterministic
  path below the owning object when a node has none.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from pid_agent.errors import GraphNormalizationError
from pid_agent.ingestion.dexpi_loader import LoadedPlant
from pid_agent.models import (
    Category,
    Connection,
    ConnectionType,
    Entity,
    IdentifierOrigin,
    NozzleRef,
    Provenance,
    SubObject,
)

logger = logging.getLogger(__name__)

PIPING_CONNECTION_LABELS = {"Pipe": "pipe", "DirectPipingConnection": "direct_piping_connection"}
INSTRUMENTATION_EDGE_TYPES: dict[str, ConnectionType] = {
    "MeasuringLineFunction": "measuring_line",
    "SignalConveyingFunction": "signal_line",
    "OperatedValveReference": "operated_valve_reference",
}
# Attributes added by GraphLoader / GraphAbstractor that are bookkeeping, not plant facts.
BOOKKEEPING_KEYS = {
    "label",
    "labels",
    "label_description",
    "proteusId",
    "attr_name",
    "collapsed_from",
    "collapsed_node_id",
    "stitched_from",
}
# Abstract mixins in the DEXPI class hierarchy that say nothing useful about an item's type.
MIXIN_SUFFIXES = ("Owner", "Structure", "Item")
IDENTIFIER_FIELDS = (
    "tagName",
    "positionNumber",
    "pipingComponentName",
    "pipingComponentNumber",
    "processInstrumentationFunctionNumber",
    "processSignalGeneratingFunctionNumber",
    "actuatingFunctionNumber",
    "actuatingSystemNumber",
    "instrumentationLoopFunctionNumber",
    "subTagName",
    "lineNumber",
)
NAME_FIELDS = (
    "tagName",
    "positionNumber",
    "actuatingFunctionNumber",
    "processSignalGeneratingFunctionNumber",
)


@dataclass(frozen=True)
class ObjectRecord:
    """Any addressable DEXPI object (entity or not), keyed by public id."""

    id: str
    type: str
    properties: dict[str, Any]
    owner_entity_id: str | None = None


@dataclass
class PlantIndex:
    """Everything the graph service needs, free of pyDEXPI internals."""

    entities: dict[str, Entity] = field(default_factory=dict)
    connections: dict[str, Connection] = field(default_factory=dict)
    objects: dict[str, ObjectRecord] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def clean_attributes(attrs: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in attrs.items() if k not in BOOKKEEPING_KEYS}


def type_hierarchy(labels: str) -> list[str]:
    return [name for name in labels.split(":") if name and not name.endswith(MIXIN_SUFFIXES)]


class _Normalizer:
    def __init__(self, loaded: LoadedPlant) -> None:
        self.plant = loaded.plant_graph
        self.conceptual = loaded.conceptual_graph
        self.index = PlantIndex()
        self._public_ids: dict[str, str] = {}
        self._segment_info: dict[str, dict[str, Any]] = {}
        self._collapsed_edge_nodes = {
            data["collapsed_node_id"]
            for *_, data in self.conceptual.edges(data=True)
            if "collapsed_node_id" in data
        }

    # ------------------------------------------------------------------ ids
    def public_id(self, node: str) -> str:
        """Stable id: the Proteus id, else ``<owner id>/<attribute>/<n>`` (1-based)."""
        if node in self._public_ids:
            return self._public_ids[node]
        data = self.plant.nodes[node]
        if data.get("proteusId"):
            result = data["proteusId"]
        else:
            result = data["label"]
            for parent, _, edge in self.plant.in_edges(node, data=True):
                if edge["label"] != "composition":
                    continue
                siblings = [
                    child
                    for _, child, e in self.plant.out_edges(parent, data=True)
                    if e["label"] == "composition" and e["attr_name"] == edge["attr_name"]
                ]
                position = siblings.index(node) + 1
                result = f"{self.public_id(parent)}/{edge['attr_name']}/{position}"
                break
        self._public_ids[node] = result
        return result

    # -------------------------------------------------------------- helpers
    def _out(self, node: str, attr_name: str) -> list[str]:
        return [
            target
            for _, target, e in self.plant.out_edges(node, data=True)
            if e["attr_name"] == attr_name
        ]

    def _in(self, node: str, attr_name: str) -> list[str]:
        return [
            source
            for source, _, e in self.plant.in_edges(node, data=True)
            if e["attr_name"] == attr_name
        ]

    def _label(self, node: str) -> str:
        return self.plant.nodes[node]["label"]

    def _nozzle_ref(self, node: str | None) -> NozzleRef | None:
        if node is None or self._label(node) != "Nozzle":
            return None
        chambers = self._out(node, "chamber")
        return NozzleRef(
            id=self.public_id(node),
            sub_tag=self.plant.nodes[node].get("subTagName"),
            chamber_id=self.public_id(chambers[0]) if chambers else None,
        )

    def _owning_entity(self, node: str | None) -> str | None:
        """Map a pipe end (nozzle or component) to the conceptual entity it belongs to."""
        if node is None:
            return None
        if node in self.conceptual:
            return self.public_id(node)
        owners = self._in(node, "nozzles")
        if owners and owners[0] in self.conceptual:
            return self.public_id(owners[0])
        return None

    # ------------------------------------------------------------- segments
    def _collect_segments(self) -> None:
        for node, data in self.plant.nodes(data=True):
            if data["label"] != "PipingNetworkSegment":
                continue
            systems = self._in(node, "segments")
            system_attrs = clean_attributes(self.plant.nodes[systems[0]]) if systems else {}
            # Same precedence GraphAbstractor uses: segment values override line values.
            properties = {**system_attrs, **clean_attributes(data)}
            self._segment_info[node] = {
                "segment_id": self.public_id(node),
                "system_id": self.public_id(systems[0]) if systems else None,
                "properties": properties,
            }

    def _segment_of(self, node: str, attr_name: str) -> dict[str, Any] | None:
        owners = self._in(node, attr_name)
        return self._segment_info.get(owners[0]) if owners else None

    # ------------------------------------------------------------- entities
    def _category(self, node: str, hierarchy: list[str]) -> Category:
        if "Equipment" in hierarchy:
            return "equipment"
        if self._in(node, "items"):
            return "piping_component"
        return "instrumentation"

    def _children(self, node: str) -> list[SubObject]:
        children: list[SubObject] = []
        seen = {node}
        stack = [node]
        while stack:
            current = stack.pop(0)
            for _, child, edge in self.plant.out_edges(current, data=True):
                if edge["label"] != "composition" or child in seen:
                    continue
                seen.add(child)
                skip = (
                    child in self.conceptual
                    or child in self._collapsed_edge_nodes
                    or self._label(child) == "PipingNode"
                )
                if skip:
                    continue
                children.append(self._sub_object(child, edge["attr_name"]))
                stack.append(child)
        merged = self.conceptual.nodes[node].get("collapsed_from", "")
        for other in filter(None, merged.split(",")):
            if other in seen or other not in self.plant:
                continue
            if self._label(other) in ("PipingNetworkSegment", "PipingNetworkSystem"):
                continue
            seen.add(other)
            children.append(self._sub_object(other, "associated"))
        return children

    def _sub_object(self, node: str, relation: str) -> SubObject:
        properties = clean_attributes(self.plant.nodes[node])
        if self._label(node) == "Nozzle":
            chambers = self._out(node, "chamber")
            if chambers:
                properties["chamber"] = self.public_id(chambers[0])
        return SubObject(
            id=self.public_id(node), type=self._label(node), relation=relation, properties=properties
        )

    def _piping_context(self, node: str) -> dict[str, Any] | None:
        info = self._segment_of(node, "items")
        if info is None:
            return None
        return {"segment_id": info["segment_id"], "line_id": info["system_id"], **info["properties"]}

    def _build_entities(self) -> None:
        for node in self.conceptual.nodes:
            data = self.plant.nodes[node]
            hierarchy = type_hierarchy(data["labels"])
            properties = clean_attributes(data)
            children = self._children(node)
            context = self._piping_context(node)
            identifiers = {k: str(properties[k]) for k in IDENTIFIER_FIELDS if properties.get(k)}
            origins: dict[str, IdentifierOrigin] = {}
            for child in children:
                for key in IDENTIFIER_FIELDS:
                    if child.relation == "associated" and child.properties.get(key):
                        name = f"{child.type}.{key}"
                        identifiers[name] = str(child.properties[key])
                        origins[name] = IdentifierOrigin(
                            kind="alias",
                            origin=f"attribute {key} of the associated {child.type} {child.id}",
                        )
            line = (context or {}).get("lineNumber")
            component_number = properties.get("pipingComponentNumber")
            if line and component_number:
                identifiers["lineComponent"] = f"{line}/{component_number}"
                origins["lineComponent"] = IdentifierOrigin(
                    kind="derived_identifier",
                    origin=(
                        f"composed from lineNumber of the owning line {context['line_id']} "
                        "and this item's pipingComponentNumber"
                    ),
                )
            category_code = properties.get("processInstrumentationFunctionCategory")
            number = properties.get("processInstrumentationFunctionNumber")
            if category_code and number:
                functions = properties.get("processInstrumentationFunctions", "")
                identifiers["instrumentTag"] = f"{category_code}{functions}{number}"
                origins["instrumentTag"] = IdentifierOrigin(
                    kind="derived_identifier",
                    origin=(
                        "composed from processInstrumentationFunctionCategory + "
                        "processInstrumentationFunctions + processInstrumentationFunctionNumber"
                    ),
                )
            entity_id = self.public_id(node)
            self.index.entities[entity_id] = Entity(
                id=entity_id,
                type=data["label"],
                type_hierarchy=hierarchy,
                category=self._category(node, hierarchy),
                tag=properties.get("tagName"),
                name=self._name(entity_id, data["label"], properties, identifiers),
                identifiers=identifiers,
                identifier_origins=origins,
                properties=properties,
                piping_context=context,
                children=children,
            )

    @staticmethod
    def _name(entity_id: str, label: str, properties: dict, identifiers: dict) -> str:
        for key in NAME_FIELDS:
            if properties.get(key):
                return str(properties[key])
        for key in ("instrumentTag", "lineComponent"):
            if key in identifiers:
                return f"{label} {identifiers[key]}"
        return entity_id

    def _build_lines(self) -> None:
        """Piping lines (PipingNetworkSystem) are addressable but are not topology nodes."""
        for node, data in self.plant.nodes(data=True):
            if data["label"] != "PipingNetworkSystem":
                continue
            properties = clean_attributes(data)
            segments = []
            for segment in self._out(node, "segments"):
                segment_props = clean_attributes(self.plant.nodes[segment])
                segment_props["items"] = [self.public_id(n) for n in self._out(segment, "items")]
                segment_props["connections"] = [
                    self.public_id(n) for n in self._out(segment, "connections")
                ]
                segments.append(
                    SubObject(
                        id=self.public_id(segment),
                        type="PipingNetworkSegment",
                        relation="segments",
                        properties=segment_props,
                    )
                )
            entity_id = self.public_id(node)
            line_number = properties.get("lineNumber")
            self.index.entities[entity_id] = Entity(
                id=entity_id,
                type="PipingNetworkSystem",
                type_hierarchy=["PipingNetworkSystem", "PipingLine"],
                category="piping_line",
                name=f"Line {line_number}" if line_number else entity_id,
                identifiers={"lineNumber": str(line_number)} if line_number else {},
                properties=properties,
                in_topology=False,
                children=segments,
            )

    # ---------------------------------------------------------- connections
    def _piping_connection(self, pipe: str, in_conceptual: bool) -> Connection:
        info = self._segment_of(pipe, "connections")
        if info is None:
            raise GraphNormalizationError(f"Piping connection {pipe} has no owning segment.")
        sources = self._out(pipe, "sourceItem")
        targets = self._out(pipe, "targetItem")
        source_item = sources[0] if sources else None
        target_item = targets[0] if targets else None
        source = self._owning_entity(source_item)
        target = self._owning_entity(target_item)
        open_end = None if source and target else ("source" if source is None else "target")
        connection_type: ConnectionType = (
            "open_end" if open_end else PIPING_CONNECTION_LABELS[self._label(pipe)]  # type: ignore[assignment]
        )
        note = None
        if open_end:
            note = (
                f"This pipe exists in the DEXPI model but has no {open_end} item on this "
                "drawing, so pyDEXPI's conceptual graph omits it. Where it "
                f"{'comes from' if open_end == 'source' else 'leads'} is not represented."
            )
        connection_id = self.public_id(pipe)
        return Connection(
            id=connection_id,
            source=source,
            target=target,
            relationship="piping",
            connection_type=connection_type,
            properties=dict(info["properties"]),
            source_nozzle=self._nozzle_ref(source_item),
            target_nozzle=self._nozzle_ref(target_item),
            open_end=open_end,
            provenance=Provenance(
                derived_from="conceptual_graph" if in_conceptual else "plant_graph",
                present_in_conceptual_graph=in_conceptual,
                source_object_ids=[
                    i for i in (connection_id, info["segment_id"], info["system_id"]) if i
                ],
                note=note,
            ),
        )

    def _build_piping_connections(self) -> None:
        for source, target, data in self.conceptual.edges(data=True):
            if data.get("label") not in PIPING_CONNECTION_LABELS:
                continue
            pipe = data["collapsed_node_id"]
            connection = self._piping_connection(pipe, in_conceptual=True)
            expected = (self.public_id(source), self.public_id(target))
            if (connection.source, connection.target) != expected:
                raise GraphNormalizationError(
                    f"Conceptual edge {expected} disagrees with plant pipe {connection.id}."
                )
            # The conceptual edge is the topology authority; its attributes were verified
            # against the plant segments and are used as the connection properties.
            connection.properties = {"segment_id": data.get("proteusId"), **clean_attributes(data)}
            self.index.connections[connection.id] = connection

        for node, data in self.plant.nodes(data=True):
            if data["label"] in PIPING_CONNECTION_LABELS and node not in self._collapsed_edge_nodes:
                connection = self._piping_connection(node, in_conceptual=False)
                segment_id = connection.provenance.source_object_ids[1]
                connection.properties = {"segment_id": segment_id, **connection.properties}
                self.index.connections[connection.id] = connection

    def _build_instrumentation_connections(self) -> None:
        for source, target, data in self.conceptual.edges(data=True):
            label = data.get("label")
            if label in PIPING_CONNECTION_LABELS:
                continue
            source_id, target_id = self.public_id(source), self.public_id(target)
            target_nozzle = None
            source_objects = [source_id, target_id]
            if label == "reference" and data.get("attr_name") == "sensingLocation":
                connection_type: ConnectionType = "sensing_location"
                connection_id = f"{source_id}/sensingLocation"
                stitched = data.get("stitched_from")
                if stitched in self.plant:
                    target_nozzle = self._nozzle_ref(stitched)
                    source_objects.append(self.public_id(stitched))
            elif label in INSTRUMENTATION_EDGE_TYPES:
                connection_type = INSTRUMENTATION_EDGE_TYPES[label]
                connection_id = data.get("proteusId") or f"{source_id}/{label}/{target_id}"
                source_objects.insert(0, connection_id)
            else:
                message = f"Ignored unrecognised conceptual edge {source_id} -> {target_id} ({label})."
                logger.warning(message)
                self.index.warnings.append(message)
                continue
            properties = clean_attributes(data)
            self.index.connections[connection_id] = Connection(
                id=connection_id,
                source=source_id,
                target=target_id,
                relationship="instrumentation",
                connection_type=connection_type,
                properties=properties,
                target_nozzle=target_nozzle,
                provenance=Provenance(
                    derived_from="conceptual_graph",
                    present_in_conceptual_graph=True,
                    source_object_ids=source_objects,
                ),
            )
            if connection_type == "operated_valve_reference" and properties.get("subTagName"):
                valve = self.index.entities[target_id]
                valve.identifiers["operatedValveReference"] = str(properties["subTagName"])
                valve.identifier_origins["operatedValveReference"] = IdentifierOrigin(
                    kind="alias",
                    origin=f"subTagName of {connection_id}, which references this valve",
                )

    # -------------------------------------------------------------- objects
    def _build_objects(self) -> None:
        owners: dict[str, str] = {}
        for entity in self.index.entities.values():
            for child in entity.children:
                owners.setdefault(child.id, entity.id)
        for node, data in self.plant.nodes(data=True):
            if data["label"] in ("ConceptualModel", "PipingNode"):
                continue
            object_id = self.public_id(node)
            self.index.objects[object_id] = ObjectRecord(
                id=object_id,
                type=data["label"],
                properties=clean_attributes(data),
                owner_entity_id=owners.get(object_id),
            )

    def run(self) -> PlantIndex:
        self._collect_segments()
        self._build_entities()
        self._build_lines()
        self._build_piping_connections()
        self._build_instrumentation_connections()
        self._build_objects()
        return self.index


def normalize(loaded: LoadedPlant) -> PlantIndex:
    """Build the normalized index for one loaded P&ID."""
    index = _Normalizer(loaded).run()
    logger.info(
        "normalized entities=%d connections=%d open_ends=%d",
        len(index.entities),
        len(index.connections),
        sum(1 for c in index.connections.values() if c.open_end),
    )
    return index
