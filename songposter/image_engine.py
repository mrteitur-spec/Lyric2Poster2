from __future__ import annotations

import hashlib
import math
import random
from PIL import Image, ImageDraw

from .models import ArtBrief


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def create_demo_artwork(brief: ArtBrief, size: tuple[int, int] = (900, 1350)) -> Image.Image:
    """Render original abstract artwork locally with Pillow (no network/GPU)."""
    width, height = size
    colors = [_rgb(c) for c in brief.palette]
    digest = hashlib.sha256((brief.concept + brief.description + brief.style).encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))

    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image, "RGBA")
    stops = [i * (height - 1) / max(1, len(colors) - 1) for i in range(len(colors))]
    for y in range(height):
        idx = min(len(colors) - 2, int(y / max(1, height - 1) * (len(colors) - 1)))
        local_t = (y - stops[idx]) / max(1.0, stops[idx + 1] - stops[idx])
        color = _lerp(colors[idx], colors[idx + 1], local_t)
        draw.line((0, y, width, y), fill=(*color, 255))

    # Large translucent orbital shapes create a distinctive abstract backdrop.
    for i in range(9):
        cx = rng.randint(-width // 4, width + width // 4)
        cy = rng.randint(height // 8, height * 3 // 4)
        radius = rng.randint(width // 9, width // 2)
        alpha = rng.randint(16, 48)
        color = colors[i % len(colors)]
        box = (cx - radius, cy - radius, cx + radius, cy + radius)
        if i % 3 == 0:
            draw.ellipse(box, outline=(*color, alpha), width=rng.randint(5, 18))
        elif i % 3 == 1:
            draw.arc(box, start=rng.randint(0, 180), end=rng.randint(200, 360), fill=(*color, alpha), width=rng.randint(8, 24))
        else:
            points = [(cx, cy - radius), (cx + radius, cy + radius // 2), (cx - radius, cy + radius // 2)]
            draw.polygon(points, fill=(*color, alpha // 2))

    # Fine radial rays and particles add texture without using lyric text.
    center = (rng.randint(width // 4, width * 3 // 4), rng.randint(height // 4, height * 2 // 3))
    for i in range(54):
        angle = (2 * math.pi * i / 54) + rng.uniform(-0.035, 0.035)
        inner = rng.randint(width // 8, width // 3)
        outer = rng.randint(width // 3, width)
        x1 = center[0] + math.cos(angle) * inner
        y1 = center[1] + math.sin(angle) * inner
        x2 = center[0] + math.cos(angle) * outer
        y2 = center[1] + math.sin(angle) * outer
        draw.line((x1, y1, x2, y2), fill=(*colors[i % len(colors)], rng.randint(12, 42)), width=rng.choice([1, 2, 3]))

    for _ in range(180):
        x, y = rng.randrange(width), rng.randrange(height)
        r = rng.choice([1, 1, 2, 3])
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rng.randint(18, 90)))

    # Gentle dark vignette at the bottom to keep overlaid text legible.
    vignette = Image.new("RGBA", size, (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for y in range(height // 2, height):
        alpha = int(150 * ((y - height // 2) / (height // 2)) ** 1.7)
        vd.line((0, y, width, y), fill=(0, 0, 0, alpha))
    image = Image.alpha_composite(image.convert("RGBA"), vignette)
    return image.convert("RGB")
