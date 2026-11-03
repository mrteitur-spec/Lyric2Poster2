"""Song-specific abstract artwork, drawn locally with Pillow (no API, no GPU).

Each song has a seed and one or two scene motifs (sun, skyline, rain, ...).
The first motif is the hero; the second is a quieter supporting layer.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .models import ArtBrief

RGB = tuple[int, int, int]


# --------------------------------------------------------------------------- helpers
def _rgb(hex_color: str) -> RGB:
    v = hex_color.lstrip("#")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


def _lum(c: RGB) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def _light(c: RGB, t: float) -> RGB:
    return _mix(c, (255, 255, 255), t)


def _dark(c: RGB, t: float) -> RGB:
    return _mix(c, (0, 0, 0), t)


@dataclass
class Ctx:
    W: int
    H: int
    rng: random.Random
    dark: RGB
    c1: RGB
    c2: RGB
    light: RGB
    horizon: int

    @property
    def k(self) -> float:  # stroke scale relative to a 900px-wide poster
        return self.W / 900


def _layer(ctx: Ctx) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (ctx.W, ctx.H), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img, "RGBA")


def _over(canvas: Image.Image, layer: Image.Image, blur: float = 0, glow: float = 0) -> Image.Image:
    """Composite a layer, optionally with a soft glow copy underneath."""
    if glow:
        canvas = Image.alpha_composite(canvas, layer.filter(ImageFilter.GaussianBlur(glow)))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(canvas, layer)


def _vgrad(size: tuple[int, int], top: RGB, bottom: RGB) -> Image.Image:
    w, h = size
    strip = Image.new("RGB", (1, max(1, h)))
    px = strip.load()
    for y in range(h):
        px[0, y] = _mix(top, bottom, y / max(1, h - 1))
    return strip.resize((w, h), Image.NEAREST)


def _sky(ctx: Ctx) -> Image.Image:
    h = ctx.H
    hz = ctx.horizon / h
    stops = [(0.0, ctx.dark), (hz * 0.45, ctx.c1), (hz * 0.80, ctx.c2), (hz, ctx.light), (1.0, _dark(ctx.c1, 0.55))]
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        t = y / (h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t <= t1:
                px[0, y] = _mix(c0, c1, (t - t0) / max(1e-6, t1 - t0))
                break
    return strip.resize((ctx.W, h), Image.NEAREST).convert("RGBA")


def _sparkle(d: ImageDraw.ImageDraw, x: float, y: float, r: float, fill) -> None:
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i
        rad = r if i % 2 == 0 else r * 0.22
        pts.append((x + math.cos(ang) * rad, y + math.sin(ang) * rad))
    d.polygon(pts, fill=fill)


def _ridge(rng: random.Random, n: int, rough: float) -> list[float]:
    pts = [0.5, 0.5]
    amp = 1.0
    while len(pts) < n:
        nxt = []
        for a, b in zip(pts, pts[1:]):
            nxt += [a, (a + b) / 2 + rng.uniform(-amp, amp) * 0.5]
        nxt.append(pts[-1])
        pts = nxt
        amp *= rough
    return pts[:n]


# --------------------------------------------------------------------------- motifs
# Every motif: fn(ctx, canvas, s) -> canvas, with s = strength (1.0 hero, ~0.55 support).
def sun(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, hz = ctx.W, ctx.horizon
    R = int(W * (0.30 if s >= 1 else 0.20))
    cx = int(W * ctx.rng.uniform(0.40, 0.60))
    cy = int(hz - R * 0.30)
    glow, gd = _layer(ctx)
    gd.ellipse((cx - R * 1.6, cy - R * 1.6, cx + R * 1.6, cy + R * 1.6), fill=(*_light(ctx.c2, 0.25), int(170 * s)))
    canvas = _over(canvas, glow, blur=R * 0.5)
    mask = Image.new("L", (2 * R, 2 * R), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((0, 0, 2 * R - 1, 2 * R - 1), fill=int(255 * min(1, s + 0.1)))
    if s >= 1:  # retro sunset bands
        for i in range(7):
            y0 = int(R * (0.80 + i * 0.20))
            md.rectangle((0, y0, 2 * R, y0 + int(R * 0.015 * (i + 1) + 2 * ctx.k)), fill=0)
    grad = _vgrad((2 * R, 2 * R), _light(ctx.light, 0.6), _mix(ctx.c2, ctx.light, 0.25))
    canvas.paste(grad, (cx - R, cy - R), mask)
    return canvas


def moon(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H = ctx.W, ctx.H
    R = int(W * (0.20 if s >= 1 else 0.12))
    cx = int(W * ctx.rng.choice([0.34, 0.66]))
    cy = int(H * 0.27)
    glow, gd = _layer(ctx)
    gd.ellipse((cx - R * 1.9, cy - R * 1.9, cx + R * 1.9, cy + R * 1.9), fill=(*_light(ctx.light, 0.3), int(120 * s)))
    canvas = _over(canvas, glow, blur=R * 0.7)
    mask = Image.new("L", (4 * R, 4 * R), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((R, R, 3 * R, 3 * R), fill=255)
    off = int(R * 0.55)
    md.ellipse((R + off, R - int(off * 0.3), 3 * R + off, 3 * R - int(off * 0.3)), fill=0)
    mask = mask.point(lambda v: int(v * min(1, s + 0.15)))
    tint = _vgrad((4 * R, 4 * R), _light(ctx.light, 0.75), _light(ctx.c2, 0.55))
    canvas.paste(tint, (cx - 2 * R, cy - 2 * R), mask)
    return canvas


def stars(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    layer, d = _layer(ctx)
    W, H, k = ctx.W, ctx.H, ctx.k
    for _ in range(int(220 * s + 40)):
        x, y = ctx.rng.randrange(W), int(ctx.rng.random() ** 1.4 * ctx.horizon)
        r = ctx.rng.choice([1, 1, 2, 2, 3]) * k
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, ctx.rng.randint(60, 230)))
    for _ in range(int(8 * s) + 2):
        x, y = ctx.rng.randrange(W), ctx.rng.randrange(int(H * 0.5))
        _sparkle(d, x, y, ctx.rng.randint(10, 26) * k, (*_light(ctx.light, 0.6), 235))
    return _over(canvas, layer, glow=5 * k)


def skyline(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, hz, k, rng = ctx.W, ctx.H, ctx.horizon, ctx.k, ctx.rng
    window = _light(ctx.light, 0.35)
    for far, (hmax, col, alpha) in enumerate([(0.22, _mix(ctx.c1, ctx.dark, 0.45), 200), (0.34, _dark(ctx.dark, 0.5), 255)]):
        layer, d = _layer(ctx)
        a = int(alpha * min(1, s + 0.15))
        x = -int(W * 0.03)
        while x < W:
            w = int(W * rng.uniform(0.04, 0.10))
            h = int(H * rng.uniform(0.05, hmax))
            d.rectangle((x, hz - h, x + w, hz + int(H * 0.012)), fill=(*col, a))
            if rng.random() < 0.22:
                d.line((x + w // 2, hz - h, x + w // 2, hz - h - int(H * 0.05)), fill=(*col, a), width=max(2, int(3 * k)))
            if far:
                ww, wh, gx, gy = int(7 * k), int(10 * k), int(17 * k), int(26 * k)
                for wy in range(hz - h + gy, hz - gy // 2, gy):
                    for wx in range(x + gx // 2, x + w - ww, gx):
                        if rng.random() < 0.30:
                            d.rectangle((wx, wy, wx + ww, wy + wh), fill=(*window, int(210 * min(1, s + 0.2))))
            x += w + rng.randint(0, int(W * 0.008))
        if far and s >= 1:  # dark ground + glowing reflection streaks
            d.rectangle((0, hz + int(H * 0.012), W, H), fill=(*_dark(ctx.dark, 0.5), 235))
            for _ in range(14):
                rx = rng.randrange(W)
                d.rectangle((rx, hz + int(H * 0.02), rx + int(5 * k), hz + int(H * rng.uniform(0.05, 0.16))), fill=(*window, 70))
        canvas = _over(canvas, layer, glow=(10 * k if far else 0))
    return canvas


def waves(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, hz, k = ctx.W, ctx.H, ctx.horizon, ctx.k
    rows = 8 if s >= 1 else 4
    top = hz - int(H * (0.02 if s >= 1 else 0))
    for i in range(rows):
        t = i / max(1, rows - 1)
        base = top + int((H - top) * (t ** 1.15) * 0.92) + int(H * 0.012)
        amp = (10 + 34 * t) * k * (1 if s >= 1 else 0.6)
        freq = ctx.rng.uniform(1.4, 2.6)
        phase = ctx.rng.uniform(0, 6.28)
        pts = [(x, base + math.sin(x / W * math.pi * 2 * freq + phase) * amp + math.sin(x / W * 9 + phase) * amp * 0.3) for x in range(0, W + 8, 8)]
        col = _mix(ctx.c2, ctx.dark, 0.25 + 0.65 * t)
        layer, d = _layer(ctx)
        d.polygon(pts + [(W, H), (0, H)], fill=(*col, int(235 * min(1, s + 0.2))))
        d.line(pts, fill=(*_light(ctx.light, 0.4), int(120 * s)), width=max(2, int(3 * k)))
        canvas = _over(canvas, layer)
    return canvas


def rain(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, k, rng = ctx.W, ctx.H, ctx.k, ctx.rng
    bokeh, bd = _layer(ctx)
    for i in range(int(16 * s) + 4):
        r = rng.randint(int(14 * k), int(50 * k))
        x, y = rng.randrange(W), rng.randrange(int(H * 0.25), int(H * 0.75))
        col = [ctx.c2, ctx.light, _light(ctx.c2, 0.4)][i % 3]
        bd.ellipse((x - r, y - r, x + r, y + r), fill=(*col, rng.randint(40, 90)))
    canvas = _over(canvas, bokeh, blur=3 * k)
    layer, d = _layer(ctx)
    streak = _light(ctx.light, 0.35)
    for _ in range(int(320 * s) + 60):
        x, y = rng.randrange(-W // 4, W), rng.randrange(0, H)
        ln = rng.randint(int(40 * k), int(120 * k))
        d.line((x, y, x - ln * 0.22, y + ln), fill=(*streak, rng.randint(30, 110)), width=max(1, int(rng.choice([1, 2, 2, 3]) * k)))
    for _ in range(int(16 * s) + 4):  # ripples on the ground
        x, y = rng.randrange(W), rng.randint(ctx.horizon + int(H * 0.04), int(H * 0.88))
        rw = rng.randint(int(30 * k), int(110 * k))
        d.ellipse((x - rw, y - rw // 4, x + rw, y + rw // 4), outline=(*streak, 90), width=max(1, int(2 * k)))
    return _over(canvas, layer)


def mountains(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, hz = ctx.W, ctx.H, ctx.horizon
    n = 5 if s >= 1 else 3
    for i in range(n):
        t = i / max(1, n - 1)
        base = hz - int(H * (0.12 - 0.10 * t))
        amp = H * (0.20 - 0.07 * t) * (1 if s >= 1 else 0.7)
        ridge = _ridge(ctx.rng, 65, 0.52)
        pts = [(j * W / 64, base - (r - 0.5) * 2 * amp - amp * 0.4) for j, r in enumerate(ridge)]
        col = _mix(_mix(ctx.c2, ctx.light, 0.15), ctx.dark, 0.2 + 0.7 * t)
        layer, d = _layer(ctx)
        d.polygon(pts + [(W, H), (0, H)], fill=(*col, 255 if i else int(230 * min(1, s + 0.2))))
        canvas = _over(canvas, layer)
        if i < n - 1:  # atmospheric haze between ranges
            haze, hd = _layer(ctx)
            hd.rectangle((0, base - int(H * 0.03), W, base + int(H * 0.06)), fill=(*_light(ctx.c2, 0.35), 45))
            canvas = _over(canvas, haze, blur=22 * ctx.k)
    return canvas


def flowers(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, k, rng = ctx.W, ctx.H, ctx.k, ctx.rng

    def bloom(cx: float, cy: float, L: float, n: int, cols: list[RGB], alpha: int) -> None:
        nonlocal canvas
        layer, d = _layer(ctx)
        for ring, (scale, off) in enumerate([(1.0, 0.0), (0.72, math.pi / n)]):
            for i in range(n):
                ang = 2 * math.pi * i / n + off + rng.uniform(-0.04, 0.04)
                pts = []
                for u in [j / 14 for j in range(15)]:
                    pts.append((L * scale * u, L * scale * 0.20 * math.sin(math.pi * u) ** 0.8))
                pts += [(x, -y) for x, y in reversed(pts)]
                rot = [(cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang)) for x, y in pts]
                d.polygon(rot, fill=(*cols[(i + ring) % len(cols)], alpha))
        r0 = L * 0.20
        d.ellipse((cx - r0, cy - r0, cx + r0, cy + r0), fill=(*_dark(ctx.c1, 0.35), 255))
        for _ in range(26):
            a, rr = rng.uniform(0, 6.28), r0 * math.sqrt(rng.random())
            px, py, pr = cx + math.cos(a) * rr, cy + math.sin(a) * rr, 2.5 * k
            d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=(*_light(ctx.light, 0.4), 220))
        canvas = _over(canvas, layer, glow=8 * k)

    petals = [ctx.c2, _light(ctx.c2, 0.35), ctx.light]
    if s >= 1:
        bloom(W * 0.5, H * 0.38, W * 0.33, 13, petals, 215)
        for _ in range(3):
            bloom(rng.choice([W * 0.12, W * 0.88]), rng.randint(int(H * 0.12), int(H * 0.5)), W * 0.12, 9, petals, 150)
    else:
        for _ in range(3):
            bloom(rng.randint(int(W * 0.1), int(W * 0.9)), rng.randint(int(H * 0.15), int(H * 0.5)), W * 0.10, 9, petals, 120)
    return canvas


def flames(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, k, rng = ctx.W, ctx.H, ctx.k, ctx.rng
    base_y = int(ctx.horizon + H * 0.08)
    layer0, d0 = _layer(ctx)
    d0.rectangle((0, base_y - 4, W, H), fill=(*_dark(ctx.dark, 0.5), 255))
    canvas = _over(canvas, layer0)
    tongues = [(0.07 + 0.86 * i / 7 + rng.uniform(-0.03, 0.03), rng.uniform(0.18, 0.42), rng.uniform(0.07, 0.11), rng.uniform(-1, 1)) for i in range(8)]
    for tier, col in enumerate([_mix(ctx.c1, ctx.c2, 0.55), ctx.c2, _light(ctx.light, 0.2)]):
        layer, d = _layer(ctx)
        shrink = 1 - 0.30 * tier
        for fx, fh, fw, sway in tongues:
            cx, h, w = W * fx, H * fh * shrink * (1 if s >= 1 else 0.6), W * fw * shrink
            left, right = [], []
            for j in range(0, 21):
                u = j / 20
                centre = cx + sway * w * 0.9 * math.sin(u * math.pi * 1.4)
                half = w * math.sin(min(1.0, u * 1.25) * math.pi / 2 + 0.0) ** 0.9 * (1 - u) ** 0.75
                y = base_y - h * u
                left.append((centre - half, y))
                right.append((centre + half, y))
            d.polygon(left + right[::-1], fill=(*col, int((205 if tier < 2 else 240) * min(1, s + 0.2))))
        canvas = _over(canvas, layer, glow=16 * k if tier == 0 else 0)
    layer, d = _layer(ctx)
    for _ in range(int(80 * s) + 10):
        x, y, r = rng.randrange(W), rng.randint(int(H * 0.22), base_y), rng.choice([1, 2, 3]) * k
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*_light(ctx.light, 0.3), rng.randint(80, 230)))
    return _over(canvas, layer, glow=4 * k)


def road(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, hz, k = ctx.W, ctx.H, ctx.horizon, ctx.k
    vx = W * 0.5 + ctx.rng.uniform(-W * 0.06, W * 0.06)
    layer, d = _layer(ctx)
    asphalt = _dark(_mix(ctx.dark, ctx.c1, 0.35), 0.35)
    d.rectangle((0, hz, W, H), fill=(*_dark(ctx.dark, 0.55), 255))
    d.polygon([(vx - W * 0.012, hz), (vx + W * 0.012, hz), (W * 1.25, H), (-W * 0.25, H)], fill=(*asphalt, 255))
    edge = _light(ctx.c2, 0.25)
    d.line([(vx - W * 0.012, hz), (-W * 0.25, H)], fill=(*edge, 200), width=max(3, int(5 * k)))
    d.line([(vx + W * 0.012, hz), (W * 1.25, H)], fill=(*edge, 200), width=max(3, int(5 * k)))
    n = 12
    for i in range(n):
        t0, t1 = (i / n) ** 2.3, ((i + 0.5) / n) ** 2.3
        y0, y1 = hz + t0 * (H - hz), hz + t1 * (H - hz)
        w0, w1 = max(1.5, 14 * k * t0), max(2, 14 * k * t1)
        d.polygon([(vx - w0, y0), (vx + w0, y0), (vx + w1, y1), (vx - w1, y1)], fill=(*ctx.light, 235))
    canvas = _over(canvas, layer, glow=3 * k)
    glow, gd = _layer(ctx)
    gd.ellipse((vx - W * 0.28, hz - W * 0.05, vx + W * 0.28, hz + W * 0.05), fill=(*_light(ctx.light, 0.4), 190))
    return _over(canvas, glow, blur=26 * k)


def vinyl(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, k = ctx.W, ctx.H, ctx.k
    R = int(W * (0.34 if s >= 1 else 0.22))
    cx, cy = int(W * (0.5 if s >= 1 else ctx.rng.choice([0.25, 0.75]))), int(H * (0.38 if s >= 1 else 0.28))
    layer, d = _layer(ctx)
    for i in range(1, 4):  # sound ripples
        rr = R + i * W * 0.05
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(*ctx.light, int(90 / i * s)), width=max(2, int(3 * k)))
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(*_dark(ctx.dark, 0.45), 255))
    for r in range(int(R * 0.34), R, max(4, int(7 * k))):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 14), width=1)
    shine, sd = _layer(ctx)
    for a0 in (200, 20):
        sd.pieslice((cx - R, cy - R, cx + R, cy + R), a0, a0 + 38, fill=(255, 255, 255, 46))
    lab = int(R * 0.34)
    d.ellipse((cx - lab, cy - lab, cx + lab, cy + lab), fill=(*ctx.c2, 255))
    d.ellipse((cx - lab * 0.72, cy - lab * 0.72, cx + lab * 0.72, cy + lab * 0.72), outline=(*ctx.light, 220), width=max(2, int(3 * k)))
    d.ellipse((cx - 7 * k, cy - 7 * k, cx + 7 * k, cy + 7 * k), fill=(*ctx.dark, 255))
    canvas = _over(canvas, layer, glow=10 * k)
    return Image.alpha_composite(canvas, shine)


def grid(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, hz, k = ctx.W, ctx.H, ctx.horizon, ctx.k
    layer, d = _layer(ctx)
    d.rectangle((0, hz, W, H), fill=(*_dark(ctx.dark, 0.35), 245))
    col = _light(ctx.light, 0.2)
    vx = W / 2
    for i in range(-14, 15):
        d.line((vx + i * W * 0.012, hz, vx + i * W * 0.30, H), fill=(*col, 210), width=max(2, int(2.5 * k)))
    for i in range(1, 13):
        y = hz + (i / 12) ** 2.2 * (H - hz)
        d.line((0, y, W, y), fill=(*col, 210), width=max(2, int(2.5 * k)))
    return _over(canvas, layer, glow=7 * k)


def ribbons(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, k, rng = ctx.W, ctx.H, ctx.k, ctx.rng
    cols = [ctx.c2, ctx.light, _light(ctx.c2, 0.4), ctx.c1]
    for i in range(6 if s >= 1 else 3):
        layer, d = _layer(ctx)
        y0 = H * rng.uniform(0.10, 0.50)
        amp, freq, ph = H * rng.uniform(0.04, 0.10), rng.uniform(0.8, 1.8), rng.uniform(0, 6.28)
        thick = H * rng.uniform(0.025, 0.06)
        top = [(x, y0 + math.sin(x / W * 6.28 * freq + ph) * amp + x * 0.06) for x in range(0, W + 10, 10)]
        bot = [(x, y + thick * (1 + 0.6 * math.sin(x / W * 5 + ph))) for x, y in top]
        d.polygon(top + bot[::-1], fill=(*cols[i % 4], int(95 * (1 if s >= 1 else 0.5))))
        d.line(top, fill=(*_light(cols[i % 4], 0.5), int(160 * s)), width=max(2, int(3 * k)))
        canvas = _over(canvas, layer, glow=16 * k)
    return canvas


def heart(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, k, rng = ctx.W, ctx.H, ctx.k, ctx.rng

    def shape(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
        pts = []
        for i in range(120):
            t = i / 120 * 2 * math.pi
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((cx + x * size / 17, cy - y * size / 17))
        return pts

    if s >= 1:
        cx, cy, size = W * 0.5, H * 0.37, W * 0.30
        layer, d = _layer(ctx)
        for i in range(3, 0, -1):  # echo outlines
            d.polygon(shape(cx, cy, size * (1 + 0.22 * i)), outline=(*ctx.light, 90 - i * 18), width=max(2, int(3 * k)))
        canvas = _over(canvas, layer, glow=6 * k)
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(shape(cx, cy, size), fill=255)
        grad = Image.new("RGB", (W, H), ctx.c2)
        grad.paste(_vgrad((W, int(size * 1.4)), _light(ctx.light, 0.25), _mix(ctx.c2, ctx.c1, 0.25)), (0, int(cy - size * 0.75)))
        glow, gd = _layer(ctx)
        gd.polygon(shape(cx, cy, size * 1.1), fill=(*ctx.c2, 190))
        canvas = _over(canvas, glow, blur=26 * k)
        canvas.paste(grad, (0, 0), mask)
    layer, d = _layer(ctx)
    for _ in range(14 if s >= 1 else 6):
        d.polygon(shape(rng.randrange(W), rng.randint(int(H * 0.08), int(H * 0.58)), rng.uniform(0.02, 0.06) * W), fill=(*_light(ctx.light, 0.3), rng.randint(50, 150)))
    return _over(canvas, layer, glow=4 * k)


def spotlight(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, hz, rng = ctx.W, ctx.H, ctx.horizon, ctx.rng
    beams, bd = _layer(ctx)
    n = 3 if s >= 1 else 2
    floor = [W * (0.5 + (i - (n - 1) / 2) * 0.26) for i in range(n)]
    for i, fx in enumerate(floor):
        sx = W * rng.uniform(0.1, 0.9)
        half = W * 0.09
        col = [ctx.light, _light(ctx.c2, 0.5), _light(ctx.light, 0.5)][i % 3]
        bd.polygon([(sx - 12, 0), (sx + 12, 0), (fx + half, hz + H * 0.10), (fx - half, hz + H * 0.10)], fill=(*col, int(70 * min(1, s + 0.3))))
    canvas = _over(canvas, beams, blur=14 * ctx.k)
    if s < 1:
        return canvas
    stage, sd = _layer(ctx)
    sd.rectangle((0, hz + H * 0.04, W, H), fill=(*_dark(ctx.dark, 0.5), 240))
    pools, pd_ = _layer(ctx)
    for fx in floor:
        pd_.ellipse((fx - W * 0.16, hz + H * 0.055, fx + W * 0.16, hz + H * 0.12), fill=(*_light(ctx.light, 0.4), 150))
    canvas = _over(canvas, stage, glow=14 * ctx.k)
    return _over(canvas, pools, blur=10 * ctx.k)


def lightning(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, k, rng = ctx.W, ctx.H, ctx.k, ctx.rng

    def bolt(x: float, y: float, y_end: float, step: float) -> list[tuple[float, float]]:
        pts = [(x, y)]
        while y < y_end:
            y += step * rng.uniform(0.6, 1.3)
            x += rng.uniform(-step * 0.9, step * 0.9)
            pts.append((x, y))
        return pts

    for _ in range(2 if s >= 1 else 1):
        layer, d = _layer(ctx)
        main = bolt(rng.uniform(W * 0.25, W * 0.75), -10, H * 0.62, H * 0.055)
        for width, col, a in [(int(16 * k), ctx.light, 90), (int(7 * k), _light(ctx.light, 0.6), 200), (int(3 * k), (255, 255, 255), 255)]:
            d.line(main, fill=(*col, int(a * min(1, s + 0.2))), width=max(2, width), joint="curve")
        for i in rng.sample(range(2, len(main) - 2), k=min(2, len(main) - 4)):
            br = bolt(main[i][0], main[i][1], main[i][1] + H * 0.16, H * 0.04)
            d.line(br, fill=(255, 255, 255, 190), width=max(2, int(3 * k)), joint="curve")
        canvas = _over(canvas, layer, glow=22 * k)
    flash, fd = _layer(ctx)
    fd.rectangle((0, 0, W, int(H * 0.5)), fill=(*_light(ctx.light, 0.5), int(38 * s)))
    return _over(canvas, flash, blur=30 * k)


def bubbles(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, k, rng = ctx.W, ctx.H, ctx.k, ctx.rng
    layer, d = _layer(ctx)
    cols = [ctx.c2, ctx.light, _light(ctx.c2, 0.4)]
    for i in range(int(30 * s) + 8):
        r = rng.randint(int(W * 0.015), int(W * 0.10))
        x, y = rng.randrange(W), int(rng.random() ** 0.9 * H * 0.72)
        col = cols[i % 3]
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*col, rng.randint(35, 85)), outline=(*_light(col, 0.5), 150), width=max(1, int(2 * k)))
        d.arc((x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7), 200, 260, fill=(255, 255, 255, 170), width=max(2, int(3 * k)))
    return _over(canvas, layer, glow=4 * k)


def clouds(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, rng = ctx.W, ctx.H, ctx.rng
    for i in range(7 if s >= 1 else 4):
        layer, d = _layer(ctx)
        cx, cy = rng.randint(-int(W * 0.1), int(W * 1.1)), int(H * rng.uniform(0.08, 0.55))
        scale = W * rng.uniform(0.10, 0.20) * (1.3 if s >= 1 else 1)
        col = _light(ctx.light, 0.35 + 0.1 * (i % 3)) if i % 2 else _light(ctx.c2, 0.55)
        for _ in range(9):
            ex, ey = cx + rng.uniform(-1.6, 1.6) * scale, cy + rng.uniform(-0.25, 0.25) * scale
            rx, ry = scale * rng.uniform(0.6, 1.1), scale * rng.uniform(0.28, 0.5)
            d.ellipse((ex - rx, ey - ry, ex + rx, ey + ry), fill=(*col, int(rng.randint(70, 130) * min(1, s + 0.2))))
        canvas = _over(canvas, layer, blur=16 * ctx.k)
    return canvas


def fireworks(ctx: Ctx, canvas: Image.Image, s: float) -> Image.Image:
    W, H, k, rng = ctx.W, ctx.H, ctx.k, ctx.rng
    cols = [ctx.light, _light(ctx.c2, 0.4), ctx.c2, (255, 255, 255)]
    layer, d = _layer(ctx)
    for b in range(5 if s >= 1 else 2):
        cx, cy = rng.randint(int(W * 0.12), int(W * 0.88)), rng.randint(int(H * 0.10), int(H * 0.46))
        R = rng.randint(int(W * 0.12), int(W * 0.26))
        col = cols[b % 4]
        n = 30
        for i in range(n):
            a = 2 * math.pi * i / n + rng.uniform(-0.05, 0.05)
            r0, r1 = R * rng.uniform(0.25, 0.4), R * rng.uniform(0.8, 1.0)
            d.line((cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * r1, cy + math.sin(a) * r1), fill=(*col, 190), width=max(2, int(3 * k)))
            d.ellipse((cx + math.cos(a) * r1 - 4 * k, cy + math.sin(a) * r1 - 4 * k, cx + math.cos(a) * r1 + 4 * k, cy + math.sin(a) * r1 + 4 * k), fill=(*_light(col, 0.4), 245))
        d.ellipse((cx - 8 * k, cy - 8 * k, cx + 8 * k, cy + 8 * k), fill=(255, 255, 255, 240))
    return _over(canvas, layer, glow=12 * k)


MOTIFS: dict[str, Callable[[Ctx, Image.Image, float], Image.Image]] = {
    "sun": sun, "moon": moon, "stars": stars, "skyline": skyline, "waves": waves, "rain": rain,
    "mountains": mountains, "flowers": flowers, "flames": flames, "road": road, "vinyl": vinyl,
    "grid": grid, "ribbons": ribbons, "heart": heart, "spotlight": spotlight, "lightning": lightning,
    "bubbles": bubbles, "clouds": clouds, "fireworks": fireworks,
}


# --------------------------------------------------------------------------- public API
def create_scene_artwork(brief: ArtBrief, size: tuple[int, int] = (900, 1350), scale: int = 2) -> Image.Image:
    """Render a song-specific scene. `scale` supersamples for smooth edges."""
    out_w, out_h = size
    W, H = out_w * scale, out_h * scale
    colors = sorted((_rgb(c) for c in brief.palette), key=_lum)
    while len(colors) < 4:
        colors.append(colors[-1])
    seed = hashlib.sha256(f"{brief.seed}|{brief.concept}|{brief.style}".encode("utf-8")).digest()
    ctx = Ctx(W, H, random.Random(int.from_bytes(seed[:8], "big")), colors[0], colors[1], colors[-2], colors[-1], int(H * 0.585))

    canvas = _sky(ctx)
    motifs = [m for m in brief.scene_motifs if m in MOTIFS] or ["stars", "ribbons"]
    if _lum(ctx.dark) < 90 and not {"stars", "clouds"} & set(motifs):
        canvas = stars(ctx, canvas, 0.35)  # faint star dust in dark skies
    for i, name in reversed(list(enumerate(motifs[:2]))):  # support first, hero on top
        canvas = MOTIFS[name](ctx, canvas, 1.0 if i == 0 else 0.55)

    rgb = canvas.convert("RGB")
    noise = Image.frombytes("L", (W, H), ctx.rng.randbytes(W * H)).convert("RGB")  # seeded film grain
    rgb = Image.blend(rgb, ImageChops.soft_light(rgb, noise), 0.24)
    vig = Image.radial_gradient("L").resize((W, H), Image.BICUBIC).point(lambda v: int(max(0, v - 90) * 0.9))
    rgb = Image.composite(Image.new("RGB", (W, H), _dark(ctx.dark, 0.6)), rgb, vig)
    return rgb.resize((out_w, out_h), Image.LANCZOS) if scale != 1 else rgb

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

"""Song Poster Studio application package."""

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

# Per-session guards. Posters are drawn locally (no paid API), so these are
# generous; they only stop one browser session from hogging shared CPU.
BRIEF_LIMIT = 20
POSTER_LIMIT = 20

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
