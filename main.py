#!/usr/bin/env python3
"""VELMARA - The Floating Isles.

A travel poster for a place that isn't there, drawn with only the Python
standard library (struct, zlib, hashlib, math, os). No network, no fonts
from disk, no unseeded randomness: the picture is painted pixel by pixel
from a fixed-seed generator, so running the program twice produces
byte-identical output.

Usage:  python3 main.py
Output: /output/entry.png (or $POSTER_OUTPUT), 1024x1024 PNG, <= 1 MiB.
"""

import hashlib
import math
import os
import struct
import zlib

W = 1024
H = 1024
OUT = os.environ.get("POSTER_OUTPUT", "/output/entry.png")

# ---------------------------------------------------------------- canvas
buf = bytearray(W * H * 3)


def fill_span(y, x0, x1, r, g, b):
    """Opaque horizontal span on row y (clipped)."""
    if y < 0 or y >= H:
        return
    if x0 < 0:
        x0 = 0
    if x1 >= W:
        x1 = W - 1
    if x1 < x0:
        return
    n = x1 - x0 + 1
    i = (y * W + x0) * 3
    buf[i:i + n * 3] = bytes((r, g, b)) * n


def blend_span(y, x0, x1, r, g, b, a):
    """Alpha-blended horizontal span on row y (clipped)."""
    if a <= 0 or y < 0 or y >= H:
        return
    if x0 < 0:
        x0 = 0
    if x1 >= W:
        x1 = W - 1
    if x1 < x0:
        return
    if a >= 255:
        fill_span(y, x0, x1, r, g, b)
        return
    ia = 255 - a
    base = y * W * 3
    for x in range(x0, x1 + 1):
        i = base + x * 3
        buf[i] = (r * a + buf[i] * ia) // 255
        buf[i + 1] = (g * a + buf[i + 1] * ia) // 255
        buf[i + 2] = (b * a + buf[i + 2] * ia) // 255


def fill_rect(x, y, w, h, r, g, b):
    for yy in range(y, y + h):
        fill_span(yy, x, x + w - 1, r, g, b)


