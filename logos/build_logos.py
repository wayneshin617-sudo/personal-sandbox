#!/usr/bin/env python3
"""CSC marks using one swoosh: thin tail, thick head, straight cut at the tip."""

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT_CANDIDATES = [
    Path("/tmp/fonts/Montserrat-ExtraBold.ttf"),
    Path(__file__).with_name("fonts") / "Montserrat-ExtraBold.ttf",
]

# Drawn in a 300 x 120 box. The tip is a straight cut, not a second point.
SWOOSH = (
    "M 8 88 C 60 102, 120 90, 190 48 "
    "C 230 22, 265 6, 294 0 L 262 38 "
    "C 228 52, 175 72, 110 84 "
    "C 55 94, 22 92, 8 88 Z"
)
SW_W, SW_H = 300.0, 120.0


def load_font():
    for path in FONT_CANDIDATES:
        if path.exists():
            font = TTFont(str(path))
            return font.getGlyphSet(), font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm
    raise SystemExit("Montserrat ExtraBold was not found.")


GLYPH, CMAP, HMTX, UPEM = load_font()


def text_path(text, em, x, baseline, tracking=-0.045):
    scale = em / UPEM
    parts = []
    cursor = x
    extra = tracking * em
    for ch in text:
        pen = SVGPathPen(GLYPH)
        GLYPH[CMAP[ord(ch)]].draw(TransformPen(pen, (scale, 0, 0, -scale, cursor, baseline)))
        parts.append(pen.getCommands())
        adv, _lsb = HMTX[CMAP[ord(ch)]]
        cursor += adv * scale + extra
    return " ".join(parts), cursor - x - extra


def swoosh(x, y, w, h, fill="#000"):
    return (
        f'<g transform="translate({x:.2f} {y:.2f}) scale({w / SW_W:.6f} {h / SW_H:.6f})">'
        f'<path fill="{fill}" d="{SWOOSH}"/></g>'
    )


def doc(body, w, h, label):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h:.2f}" role="img" aria-label="{label}">
  <title>{label}</title>
  {body}
</svg>
'''


def word_block(em=240, fill="#000"):
    """Swoosh over CSC. Returns (svg fragment, width, height) with origin at 0,0."""
    cap = 0.714 * em
    path, width = text_path("CSC", em, 0, 0)
    sw_w = width * 1.04
    sw_h = cap * 0.50
    gap = cap * 0.12
    sw_x = -(sw_w - width) * 0.2
    baseline = sw_h + gap + cap
    path, width = text_path("CSC", em, 0, baseline)
    height = baseline + em * 0.02
    fragment = (
        swoosh(sw_x, 0, sw_w, sw_h, fill)
        + f'<path fill="{fill}" d="{path}"/>'
    )
    return fragment, sw_x, width - sw_x, height


def build_wordmark():
    frag, left, width, height = word_block()
    pad = 4
    body = f'<g transform="translate({pad - left:.2f} {pad:.2f})">{frag}</g>'
    return doc(body, width + pad * 2, height + pad * 2, "CSC 워드마크")


def build_horizontal():
    em = 200
    cap = 0.714 * em
    sw_h = cap * 0.92
    sw_w = sw_h * (SW_W / SW_H)
    gap = em * 0.16
    path, tw = text_path("CSC", em, 0, 0)
    baseline = 8 + cap * 0.98
    path, tw = text_path("CSC", em, sw_w + gap, baseline)
    sw_y = baseline - cap + (cap - sw_h) / 2
    body = swoosh(4, sw_y, sw_w, sw_h) + f'<path fill="#000" d="{path}"/>'
    return doc(body, sw_w + gap + tw + 16, baseline + 12, "CSC 가로형")


def build_badge():
    size = 520
    cx = size / 2
    em = 108
    cap = 0.714 * em
    path, tw = text_path("CSC", em, 0, 0)
    sw_w = tw * 1.15
    sw_h = sw_w * (SW_H / SW_W)
    gap = 18
    block = sw_h + gap + cap
    top = cx - block / 2 + 6
    path, tw = text_path("CSC", em, cx - tw / 2, top + sw_h + gap + cap)
    body = f'''<circle cx="{cx:.2f}" cy="{cx:.2f}" r="248" fill="#000"/>
  {swoosh(cx - sw_w / 2, top, sw_w, sw_h, "#fff")}
  <path fill="#fff" d="{path}"/>'''
    return doc(body, size, size, "CSC 배지")


def container(x, y, w, h):
    frame = h * 0.16
    grooves = 6
    inner_w = w - frame * 2
    gap = inner_w * 0.04
    groove_w = (inner_w - gap * (grooves + 1)) / grooves
    parts = [f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="#000"/>']
    gx = x + frame + gap
    for _ in range(grooves):
        parts.append(
            f'<rect x="{gx:.2f}" y="{y + frame:.2f}" width="{groove_w:.2f}" height="{h - frame * 2:.2f}" fill="#fff"/>'
        )
        gx += groove_w + gap
    return "".join(parts)


def build_logistics():
    frag, left, width, height = word_block(210)
    cont_h = height * 0.72
    cont_w = cont_h * 1.7
    gap = 36
    pad = 8
    total_h = max(cont_h, height)
    cont_y = pad + (total_h - cont_h) / 2
    word_y = pad + (total_h - height) / 2
    word_x = pad + cont_w + gap - left
    body = (
        container(pad, cont_y, cont_w, cont_h)
        + f'<g transform="translate({word_x:.2f} {word_y:.2f})">{frag}</g>'
    )
    return doc(body, word_x + width + pad, total_h + pad * 2, "CSC 물류 로고")


def build_swoosh():
    return doc(swoosh(0, 0, SW_W, SW_H), SW_W, SW_H, "스우시")


def main():
    out = Path(__file__).parent
    files = {
        "csc-swoosh.svg": build_swoosh(),
        "csc-wordmark.svg": build_wordmark(),
        "csc-lockup.svg": build_wordmark(),
        "csc-horizontal.svg": build_horizontal(),
        "csc-badge.svg": build_badge(),
        "csc-logistics.svg": build_logistics(),
        "csc-mark.svg": build_swoosh(),
    }
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
