"""Versioned editor documents and bounded, non-executable collaboration actions."""

import hashlib
import json
from dataclasses import dataclass
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from backend.schematic_ac_models import Sweep
from backend.schematic_models import Identifier, Part, Pin, StrictModel, Timing, Wire


@dataclass(frozen=True)
class ProjectFailure(Exception):
    """A safe domain failure shared by REST and MCP adapters."""

    message: str
    status: int = 422


@dataclass(frozen=True)
class Principal:
    """Verified owner and acting client; models cannot supply either identity."""

    owner: str
    actor: str
    correlation_id: str
    grant: str | None = None
    client: str | None = None
    scopes: frozenset[str] = frozenset()


class EditorCircuit(StrictModel):
    """A construction-valid graph; incomplete wiring is permitted until simulation."""

    parts: list[Part] = Field(max_length=20)
    wires: list[Wire] = Field(max_length=40)
    timing: Timing

    @model_validator(mode="after")
    def validate_connections(self) -> Self:
        """Reject duplicate identities, dangling connections and invalid terminals."""
        if len({part.id for part in self.parts}) != len(self.parts):
            raise ValueError("Part IDs must be unique")
        pins = {f"{part.id}:{terminal}" for part in self.parts
                for terminal in range(1 if part.kind == "GND" else 2)}
        edges: set[frozenset[str]] = set()
        for wire in self.wires:
            edge = frozenset((f"{wire.a.part}:{wire.a.terminal}",
                              f"{wire.b.part}:{wire.b.terminal}"))
            if len(edge) != 2 or not edge <= pins or edge in edges:
                raise ValueError("Wires must connect distinct existing pins without duplicates")
            edges.add(edge)
        if len(self.model_dump_json().encode()) > 8192:
            raise ValueError("Circuit exceeds the 8 KB graph budget")
        return self


class DocumentContents(StrictModel):
    """Complete editor settings restored together by one undoable revision."""

    circuit: EditorCircuit
    sweep: Sweep | None = None


class NewDocument(StrictModel):
    """An explicitly saved project or separately shared browser workspace."""

    name: str = Field(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$")
    kind: Literal["project", "workspace"] = "project"
    contents: DocumentContents
    idempotency_key: UUID


class RevisionCommand(StrictModel):
    """Optimistic concurrency and retry identity for every document mutation."""

    expected_revision: UUID
    idempotency_key: UUID
    reason: str = Field(min_length=1, max_length=240, pattern=r"^[^\x00-\x1f\x7f]+$")


class ReplaceDocument(RevisionCommand):
    """A bounded replacement through the same revision boundary as small edits."""

    contents: DocumentContents


class RestoreDocument(RevisionCommand):
    """An immutable historical snapshot to restore as a new head."""

    revision: UUID


class PutPart(StrictModel):
    """Add or replace a complete numeric component with an explicit ID."""

    operation: Literal["put_part"]
    part: Part


class RemovePart(StrictModel):
    """Remove a part and its wires atomically, retaining both in history."""

    operation: Literal["remove_part"]
    part: Identifier


class ConnectPins(StrictModel):
    """Connect named terminals without interpreting drawn crossings."""

    operation: Literal["connect"]
    a: Pin
    b: Pin


class DisconnectPins(StrictModel):
    """Remove the explicit connection between two named terminals."""

    operation: Literal["disconnect"]
    a: Pin
    b: Pin


class SetTiming(StrictModel):
    """Update solver output timing, not visual playback speed."""

    operation: Literal["set_timing"]
    timing: Timing


class SetSweep(StrictModel):
    """Update an explicit small-signal excitation independently of sine sources."""

    operation: Literal["set_sweep"]
    sweep: Sweep | None


Edit = Annotated[PutPart | RemovePart | ConnectPins | DisconnectPins | SetTiming | SetSweep,
                 Field(discriminator="operation")]


class EditDocument(RevisionCommand):
    """One bounded atomic batch, and one undo step, for human or AI editing."""

    edits: list[Edit] = Field(min_length=1, max_length=40)


class NewGrant(StrictModel):
    """Browser-only delegation to one document, never the whole account by default."""

    client: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    scopes: list[Literal["read", "edit", "simulate", "view"]] = Field(min_length=1, max_length=4)
    lifetime_minutes: int = Field(strict=True, ge=5, le=60)
    mode: Literal["oauth", "token"] = "oauth"

    @model_validator(mode="after")
    def require_read_scope(self) -> Self:
        """Every connection must be able to reread its revision before editing."""
        if "read" not in self.scopes or len(set(self.scopes)) != len(self.scopes):
            raise ValueError("Include read and do not duplicate permissions")
        return self


def contents_hash(contents: DocumentContents) -> str:
    """Hash canonical structured input, independent of JSON key ordering."""
    encoded = json.dumps(contents.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def apply_edits(contents: DocumentContents, edits: list[Edit]) -> DocumentContents:
    """Pure batch transformation; validate once before any persistence happens."""
    submitted = contents.model_dump()
    graph = submitted["circuit"]
    for edit in edits:
        match edit:
            case PutPart(part=part):
                graph["parts"] = [old for old in graph["parts"] if old["id"] != part.id]
                graph["parts"].append(part.model_dump())
            case RemovePart(part=part_id):
                if not any(part["id"] == part_id for part in graph["parts"]):
                    raise ProjectFailure("Unknown part")
                graph["parts"] = [part for part in graph["parts"] if part["id"] != part_id]
                graph["wires"] = [wire for wire in graph["wires"]
                                  if wire["a"]["part"] != part_id and wire["b"]["part"] != part_id]
            case ConnectPins(a=first, b=second):
                graph["wires"].append({"a": first.model_dump(), "b": second.model_dump()})
            case DisconnectPins(a=first, b=second):
                edge = {first.model_dump_json(), second.model_dump_json()}
                graph["wires"] = [wire for wire in graph["wires"] if
                                  {Pin(**wire["a"]).model_dump_json(),
                                   Pin(**wire["b"]).model_dump_json()} != edge]
            case SetTiming(timing=timing):
                graph["timing"] = timing.model_dump()
            case SetSweep(sweep=sweep):
                submitted["sweep"] = sweep.model_dump() if sweep else None
    return DocumentContents.model_validate(submitted)
