from __future__ import annotations

import re
import unicodedata


def clean_lyrics(value: str, max_chars: int = 12000) -> str:
    """Normalize user input for transient analysis; never persist it here."""
    if not isinstance(value, str):
        raise TypeError("Lyrics must be text.")
    normalized = unicodedata.normalize("NFC", value)
    normalized = "".join(ch for ch in normalized if ch in "\n\t" or not unicodedata.category(ch).startswith("C"))
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if len(normalized) > max_chars:
        raise ValueError(f"Please limit lyrics to {max_chars} characters.")
    return normalized


def validate_metadata(title: str, artist: str) -> tuple[str, str]:
    title = (title or "").strip()
    artist = (artist or "").strip()
    if len(title) > 120 or len(artist) > 120:
        raise ValueError("Song title and artist must be 120 characters or fewer.")
    return title, artist
