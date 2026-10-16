"""Write the Open-H-RF logo as SVG and PNG, with and without the glow, on a
transparent, black and white background, into site/assets/img/logo/.

The shapes and colours were traced from site/assets/img/logo.webp (211 x 160 px);
the coordinates below are in its pixel frame.

    uv run --no-project --with resvg-py python site/logo.py
"""

from math import atan2, cos, hypot, radians, sin, sqrt
from pathlib import Path

import resvg_py

OUT = Path(__file__).parent / "assets" / "img" / "logo"

# The ring: centre, inner radius, radius between its two bands, outer radius.
RING = (59, 91, 39, 47, 55.8)
# The bars of the H: left edge, line between its halves, right edge; and the
# height between their upper and lower piece (the wave cuts them there).
LEFT, RIGHT = (50, 61.5, 72.5, 106), (116, 128, 138.5, 80)
BARS = "".join(
    f'<rect x="{x0}" y="25" width="{x1 - x0}" height="132"/>' for x0, _, x1, _ in (LEFT, RIGHT)
)
# Next to the cut, each bar has a dark wedge.
WEDGES = (
    '<polygon points="72.5,76.3 61.5,86.5 61.5,100 72.5,100" fill="#07567f"/>'
    '<polygon points="116,88 128,88 128,102.3 116,112.1" fill="#11365f"/>'
)
# The wave: its outline, the upper strip and the line between the strips.
BAND = (
    "M 45.5 147.8 C 41.8 140.9 42.7 118.6 50.1 106.5 C 57.6 94.4 69.9 86.6 83.5 83.5 "
    "C 97.3 80.4 111.2 78.3 123.7 71.5 C 137.9 63.8 144.3 42.5 144.5 37.5 "
    "C 149.2 44.1 150.4 65.1 142.6 78.1 C 135.2 90.5 122.4 97.2 108.3 100.4 "
    "C 94.3 103.6 80.8 104.5 68.3 112.4 C 54.5 121.1 46 142.9 45.5 147.8 Z"
)
STRIP = (
    "M 45.5 147.8 C 41.8 140.9 42.7 118.6 50.1 106.5 C 57.6 94.4 69.9 86.6 83.5 83.5 "
    "C 97.3 80.4 111.2 78.3 123.7 71.5 C 137.9 63.8 144.3 42.5 144.5 37.5 "
    "C 149.6 54.6 140.2 75.3 124.6 84.1 C 108 95.8 86.1 90.1 69.4 101.3 "
    "C 53.4 110.3 40.4 128.9 45.5 147.8 Z"
)
SPLIT = (
    "M 45.5 147.8 C 40.4 128.9 53.4 110.3 69.4 101.3 C 86.1 90.1 108 95.8 124.6 84.1 "
    "C 140.2 75.3 149.6 54.6 144.5 37.5"
)
# The signal arcs about (122, 61): radius and shading. They are equally wide and cut
# off by the same two lines, which leave (125, 61) at CHOP degrees up and down.
ARCS = [(40.5, "arc1"), (58.5, "arc2"), (76.5, "arc3")]
WIDTH, CHOP = 8, 47.5
GAP = 4.2  # between a piece and the shape cutting through it

# Linear gradients: start and end point, and the colours, evenly spaced or as
# (offset, colour). Those of the ring and the bars were fitted to the original.
WAVE = (45, 147, 144, 37)
SHADES = {
    "o-left-in": (56.1, 67.3, 9.4, 97.1, "#226a84 #316e86 #366983 #2c5a75"),
    "o-left-out": (53.5, 46.9, -0.5, 111.3, "#4599a9 #2b738e #1a5585 #0d264e"),
    "o-top-in": (92.9, 59.7, 86, 65, "#2f7586 #27748c #217083 #2b8192"),
    "o-top-out": (99.1, 52.7, 88.4, 60.2, "#69a9a6 #74a5a1 #6da3a7 #5f9ea2"),
    "o-bottom": (103, 103.1, 88.2, 143.7, "#448783 #3d6e7d #315c75 #1e4358"),
    "lbar-l-up": (64.7, 56.9, 46.8, 60, "#337f9d #397998 #3c6d8a #2d6482"),
    "lbar-l-lo": (52.2, 143.4, 61.8, 146, "#1d496d #0a274e #113263 #0e3061"),
    "lbar-r-up": (51.2, 45.2, 80.9, 64.1, "#60b8c3 #5fb6c2 #39a7ba #22829e"),
    "lbar-r-lo": (61.2, 120.4, 71.9, 154.1, "#327785 #285773 #215176 #134268"),
    "rbar-l-up": (129.2, 44.3, 114.3, 47.6, "#3ca29f #3c9b9d #348c91 #28777c"),
    "rbar-l-lo": (108.1, 118.4, 136.7, 138.5, "#143f62 #2c5e83 #2e5d7d #265779"),
    "rbar-r-up": (137.6, 39.6, 126.9, 40.5, "#74cda8 #7bd1b5 #80d6c1 #6dc4b4"),
    "rbar-r-lo": (131.2, 93.7, 133.9, 154.6, "#3f8e89 #539c93 #367e89 #255e79"),
    "upper": (
        *WAVE,
        [
            (0, "#1e6282"),
            (0.14, "#1e6282"),
            (0.25, "#266486"),
            (0.36, "#307f95"),
            (0.46, "#37959b"),
            (0.55, "#43a9a2"),
            (0.65, "#4eb8a4"),
            (0.75, "#64ccae"),
            (0.87, "#79dab9"),
            (1, "#88e3cc"),
        ],
    ),
    "lower": (
        *WAVE,
        [
            (0, "#14466c"),
            (0.14, "#11416e"),
            (0.25, "#124876"),
            (0.36, "#16507c"),
            (0.46, "#17537e"),
            (0.55, "#19547a"),
            (0.65, "#1e6580"),
            (0.75, "#2c848e"),
            (0.87, "#44a39d"),
            (1, "#74d4c2"),
        ],
    ),
    "edge": (10, 150, 200, 20, "#4f93bd #6cbfce #7fd0cc"),
    "arc1": (0, 30, 0, 92, "#56a3bc #184a7b"),
    "arc2": (0, 18, 0, 104, "#6cc6c0 #5fa2ad #28607f"),
    "arc3": (0, 4, 0, 117, "#8edabf #8abdc3 #6690bc"),
    "arc-edge": (0, 4, 0, 117, "#8ee2d6 #62b4d0"),
    "ramp": (125, 0, 175, 0, "#000 #555 #fff"),
}


