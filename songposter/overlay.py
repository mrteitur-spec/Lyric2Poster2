from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .styles import STYLE_PRESETS

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Title/artist font pairings. "upper" renders the title in capitals.
TYPE_PRESETS = {
    "impact": {"title": "Anton-Regular.ttf", "artist": "Poppins-SemiBold.ttf", "upper": True, "leading": 1.0},
    "bebas": {"title": "BebasNeue-Regular.ttf", "artist": "Poppins-Medium.ttf", "upper": True, "leading": 0.95},
    "serif": {"title": "DMSerifDisplay-Regular.ttf", "artist": "Poppins-Medium.ttf", "upper": False, "leading": 1.02},
}

# Korean / Japanese / Chinese text needs a CJK-capable fallback font.
CJK_RE = re.compile(r"[\u1100-\u11ff\u3040-\u30ff\u3130-\u318f\u4e00-\u9fff\uac00-\ud7af]")
CJK_FONTS = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]


@lru_cache(maxsize=64)
def _font(name: str, size: int, cjk: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = list(CJK_FONTS) if cjk else [str(FONT_DIR / name)]
    candidates += FALLBACK_FONTS
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _rgb(hex_color: str) -> tuple[int, int, int]:
    v = hex_color.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _lum(c) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _tracked_width(font, text: str, tracking: float) -> float:
    return sum(font.getlength(ch) for ch in text) + tracking * max(0, len(text) - 1)


def _draw_tracked(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font, tracking: float, fill) -> None:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking


def _wrap(text: str, font, max_w: int, max_lines: int) -> list[str] | None:
    words, lines, cur = text.split(), [], ""
    for word in words:
        cand = f"{cur} {word}".strip()
        if font.getlength(cand) <= max_w:
            cur = cand
        else:
            if not cur:  # a single word is already too wide
                return None
            lines.append(cur)
            cur = word
    if cur:
        if font.getlength(cur) > max_w:
            return None
        lines.append(cur)
    return lines if len(lines) <= max_lines else None


def _ink_height(font, lines: list[str], pitch: int) -> int:
    """Height from the top of the capitals on line 1 to the lowest ink on the last line."""
    cap_top = font.getbbox("H")[1]
    return (len(lines) - 1) * pitch + max(font.getbbox(ln)[3] for ln in lines[-1:]) - cap_top


def _fit_title(text: str, font_name: str, cjk: bool, max_w: int, max_h: int, start: int, leading: float):
    """Largest font size whose wrapped title fits the box (max 3 lines)."""
    for size in range(start, 27, -3):
        font = _font(font_name, size, cjk)
        lines = _wrap(text, font, max_w, 3)
        if lines and _ink_height(font, lines, int(size * leading)) <= max_h:
            return font, lines, size
    font = _font(font_name, 28, cjk)
    return font, (_wrap(text, font, max_w, 3) or [text[:24]]), 28


def _scrim_mask(size: tuple[int, int], top: bool, strength: int = 225) -> Image.Image:
    """Vertical alpha ramp: transparent mid-poster, dark at the text edge."""
    w, h = size
    strip = Image.new("L", (1, h))
    px = strip.load()
    start = 0.42
    for y in range(h):
        t = (1 - y / (h - 1)) if top else (y / (h - 1))
        px[0, y] = int(strength * max(0.0, (t - start) / (1 - start)) ** 1.5)
    return strip.resize((w, h), Image.NEAREST)


def add_title_overlay(
    image: Image.Image,
    *,
    title: str,
    artist: str,
    style: str,
    palette: list[str] | None = None,
    tagline: str = "",
    position: str = "bottom",
) -> Image.Image:
    """Add large, readable title + artist typography. `position`: bottom | top."""
    poster = image.convert("RGB")
    W, H = poster.size
    margin = int(W * 0.085)
    preset = TYPE_PRESETS[STYLE_PRESETS.get(style, STYLE_PRESETS["Aurora"])["type"]]
    colors = sorted((_rgb(c) for c in (palette or STYLE_PRESETS.get(style, STYLE_PRESETS["Aurora"])["palette"])), key=_lum)
    accent = _mix(colors[-1], (255, 255, 255), 0.25)
    top = position == "top"

    clean_title = " ".join((title or "Untitled").split())[:120]
    clean_artist = " ".join((artist or "Unknown artist").split())[:120]
    title_cjk, artist_cjk = bool(CJK_RE.search(clean_title)), bool(CJK_RE.search(clean_artist))
    shown_title = clean_title.upper() if preset["upper"] and not title_cjk else clean_title
    shown_artist = clean_artist.upper() if not artist_cjk else clean_artist

    # Dark gradient behind the text (tinted by the palette, not pure black).
    scrim_color = _mix(colors[0], (0, 0, 0), 0.6)
    poster.paste(Image.new("RGB", (W, H), scrim_color), (0, 0), _scrim_mask((W, H), top))

    max_w = W - margin * 2
    title_font, lines, size = _fit_title(
        shown_title, preset["title"], title_cjk, max_w, int(H * 0.27), int(W * 0.26), preset["leading"]
    )
    pitch = int(size * preset["leading"] * (1.12 if title_cjk else 1.0))
    cap_off = title_font.getbbox("H")[1]  # lets us position by the top of the capitals
    title_h = _ink_height(title_font, lines, pitch)

    # Artist line: wide-tracked capitals, shrunk until it fits on one line.
    a_size = max(22, int(W * 0.042))
    tracking = a_size * (0.0 if artist_cjk else 0.20)
    artist_font = _font(preset["artist"], a_size, artist_cjk)
    while _tracked_width(artist_font, shown_artist, tracking) > max_w and a_size > 18:
        a_size -= 1
        tracking = a_size * (0.0 if artist_cjk else 0.20)
        artist_font = _font(preset["artist"], a_size, artist_cjk)
    a_h = artist_font.getbbox("Hg")[3]

    tag_font = _font("Poppins-Medium.ttf", max(16, int(W * 0.026)))
    tag_h = int(tag_font.size * 2.1) if tagline else 0
    bar_h, gap = max(4, int(W * 0.008)), int(W * 0.032)
    block_h = tag_h + title_h + gap + bar_h + int(gap * 0.8) + a_h
    y0 = margin + int(W * 0.02) if top else H - margin - block_h - int(W * 0.02)

    # Text is drawn on its own layer so we can add a soft shadow beneath it.
    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    y = y0
    if tagline:
        _draw_tracked(td, (margin, y), tagline.upper(), tag_font, tag_font.size * 0.18, (*accent, 235))
        y += tag_h
    for i, line in enumerate(lines):
        td.text((margin, y + i * pitch - cap_off), line, font=title_font, fill=(255, 255, 255, 255))
    y += title_h + gap
    td.rectangle((margin, y, margin + int(W * 0.14), y + bar_h), fill=(*accent, 255))
    y += bar_h + int(gap * 0.8)
    _draw_tracked(td, (margin, y), shown_artist, artist_font, tracking, (*accent, 255))

    shadow_a = text_layer.getchannel("A").point(lambda v: int(v * 0.75)).filter(ImageFilter.GaussianBlur(W * 0.008))
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    black.putalpha(shadow_a)
    out = Image.alpha_composite(Image.alpha_composite(poster.convert("RGBA"), black), text_layer)

    # Thin inset frame for a finished, printed-poster look.
    fd = ImageDraw.Draw(out, "RGBA")
    inset = int(margin * 0.42)
    fd.rectangle((inset, inset, W - inset, H - inset), outline=(255, 255, 255, 120), width=max(2, int(W * 0.0025)))
    return out.convert("RGB")
