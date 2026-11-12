#!/usr/bin/env python3
"""Koi over the Red Sun -- coolest-art-01 entry.

A deterministic, standard-library-only program that paints a bold
ukiyo-e style poster -- a giant koi leaping across a huge red sun
above a night sea -- and writes it to /output/entry.png (1024x1024,
under 1 MiB). No network, no randomness from the environment: every
pixel is computed from fixed constants, so two runs write identical
bytes. Rebuilt in a session started after the competition opened.

Run locally:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- canvas
# The picture is painted into one flat RGB bytearray, row by row.
buf = bytearray(W * H * 3)


def _lerp(a, b, t):
    """Linear interpolation between a and b."""
    return a + (b - a) * t


def _mix(c1, c2, t):
    """Blend two RGB colours by t (0 -> c1, 1 -> c2)."""
    return (
        round(_lerp(c1[0], c2[0], t)),
        round(_lerp(c1[1], c2[1], t)),
        round(_lerp(c1[2], c2[2], t)),
    )


def span(y, x0, x1, color):
    """Fill a horizontal run of pixels on row y with a flat colour.

    Spans are the only primitive that touches the canvas: discs,
    rings and polygons all decompose into spans, so the painter
    stays fast and deterministic.
    """
    if y < 0 or y >= H:
        return
    lo = max(0, int(x0))
    hi = min(W - 1, int(x1))
    if hi < lo:
        return
    r, g, b = color
    start = y * W * 3
    count = hi - lo + 1
    buf[start + lo * 3: start + (hi + 1) * 3] = bytes((r, g, b)) * count


def disc(cx, cy, r, color):
    """Filled circle, drawn as horizontal spans."""
    rr = int(r)
    for dy in range(-rr, rr + 1):
        half = int(math.sqrt(rr * rr - dy * dy))
        span(cy + dy, cx - half, cx + half, color)


def ring(cx, cy, r_outer, r_inner, color):
    """A flat ring: disc minus a smaller disc, drawn as spans."""
    ro = int(r_outer)
    ri = int(r_inner)
    for dy in range(-ro, ro + 1):
        dx_o = int(math.sqrt(ro * ro - dy * dy))
        if abs(dy) < ri:
            dx_i = int(math.sqrt(ri * ri - dy * dy))
            span(cy + dy, cx - dx_o, cx - dx_i - 1, color)
            span(cy + dy, cx + dx_i + 1, cx + dx_o, color)
        else:
            span(cy + dy, cx - dx_o, cx + dx_o, color)


def polygon(points, color):
    """Filled polygon via scanline edge intersection.

    For each scanline, collect the x where each edge crosses it,
    sort them, and fill between successive pairs.
    """
    ys = [pt[1] for pt in points]
    top = max(0, int(min(ys)))
    bottom = min(H - 1, int(max(ys)))
    count = len(points)
    for y in range(top, bottom + 1):
        crossings = []
        for i in range(count):
            ax, ay = points[i]
            bx, by = points[(i + 1) % count]
            if (ay <= y < by) or (by <= y < ay):
                frac = (y - ay) / (by - ay)
                crossings.append(ax + frac * (bx - ax))
        if len(crossings) >= 2:
            crossings.sort()
            for k in range(0, len(crossings) - 1, 2):
                span(y, crossings[k], crossings[k + 1], color)


# ---------------------------------------------------------------- sky
# The sky is a vertical gradient through six stops, deep indigo at
# the top down to a burning orange horizon, sampled per scanline.
SKY_STOPS = [
    (0.00, (13, 10, 44)),     # deep indigo night
    (0.30, (46, 20, 88)),     # violet
    (0.50, (118, 32, 96)),    # magenta dusk
    (0.66, (196, 62, 72)),    # ember red
    (0.78, (250, 122, 54)),   # burning horizon
    (1.00, (250, 122, 54)),
]


def sky_color(t):
    """Sky gradient colour at height fraction t (0 top, 1 horizon)."""
    for i in range(len(SKY_STOPS) - 1):
        start_t, start_c = SKY_STOPS[i]
        end_t, end_c = SKY_STOPS[i + 1]
        if start_t <= t <= end_t:
            span_len = end_t - start_t
            frac = (t - start_t) / span_len if span_len > 0 else 0
            return _mix(start_c, end_c, frac)
    return SKY_STOPS[-1][1]


# Paint the gradient one scanline at a time, top to bottom.
for _y in range(H):
    span(_y, 0, W - 1, sky_color(_y / (H - 1)))

# ---------------------------------------------------------------- stars
# Deterministic pseudo-random dots (fixed-seed LCG), upper sky only.
# The same seed always gives the same stars, in the same order.
_seed = 123456789


def _rand():
    """Next deterministic pseudo-random float in [0, 1)."""
    global _seed
    _seed = (_seed * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed / 0x7FFFFFFF


SUN_CX, SUN_CY, SUN_R = 512, 452, 292
for _ in range(140):
    sx = int(_rand() * W)
    sy = int(_rand() * 470)
    if (sx - SUN_CX) ** 2 + (sy - SUN_CY) ** 2 < (SUN_R + 12) ** 2:
        continue
    size = 1 if _rand() < 0.6 else 2
    star_col = (255, 244, 214) if _rand() < 0.5 else (255, 255, 255)
    disc(sx, sy, size, star_col)
    if _rand() < 0.18:  # a few four-point sparkles
        for dx in range(-5, 6):
            span(sy, sx + dx, sx + dx, star_col)
        for dy in range(-5, 6):
            span(sy + dy, sx, sx, star_col)

# ---------------------------------------------------------------- sun
disc(SUN_CX, SUN_CY, SUN_R + 6, (176, 32, 24))          # dark rim
disc(SUN_CX, SUN_CY, SUN_R, (255, 84, 38))              # blazing disc
disc(SUN_CX, SUN_CY, 185, (255, 112, 50))               # softer hot core
ring(SUN_CX, SUN_CY, SUN_R + 26, SUN_R + 18, (255, 196, 110))  # gold halo

# ---------------------------------------------------------------- birds
# Silhouette birds: each is two short thick strokes meeting at a point.
def _line(x0, y0, x1, y1, r, color):
    """A short thick line, drawn as discs along the segment."""
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(dist))
    for i in range(steps + 1):
        frac = i / steps
        disc(int(x0 + (x1 - x0) * frac), int(y0 + (y1 - y0) * frac), r, color)


def bird(x, y, s, color=(22, 12, 40)):
    """A bird as a shallow V: left wing, right wing, meeting at (x, y)."""
    _line(x - s, y + s * 0.28, x, y, 3, color)
    _line(x, y, x + s, y + s * 0.28, 3, color)


bird(210, 210, 26)
bird(300, 165, 19)
bird(820, 180, 22)
bird(760, 250, 15)

# ---------------------------------------------------------------- sea
# The sea is a dark gradient from the horizon down, then three
# rolling wave bands with foam crests drawn over it.
SEA_TOP = 786
for y in range(SEA_TOP, H):
    t = (y - SEA_TOP) / (H - SEA_TOP)
    span(y, 0, W - 1, _mix((14, 44, 92), (6, 16, 44), t))


def wave_band(y_base, amp, color, crest):
    """One rolling wave band: a sine-topped fill plus a foam crest."""
    # Sine-topped fill down to the bottom of the canvas.
    crest_line = []
    for x in range(0, W + 1, 8):
        crest_line.append((x, y_base + amp * math.sin(x / 150.0 + y_base)))
    fill = crest_line + [(W, H), (0, H)]
    polygon(fill, color)
    # Continuous foam crest: a thin sine strip, not beads.
    strip = [(x, y_base + amp * math.sin(x / 150.0 + y_base))
             for x in range(0, W + 1, 4)]
    strip += [(x, y_base + 4 + amp * math.sin(x / 150.0 + y_base))
              for x in range(W, -1, -4)]
    polygon(strip, crest)


wave_band(800, 16, (16, 78, 122), (214, 240, 255))
wave_band(872, 20, (11, 58, 98), (190, 228, 252))
wave_band(946, 18, (7, 38, 72), (160, 210, 245))

# ---------------------------------------------------------------- koi
# A great koi arcs over the sun: tail low-left, head high-right.
# Quadratic bezier from tail to head.
P0 = (128.0, 812.0)
P1 = (330.0, 210.0)
P2 = (906.0, 330.0)


def bez(t):
    """Point and unit tangent on the koi's quadratic bezier spine."""
    mt = 1 - t
    x = mt * mt * P0[0] + 2 * mt * t * P1[0] + t * t * P2[0]
    y = mt * mt * P0[1] + 2 * mt * t * P1[1] + t * t * P2[1]
    dx = 2 * mt * (P1[0] - P0[0]) + 2 * t * (P2[0] - P1[0])
    dy = 2 * mt * (P1[1] - P0[1]) + 2 * t * (P2[1] - P1[1])
    length = math.hypot(dx, dy) or 1.0
    return x, y, dx / length, dy / length


