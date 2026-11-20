"""Pydantic data models for Sanket.

Single source of truth for all core data contracts:
Octants, Bearings, Labels, Nodes, Edges, Venues, Board Entries,
Distractors, Knobs, Scenes, Receipts, and Tasks.
"""

from typing import Literal, Self

import networkx as nx
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Octant = Literal[
    "AHEAD",
    "AHEAD_RIGHT",
    "RIGHT",
    "BACK_RIGHT",
    "BACK",
    "BACK_LEFT",
    "LEFT",
    "AHEAD_LEFT",
]

Answer = Literal[
    "AHEAD",
    "AHEAD_RIGHT",
    "RIGHT",
    "BACK_RIGHT",
    "BACK",
    "BACK_LEFT",
    "LEFT",
    "AHEAD_LEFT",
    "CLOSED",
    "NOT_INDICATED",
]

Bearing = Literal[0, 45, 90, 135, 180, 225, 270, 315]

VALID_BEARINGS: tuple[int, ...] = (0, 45, 90, 135, 180, 225, 270, 315)

OCTANTS: list[Octant] = [
    "AHEAD",
    "AHEAD_RIGHT",
    "RIGHT",
    "BACK_RIGHT",
    "BACK",
    "BACK_LEFT",
    "LEFT",
    "AHEAD_LEFT",
]

ANSWER_OPTIONS: list[Answer] = [
    "AHEAD",
    "AHEAD_RIGHT",
    "RIGHT",
    "BACK_RIGHT",
    "BACK",
    "BACK_LEFT",
    "LEFT",
    "AHEAD_LEFT",
    "CLOSED",
    "NOT_INDICATED",
]


class Label(BaseModel):
    """Multilingual label for a signage item or node."""

    en: str
    hi: str | None = None
    regional: str | None = None
    regional_script: str | None = None


class Node(BaseModel):
    """Node in a venue graph (junction or destination)."""

    id: str
    kind: Literal["junction", "destination"]
    category: str | None = None
    label: Label

    @model_validator(mode="after")
    def validate_destination_label(self) -> Self:
        """Destination nodes must have at least English and Hindi labels."""
        if self.kind == "destination":
            if not self.label.en or not self.label.en.strip():
                raise ValueError(
                    f"Destination node '{self.id}' must have a non-empty English label ('en')."
                )
            if not self.label.hi or not self.label.hi.strip():
                raise ValueError(
                    f"Destination node '{self.id}' must have a non-empty Hindi label ('hi')."
                )
        return self


class Edge(BaseModel):
    """Walkable edge between two venue nodes."""

    a: str
    b: str
    bearing_ab: Bearing
    length: float
    status: Literal["open", "closed"] = "open"

    @field_validator("bearing_ab")
    @classmethod
    def validate_bearing(cls, v: int) -> int:
        """Validate that bearing is a multiple of 45 degrees in [0, 315]."""
        if v not in VALID_BEARINGS:
            raise ValueError(
                f"Bearing must be a multiple of 45 degrees in {VALID_BEARINGS}, got {v}"
            )
        return v


class Venue(BaseModel):
    """Physical layout topology graph for a wayfinding venue."""

    id: str
    name: str
    kind: Literal["railway", "hospital", "metro"]
    nodes: list[Node]
    edges: list[Edge]

    @model_validator(mode="after")
    def validate_venue_topology(self) -> Self:
        """Validate node uniqueness, edge endpoint existence, and graph connectivity."""
        if not self.nodes:
            raise ValueError(f"Venue '{self.id}' must contain at least one node.")

        node_ids: set[str] = set()
        for node in self.nodes:
            if node.id in node_ids:
                raise ValueError(f"Duplicate node id '{node.id}' in venue '{self.id}'.")
            node_ids.add(node.id)

        for edge in self.edges:
            if edge.a not in node_ids:
                raise ValueError(
                    f"Edge endpoint '{edge.a}' does not exist in venue nodes for venue '{self.id}'."
                )
            if edge.b not in node_ids:
                raise ValueError(
                    f"Edge endpoint '{edge.b}' does not exist in venue nodes for venue '{self.id}'."
                )

        g = nx.Graph()
        for node in self.nodes:
            g.add_node(node.id)
        for edge in self.edges:
            g.add_edge(edge.a, edge.b)

        if not nx.is_connected(g):
            raise ValueError(f"Venue '{self.id}' graph is disconnected when all edges are open.")

        return self