def gradients():
    out = []
    for name, (x1, y1, x2, y2, stops) in SHADES.items():
        if isinstance(stops, str):
            stops = stops.split()
            stops = [(i / (len(stops) - 1), c) for i, c in enumerate(stops)]
        s = "".join(f'<stop offset="{o:g}" stop-color="{c}"/>' for o, c in stops)
        out.append(
            f'<linearGradient id="{name}" gradientUnits="userSpaceOnUse" '
            f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{s}</linearGradient>'
        )
    return "\n".join(out)


def ring():
    cx, cy, ri, rm, ro = RING

    def band(r0, r1, fill):
        return (
            f'<circle cx="{cx}" cy="{cy}" r="{(r0 + r1) / 2}" stroke="url(#{fill})" '
            f'stroke-width="{r1 - r0}"/>'
        )

    # The bars and the wave cut the ring into a left, top and bottom piece.
    return (
        f'<g clip-path="url(#clip-left)">{band(ri, rm, "o-left-in")}'
        f"{band(rm, ro, 'o-left-out')}</g>"
        f'<g clip-path="url(#clip-top)">{band(ri, rm, "o-top-in")}{band(rm, ro, "o-top-out")}</g>'
        f'<g clip-path="url(#clip-bottom)">{band(ri, ro, "o-bottom")}</g>'
    )


def bars():
    out = []
    for (x0, xm, x1, cut), bar in ((LEFT, "lbar"), (RIGHT, "rbar")):
        for a, b, half in ((x0, xm, "l"), (xm, x1, "r")):
            out.append(
                f'<rect x="{a}" y="25" width="{b - a}" height="{cut - 25}" '
                f'fill="url(#{bar}-{half}-up)"/>'
            )
            out.append(
                f'<rect x="{a}" y="{cut}" width="{b - a}" height="{157 - cut}" '
                f'fill="url(#{bar}-{half}-lo)"/>'
            )
    return "".join(out) + WEDGES


def sector(r, c=3):
    """The path of the arc of radius r, with its corners rounded by c."""

    def corner(R, up):
        u, v = cos(radians(CHOP)), sin(radians(-CHOP if up else CHOP))
        t = -3 * u + sqrt(9 * u * u - 9 + R * R)
        return 125 + t * u, 61 + t * v

    def along_circle(p, R, d):
        a = atan2(p[1] - 61, p[0] - 122) + d / R
        return 122 + R * cos(a), 61 + R * sin(a)

    def along_line(p, q, d):
        n = hypot(q[0] - p[0], q[1] - p[1])
        return p[0] + d * (q[0] - p[0]) / n, p[1] + d * (q[1] - p[1]) / n

    def f(p):
        return f"{p[0]:.2f} {p[1]:.2f}"

    ro, ri = r + WIDTH / 2, r - WIDTH / 2
    to, bo, ti, bi = corner(ro, True), corner(ro, False), corner(ri, True), corner(ri, False)
    return (
        f"M {f(along_circle(to, ro, c))} A {ro} {ro} 0 0 1 {f(along_circle(bo, ro, -c))} "
        f"Q {f(bo)} {f(along_line(bo, bi, c))} L {f(along_line(bi, bo, c))} "
        f"Q {f(bi)} {f(along_circle(bi, ri, -c))} A {ri} {ri} 0 0 0 {f(along_circle(ti, ri, c))} "
        f"Q {f(ti)} {f(along_line(ti, to, c))} L {f(along_line(to, ti, c))} "
        f"Q {f(to)} {f(along_circle(to, ro, c))} Z"
    )