def body_r(t):
    """Body radius along the spine: tail narrow, belly full, head broad."""
    return 22 + 44 * math.sin(math.pi * (0.10 + 0.78 * t)) ** 0.9


def _up(dx, dy):
    """Unit normal pointing up on screen (negative y)."""
    nx, ny = -dy, dx
    if ny > 0:
        nx, ny = -nx, -ny
    return nx, ny


def _down(dx, dy):
    """Unit normal pointing down on screen: the opposite of _up."""
    nx, ny = _up(dx, dy)
    return -nx, -ny


KOI = (255, 122, 26)       # flame orange
KOI_DARK = (214, 74, 18)
BELLY = (255, 236, 205)    # cream belly
INK = (16, 10, 30)

# Tail fins first (behind the body): two long flowing ribbons, wide
# where they leave the body and tapering to a point as they trail.
tx, ty, tdx, tdy = bez(0.0)
bx, by = tx - tdx * 115, ty - tdy * 115          # tail tip, far behind
ux, uy = _up(tdx, tdy)
polygon([(tx + ux * 22, ty + uy * 22),
         (tx - ux * 8, ty - uy * 8),
         (bx + ux * 88, by + uy * 88)], (255, 92, 40))
polygon([(tx + ux * 8, ty + uy * 8),
         (tx - ux * 22, ty - uy * 22),
         (bx - ux * 88, by - uy * 88)], (232, 66, 30))