class BoardEntry(BaseModel):
    """Individual entry displayed on a signboard."""

    dest_id: str
    label: Label
    arrow_angle: Bearing
    status: Literal["open", "closed"] = "open"
    source: Literal["permanent", "temporary_notice"] = "permanent"

    @field_validator("arrow_angle")
    @classmethod
    def validate_arrow_angle(cls, v: int) -> int:
        """Validate that arrow_angle is a multiple of 45 degrees in [0, 315]."""
        if v not in VALID_BEARINGS:
            raise ValueError(
                f"arrow_angle must be a multiple of 45 degrees in {VALID_BEARINGS}, got {v}"
            )
        return v


class Distractor(BaseModel):
    """Visual or informational distractor in a signboard scene."""

    id: str = ""
    kind: Literal["ad", "icon", "number", "text"] = "text"
    content: str = ""
    position: tuple[float, float] | None = None
    model_config = ConfigDict(extra="allow")


class Knobs(BaseModel):
    """Environmental and perturbation knobs for signboard generation."""

    n_entries: int
    scripts: list[str]
    perspective_deg: float
    blur: float
    noise: float
    lighting: float
    clutter: int
    occlusion: float
    jpeg_quality: int
    template: str
    model_config = ConfigDict(extra="allow")


class Scene(BaseModel):
    """Renderable scene specification for a signboard at a junction."""

    scene_id: str
    venue_id: str
    junction_id: str
    heading: Bearing
    entries: list[BoardEntry]
    distractors: list[Distractor] = []
    knobs: Knobs
    closed_edges: list[tuple[str, str]] = []

    @field_validator("heading")
    @classmethod
    def validate_heading(cls, v: int) -> int:
        """Validate that heading is a multiple of 45 degrees in [0, 315]."""
        if v not in VALID_BEARINGS:
            raise ValueError(
                f"Heading must be a multiple of 45 degrees in {VALID_BEARINGS}, got {v}"
            )
        return v


class Receipt(BaseModel):
    """Verification receipt tracking audit outcomes for a generated task."""

    solver_answer: Answer
    independent_answer: Answer
    agree: bool
    fidelity_ok: bool
    visibility_ok: bool
    evidence_visible_ratio: float
    blind_correct_rate: float | None = None
    blind_rejected: bool = False
    pair_verified: bool | None = None
    human_audit: Literal["pass", "fail", "unaudited"] = "unaudited"
    notes: str = ""
    model_config = ConfigDict(extra="allow")


class Task(BaseModel):
    """Complete benchmark task specification."""

    task_id: str
    schema_version: str = "1.0.0"
    generator_version: str = "1.0.0"
    seed: int = 0
    qtype: str = "REAL"
    question: str
    options: list[Answer] = ANSWER_OPTIONS
    gold: Answer
    image_path: str
    scene_path: str = ""
    target_dest_id: str = ""
    turn_cw: int | None = None
    skill_tags: list[str] = []
    difficulty: dict = {}
    pair_id: str | None = None
    pair_role: Literal["a", "b"] | None = None
    receipt: Receipt | None = None
    notes: str = ""
    task_set: str = "synthetic"
    model_config = ConfigDict(extra="allow")


class ElementGeo(BaseModel):
    """Geometry and visibility properties of a rendered signage element."""

    role: str
    dest_id: str | None = None
    angle: float | None = None
    text: str | None = None
    bbox: tuple[float, float, float, float] | list[float]
    occluded_ratio: float = 0.0
    source: str | None = None
    model_config = ConfigDict(extra="allow")


class Geometry(BaseModel):
    """Collection of exported element geometries for a rendered scene."""

    elements: list[ElementGeo]
    model_config = ConfigDict(extra="allow")


class RawResponse(BaseModel):
    """Raw model response payload."""

    text: str
    latency_s: float
    meta: dict = {}
    model_config = ConfigDict(extra="allow")


EvalMode = Literal["image", "text"]


class EvaluationResult(BaseModel):
    """Single scored evaluation trial result."""

    task_id: str
    model_id: str
    mode: EvalMode
    prompt_version: str
    gold: Answer
    parsed_answer: Answer | None
    correct: bool
    raw_text: str
    latency_s: float
    error: str | None = None
    timestamp: float
    qtype: str
    difficulty: dict = {}
    skill_tags: list[str] = []
    pair_id: str | None = None
    pair_role: str | None = None
    target_dest_id: str | None = None
    turn_cw: int | None = None
    task_set: str = "synthetic"
    model_config = ConfigDict(extra="allow")
