"""Write the Open-H-RF banner (the header of the README,
2752 x 938 px) as site/assets/img/logo/banner.svg, with the logo of logo.py. The
text is Roboto Bold, drawn as outlines.

    uv run --no-project --with resvg-py --with fonttools python site/banner.py
"""

import io
import urllib.request

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

import logo

FONT = "https://cdn.jsdelivr.net/fontsource/fonts/roboto@5.2.5/latin-700-normal.ttf"
W, H = 2752, 938
# The logo's frame in the banner: its pixels are 2.9 px, (0, 0) at (178, 302.5).
SCALE, X0, Y0 = 2.9, 178, 302.5
# The lines of text: left end, baseline.
TEXT = [("Open-H-RF:", 843, 520), ("Open Data Initiative", 843, 731)]
SIZE = 200

# The network at the top right: nodes in focus (x, y, radius) and the lines between
# them and out of the banner; nodes and lines out of focus.
NODES = {
    "a": (2332, 38, 16),
    "b": (2102, 98, 10),
    "c": (1942, 143, 8),
    "d": (2212, 287, 18),
    "e": (2614, 207, 14),
    "f": (2495, 572, 13),
}
LINKS = [
    "cb",
    "cd",
    "bd",
    "ba",
    "de",
    "ef",
    ((1995, 0), "c"),
    ((2048, 0), "b"),
    ("a", (2480, 0)),
    ("d", (2502, 0)),
    ("e", (2555, 0)),
    ("e", (W, 90)),
    ("e", (W, 240)),
    ("e", (W, 480)),
    ((2680, 0), (W, 20)),
]
BLURRED = [
    (1695, 52),
    (1760, 110),
    (2230, 207),
    (2322, 222),
    (2342, 100),
    (2452, 200),
    (2472, 67),
    (2466, 257),
    (2556, 260),
    (2343, 303),
    (2676, 127),
    (2582, 172),
    (2682, 207),
    (2707, 222),
    (2742, 193),
    (2610, 327),
    (2125, 403),
    (2165, 405),
    (2472, 425),
    (2527, 413),
    (2655, 490),
    (2738, 527),
    (2520, 540),
]
FAINT = [
    ((1760, 110), (1900, 0)),
    ((1760, 110), (2120, 113)),
    ((2102, 98), (2290, 210)),
    ((2230, 207), (2614, 207)),
    ((2125, 403), (2332, 45)),
    ((2165, 405), (2466, 257)),
    ((2466, 257), (2614, 207)),
    ((2332, 38), (2472, 425)),
    ((2472, 425), (2495, 572)),
    ((2472, 425), (2655, 490)),
    ((2655, 490), (W, 450)),
    ((2520, 540), (2655, 490)),
    ((2332, 38), (2582, 172)),
    ((2676, 127), (W, 80)),
]


def text():
    font = TTFont(io.BytesIO(urllib.request.urlopen(FONT).read()))
    glyphs, cmap, k = font.getGlyphSet(), font.getBestCmap(), SIZE / font["head"].unitsPerEm
    pen = SVGPathPen(glyphs)
    for line, x, y in TEXT:
        for c in line:
            name = cmap[ord(c)]
            glyphs[name].draw(TransformPen(pen, (k, 0, 0, -k, x, y)))
            x += font["hmtx"][name][0] * k
    return pen.getCommands()


def network():
    def at(p):
        return NODES[p][:2] if isinstance(p, str) else p

    def line(p, q):
        return f'<line x1="{p[0]}" y1="{p[1]}" x2="{q[0]}" y2="{q[1]}"/>'

    faint = "".join(line(p, q) for p, q in FAINT)
    blurred = "".join(f'<circle cx="{x}" cy="{y}" r="9"/>' for x, y in BLURRED)
    links = "".join(line(at(p), at(q)) for p, q in LINKS)
    nodes = "".join(f'<circle cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in NODES.values())
    return (
        f'<g stroke="#1d4b5b" stroke-width="4" filter="url(#defocus)">{faint}</g>'
        f'<g fill="#2f6474" filter="url(#defocus)">{blurred}</g>'
        f'<g stroke="#245464" stroke-width="2.5">{links}</g>'
        f'<g fill="#336a78" filter="url(#halo)">{nodes}</g>'
    )


def svg():
    mark = logo.svg(glow=True, background=None).replace(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox',
        f'<svg x="{X0 - 10 * SCALE}" y="{Y0 - 10 * SCALE}" width="{231 * SCALE}" '
        f'height="{180 * SCALE}" overflow="visible" viewBox',
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">
<defs>
<linearGradient id="sky" x2="1"><stop offset="0" stop-color="#030f20"/>\
<stop offset=".2" stop-color="#061a2b"/>
<stop offset=".45" stop-color="#082839"/><stop offset=".7" stop-color="#0c3446"/>\
<stop offset=".88" stop-color="#0f3a4b"/>
<stop offset="1" stop-color="#0d3547"/></linearGradient>
<linearGradient id="dusk" y2="1" x2="0"><stop offset=".25" stop-opacity="0"/>\
<stop offset="1" stop-opacity=".3"/></linearGradient>
<filter id="defocus" x="-20%" y="-20%" width="140%" height="140%">\
<feGaussianBlur stdDeviation="4"/></filter>
<filter id="halo" x="-100%" y="-100%" width="300%" height="300%">\
<feGaussianBlur stdDeviation="6" result="b"/>
<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="shadow" x="-5%" y="-20%" width="110%" height="140%">\
<feGaussianBlur in="SourceAlpha" stdDeviation="14"/>
<feOffset dy="4"/><feComponentTransfer><feFuncA type="linear" slope=".7"/>\
</feComponentTransfer>
<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#sky)"/>
<rect width="{W}" height="{H}" fill="url(#dusk)"/>
{network()}
{mark}
<path d="{text()}" fill="#fff" filter="url(#shadow)"/>
</svg>
"""


if __name__ == "__main__":
    path = logo.OUT / "banner.svg"
    path.write_text(svg())
    print(path)
