"""Normalized, pyDEXPI-independent representations shared by the graph layer and the tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Category = Literal["equipment", "piping_component", "instrumentation", "piping_line"]
Relationship = Literal["piping", "instrumentation"]
ConnectionType = Literal[
    "pipe",
    "direct_piping_connection",
    "open_end",
    "sensing_location",
    "measuring_line",
    "signal_line",
    "operated_valve_reference",
]
SourceGraph = Literal["plant_graph", "conceptual_graph"]
Status = Literal["success", "empty", "not_found", "ambiguous", "error"]


class SubObject(BaseModel):
    """A DEXPI object that belongs to an entity but is not a topology node (nozzle, chamber, ...)."""

    id: str
    type: str
    relation: str
    properties: dict[str, Any] = Field(default_factory=dict)


IdentifierKind = Literal["source_identifier", "derived_identifier", "alias"]


class IdentifierOrigin(BaseModel):
    """How an identifier was obtained.

    * ``source_identifier``  a field of this object, literally present in the DEXPI file
    * ``derived_identifier`` composed by this application from several DEXPI fields
    * ``alias``              a literal field of a *related* DEXPI object that refers to this one
    """

    kind: IdentifierKind
    origin: str


class Entity(BaseModel):
    """A plant item the user can ask about. ``id`` is the stable Proteus ID."""

    id: str
    type: str
    type_hierarchy: list[str]
    category: Category
    tag: str | None = None
    name: str
    identifiers: dict[str, str] = Field(default_factory=dict)
    identifier_origins: dict[str, IdentifierOrigin] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)
    piping_context: dict[str, Any] | None = None
    in_topology: bool = True
    children: list[SubObject] = Field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """Compact form used in list-style results."""
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "category": self.category,
        }
        if self.tag:
            out["tag"] = self.tag
        if self.identifiers:
            out["identifiers"] = self.identifiers
        notes = {
            key: f"{origin.kind}: {origin.origin}"
            for key, origin in self.identifier_origins.items()
            if origin.kind != "source_identifier"
        }
        if notes:
            out["identifier_notes"] = notes
        return out

    def origin_of(self, key: str) -> IdentifierOrigin:
        return self.identifier_origins.get(
            key, IdentifierOrigin(kind="source_identifier", origin=f"DEXPI attribute {key}")
        )


class NozzleRef(BaseModel):
    """Where a pipe attaches to a piece of equipment."""

    id: str
    sub_tag: str | None = None
    chamber_id: str | None = None


class Provenance(BaseModel):
    derived_from: SourceGraph
    present_in_conceptual_graph: bool
    source_object_ids: list[str] = Field(default_factory=list)
    note: str | None = None


class Connection(BaseModel):
    """A directed relationship between two entities.

    For ``relationship == "piping"`` the direction source -> target is the process-flow
    direction (DEXPI sourceItem -> targetItem, i.e. Proteus FromID -> ToID).
    For instrumentation it is the reference/signal direction and says nothing about flow.
    """

    id: str
    source: str | None
    target: str | None
    relationship: Relationship
    connection_type: ConnectionType
    properties: dict[str, Any] = Field(default_factory=dict)
    source_nozzle: NozzleRef | None = None
    target_nozzle: NozzleRef | None = None
    open_end: Literal["source", "target"] | None = None
    provenance: Provenance

    @property
    def is_traversable(self) -> bool:
        return self.source is not None and self.target is not None


class Evidence(BaseModel):
    """One graph fact, with enough provenance to trace it back to DEXPI objects."""

    kind: Literal["entity", "connection", "property", "path", "open_end", "boundary", "derived"]
    id: str
    fact: dict[str, Any]
    source_graph: SourceGraph
    source_object_ids: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    """Common envelope returned by every graph tool."""

    tool: str
    status: Status
    input: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    entities: list[dict[str, Any]] = Field(default_factory=list)
    connections: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[dict[str, Any]] = Field(default_factory=list)
    # Places where a traversal deliberately did not continue (e.g. between the chambers of
    # an exchanger). Graph-derived facts; the matching text in ``warnings`` is only prose.
    boundaries: list[dict[str, Any]] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    # Facts computed by a graph algorithm (a boundary, a chain, a run of a line): each row is a
    # typed fact with the operation and the graph objects it was computed from.
    derived: list[dict[str, Any]] = Field(default_factory=list)
    resolution: dict[str, Any] | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
