#!/usr/bin/env python3
"""CSC logistics logo. Letters are outlined from Montserrat ExtraBold."""

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT_CANDIDATES = [
    Path("/tmp/fonts/Montserrat-ExtraBold.ttf"),
    Path(__file__).with_name("fonts") / "Montserrat-ExtraBold.ttf",
]
INK = "#000000"
PAPER = "#ffffff"


def load_font():
    for path in FONT_CANDIDATES:
        if path.exists():
            font = TTFont(str(path))
            return font, font.getGlyphSet(), font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm
    raise SystemExit("Montserrat ExtraBold was not found.")


FONT, GLYPH, CMAP, HMTX, UPEM = load_font()


def text_d(text, em, x, baseline, tracking=-0.045):
    scale = em / UPEM
    parts = []
    cursor = x
    extra = tracking * em
    for ch in text:
        name = CMAP[ord(ch)]
        pen = SVGPathPen(GLYPH)
        GLYPH[name].draw(TransformPen(pen, (scale, 0, 0, -scale, cursor, baseline)))
        parts.append(pen.getCommands())
        adv, _lsb = HMTX[name]
        cursor += adv * scale + extra
    return " ".join(parts), cursor - x - extra


def swoosh_d(x, y, w, h):
    """Thick hook, sharp tip, tail at the lower left. Box origin is top-left."""
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


def svg(body, w, h, label):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h:.2f}" role="img" aria-label="{label}">
  <title>{label}</title>
  {body}
</svg>
'''


def container_icon(x, y, w, h, grooves=4):
    """White container body with a frame and vertical corrugation."""
    frame = max(10, h * 0.14)
    groove_gap = w * 0.055
    inner_w = w - frame * 2
    groove_w = (inner_w - groove_gap * (grooves + 1)) / grooves
    parts = [f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{PAPER}"/>']
    gx = x + frame + groove_gap
    gy = y + frame
    gh = h - frame * 2
    for _ in range(grooves):
        parts.append(
            f'<rect x="{gx:.2f}" y="{gy:.2f}" width="{groove_w:.2f}" height="{gh:.2f}" fill="{INK}"/>'
        )
        gx += groove_w + groove_gap
    return "\n    ".join(parts), w


def build_lockup():
    """Black sign: a framed container, then the swoosh and CSC."""
    em = 132
    cap = 714 / UPEM * em
    sw_h = 72
    gap = 16
    block_h = sw_h + gap + cap
    _td, tw = text_d("CSC", em, 0, 0)
    cont_h = block_h * 0.78
    cont_w = cont_h * 1.55
    pad_x, pad_y = 28, 26
    between = 36
    right = 32
    width = pad_x + cont_w + between + tw + right
    height = pad_y + block_h + pad_y
    top = pad_y
    cont_y = top + (block_h - cont_h) / 2
    word_x = pad_x + cont_w + between
    baseline = top + sw_h + gap + cap
    td, _tw = text_d("CSC", em, word_x, baseline)
    sw = swoosh_d(word_x - 2, top - 2, tw + 12, sw_h)
    icon, _ = container_icon(pad_x, cont_y, cont_w, cont_h, grooves=7)
    body = f'''<g>
    <rect width="{width:.2f}" height="{height:.2f}" fill="{INK}"/>
    {icon}
    <path fill="{PAPER}" d="{sw}"/>
    <path fill="{PAPER}" d="{td}"/>
  </g>'''
    return svg(body, width, height, "CSC 물류센터 로고")


def build_wordmark():
    em = 220
    cap = 714 / UPEM * em
    _td, tw = text_d("CSC", em, 0, 0)
    sw_h = cap * 0.58
    gap = cap * 0.16
    pad = 4
    baseline = pad + sw_h + gap + cap
    td, tw = text_d("CSC", em, pad, baseline)
    sw = swoosh_d(pad - 2, pad, tw + 16, sw_h)
    width = pad + tw + 28
    height = baseline + 8
    body = f'''<g fill="{INK}">
    <path d="{sw}"/>
    <path d="{td}"/>
  </g>'''
    return svg(body, width, height, "CSC 워드마크")


def build_mark():
    """Square container mark for gates, apps, and stamps."""
    size = 256
    margin = 28
    cont = size - margin * 2
    icon, _ = container_icon(margin, margin, cont, cont * 0.62, grooves=6)
    sw_w = cont * 0.86
    sw_h = 52
    sw_y = margin + cont * 0.62 + 16
    sw = swoosh_d(margin + (cont - sw_w) / 2, sw_y, sw_w, sw_h)
    body = f'''<g>
    <rect width="{size}" height="{size}" rx="28" fill="{INK}"/>
    {icon}
    <path fill="{PAPER}" d="{sw}"/>
  </g>'''
    return svg(body, size, size, "CSC 컨테이너 심볼")


def main():
    out = Path(__file__).parent
    files = {
        "csc-lockup.svg": build_lockup(),
        "csc-wordmark.svg": build_wordmark(),
        "csc-mark.svg": build_mark(),
    }
    for name, doc in files.items():
        (out / name).write_text(doc, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