def arcs():
    return "".join(
        f'<path d="{sector(r)}" fill="url(#{fill})" stroke="url(#arc-edge)" stroke-width="2" '
        'paint-order="stroke"/>'
        for r, fill in ARCS
    )


def haze():
    """The glow: a dark teal haze around the wave and the arcs, absent at the
    left of the arcs and nearly opaque between the outer two."""
    shapes = "".join(f'<path d="{sector(r)}"/>' for r, _ in ARCS)
    return (
        f'<g filter="url(#haze)" mask="url(#ramp-mask)" fill="#fff"><path d="{BAND}"/>{shapes}</g>'
    )


def masks(frame):
    """What shows of the ring and the bars, where the bars and the wave cut
    them: each piece in full (its outline), and 0.5 px inside its edges (its fill);
    and the inside of the wave."""
    cx, cy, ri, _, ro = RING
    out = []
    for inset, name in ((-0.5, "edge"), (0.5, "fill")):
        cut = f'stroke-width="{2 * (GAP + inset + 0.5)}" stroke-linejoin="round"'
        out.append(
            f'<mask id="ring-{name}"><rect {frame} fill="#000"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{(ri + ro) / 2}" fill="none" stroke="#fff" '
            f'stroke-width="{ro - ri - 2 * inset}"/>'
            f'<g fill="#000" stroke="#000" {cut}>{BARS}<path d="{BAND}"/></g></mask>'
        )
        out.append(
            f'<mask id="bars-{name}"><rect {frame} fill="#000"/>'
            f'<g fill="#fff" stroke="{"#fff" if inset < 0 else "#000"}" stroke-width="1">{BARS}</g>'
            f'<path d="{BAND}" fill="#000" stroke="#000" {cut}/></mask>'
        )
    out.append(
        f'<mask id="band-fill"><rect {frame} fill="#000"/>'
        f'<path d="{BAND}" fill="#fff" stroke="#000" stroke-width="2"/></mask>'
    )
    return "\n".join(out)


def svg(glow: bool, background: str | None) -> str:
    frame = 'x="-10" y="-10" width="231" height="180"'
    rect = f'<rect {frame} fill="{background}"/>' if background else ""
    xm = LEFT[1]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-10 -10 231 180">
<defs>
{gradients()}
<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="45" y1="147" x2="144" y2="37">\
<stop offset=".5" stop-color="#a0f0d8" stop-opacity="0"/>\
<stop offset=".72" stop-color="#a0f0d8" stop-opacity=".6"/>\
<stop offset=".95" stop-color="#a0f0d8" stop-opacity=".2"/></linearGradient>
<filter id="haze" x="-30%" y="-30%" width="160%" height="160%">
<feGaussianBlur stdDeviation="8"/>
<feComponentTransfer result="b"><feFuncA type="linear" slope="2.5"/></feComponentTransfer>
<feFlood flood-color="#2f626a"/><feComposite in2="b" operator="in"/>
</filter>
<mask id="ramp-mask"><rect {frame} fill="url(#ramp)"/></mask>
<clipPath id="clip-left"><rect x="-10" y="-10" width="{xm + 10}" height="180"/></clipPath>
<clipPath id="clip-top"><rect x="{xm}" y="-10" width="100" height="98"/></clipPath>
<clipPath id="clip-bottom"><rect x="{xm}" y="88" width="100" height="82"/></clipPath>
{masks(frame)}
</defs>
{rect}
<rect {frame} fill="url(#edge)" mask="url(#ring-edge)"/>
<g mask="url(#ring-fill)" fill="none">{ring()}</g>
<rect {frame} fill="url(#edge)" mask="url(#bars-edge)"/>
<g mask="url(#bars-fill)">{bars()}</g>
{haze() if glow else ""}
<path d="{BAND}" fill="url(#edge)"/>
<g mask="url(#band-fill)">
<path d="{BAND}" fill="url(#lower)"/>
<path d="{STRIP}" fill="url(#upper)"/>
<path d="{SPLIT}" fill="none" stroke="url(#shine)" stroke-width="1.2"/>
</g>
{arcs()}
</svg>
"""


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for glow in (False, True):
        for name, background in [("transparent", None), ("black", "#000"), ("white", "#fff")]:
            stem = OUT / f"logo-{'glow' if glow else 'plain'}-{name}"
            text = svg(glow, background)
            stem.with_suffix(".svg").write_text(text)
            stem.with_suffix(".png").write_bytes(resvg_py.svg_to_bytes(svg_string=text, zoom=5))
            print(stem.with_suffix(".svg"))
