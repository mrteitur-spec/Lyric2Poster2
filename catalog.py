from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .styles import KNOWN_MOTIFS, STYLE_PRESETS

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / "data" / "catalog" / "popular_songs.json"


@dataclass(frozen=True)
class SongProfile:
    """Descriptive data for one popular song (mood, themes, colours).

    This is metadata written for the app. Copyrighted lyrics are never stored;
    `lyrics` is only filled for public-domain songs.
    """

    id: str
    title: str
    artist: str
    year: int | None
    genre: str
    mood: str
    style: str
    motifs: tuple[str, ...]
    palette: tuple[str, ...]
    themes: str
    lyrics: str = ""
    public_domain: bool = False

    @property
    def label(self) -> str:
        year = f" ({self.year})" if self.year else ""
        return f"{self.title} — {self.artist}{year}"

    @property
    def tagline(self) -> str:
        parts = [self.genre.upper()]
        if self.year:
            parts.append(str(self.year))
        return "  ·  ".join(parts)


def _parse(entry: dict) -> SongProfile:
    motifs = tuple(m for m in entry["motifs"] if m in KNOWN_MOTIFS)
    palette = tuple(entry["palette"])
    if not motifs:
        raise ValueError("no valid motifs")
    if len(palette) != 4 or not all(_HEX.match(c) for c in palette):
        raise ValueError("palette must be four #RRGGBB colours")
    style = entry.get("style", "Aurora")
    if style not in STYLE_PRESETS:
        style = "Aurora"
    year = entry.get("year")
    return SongProfile(
        id=str(entry["id"]),
        title=str(entry["title"])[:120],
        artist=str(entry["artist"])[:120],
        year=int(year) if year else None,
        genre=str(entry.get("genre", "Pop")),
        mood=str(entry.get("mood", "introspective")),
        style=style,
        motifs=motifs,
        palette=palette,
        themes=str(entry.get("themes", "")),
        lyrics=str(entry.get("lyrics", "")) if entry.get("public_domain") else "",
        public_domain=bool(entry.get("public_domain", False)),
    )


def load_catalog(path: Path | None = None) -> list[SongProfile]:
    """Load the song catalog. Malformed entries are skipped, never fatal."""
    path = path or DEFAULT_CATALOG
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    songs: list[SongProfile] = []
    for entry in data.get("songs", []):
        try:
            songs.append(_parse(entry))
        except (KeyError, TypeError, ValueError):
            continue
    return songs


def genres(catalog: list[SongProfile]) -> list[str]:
    seen: list[str] = []
    for song in catalog:
        if song.genre not in seen:
            seen.append(song.genre)
    return seen


def filter_songs(catalog: list[SongProfile], genre: str = "All", query: str = "") -> list[SongProfile]:
    query = " ".join(query.casefold().split())
    result = []
    for song in catalog:
        if genre not in ("All", "") and song.genre != genre:
            continue
        if query and query not in f"{song.title} {song.artist}".casefold():
            continue
        result.append(song)
    return result
