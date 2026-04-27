#!/usr/bin/env python3
"""Generate PWA icons for Avalanche: static/icon-192.png and static/icon-512.png.

Pure Python (stdlib only: struct + zlib).  Run once from the project root:
    python scripts/make_icons.py

Design: isometric cube on black background, gold colour scheme.
The three visible cube faces (top / right / left) are shaded light-to-dark to
give the 3D illusion.  A bright gold edge is drawn over the face fills.
"""

import struct
import zlib
from pathlib import Path

# ---- Colour palette (R, G, B) -----------------------------------------------
BG: tuple[int, int, int] = (0, 0, 0)             # Background — pure black
FACE_TOP: tuple[int, int, int] = (255, 215, 0)   # Top face  — bright gold
FACE_RIGHT: tuple[int, int, int] = (184, 134, 11) # Right face — dark goldenrod
FACE_LEFT: tuple[int, int, int] = (110, 78, 0)   # Left face  — deep brown-gold
EDGE: tuple[int, int, int] = (255, 248, 200)      # Edges      — warm off-white

# ---- PNG encoding -----------------------------------------------------------

def _make_chunk(tag: bytes, data: bytes) -> bytes:
    """Pack a single PNG chunk: length + tag + data + CRC32."""
    combined = tag + data
    crc = zlib.crc32(combined) & 0xFFFF_FFFF
    return struct.pack(">I", len(data)) + combined + struct.pack(">I", crc)


def _encode_png(w: int, h: int, pixels: list[tuple[int, int, int]]) -> bytes:
    """Encode a flat RGB pixel list as a minimal PNG bytestring."""
    assert len(pixels) == w * h, "pixel count must equal w * h"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # RGB, no alpha
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type = None
        for x in range(w):
            raw.extend(pixels[y * w + x])
    idat = zlib.compress(bytes(raw), 9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _make_chunk(b"IHDR", ihdr)
        + _make_chunk(b"IDAT", idat)
        + _make_chunk(b"IEND", b"")
    )


# ---- Drawing primitives -----------------------------------------------------

def _fill_poly(
    pixels: list[tuple[int, int, int]],
    w: int,
    h: int,
    verts: list[tuple[float, float]],
    color: tuple[int, int, int],
) -> None:
    """Scanline fill for a convex polygon."""
    if len(verts) < 3:
        return
    ys = [v[1] for v in verts]
    y_lo = max(0, int(min(ys)))
    y_hi = min(h - 1, int(max(ys)))
    n = len(verts)
    for y in range(y_lo, y_hi + 1):
        xs: list[float] = []
        for i in range(n):
            x0, y0 = verts[i]
            x1, y1 = verts[(i + 1) % n]
            if y0 == y1:
                continue
            if (y0 <= y <= y1) or (y1 <= y <= y0):
                t = (y - y0) / (y1 - y0)
                xs.append(x0 + t * (x1 - x0))
        if len(xs) >= 2:
            xs.sort()
            x_lo = max(0, int(xs[0]))
            x_hi = min(w - 1, int(xs[-1]))
            for x in range(x_lo, x_hi + 1):
                pixels[y * w + x] = color


def _draw_line(
    pixels: list[tuple[int, int, int]],
    w: int,
    h: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    """Bresenham line draw with an explicit step bound (Rule 2).

    The bound dx+dy+2 is a known mathematical tight upper bound for Bresenham's
    algorithm.  Exceeding it indicates a bug in the caller (non-integer coords
    or mismatched state), so the guard is an assert per the Rule 2 note.
    """
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    max_steps = dx + dy + 2   # tight upper bound; exceeding it is a bug
    steps = 0
    while True:
        assert steps <= max_steps, f"_draw_line exceeded Bresenham bound ({max_steps})"
        if 0 <= x0 < w and 0 <= y0 < h:
            pixels[y0 * w + x0] = color
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
        steps += 1


def _thick_edge(
    pixels: list[tuple[int, int, int]],
    w: int,
    h: int,
    p0: tuple[float, float],
    p1: tuple[float, float],
    color: tuple[int, int, int],
    thickness: int,
) -> None:
    """Draw a line with a given pixel thickness by offsetting in both axes."""
    if thickness < 1:
        raise ValueError(f"thickness must be >= 1, got {thickness}")
    x0, y0 = int(p0[0]), int(p0[1])
    x1, y1 = int(p1[0]), int(p1[1])
    offsets = range(thickness)
    for dy in offsets:
        _draw_line(pixels, w, h, x0, y0 + dy, x1, y1 + dy, color)
        _draw_line(pixels, w, h, x0 + dy, y0, x1 + dy, y1, color)


# ---- Icon pixel builder -----------------------------------------------------

def _make_pixels(size: int) -> list[tuple[int, int, int]]:
    """Build the pixel array for the isometric-cube icon at *size* × *size*."""
    pixels: list[tuple[int, int, int]] = [BG] * (size * size)

    cx, cy = size // 2, size // 2
    a = int(size * 0.34)   # horizontal half-scale
    b = a // 2             # vertical half-scale  (gives a 2:1-ish cube proportion)

    # 7 key vertices — (x, y) in screen coords (y increases downward)
    vtop: tuple[float, float] = (cx,     cy - a)
    vtr:  tuple[float, float] = (cx + a, cy - b)
    vbr:  tuple[float, float] = (cx + a, cy + b)
    vbot: tuple[float, float] = (cx,     cy + a)
    vbl:  tuple[float, float] = (cx - a, cy + b)
    vtl:  tuple[float, float] = (cx - a, cy - b)
    vmid: tuple[float, float] = (cx,     cy)

    # Fill faces (painter's order — no overlap needed, faces don't intersect)
    _fill_poly(pixels, size, size, [vtop, vtr, vmid, vtl], FACE_TOP)
    _fill_poly(pixels, size, size, [vtr, vbr, vbot, vmid], FACE_RIGHT)
    _fill_poly(pixels, size, size, [vtl, vmid, vbot, vbl], FACE_LEFT)

    # Draw edges on top of faces — outer hexagon + inner Y
    tk = max(1, size // 150)   # thickness: ~1 px @ 192, ~3 px @ 512
    outer = [(vtop, vtr), (vtr, vbr), (vbr, vbot), (vbot, vbl), (vbl, vtl), (vtl, vtop)]
    inner = [(vmid, vtr), (vmid, vtl), (vmid, vbot)]
    for p0, p1 in outer + inner:
        _thick_edge(pixels, size, size, p0, p1, EDGE, tk)

    assert len(pixels) == size * size, "pixel count invariant violated"
    return pixels


# ---- Entry point ------------------------------------------------------------

def main() -> None:
    """Generate icon-192.png and icon-512.png into static/."""
    # Rule 9: no more than two chained attribute accesses.
    scripts_dir = Path(__file__).parent
    out_dir = scripts_dir.parent / "static"
    out_dir.mkdir(exist_ok=True)
    for size in (192, 512):
        pix = _make_pixels(size)
        data = _encode_png(size, size, pix)
        path = out_dir / f"icon-{size}.png"
        path.write_bytes(data)
        print(f"  {path.name}  {size}×{size}  {len(data):,} bytes")
    print("done.")


if __name__ == "__main__":
    main()