# Body: overlapping discs along the curve, 130 of them.
N = 130
spine = []
for i in range(N + 1):
    tt = i / N
    bx2, by2, bdx, bdy = bez(tt)
    spine.append((tt, bx2, by2, bdx, bdy))
    disc(int(bx2), int(by2), body_r(tt), KOI)

# Rounded snout: one broad disc at the head so the face is not blunt.
hx, hy, hdx, hdy = bez(1.0)
disc(int(hx + hdx * 8), int(hy + hdy * 8), 50, KOI)

# Dark edge along the top of the body, contiguous so it reads as a line.
for tt, xx, yy, ddx, ddy in spine[::2]:
    nx, ny = _up(ddx, ddy)
    disc(int(xx + nx * (body_r(tt) - 2)), int(yy + ny * (body_r(tt) - 2)),
         3, KOI_DARK)

# Slim cream belly stripe along the underside, mid-body only.
for tt, xx, yy, ddx, ddy in spine[::2]:
    if tt < 0.22 or tt > 0.88:
        continue
    nx, ny = _down(ddx, ddy)
    rr = body_r(tt)
    disc(int(xx + nx * rr * 0.55), int(yy + ny * rr * 0.55), rr * 0.34, BELLY)

# Ink spots on the back (upper side), four of them along the spine.
for tt, off in ((0.30, -0.30), (0.48, -0.42), (0.62, -0.25), (0.78, -0.38)):
    xx, yy, ddx, ddy = bez(tt)
    nx, ny = _up(ddx, ddy)
    rr = body_r(tt)
    disc(int(xx + nx * rr * -off), int(yy + ny * rr * -off), rr * 0.34, INK)

# Dorsal fin: a row of spiky triangles along the back.
for tt in (0.34, 0.44, 0.54, 0.64):
    xx, yy, ddx, ddy = bez(tt)
    nx, ny = -ddy, ddx
    if ny > 0:
        nx, ny = -nx, -ny
    rr = body_r(tt)
    fx, fy = xx + nx * rr * 0.85, yy + ny * rr * 0.85
    polygon([(fx - ddx * 26, fy - ddy * 26),
             (fx + nx * 52, fy + ny * 52),
             (fx + ddx * 26, fy + ddy * 26)], KOI_DARK)

# Pectoral fin near the head, sweeping down and back.
px, py, pdx, pdy = bez(0.88)
pnx, pny = _down(pdx, pdy)
qx, qy, qdx, qdy = bez(0.95)
polygon([(px + pnx * 18, py + pny * 18),
         (qx + pnx * 18, qy + pny * 18),
         (px + pnx * 56 - pdx * 22, py + pny * 56 - pdy * 22)],
        (255, 150, 70))

# Head and eye: a dark eye with a white glint, then a small mouth.
ex, ey, edx, edy = bez(0.985)
enx, eny = _up(edx, edy)
disc(int(ex + enx * 16), int(ey + eny * 16), 15, INK)
disc(int(ex + enx * 16 + 5), int(ey + eny * 16 - 5), 5, (255, 255, 255))
# Mouth: a small dark smile at the snout.
mx, my = ex + edx * 34, ey + edy * 34
disc(int(mx), int(my), 5, INK)

# ---------------------------------------------------------------- frame
# A dark border, 16 px on every side, framing the poster.
BORDER = (10, 8, 32)
for _y in range(0, 16):
    span(_y, 0, W - 1, BORDER)
    span(H - 1 - _y, 0, W - 1, BORDER)
for _x in range(0, 16):
    for _y in range(H):
        span(_y, _x, _x, BORDER)
        span(_y, W - 1 - _x, W - 1 - _x, BORDER)

# ---------------------------------------------------------------- PNG out
# The PNG is written with zlib level 9; identical input pixels give
# identical bytes on every run.
def _chunk(kind, data):
    """One PNG chunk: length, type, data, CRC32 over type+data."""
    c = struct.pack(">I", len(data)) + kind + data
    return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


raw = b"".join(b"\x00" + bytes(buf[y * W * 3:(y + 1) * W * 3])
               for y in range(H))
png = (b"\x89PNG\r\n\x1a\n"
       + _chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
       + _chunk(b"IDAT", zlib.compress(raw, 9))
       + _chunk(b"IEND", b""))

out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "entry.png"), "wb") as f:
    f.write(png)
print(f"wrote {os.path.join(out_dir, 'entry.png')} ({len(png)} bytes)")
