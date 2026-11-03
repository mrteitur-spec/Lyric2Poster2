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
