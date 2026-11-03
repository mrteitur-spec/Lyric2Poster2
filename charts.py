from __future__ import annotations

import csv
from pathlib import Path


def load_tracks(directory: Path) -> list[dict[str, str]]:
    """Load simple chart CSV files with title and artist columns."""
    tracks: list[dict[str, str]] = []
    if not directory.exists():
        return tracks
    for path in sorted(directory.glob("*.csv")):
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    title = (row.get("title") or row.get("track") or "").strip()
                    artist = (row.get("artist") or "").strip()
                    if title and artist:
                        tracks.append({"title": title[:120], "artist": artist[:120]})
        except (OSError, csv.Error, UnicodeError):
            # Ignore malformed optional chart files; custom entry remains available.
            continue
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for item in tracks:
        unique[(item["title"], item["artist"])] = item
    return list(unique.values())
