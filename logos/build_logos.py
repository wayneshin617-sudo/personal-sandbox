#!/usr/bin/env python3
"""Build CSC logistics-center logo SVGs from outlined Inter Bold and custom marks."""

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT_PATH = "/usr/share/fonts/truetype/macos/Inter-Bold.ttf"
INK = "#111111"

font = TTFont(FONT_PATH)
GLYPH = font.getGlyphSet()
CMAP = font.getBestCmap()
HMTX = font["hmtx"]
UPEM = font["head"].unitsPerEm


def r(n):
    return round(n, 2)


def text_path(text, em, x, baseline, tracking=0.0):
    """Return (svg path d, advance width) for text. Y grows downward."""
    scale = em / UPEM
    parts = []
    cursor = x
    for ch in text:
        name = CMAP[ord(ch)]
        pen = SVGPathPen(GLYPH)
        tpen = TransformPen(pen, (scale, 0, 0, -scale, cursor, baseline))
        GLYPH[name].draw(tpen)
        parts.append(pen.getCommands())
        adv, _lsb = HMTX[name]
        cursor += adv * scale + tracking
    width = cursor - x - tracking
    return " ".join(parts), width


def fmt_path(commands):
    """Round numbers inside an SVG path command string."""
    out = []
    token = ""
    for ch in commands:
        if ch in "MmLlHhVvCcSsQqTtAaZz ,":
            if token:
                out.append(str(r(float(token))))
                token = ""
            if ch != " " or (out and out[-1] not in " ,"):
                if ch != ",":
                    out.append(ch)
                else:
                    out.append(" ")
        else:
            token += ch
    if token:
        out.append(str(r(float(token))))
    # collapse spaces
    s = "".join(out)
    while "  " in s:
        s = s.replace("  ", " ")
    return s.strip()


def text_d(text, em, x, baseline, tracking=0.0):
    raw, width = text_path(text, em, x, baseline, tracking)
    return fmt_path(raw), width


def swoosh_d(x, y, w, h):
    """Athletic swoosh. Tail at the lower left, hook rising to the upper right.

    (x, y) is the top-left of the bounding box. The hook is heavy enough to
    read at small sizes; the tail tapers to a point.
    """

    def p(nx, ny):
        ny = ny / 0.911
        return r(x + nx * w), r(y + ny * h)

    pts = [
        (0.018, 0.778),
        (0.235, 0.911),
        (0.441, 0.756),
        (0.647, 0.444),
        (0.779, 0.244),
        (0.882, 0.089),
        (1.000, 0.000),
        (0.859, 0.422),
        (0.750, 0.578),
        (0.588, 0.733),
        (0.412, 0.822),
        (0.206, 0.911),
        (0.082, 0.844),
    ]
    a, c1, c2, b, c3, c4, tip, heel, k1, k2, k3, k4, tail = (p(*q) for q in pts)
    return (
        f"M {a[0]} {a[1]} "
        f"C {c1[0]} {c1[1]} {c2[0]} {c2[1]} {b[0]} {b[1]} "
        f"C {c3[0]} {c3[1]} {c4[0]} {c4[1]} {tip[0]} {tip[1]} "
        f"L {heel[0]} {heel[1]} "
        f"C {k1[0]} {k1[1]} {k2[0]} {k2[1]} {k3[0]} {k3[1]} "
        f"C {k4[0]} {k4[1]} {tail[0]} {tail[1]} {a[0]} {a[1]} Z"
    )


def dock_d(x, y, w, h):
    """Distribution-center silhouette: roof canopy and two loading docks.

    Coordinates are the outer bounds including the canopy overhang.
    """
    # Local fractions of w / h
    roof_b = 0.15
    body_l = 0.075
    body_r = 0.925
    door_t = 0.46
    # two doors, equal, sitting on the floor
    inner_l = body_l + 0.085
    inner_r = body_r - 0.085
    gap = 0.115
    door_w = (inner_r - inner_l - gap) / 2
    d1l = inner_l
    d1r = inner_l + door_w
    d2l = d1r + gap
    d2r = inner_r

    def p(nx, ny):
        return r(x + nx * w), r(y + ny * h)

    pts = [
        p(0, 0.0),
        p(1, 0.0),
        p(1, roof_b),
        p(body_r, roof_b),
        p(body_r, 1),
        p(d2r, 1),
        p(d2r, door_t),
        p(d2l, door_t),
        p(d2l, 1),
        p(d1r, 1),
        p(d1r, door_t),
        p(d1l, door_t),
        p(d1l, 1),
        p(body_l, 1),
        p(body_l, roof_b),
        p(0, roof_b),
    ]
    d = f"M {pts[0][0]} {pts[0][1]} " + " ".join(f"L {px} {py}" for px, py in pts[1:]) + " Z"
    return d


def iso_faces(x, y, w, h, depth):
    """Three faces of a carton. Returns (front, top, side) point lists."""
    dx = depth
    dy = depth * 0.56
    fl = (x, y)
    fr = (x + w, y)
    br = (x + w, y + h)
    bl = (x, y + h)
    tl = (x + dx, y - dy)
    tr = (x + w + dx, y - dy)
    sr = (x + w + dx, y + h - dy)
    front = [fl, fr, br, bl]
    top = [fl, tl, tr, fr]
    side = [fr, tr, sr, br]
    return front, top, side


def poly(points):
    p0 = points[0]
    rest = " ".join(f"L {r(px)} {r(py)}" for px, py in points[1:])
    return f"M {r(p0[0])} {r(p0[1])} {rest} Z"


