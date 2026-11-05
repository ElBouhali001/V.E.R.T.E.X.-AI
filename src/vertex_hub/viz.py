"""Impact map: a left-to-right SVG (attribute -> interfaces -> stories -> tests), readable at a glance.
Pure SVG, no JS dependency; hover any box for its full text."""
import re
from html import escape

from .graph import impact

COL_X = [16, 276, 536, 796]
W, H, GAP = 232, 46, 12
COLORS = {"Attribute": ("#1D1D1F", "#FFFFFF"), "Interface": ("#E8F0FF", "#0A50C2"),
          "UserStory": ("#E9F7EE", "#1E6B37"), "TestCase": ("#FFF4E0", "#8A4B00")}
RED = "#FF3B30"
GREEN = "#34C759"


def _short(s, n=30):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _box(x, y, kind, title, subtitle, hover, alert=None, status=None):
    fill, ink = COLORS[kind]
    badge = GREEN if alert == "fixed" else RED
    stroke = badge if alert else ("#1D1D1F" if kind == "Attribute" else "#E5E5EA")
    sw = 2 if alert else 1
    out = [f'<g><title>{escape(hover)}</title>',
           f'<rect x="{x}" y="{y}" width="{W}" height="{H}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>',
           f'<text x="{x + 12}" y="{y + 19}" font-size="12.5" font-weight="700" fill="{ink}">{escape(title)}</text>',
           f'<text x="{x + 12}" y="{y + 35}" font-size="11" fill="{ink}" opacity="0.8">{escape(subtitle)}</text>']
    if alert:
        tw = 7 * len(alert) + 14
        out.append(f'<rect x="{x + W - tw - 8}" y="{y + 8}" width="{tw}" height="16" rx="8" fill="{badge}"/>'
                   f'<text x="{x + W - tw / 2 - 8}" y="{y + 20}" font-size="10" font-weight="700" fill="#fff" text-anchor="middle">{escape(alert)}</text>')
    if status:
        color = {"Failed": RED, "Passed": GREEN}.get(status, "#C7C7CC")
        out.append(f'<circle cx="{x + W - 14}" cy="{y + H - 13}" r="5" fill="{color}"/>')
    out.append("</g>")
    return "".join(out)


def _edge(x1, y1, x2, y2, hot=False):
    mx = (x1 + x2) / 2
    color, w = (RED, 2) if hot else ("#C7C7CC", 1.3)
    return f'<path d="M{x1} {y1} C{mx} {y1}, {mx} {y2}, {x2} {y2}" fill="none" stroke="{color}" stroke-width="{w}" opacity="0.9"/>'


def impact_map(p, G, attr_id, assessment=None, title=None):
    """assessment: output of impact.assess (to colour conflicts). Returns (svg_string, height_px)."""
    r = assessment or impact(G, attr_id)
    ints, stories, tests = r["interfaces"], r["stories_direct"], r["tests_direct"]
    hot = {i: k for i, k, _ in (assessment or {}).get("conflicts", [])}
    fixed = {i for i, _, _ in (assessment or {}).get("resolves", [])}
    outdated = set((assessment or {}).get("outdated_tests", []))
    rows = max(len(ints), len(stories), len(tests), 1)
    top = 64
    height = top + rows * (H + GAP) + 16

    def ys(n):
        block = n * (H + GAP) - GAP
        start = top + (rows * (H + GAP) - GAP - block) / 2
        return [start + k * (H + GAP) for k in range(n)]

    pos = {attr_id: (COL_X[0], ys(1)[0])}
    pos.update({i: (COL_X[1], y) for i, y in zip(ints, ys(len(ints)))})
    pos.update({s: (COL_X[2], y) for s, y in zip(stories, ys(len(stories)))})
    pos.update({t: (COL_X[3], y) for t, y in zip(tests, ys(len(tests)))})

    def right(n):
        x, y = pos[n]
        return x + W, y + H / 2

    def left(n):
        x, y = pos[n]
        return x, y + H / 2

    parts = []
    for i in ints:
        parts.append(_edge(*right(attr_id), *left(i), hot=i in hot))
    for s in stories:
        via = [i for i in p.stories[s]["implements"] if i in ints]
        src = via[0] if via else attr_id
        parts.append(_edge(*right(src), *left(s), hot=src in hot))
    for t in tests:
        v = p.tests[t]["verifies"]
        src = v if v in stories else attr_id
        parts.append(_edge(*right(src), *left(t), hot=t in outdated))

    a = p.attributes[attr_id]
    defs = ", ".join(f"{s.replace('SYS-', '')} {d.get('max_length', d.get('unit', ''))}" for s, d in a["definitions"].items()
                      if "max_length" in d or "unit" in d)
    parts.append(_box(*pos[attr_id], "Attribute", a["canonical"], _short(defs, 34), f"{attr_id}: {defs}"))
    for i in ints:
        it = p.interfaces[i]
        sub = f"{it['from'].replace('SYS-', '')} → {it['to'].replace('SYS-', '')}"
        badge = hot.get(i) or ("fixed" if i in fixed else None)
        parts.append(_box(*pos[i], "Interface", i, sub, f"{i}: {it['name']}", alert=badge))
    for s in stories:
        st = p.stories[s]
        who = re.sub(r"^As an? ", "", st["text"]).split(",")[0]
        parts.append(_box(*pos[s], "UserStory", f"{s}  {st['jira_key']}", _short(who[0].upper() + who[1:], 34), st["text"]))
    for t in tests:
        tc = p.tests[t]
        parts.append(_box(*pos[t], "TestCase", f"{t}  {tc['status']}", _short(tc["title"], 34), tc["title"],
                          alert="outdated" if t in outdated else None, status=tc["status"]))

    heads = ["Attribute", f"Interfaces ({len(ints)})", f"User stories ({len(stories)})", f"Test cases ({len(tests)})"]
    for x, h in zip(COL_X, heads):
        parts.append(f'<text x="{x}" y="{top - 14}" font-size="12.5" font-weight="600" fill="#6E6E73">{escape(h)}</text>')
    if title:
        parts.append(f'<text x="16" y="22" font-size="16" font-weight="650" fill="#1D1D1F" letter-spacing="-0.2">{escape(title)}</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1044 {height:.0f}" width="100%" '
           f'font-family="-apple-system, BlinkMacSystemFont, SF Pro Text, Inter, Helvetica Neue, Arial, sans-serif">{"".join(parts)}</svg>')
    return svg, height
