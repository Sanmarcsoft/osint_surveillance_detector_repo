"""Shared Phenom brand backdrop for the ghostmode dashboards.

The perspective-floor backdrop matches www.thephenom.app: a Figma-exported
floor (cyan #A5E3E8 converging lines with a baked-in Gaussian blur) sitting over
a near-black #060606 surface, so the grid appears to fade up into the dark. The
SVG is inlined here so the server-rendered dashboards stay self-contained and
need no external asset hosting on the container.

Source asset: web/assets/figma/floor.svg on the www repo's figma redesign branch.
Apply with: inject ``backdrop_div()`` right after ``<body>`` and include
``BACKDROP_CSS`` in the page's ``<style>``.
"""

# Exact Figma export (viewBox 0 0 6355.56 1293.66, preserveAspectRatio="none").
# The feGaussianBlur (filter0_f) is the "fade"; the linear gradient runs from
# solid cyan up to transparent toward the vanishing point.
FLOOR_SVG = r"""<svg preserveAspectRatio="none" width="100%" height="100%" overflow="visible" style="display: block;" viewBox="0 0 6355.56 1293.66" fill="none" xmlns="http://www.w3.org/2000/svg">
<g id="floor">
<g id="2" filter="url(#filter0_f_0_125)">
<path d="M11.2347 1282.18L2401.61 11.5H3953.94L6344.32 1282.18M2498.63 11.5L656.812 1282.18M2595.65 11.5L1160.69 1282.18M2692.68 11.5L1580.29 1282.18M2789.69 11.5L1946.84 1282.18M2886.71 11.5L2279.14 1282.18M2983.74 11.5L2589.49 1282.18M3080.75 11.5L2886.71 1282.18M3177.77 11.5V1282.18M3274.8 11.5L3468.84 1282.18M3371.82 11.5L3766.06 1282.18M3468.84 11.5L4076.41 1282.18M3565.86 11.5L4408.7 1282.18M3662.88 11.5L4775.26 1282.18M3759.9 11.5L5194.86 1282.18M3856.92 11.5L5698.74 1282.18M2401.61 11.5177H3953.95H2401.61M2401.6 11.5177H3953.95M2401.59 11.5266H3953.97M2401.55 11.5399H3954M2401.49 11.549H3954.05M2401.39 11.6241H3954.16M2401.21 11.695H3954.34M2400.93 11.8591H3954.62M2400.5 12.0937H3955.05M2399.85 12.4393H3955.71M2398.89 12.9533H3956.67M2397.53 13.6799H3958.03M2395.62 14.6724H3959.93M2393 16.077H3962.55M2389.47 17.9645H3966.08M2384.78 20.4502H3970.78M2378.62 23.7244H3976.93M2370.64 27.9692H3984.91M2360.43 33.3925H3995.13M2347.47 40.2913H4008.08M2331.2 48.9313H4024.35M2310.94 59.7114H4044.61M2285.92 72.9905H4069.63M2255.26 89.3091H4100.29M2217.94 109.146H4137.61M2172.81 133.13H4182.74M2118.58 161.956H4236.97M2053.77 196.401H4301.78M1976.76 237.351H4378.8M1885.68 285.757H4469.87M1778.51 342.724H4577.05M1652.95 409.478H4702.6M1506.48 487.327H4849.07M1336.33 577.795H5019.23M1139.39 682.486H5216.16M912.299 803.176H5443.25M651.344 941.913H5704.21M352.467 1100.79H6003.08M11.2312 1282.16H6344.32" stroke="url(#paint0_linear_0_125)"/>
</g>
<path id="1" d="M11.2347 1282.18L2401.61 11.5H3953.94L6344.32 1282.18M2498.63 11.5L656.812 1282.18M2595.65 11.5L1160.69 1282.18M2692.68 11.5L1580.29 1282.18M2789.69 11.5L1946.84 1282.18M2886.71 11.5L2279.14 1282.18M2983.74 11.5L2589.49 1282.18M3080.75 11.5L2886.71 1282.18M3177.77 11.5V1282.18M3274.8 11.5L3468.84 1282.18M3371.82 11.5L3766.06 1282.18M3468.84 11.5L4076.41 1282.18M3565.86 11.5L4408.7 1282.18M3662.88 11.5L4775.26 1282.18M3759.9 11.5L5194.86 1282.18M3856.92 11.5L5698.74 1282.18M2401.61 11.5177H3953.95H2401.61M2401.6 11.5177H3953.95M2401.59 11.5266H3953.97M2401.55 11.5399H3954M2401.49 11.549H3954.05M2401.39 11.6241H3954.16M2401.21 11.695H3954.34M2400.93 11.8591H3954.62M2400.5 12.0937H3955.05M2399.85 12.4393H3955.71M2398.89 12.9533H3956.67M2397.53 13.6799H3958.03M2395.62 14.6724H3959.93M2393 16.077H3962.55M2389.47 17.9645H3966.08M2384.78 20.4502H3970.78M2378.62 23.7244H3976.93M2370.64 27.9692H3984.91M2360.43 33.3925H3995.13M2347.47 40.2913H4008.08M2331.2 48.9313H4024.35M2310.94 59.7114H4044.61M2285.92 72.9905H4069.63M2255.26 89.3091H4100.29M2217.94 109.146H4137.61M2172.81 133.13H4182.74M2118.58 161.956H4236.97M2053.77 196.401H4301.78M1976.76 237.351H4378.8M1885.68 285.757H4469.87M1778.51 342.724H4577.05M1652.95 409.478H4702.6M1506.48 487.327H4849.07M1336.33 577.795H5019.23M1139.39 682.486H5216.16M912.299 803.176H5443.25M651.344 941.913H5704.21M352.467 1100.79H6003.08M11.2312 1282.16H6344.32" stroke="url(#paint1_linear_0_125)" stroke-opacity="0.7"/>
</g>
<defs>
<filter id="filter0_f_0_125" x="-4.47035e-08" y="0" width="6355.56" height="1293.66" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
<feFlood flood-opacity="0" result="BackgroundImageFix"/>
<feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
<feGaussianBlur stdDeviation="5.5" result="effect1_foregroundBlur_0_125"/>
</filter>
<linearGradient id="paint0_linear_0_125" x1="3177.78" y1="578.641" x2="3177.78" y2="11.5" gradientUnits="userSpaceOnUse">
<stop stop-color="#A5E3E8"/>
<stop offset="1" stop-color="#A5E3E8" stop-opacity="0"/>
</linearGradient>
<linearGradient id="paint1_linear_0_125" x1="3177.78" y1="578.641" x2="3177.78" y2="11.5" gradientUnits="userSpaceOnUse">
<stop stop-color="#A5E3E8"/>
<stop offset="1" stop-color="#A5E3E8" stop-opacity="0"/>
</linearGradient>
</defs>
</svg>"""

