#!/usr/bin/env python3
"""CSC monogram: two open containers, an S, and a swoosh leaving the last dock."""

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT_CANDIDATES = [
    Path("/tmp/fonts/Montserrat-ExtraBold.ttf"),
    Path(__file__).with_name("fonts") / "Montserrat-ExtraBold.ttf",
]


def load_font():
    for path in FONT_CANDIDATES:
        if path.exists():
            font = TTFont(str(path))
            return font.getGlyphSet(), font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm
    raise SystemExit("Montserrat ExtraBold was not found.")


GLYPH, CMAP, HMTX, UPEM = load_font()


def container_c(x, y, w, h, t):
    """A C drawn as an open container. The right side is the dock mouth."""
    return (
        f"M {x:.2f} {y:.2f} H {x+w:.2f} V {y+t:.2f} H {x+t:.2f} "
        f"V {y+h-t:.2f} H {x+w:.2f} V {y+h:.2f} H {x:.2f} Z"
    )


def ribs(x, y, h, t):
    inset = h * 0.18
    gh = h - inset * 2
    gw = t * 0.07
    return "".join(
        f'<rect x="{x + t * p:.2f}" y="{y + inset:.2f}" width="{gw:.2f}" height="{gh:.2f}" fill="#fff"/>'
        for p in (0.30, 0.52)
    )


def swoosh(x, y, w, h):
    """Tail at the lower left, hook at the upper right. One ribbon, no crossing."""
    pts = [
        (8, 200), (120, 230), (280, 210), (460, 120),
        (600, 50), (740, 8), (860, 0), (760, 70),
        (640, 110), (500, 160), (320, 196), (160, 228), (50, 220),
    ]

    def m(px, py):
        return x + px / 860 * w, y + py / 230 * h

    a, c1, c2, b, c3, c4, tip, heel, k1, k2, k3, k4, tail = (m(*q) for q in pts)
    return (
        f"M {a[0]:.2f} {a[1]:.2f} "
        f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {b[0]:.2f} {b[1]:.2f} "
        f"C {c3[0]:.2f} {c3[1]:.2f} {c4[0]:.2f} {c4[1]:.2f} {tip[0]:.2f} {tip[1]:.2f} "
        f"L {heel[0]:.2f} {heel[1]:.2f} "
        f"C {k1[0]:.2f} {k1[1]:.2f} {k2[0]:.2f} {k2[1]:.2f} {k3[0]:.2f} {k3[1]:.2f} "
        f"C {k4[0]:.2f} {k4[1]:.2f} {tail[0]:.2f} {tail[1]:.2f} {a[0]:.2f} {a[1]:.2f} Z"
    )


def glyph(ch, em, x, baseline):
    scale = em / UPEM
    pen = SVGPathPen(GLYPH)
    GLYPH[CMAP[ord(ch)]].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
    adv, _lsb = HMTX[CMAP[ord(ch)]]
    return pen.getCommands(), adv * scale


def svg_doc(body, w, h, label):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h:.2f}" role="img" aria-label="{label}">
  <title>{label}</title>
  {body}
</svg>
'''


def layout(height):
    """Shared geometry. Returns pieces for the full monogram and the single-dock mark."""
    t = height * 0.25
    cw = height * 0.70
    em = height / 0.714
    gap = height * 0.055
    y = 4
    baseline = y + 0.714 * em
    x1 = 4
    _d, swid = glyph("S", em, 0, baseline)
    x_s = x1 + cw + gap
    s_path, swid = glyph("S", em, x_s, baseline)
    x2 = x_s + swid + gap * 1.35
    mouth_top = y + t
    mouth_bot = y + height - t
    sw_h = (mouth_bot - mouth_top) * 0.84
    sw_x = x2 + t + (cw - t) * 0.08
    sw_w = (x2 + cw) - sw_x + height * 0.62
    sw_y = (mouth_top + mouth_bot) / 2 - sw_h * 0.56
    return {
        "t": t, "cw": cw, "y": y, "h": height,
        "x1": x1, "x2": x2, "s": s_path,
        "sw": swoosh(sw_x, sw_y, sw_w, sw_h),
        "sw_x": sw_x, "sw_w": sw_w, "sw_y": sw_y, "sw_h": sw_h,
        "width": sw_x + sw_w + 6,
        "height": y + height + 6,
    }


def build_lockup():
    g = layout(340)
    body = f'''<g fill="#000">
    <path d="{container_c(g["x1"], g["y"], g["cw"], g["h"], g["t"])}"/>
    <path d="{g["s"]}"/>
    <path d="{container_c(g["x2"], g["y"], g["cw"], g["h"], g["t"])}"/>
    <path d="{g["sw"]}"/>
  </g>
  {ribs(g["x1"], g["y"], g["h"], g["t"])}
  {ribs(g["x2"], g["y"], g["h"], g["t"])}'''
    return svg_doc(body, g["width"], g["height"], "CSC 물류센터 로고")


def build_mark():
    h = 320
    t = h * 0.25
    cw = h * 0.72
    x, y = 8, 8
    mouth_top, mouth_bot = y + t, y + h - t
    sw_h = (mouth_bot - mouth_top) * 0.84
    sw_x = x + t + (cw - t) * 0.06
    sw_w = (x + cw) - sw_x + h * 0.70
    sw_y = (mouth_top + mouth_bot) / 2 - sw_h * 0.56
    body = f'''<g fill="#000">
    <path d="{container_c(x, y, cw, h, t)}"/>
    <path d="{swoosh(sw_x, sw_y, sw_w, sw_h)}"/>
  </g>
  {ribs(x, y, h, t)}'''
    return svg_doc(body, sw_x + sw_w + 8, y + h + 8, "CSC 도크 심볼")


def main():
    out = Path(__file__).parent
    lockup = build_lockup()
    (out / "csc-lockup.svg").write_text(lockup, encoding="utf-8")
    (out / "csc-wordmark.svg").write_text(lockup, encoding="utf-8")
    (out / "csc-mark.svg").write_text(build_mark(), encoding="utf-8")
    print("wrote lockup, wordmark, mark")


if __name__ == "__main__":
    main()