def disc(cx, cy, rad, r, g, b, a=255):
    rad = int(rad)
    rr = rad * rad
    for dy in range(-rad, rad + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        dx = int((rr - dy * dy) ** 0.5)
        if a >= 255:
            fill_span(y, cx - dx, cx + dx, r, g, b)
        else:
            blend_span(y, cx - dx, cx + dx, r, g, b, a)


def ellipse(cx, cy, rx, ry, r, g, b, a=255):
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        t = 1.0 - (dy * dy) / float(ry * ry)
        if t <= 0:
            continue
        dx = int(rx * t ** 0.5)
        if a >= 255:
            fill_span(y, cx - dx, cx + dx, r, g, b)
        else:
            blend_span(y, cx - dx, cx + dx, r, g, b, a)


def poly(points, r, g, b, a=255):
    """Scanline-filled polygon."""
    ys = [p[1] for p in points]
    y0 = max(0, min(ys))
    y1 = min(H - 1, max(ys))
    n = len(points)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= yc < y2p) or (y2p <= yc < y1p):
                t = (yc - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa, xb = int(xs[k]), int(xs[k + 1])
            if a >= 255:
                fill_span(y, xa, xb, r, g, b)
            else:
                blend_span(y, xa, xb, r, g, b, a)


def soft_disc(cx, cy, rad, r, g, b, peak):
    """Radial-falloff glow / puff. Alpha peaks at the centre, fades to 0."""
    rr = rad * rad
    for dy in range(-rad, rad + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        dx = int((rr - dy * dy) ** 0.5)
        x0 = cx - dx
        x1 = cx + dx
        if x0 < 0:
            x0 = 0
        if x1 >= W:
            x1 = W - 1
        base = y * W * 3
        for x in range(x0, x1 + 1):
            ddx = x - cx
            t = 1.0 - (ddx * ddx + dy * dy) / rr
            a = int(peak * t * t)
            if a <= 0:
                continue
            i = base + x * 3
            ia = 255 - a
            buf[i] = (r * a + buf[i] * ia) // 255
            buf[i + 1] = (g * a + buf[i + 1] * ia) // 255
            buf[i + 2] = (b * a + buf[i + 2] * ia) // 255


def thick_line(x1, y1, x2, y2, rad, r, g, b, a=255):
    """A line drawn as overlapping discs."""
    steps = int(max(abs(x2 - x1), abs(y2 - y1))) + 1
    for s in range(steps + 1):
        t = s / float(steps)
        disc(int(x1 + (x2 - x1) * t), int(y1 + (y2 - y1) * t),
             rad, r, g, b, a)


# ------------------------------------------------------- deterministic rng
_seed = [987654321]


def rnd():
    _seed[0] = (_seed[0] * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed[0] / 0x7FFFFFFF


# ------------------------------------------------------------------- font
# 5x7 pixel font, drawn by hand for this poster.
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    "-": (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    "\u00b7": (".....", ".....", "..#..", ".....", ".....", ".....", "....."),
}


def text_width(s, scale, spacing):
    return len(s) * 5 * scale + (len(s) - 1) * spacing


def _glyph(ch, x, y, scale, r, g, b, expand):
    rows = FONT.get(ch)
    if rows is None:
        return
    for row in range(7):
        line = rows[row]
        for col in range(5):
            if line[col] == "#":
                cx = x + col * scale - expand
                cy = y + row * scale - expand
                w = scale + 2 * expand
                fill_rect(cx, cy, w, w, r, g, b)


def draw_text(s, cx, y, scale, spacing, fg, outline=None, outline_w=0):
    """Draw centred text. outline=(r,g,b) draws an expanded pass first."""
    w = text_width(s, scale, spacing)
    x = cx - w // 2
    if outline is not None and outline_w > 0:
        xx = x
        for ch in s:
            _glyph(ch, xx, y, scale, outline[0], outline[1], outline[2],
                   outline_w)
            xx += 5 * scale + spacing
    xx = x
    for ch in s:
        _glyph(ch, xx, y, scale, fg[0], fg[1], fg[2], 0)
        xx += 5 * scale + spacing


# ------------------------------------------------------------------- sky
SKY_STOPS = [
    (0.00, (18, 26, 58)),
    (0.30, (52, 58, 102)),
    (0.52, (107, 74, 114)),
    (0.68, (198, 93, 99)),
    (0.82, (240, 152, 90)),
    (1.00, (247, 200, 115)),
]


def paint_sky():
    for y in range(H):
        t = y / float(H - 1)
        for i in range(len(SKY_STOPS) - 1):
            t0, c0 = SKY_STOPS[i]
            t1, c1 = SKY_STOPS[i + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                r = int(c0[0] + (c1[0] - c0[0]) * f)
                g = int(c0[1] + (c1[1] - c0[1]) * f)
                b = int(c0[2] + (c1[2] - c0[2]) * f)
                break
        else:
            r, g, b = SKY_STOPS[-1][1]
        row = bytes((r, g, b)) * W
        buf[y * W * 3:(y + 1) * W * 3] = row


def paint_stars():
    for _ in range(230):
        x = int(rnd() * W)
        y = int(rnd() * 430)
        big = rnd() < 0.28
        a = 100 + int(rnd() * 155)
        if big:
            disc(x, y, 2, 255, 255, 255, a)
        else:
            disc(x, y, 1, 255, 255, 255, a)
    # A few hero stars with a sparkle cross.
    for (x, y) in [(120, 90), (330, 60), (880, 120), (940, 260), (60, 300)]:
        disc(x, y, 2, 255, 255, 255, 230)
        thick_line(x - 7, y, x + 7, y, 1, 255, 255, 255, 150)
        thick_line(x, y - 7, x, y + 7, 1, 255, 255, 255, 150)


def aurora_band(base, amp1, amp2, ph1, ph2, half, color, peak):
    r, g, b = color
    for x in range(W):
        cy = (base + amp1 * math.sin(x * 0.004 + ph1)
              + amp2 * math.sin(x * 0.011 + ph2))
        edge = min(1.0, x / 180.0, (W - 1 - x) / 180.0)
        if edge <= 0:
            continue
        for dy in range(-half, half + 1):
            y = int(cy) + dy
            if y < 0 or y >= H:
                continue
            t = 1.0 - (dy * dy) / float(half * half)
            a = int(peak * edge * t * t)
            if a <= 0:
                continue
            i = (y * W + x) * 3
            ia = 255 - a
            buf[i] = (r * a + buf[i] * ia) // 255
            buf[i + 1] = (g * a + buf[i + 1] * ia) // 255
            buf[i + 2] = (b * a + buf[i + 2] * ia) // 255


def paint_aurora():
    aurora_band(150, 38, 14, 0.6, 2.1, 52, (143, 245, 210), 95)
    aurora_band(212, 30, 18, 1.9, 0.4, 44, (184, 245, 154), 80)
    aurora_band(96, 26, 10, 3.1, 1.2, 36, (201, 167, 245), 68)


def paint_sun():
    soft_disc(735, 665, 130, 255, 196, 107, 90)
    soft_disc(735, 665, 70, 255, 214, 140, 110)
    disc(735, 665, 38, 255, 227, 161, 255)
    disc(735, 665, 26, 255, 246, 216, 255)


# --------------------------------------------------------------- islands
def pine(x, y, s):
    """A small pine tree, trunk at (x, y), growing upward, size s."""
    fill_rect(x - 2, y, 5, int(12 * s), 74, 58, 44)
    top = y - int(46 * s)
    poly([(x, top), (x - int(16 * s), y - int(8 * s)),
          (x + int(16 * s), y - int(8 * s))], 38, 90, 64)
    poly([(x, top + int(14 * s)), (x - int(13 * s), y + int(2 * s)),
          (x + int(13 * s), y + int(2 * s))], 30, 76, 54)
    poly([(x, top + int(26 * s)), (x - int(10 * s), y + int(10 * s)),
          (x + int(10 * s), y + int(10 * s))], 24, 64, 46)


def waterfall(x, y0, y1, width, alpha0):
    for y in range(y0, y1):
        t = (y - y0) / float(y1 - y0)
        a = int(alpha0 * (1.0 - t))
        if a <= 0:
            continue
        wob = int(3 * math.sin(y * 0.05))
        w = max(2, int(width * (1.0 - 0.3 * t)))
        blend_span(y, x + wob - w, x + wob + w, 223, 243, 255, a)
        blend_span(y, x + wob - w // 2, x + wob + w // 2,
                   255, 255, 255, min(255, a + 40))
    soft_disc(x, y1, 26, 223, 243, 255, 60)


def paint_islands():
    # --- far left isle, small, with a pine
    poly([(65, 430), (235, 430), (200, 490), (150, 545), (100, 490)],
         36, 31, 56)
    ellipse(150, 430, 86, 13, 63, 122, 79)
    ellipse(150, 427, 82, 10, 94, 164, 99)
    pine(150, 424, 0.8)

    # --- right isle, with a domed pavilion
    poly([(700, 500), (940, 500), (880, 570), (820, 640), (760, 575)],
         42, 35, 64)
    ellipse(820, 500, 122, 17, 63, 122, 79)
    ellipse(820, 497, 118, 13, 94, 164, 99)
    # pavilion: sand dome on a low base
    fill_rect(806, 482, 28, 14, 232, 217, 176)
    disc(820, 482, 14, 232, 217, 176)
    disc(820, 482, 14, 214, 192, 148, 0)  # no-op guard, keeps shape order
    disc(820, 466, 3, 255, 233, 168, 255)
    fill_rect(814, 488, 4, 8, 58, 46, 74)
    fill_rect(826, 488, 4, 8, 58, 46, 74)

    # --- main isle, wide, with the Skyneedle spire
    poly([(140, 600), (700, 600), (620, 690), (500, 780), (420, 800),
          (330, 745), (210, 685)], 36, 31, 56)
    # warm rim light on the sunlit right underside
    thick_line(700, 600, 620, 690, 3, 232, 145, 107, 150)
    thick_line(620, 690, 500, 780, 3, 232, 145, 107, 120)
    # grassy top
    ellipse(420, 600, 282, 24, 63, 122, 79)
    ellipse(420, 597, 278, 19, 94, 164, 99)
    for (gx, gy, gr) in [(210, 592, 9), (300, 588, 11), (520, 590, 10),
                         (610, 594, 8), (380, 590, 7)]:
        disc(gx, gy, gr, 48, 100, 66, 255)
    # the Skyneedle: a slender crystal spire, the one clear landmark
    soft_disc(420, 348, 110, 159, 232, 255, 70)
    soft_disc(420, 348, 46, 210, 245, 255, 110)
    poly([(408, 600), (432, 600), (428, 380), (420, 348), (412, 380)],
         216, 244, 255)
    poly([(416, 600), (424, 600), (422, 390), (420, 360), (418, 390)],
         255, 255, 255, 220)
    disc(420, 348, 9, 255, 233, 168, 255)
    thick_line(420 - 13, 348, 420 + 13, 348, 1, 255, 233, 168, 170)
    thick_line(420, 348 - 13, 420, 348 + 13, 1, 255, 233, 168, 170)
    # waterfalls spilling off both edges into the clouds
    waterfall(196, 606, 786, 9, 215)
    waterfall(644, 606, 766, 8, 205)


# -------------------------------------------------------------- cloud sea
def paint_clouds():
    # back layer, dusk-shadowed
    for _ in range(7):
        cx = int(40 + rnd() * 944)
        cy = int(700 + rnd() * 70)
        r = int(55 + rnd() * 55)
        soft_disc(cx, cy, r, 227, 172, 130, 200)
    # mid layer, warm lit
    for _ in range(8):
        cx = int(30 + rnd() * 964)
        cy = int(770 + rnd() * 90)
        r = int(60 + rnd() * 65)
        soft_disc(cx, cy, r, 243, 217, 184, 215)
    # front layer, pale gold, fills the bottom
    for _ in range(9):
        cx = int(20 + rnd() * 984)
        cy = int(870 + rnd() * 130)
        r = int(70 + rnd() * 80)
        soft_disc(cx, cy, r, 251, 238, 220, 225)
    # soft shadows where the isles hang above the clouds
    soft_disc(420, 830, 130, 201, 143, 110, 55)
    soft_disc(820, 668, 80, 201, 143, 110, 50)
    # mist veiling the island tips
    soft_disc(420, 800, 60, 255, 250, 240, 70)
    soft_disc(820, 640, 44, 255, 250, 240, 60)


def paint_birds():
    for (x, y) in [(300, 300), (342, 284), (384, 314),
                   (700, 258), (742, 284), (690, 318)]:
        thick_line(x - 7, y + 3, x, y, 2, 35, 32, 58, 210)
        thick_line(x, y, x + 7, y + 3, 2, 35, 32, 58, 210)


# ------------------------------------------------------------------- text
def paint_text():
    ink = (27, 35, 64)
    draw_text("VELMARA", W // 2, 78, 18, 18, (255, 255, 255),
              outline=ink, outline_w=5)
    draw_text("THE FLOATING ISLES", W // 2, 228, 5, 6, (255, 233, 201),
              outline=ink, outline_w=2)
    draw_text("ABOVE THE CLOUDS \u00b7 BEYOND THE MAP", W // 2, 968, 3, 4,
              (58, 46, 74))


def paint_frame():
    for x in range(26, W - 26):
        blend_span(26, x, x, 255, 255, 255, 64)
        blend_span(H - 27, x, x, 255, 255, 255, 64)
    for y in range(26, H - 26):
        blend_span(y, 26, 26, 255, 255, 255, 64)
        blend_span(y, W - 27, W - 27, 255, 255, 255, 64)


# -------------------------------------------------------------------- png
def write_png(path, w, h, rgb):
    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3]
                   for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def build():
    paint_sky()
    paint_stars()
    paint_aurora()
    paint_sun()
    paint_islands()
    paint_clouds()
    paint_birds()
    paint_text()
    paint_frame()


def main():
    build()
    outdir = os.path.dirname(OUT)
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    size = write_png(OUT, W, H, bytes(buf))
    digest = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
    print("WROTE %s %d bytes sha256=%s" % (OUT, size, digest))


if __name__ == "__main__":
    main()
