"""Cycle-safe, depth-bounded traversal of the process-flow graph.

Only traversable piping connections are part of the flow graph. Instrumentation and
open-ended connections never are.

Chamber rule: when a path enters equipment through a nozzle that belongs to one chamber,
it may only leave through nozzles of the same chamber (or nozzles with no chamber
recorded). This stops a path from jumping between the two sides of a heat exchanger.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Literal

from pid_agent.models import Connection

Direction = Literal["downstream", "upstream", "both"]
DIRECTIONS: tuple[str, ...] = ("downstream", "upstream", "both")
State = tuple[str, str | None]  # (entity id, chamber the path is in)


@dataclass(frozen=True)
class Step:
    connection_id: str
    from_id: str
    to_id: str
    with_flow: bool


@dataclass(frozen=True)
class Reach:
    entity_id: str
    distance: int
    steps: tuple[Step, ...]

    @property
    def entity_path(self) -> list[str]:
        return [self.steps[0].from_id, *[s.to_id for s in self.steps]] if self.steps else [self.entity_id]

    @property
    def connection_path(self) -> list[str]:
        return [s.connection_id for s in self.steps]


@dataclass
class TraversalOutcome:
    start: str
    reached: dict[str, Reach] = field(default_factory=dict)
    states: set[State] = field(default_factory=set)
    cycle_detected: bool = False
    returns_to_start: bool = False
    truncated: bool = False
    # Entities at the depth limit from which the graph continues: not ends, just unexplored.
    frontier: set[str] = field(default_factory=set)
    stopped_at: list[str] = field(default_factory=list)
    chamber_skips: list[tuple[str, str, str, str]] = field(default_factory=list)
    # Blocked entities the search ran into (and did not pass).
    blocked_at: list[str] = field(default_factory=list)

    @property
    def visited_count(self) -> int:
        return len({node for node, _ in self.states})

    def chambers_at(self, entity_id: str) -> set[str | None]:
        return {chamber for node, chamber in self.states if node == entity_id}


def nozzle_chamber(connection: Connection, entity_id: str, as_source: bool) -> str | None:
    nozzle = connection.source_nozzle if as_source else connection.target_nozzle
    return nozzle.chamber_id if nozzle else None


class FlowGraph:
    def __init__(self, connections: Iterable[Connection]) -> None:
        self._out: dict[str, list[Connection]] = {}
        self._in: dict[str, list[Connection]] = {}
        for connection in connections:
            if connection.relationship != "piping" or not connection.is_traversable:
                continue
            self._out.setdefault(connection.source, []).append(connection)  # type: ignore[arg-type]
            self._in.setdefault(connection.target, []).append(connection)  # type: ignore[arg-type]

    def __contains__(self, entity_id: str) -> bool:
        return entity_id in self._out or entity_id in self._in

    def _moves(self, entity_id: str, direction: Direction) -> list[tuple[Connection, bool]]:
        """Connections leaving ``entity_id`` in the travel direction, with a with-flow flag."""
        moves: list[tuple[Connection, bool]] = []
        if direction in ("downstream", "both"):
            moves += [(c, True) for c in self._out.get(entity_id, [])]
        if direction in ("upstream", "both"):
            moves += [(c, False) for c in self._in.get(entity_id, [])]
        return moves

    def has_moves(self, entity_id: str, direction: Direction) -> bool:
        """Whether any drawn connection continues from ``entity_id`` in the travel direction."""
        return bool(self._moves(entity_id, direction))

    def bfs(
        self,
        start: str,
        direction: Direction,
        max_depth: int,
        stop_at: Callable[[str], bool] | None = None,
        blocked: frozenset[str] = frozenset(),
    ) -> TraversalOutcome:
        """``blocked`` entities are treated as closed: no path enters or passes them."""
        outcome = TraversalOutcome(start=start)
        start_state: State = (start, None)
        outcome.states.add(start_state)
        parents: dict[State, tuple[State, Step]] = {}
        depth: dict[State, int] = {start_state: 0}
        queue: deque[State] = deque([start_state])
        is_start = True

        while queue:
            state = queue.popleft()
            node, chamber = state
            if not is_start and stop_at is not None and stop_at(node):
                if node not in outcome.stopped_at:
                    outcome.stopped_at.append(node)
                continue
            for connection, with_flow in self._moves(node, direction):
                exit_chamber = nozzle_chamber(connection, node, as_source=with_flow)
                if not is_start and chamber and exit_chamber and chamber != exit_chamber:
                    outcome.chamber_skips.append((node, chamber, exit_chamber, connection.id))
                    continue
                neighbour = connection.target if with_flow else connection.source
                assert neighbour is not None
                if neighbour in blocked:
                    if neighbour not in outcome.blocked_at:
                        outcome.blocked_at.append(neighbour)
                    continue
                next_state: State = (neighbour, nozzle_chamber(connection, neighbour, not with_flow))
                if next_state in outcome.states:
                    if direction != "both":
                        outcome.cycle_detected = True
                        outcome.returns_to_start |= neighbour == start
                    continue
                if depth[state] >= max_depth:
                    outcome.truncated = True
                    outcome.frontier.add(node)
                    continue
                outcome.states.add(next_state)
                depth[next_state] = depth[state] + 1
                step = Step(connection.id, node, neighbour, with_flow)
                parents[next_state] = (state, step)
                if neighbour != start and neighbour not in outcome.reached:
                    outcome.reached[neighbour] = Reach(
                        neighbour, depth[next_state], self._steps(parents, next_state)
                    )
                elif neighbour == start and direction != "both":
                    outcome.cycle_detected = True
                    outcome.returns_to_start = True
                queue.append(next_state)
            is_start = False
        return outcome

    @staticmethod
    def _steps(parents: dict[State, tuple[State, Step]], state: State) -> tuple[Step, ...]:
        steps: list[Step] = []
        while state in parents:
            state, step = parents[state]
            steps.append(step)
        return tuple(reversed(steps))

    def simple_paths(self, start: str, target: str, direction: Direction, max_length: int, limit: int, blocked: frozenset[str] = frozenset()) -> tuple[list[tuple[Step, ...]], bool]:
        """Every route from ``start`` to ``target`` that visits no entity twice, shortest first.

        The chamber rule applies as in ``bfs``; ``blocked`` entities are never entered. Returns
        the routes and whether the search was cut short by ``limit``.
        """
        found: list[tuple[Step, ...]] = []
        truncated = False

        def walk(node: str, chamber: str | None, steps: tuple[Step, ...], visited: frozenset[str]) -> None:
            nonlocal truncated
            if len(found) >= limit:
                truncated = True
                return
            if node == target:
                found.append(steps)
                return
            if len(steps) >= max_length:
                return
            for connection, with_flow in self._moves(node, direction):
                exit_chamber = nozzle_chamber(connection, node, as_source=with_flow)
                if steps and chamber and exit_chamber and chamber != exit_chamber:
                    continue
                neighbour = connection.target if with_flow else connection.source
                assert neighbour is not None
                if neighbour in visited or neighbour in blocked:
                    continue
                walk(neighbour, nozzle_chamber(connection, neighbour, not with_flow), (*steps, Step(connection.id, node, neighbour, with_flow)), visited | {neighbour})

        walk(start, None, (), frozenset({start}))
        return sorted(found, key=len), truncated