def svg_doc(body, w, h, label):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {r(w)} {r(h)}" role="img" aria-label="{label}">
  <title>{label}</title>
  <g fill="{INK}">
{body}
  </g>
</svg>
'''


def word_block(em, origin_x, top_y, tracking_em=-0.04):
    """CSC with the swoosh underneath. Returns (paths, width, height)."""
    tracking = tracking_em * em
    _d, word_w = text_d("CSC", em, 0, 0, tracking)
    cap = 1490 / UPEM * em
    sw_h = cap * 0.56
    sw_w = word_w * 1.06
    gap = cap * 0.14
    # The hook extends past the last C. The tail starts with the first C.
    sw_x = origin_x
    baseline = top_y + cap
    sw_y = baseline + gap
    word_d, _ = text_d("CSC", em, origin_x, baseline, tracking)
    height = cap + gap + sw_h
    width = max(word_w, (sw_x + sw_w) - origin_x)
    paths = (
        f'<path d="{word_d}"/>\n'
        f'    <path d="{swoosh_d(sw_x, sw_y, sw_w, sw_h)}"/>'
    )
    return paths, width, height


def build_lockup():
    em = 158
    pad_x, pad_y = 2, 2
    gap = 52
    _paths, _word_w, word_h = word_block(em, 0, 0)
    # Icon and word block share a top and a bottom: canopy with the cap line,
    # dock floor with the swoosh.
    mark_h = word_h
    mark_w = mark_h * (200 / 168)
    mark_x = pad_x
    mark_y = pad_y
    word_x = mark_x + mark_w + gap
    word_y = pad_y
    paths, word_w, word_h = word_block(em, word_x, word_y)
    body = f'''    <path d="{dock_d(mark_x, mark_y, mark_w, mark_h)}"/>
    {paths}'''
    total_w = word_x + word_w + pad_x
    total_h = pad_y + mark_h + pad_y
    return svg_doc(body, total_w, total_h, "CSC 물류센터 로고")


def build_wordmark():
    pad = 4
    paths, word_w, word_h = word_block(200, pad, pad)
    body = f"    {paths}"
    return svg_doc(body, pad + word_w + 8, pad + word_h + 4, "CSC 워드마크")


def build_mark():
    return svg_doc(f'    <path d="{dock_d(0, 0, 200, 168)}"/>', 200, 168, "CSC 물류센터 심볼")


def build_badge():
    size = 520
    cx = cy = size / 2
    radius = 248
    em = 108
    mark_w, mark_h = 158, 132
    # Measure the word block, then center the stack.
    paths, word_w, word_h = word_block(em, 0, 0)
    gap = 22
    content_h = mark_h + gap + word_h
    top = cy - content_h / 2 + 4
    mark_x = cx - mark_w / 2
    mark_y = top
    word_x = cx - word_w / 2
    word_y = mark_y + mark_h + gap
    paths, word_w, word_h = word_block(em, word_x, word_y)
    body = f'''    <circle cx="{r(cx)}" cy="{r(cy)}" r="{r(radius)}"/>
    <g fill="#ffffff">
      <path d="{dock_d(mark_x, mark_y, mark_w, mark_h)}"/>
      {paths}
    </g>'''
    return svg_doc(body, size, size, "CSC 물류센터 배지")


def build_parcel():
    """Carton with a separated top and side, CSC and swoosh stenciled on the front."""
    w, h, depth = 292, 206, 86
    dy = depth * 0.56
    x, y = 24, 16 + dy
    gap = 9
    dx, dy = depth, depth * 0.56
    front = [(x, y + gap), (x + w - gap, y + gap), (x + w - gap, y + h), (x, y + h)]
    top = [
        (x + gap * 0.6, y - 2),
        (x + dx + 2, y - dy),
        (x + w + dx, y - dy),
        (x + w - 2, y - 2),
    ]
    side = [
        (x + w + 2, y + gap),
        (x + w + dx, y - dy + gap * 0.7),
        (x + w + dx, y + h - dy),
        (x + w + 2, y + h),
    ]
    em = 86
    tracking = -0.04 * em
    _d, word_w = text_d("CSC", em, 0, 0, tracking)
    cap = 1490 / UPEM * em
    front_left, front_right = front[0][0], front[1][0]
    front_top, front_bot = front[0][1], front[2][1]
    front_w = front_right - front_left
    word_x = front_left + (front_w - word_w) / 2
    baseline = front_bot - (front_bot - front_top) * 0.16
    word_d, _ = text_d("CSC", em, word_x, baseline, tracking)
    sw_w = front_w * 0.78
    sw_h = cap * 0.70
    sw_x = front_left + (front_w - sw_w) / 2
    sw_y = front_top + 16
    body = f'''    <path d="{poly(top)}"/>
    <path d="{poly(side)}"/>
    <path fill-rule="evenodd" d="{poly(front)} {swoosh_d(sw_x, sw_y, sw_w, sw_h)} {word_d}"/>'''
    total_w = x + w + depth + 16
    total_h = y + h + 12
    return svg_doc(body, total_w, total_h, "CSC 카톤 마크")


def main():
    files = {
        "csc-lockup.svg": build_lockup(),
        "csc-wordmark.svg": build_wordmark(),
        "csc-mark.svg": build_mark(),
        "csc-badge.svg": build_badge(),
        "csc-parcel.svg": build_parcel(),
    }
    for name, doc in files.items():
        path = f"/workspace/logos/{name}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        print("wrote", name)


if __name__ == "__main__":
    main()