# Fixed full-viewport backdrop. z-index:-1 keeps it behind all dashboard chrome
# (sidebars, cards, tickers) for both the scrolling Ops board and the fixed-layout
# NEST app. The floor is stretched wide and anchored to the bottom so the lines
# converge upward and fade via the SVG's own gradient + blur.
#
# osint #34: starfield backdrop derived from the dev-nest SPA stack, bottom
# to top:
#   1. #060606 + figma/bg-image.jpg (the starfield), cover
#   2. dim linear-gradient(rgba(6,6,6,.5) -> rgba(6,6,6,.72))
#   3. cyan radial glow (165,227,232 @ 6%) from the top edge
# (the grid floor stays a separate inline-SVG layer, as before)
# M iteration 2026-06-04: the SPA's home-overlay.png is intentionally NOT
# layered here — on the boards' large exposed background it reads as purple
# blotches, especially at phone widths ("looks like shit" — M).
# Assets are served from 'self' via /assets/figma/ — cross-origin URLs are
# blocked by the boards' CSP (img-src 'self' ...) and silently never render.
BACKDROP_CSS = """
.hero-bg { position:fixed; inset:0; z-index:-1; overflow:hidden; pointer-events:none;
  background:
    radial-gradient(120% 70% at 50% -5%, rgba(165, 227, 232, 0.06), rgba(0,0,0,0) 55%) no-repeat,
    linear-gradient(rgba(6,6,6,0.5), rgba(6,6,6,0.72)) no-repeat,
    #060606 url('/assets/figma/bg-image.jpg') center/cover no-repeat; }
.hero-bg__floor { position:absolute; left:50%; bottom:-4%; transform:translateX(-50%);
  width:172%; height:60%; max-width:none; opacity:.85; transform-origin:center bottom; }
.hero-bg__floor svg { width:100%; height:100%; display:block; }
"""


def backdrop_div() -> str:
    """Return the fixed brand backdrop markup to inject right after ``<body>``."""
    return '<div class="hero-bg" aria-hidden="true"><div class="hero-bg__floor">' + FLOOR_SVG + "</div></div>"
