from __future__ import annotations

import re

from .catalog import SongProfile
from .models import ArtBrief
from .safety import clean_lyrics, validate_metadata
from .styles import MATCH_SONG, MOOD_PALETTES, MOOD_STYLE, STYLE_PRESETS

MOODS = ("hopeful", "melancholic", "energetic", "dreamlike", "introspective")

MOOD_SIGNALS = {
    "hopeful": {"light", "hope", "rise", "sun", "begin", "home", "shine", "새벽", "빛", "희망"},
    "melancholic": {"rain", "tears", "empty", "gone", "miss", "alone", "night", "비", "눈물", "그리움"},
    "energetic": {"run", "dance", "fire", "wild", "loud", "heart", "burn", "춤", "불꽃", "달려"},
    "dreamlike": {"dream", "sky", "moon", "float", "cloud", "stars", "잠", "꿈", "달", "하늘"},
}

# Word stems (English) or substrings (Korean) that suggest a scene motif.
MOTIF_KEYWORDS = {
    "waves": ("ocean", "sea", "wave", "tide", "shore", "swim", "바다", "파도"),
    "skyline": ("city", "street", "neon", "town", "tower", "도시", "거리"),
    "road": ("road", "drive", "highway", "car", "ride", "길", "도로"),
    "flowers": ("flower", "rose", "bloom", "garden", "spring", "petal", "꽃", "봄"),
    "heart": ("heart", "love", "kiss", "darling", "baby", "사랑", "마음"),
    "flames": ("fire", "burn", "flame", "blaze", "smoke", "불", "불꽃"),
    "rain": ("rain", "tear", "storm", "drown", "wet", "비", "눈물"),
    "sun": ("sun", "summer", "gold", "morning", "shine", "sunrise", "여름", "햇살", "태양"),
    "moon": ("moon", "midnight", "tonight", "night", "달", "밤"),
    "stars": ("star", "galaxy", "universe", "space", "별", "우주"),
    "clouds": ("cloud", "sky", "heaven", "fly", "구름", "하늘"),
    "mountains": ("mountain", "hill", "valley", "climb", "산"),
    "spotlight": ("dance", "stage", "party", "crowd", "show", "춤", "무대"),
    "lightning": ("thunder", "lightning", "electric", "shock", "번개"),
    "fireworks": ("firework", "celebrate", "cheers", "new year", "불꽃놀이"),
    "bubbles": ("bubble", "float", "champagne", "fizz", "giggle"),
    "grid": ("synth", "retro", "disco", "80s", "arcade", "digital"),
    "vinyl": ("record", "vinyl", "music", "song", "radio", "melody"),
}

MOOD_SCENES = {
    "hopeful": ["sun", "clouds"],
    "melancholic": ["rain", "moon"],
    "energetic": ["flames", "spotlight"],
    "dreamlike": ["moon", "stars"],
    "introspective": ["mountains", "stars"],
}


def _infer_mood(lyrics: str) -> str:
    tokens = set(lyrics.lower().replace("\n", " ").split())
    scores = {mood: len(tokens.intersection(words)) for mood, words in MOOD_SIGNALS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "introspective"


def infer_motifs(text: str, mood: str) -> list[str]:
    """Pick up to two scene motifs from keywords, falling back to the mood."""
    lowered = text.lower()
    words = re.findall(r"[a-z']+", lowered)
    scores: dict[str, int] = {}
    for motif, stems in MOTIF_KEYWORDS.items():
        for stem in stems:
            if stem.isascii():
                if " " in stem:
                    hits = lowered.count(stem)
                elif len(stem) <= 3:  # short stems must match whole words ("car" != "care")
                    hits = sum(1 for w in words if w in (stem, stem + "s"))
                else:
                    hits = sum(1 for w in words if w.startswith(stem))
            else:
                hits = lowered.count(stem)
            if hits:
                scores[motif] = scores.get(motif, 0) + hits
    ranked = [m for m, _ in sorted(scores.items(), key=lambda kv: -kv[1])]
    for fallback in MOOD_SCENES.get(mood, MOOD_SCENES["introspective"]):
        if fallback not in ranked:
            ranked.append(fallback)
    return ranked[:2]


def _describe(mood: str, style: str, motifs: list[str], themes: str = "") -> str:
    scene = " and ".join(motifs[:2])
    base = f"A {mood} {style.lower()} scene built around {scene}"
    if themes:
        base += f", inspired by {themes}"
    return (
        base + ". The artwork contains no text, people, or logos; "
        "the title and artist are added as bold typography."
    )


def create_brief_for_song(profile: SongProfile, style: str = MATCH_SONG, variation: int = 0) -> ArtBrief:
    """Build an art brief for a catalog song. No lyrics are needed."""
    style_name = profile.style if style == MATCH_SONG or style not in STYLE_PRESETS else style
    preset = STYLE_PRESETS[style_name]
    palette = list(profile.palette) if style == MATCH_SONG or style not in STYLE_PRESETS else list(preset["palette"])
    motifs = list(profile.motifs)
    seed = f"{profile.title}|{profile.artist}" + (f"#{variation}" if variation else "")
    return ArtBrief(
        concept=f"{profile.mood.title()} {motifs[0]} in {style_name}",
        description=_describe(profile.mood, style_name, motifs, profile.themes),
        mood=profile.mood,
        visual_elements=list(preset["motifs"]),
        palette=palette,
        style=style_name,
        scene_motifs=motifs,
        seed=seed,
    )


def create_demo_brief(
    *, title: str, artist: str, lyrics: str = "", style: str = MATCH_SONG, mood: str | None = None, variation: int = 0
) -> ArtBrief:
    """Create a lyric-free art direction for a custom song using local rules.

    This is a no-key demo substitute, not an LLM call. Lyrics are never placed in
    the returned object; callers should discard the input immediately afterward.
    """
    title, artist = validate_metadata(title, artist)
    text = clean_lyrics(lyrics) if lyrics else ""
    if not title or not artist:
        raise ValueError("A title and artist are required.")
    if not text and not mood:
        raise ValueError("Please enter some lyrics or choose a mood.")

    mood = mood if mood in MOODS else _infer_mood(text)
    motifs = infer_motifs(f"{text}\n{title}", mood)
    if style == MATCH_SONG or style not in STYLE_PRESETS:
        style_name = MOOD_STYLE[mood]
        palette = list(MOOD_PALETTES[mood])
    else:
        style_name = style
        palette = list(STYLE_PRESETS[style]["palette"])
    preset = STYLE_PRESETS[style_name]
    seed = f"{title}|{artist}" + (f"#{variation}" if variation else "")
    return ArtBrief(
        concept=f"{mood.title()} {motifs[0]} in {style_name}",
        description=_describe(mood, style_name, motifs),
        mood=mood,
        visual_elements=list(preset["motifs"]),
        palette=palette,
        style=style_name,
        scene_motifs=motifs,
        seed=seed,
    )
