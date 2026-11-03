from __future__ import annotations

MATCH_SONG = "Match the song"

STYLE_PRESETS = {
    "Aurora": {
        "palette": ["#101B3D", "#315C9B", "#8C6CCB", "#F3A6B8"],
        "motifs": ["glowing arcs", "soft light ribbons", "distant stars"],
        "finish": "luminous and atmospheric",
        "type": "serif",
    },
    "Minimal": {
        "palette": ["#F0EDE5", "#C8BFB1", "#65716B", "#242B2B"],
        "motifs": ["quiet negative space", "one precise circle", "fine lines"],
        "finish": "restrained and editorial",
        "type": "bebas",
    },
    "Retro": {
        "palette": ["#3C2445", "#D45D43", "#F0B65B", "#F4D9A4"],
        "motifs": ["sunset bands", "grain-like dots", "rounded geometry"],
        "finish": "warm and vintage-inspired",
        "type": "impact",
    },
    "Noir": {
        "palette": ["#080B12", "#202B37", "#52616B", "#D5D8D6"],
        "motifs": ["sharp shadows", "smoke-like forms", "silver highlights"],
        "finish": "cinematic and high-contrast",
        "type": "bebas",
    },
    "Dreamscape": {
        "palette": ["#253C68", "#658DBA", "#C5A6CE", "#F2D6D0"],
        "motifs": ["floating shapes", "misty layers", "soft stars"],
        "finish": "surreal and weightless",
        "type": "serif",
    },
    "Geometric": {
        "palette": ["#152B32", "#26756C", "#D1A65A", "#E5DCCB"],
        "motifs": ["interlocking forms", "radial lines", "bold circles"],
        "finish": "structured and graphic",
        "type": "impact",
    },
}

# Used when a custom song is generated with "Match the song".
MOOD_STYLE = {
    "hopeful": "Retro",
    "melancholic": "Noir",
    "energetic": "Geometric",
    "dreamlike": "Dreamscape",
    "introspective": "Aurora",
}

MOOD_PALETTES = {
    "hopeful": ["#2B1236", "#C8503C", "#F4A94E", "#FBE3B0"],
    "melancholic": ["#0B1220", "#22344F", "#5F7B9C", "#C9D6E3"],
    "energetic": ["#12091F", "#8E1F4F", "#F0483E", "#FFC857"],
    "dreamlike": ["#1B2150", "#5B6FB8", "#B79BD8", "#F6D9E4"],
    "introspective": ["#0D1B2A", "#1F5F6B", "#6FA8A0", "#E6EFE3"],
}

# Scene motifs the artwork engine can draw (see scene_engine.py).
KNOWN_MOTIFS = (
    "sun", "moon", "stars", "skyline", "waves", "rain", "mountains", "flowers",
    "flames", "road", "vinyl", "grid", "ribbons", "heart", "spotlight",
    "lightning", "bubbles", "clouds", "fireworks",
)
