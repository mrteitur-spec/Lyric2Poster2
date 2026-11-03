from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ArtBrief:
    """Lyric-free art direction. Never stores lyric text."""

    concept: str
    description: str
    mood: str
    visual_elements: list[str]
    palette: list[str]
    style: str
    # New in v2: which scene motifs to draw (main one first) and a seed that
    # makes every song's artwork unique but repeatable (title|artist only).
    scene_motifs: list[str] = field(default_factory=list)
    seed: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ArtBrief":
        return cls(
            concept=str(value["concept"]),
            description=str(value["description"]),
            mood=str(value["mood"]),
            visual_elements=[str(x) for x in value["visual_elements"]],
            palette=[str(x) for x in value["palette"]],
            style=str(value["style"]),
            scene_motifs=[str(x) for x in value.get("scene_motifs", [])],
            seed=str(value.get("seed", "")),
        )
