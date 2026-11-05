"""Vertex Hub look: Apple-style light surfaces, SF Pro, grouped lists. Pure HTML strings rendered with st.markdown."""
import re
from html import escape

BRAND = "Vertex Hub"
ACRONYM = "V.E.R.T.E.X. AI: Value Extraction and Reconciliation for Technical Excellence"
TAGLINE = "The intersection of PLM ontologies and agile delivery."

CSS = """
<style>
:root {
  --vx-ink: #1D1D1F; --vx-ink2: #6E6E73; --vx-ink3: #8E8E93; --vx-line: #E5E5EA; --vx-canvas: #F5F5F7;
  --vx-blue: #0A6CFF; --vx-red: #FF3B30; --vx-orange: #FF9F0A; --vx-green: #34C759; --vx-indigo: #3D3BD6;
  --vx-font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", "Helvetica Neue", Arial, sans-serif;
}
html, body, .stApp, .stMarkdown, button, input, textarea, select, [data-testid="stSidebar"] { font-family: var(--vx-font) !important; }
.stApp { background: var(--vx-canvas); }
/* the header no longer covers the first lines of each page */
header[data-testid="stHeader"] { background: rgba(245,245,247,0.72); backdrop-filter: saturate(180%) blur(20px); -webkit-backdrop-filter: saturate(180%) blur(20px); }
.block-container { padding-top: 4.25rem !important; padding-bottom: 4rem; max-width: 1320px; }
h1, h2, h3 { letter-spacing: -0.022em; color: var(--vx-ink); }

/* hero */
.vx-hero h1 { font-size: 40px; line-height: 1.08; font-weight: 700; margin: 0 0 8px; padding: 0; }
.vx-hero p { font-size: 17px; line-height: 1.45; color: var(--vx-ink2); margin: 0; max-width: 72ch; }

/* figures strip: numbers, not cards */
.vx-figures { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 28px 0 30px; }
.vx-fig { padding: 2px 22px 2px 0; border-left: 1px solid var(--vx-line); padding-left: 22px; }
.vx-fig:first-child { border-left: 0; padding-left: 0; }
.vx-fig .n { font-size: 34px; font-weight: 600; letter-spacing: -0.03em; color: var(--vx-ink); line-height: 1.1; font-variant-numeric: tabular-nums; }
.vx-fig .n.alert { color: var(--vx-red); }
.vx-fig .l { font-size: 13px; color: var(--vx-ink2); margin-top: 4px; line-height: 1.35; }

/* grouped lists (iOS Settings style): keyed containers st-key-grp-* */
[class*="st-key-grp-"] { background: #FFFFFF; border-radius: 18px !important; border: 0 !important;
  box-shadow: 0 0 0 0.5px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04); padding: 6px 18px 10px !important; }
.vx-title { font-size: 20px; font-weight: 650; letter-spacing: -0.015em; color: var(--vx-ink); margin: 6px 0 10px 2px; }
.vx-title small { font-weight: 500; color: var(--vx-ink3); font-size: 15px; margin-left: 6px; }
.vx-sep { height: 0.5px; background: var(--vx-line); margin: 10px 0 8px; }
.vx-row-t { font-size: 16px; font-weight: 600; color: var(--vx-ink); letter-spacing: -0.01em; line-height: 1.3; }
.vx-row-d { font-size: 14px; color: #3A3A3C; margin-top: 3px; line-height: 1.45; }
.vx-row-m { font-size: 12.5px; color: var(--vx-ink3); margin-top: 5px; line-height: 1.45; }
.vx-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 8px; vertical-align: 1px; }
.vx-dot.high { background: var(--vx-red); } .vx-dot.medium { background: var(--vx-orange); } .vx-dot.low { background: var(--vx-ink3); }
.vx-dot.ok { background: var(--vx-green); } .vx-dot.warn { background: var(--vx-orange); }

/* pills */
.vx-pill { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 550;
  margin: 4px 6px 0 0; background: #F2F2F7; color: #3A3A3C; white-space: nowrap; }
.vx-pill.blue { background: #E8F0FF; color: #0A50C2; } .vx-pill.red { background: #FFECEB; color: #C4271E; }
.vx-pill.orange { background: #FFF4E0; color: #A05A00; } .vx-pill.green { background: #E7F8EC; color: #1E7B39; }
.vx-pill.dark { background: var(--vx-ink); color: #FFFFFF; }

/* quotes and documents */
.vx-quote { font-size: 15px; line-height: 1.5; color: var(--vx-ink); background: #F5F8FF; border-radius: 12px; padding: 10px 14px; margin: 8px 0; }
.vx-quote .src { display: block; font-size: 12px; color: var(--vx-ink3); margin-top: 4px; }
.vx-doc { white-space: pre-wrap; font-size: 14px; line-height: 1.6; background: #FFFFFF; border-radius: 16px; padding: 18px 20px;
  box-shadow: 0 0 0 0.5px rgba(0,0,0,0.06); max-height: 560px; overflow: auto; color: var(--vx-ink); }
.vx-doc mark { background: #DDEBFF; color: inherit; padding: 1px 2px; border-radius: 4px; }
.vx-doc .pii { background: var(--vx-ink); color: #FFFFFF; border-radius: 5px; padding: 0 5px; font-size: 12px; }
.vx-map { background: #FFFFFF; border-radius: 18px; padding: 10px 6px 4px; box-shadow: 0 0 0 0.5px rgba(0,0,0,0.06); }

/* sidebar */
[data-testid="stSidebar"] { border-right: 0.5px solid #D1D1D6; }
.vx-side-client { font-size: 13px; color: var(--vx-ink2); line-height: 1.5; margin: 2px 0 14px; }
.vx-side-client b { color: var(--vx-ink); font-size: 14px; }
.vx-status { font-size: 12.5px; color: var(--vx-ink2); line-height: 1.45; }

/* buttons: quieter, rounder */
.stButton > button, .stDownloadButton > button { border-radius: 999px !important; font-weight: 550; }
.stButton > button[kind="tertiary"] { color: var(--vx-blue); padding-left: 0; }
[data-testid="stTabs"] button p { font-size: 15px; font-weight: 550; }
@media (max-width: 900px) { .vx-figures { grid-template-columns: repeat(2, 1fr); row-gap: 18px; } .vx-hero h1 { font-size: 30px; } }
</style>
"""


def pill(text, cls=""):
    return f'<span class="vx-pill {cls}">{escape(str(text))}</span>'


def dot(cls):
    return f'<span class="vx-dot {cls}"></span>'


def hero(title, sub):
    return f'<div class="vx-hero"><h1>{escape(title)}</h1><p>{escape(sub)}</p></div>'


def figures(items):
    """items: list of (number, label, is_alert)."""
    cells = "".join(f'<div class="vx-fig"><div class="n{" alert" if a else ""}">{escape(str(n))}</div><div class="l">{escape(l)}</div></div>'
                    for n, l, a in items)
    return f'<div class="vx-figures">{cells}</div>'


def title(text, count=None):
    c = f"<small>{count}</small>" if count is not None else ""
    return f'<div class="vx-title">{escape(text)}{c}</div>'


def row(t, d="", m="", lead=""):
    return (f'<div class="vx-row-t">{lead}{escape(t)}</div>' + (f'<div class="vx-row-d">{d}</div>' if d else "")
            + (f'<div class="vx-row-m">{m}</div>' if m else ""))


SEP = '<div class="vx-sep"></div>'


def quote(text, source=""):
    s = f'<span class="src">{escape(source)}</span>' if source else ""
    return f'<div class="vx-quote">“{escape(text)}”{s}</div>'


def doc_html(text, quotes=()):
    """Escape, highlight extracted quotes, style masked tokens."""
    h = escape(text)
    for q in sorted({q for q in quotes if q}, key=len, reverse=True):
        eq = escape(q)
        if eq in h:
            h = h.replace(eq, f"<mark>{eq}</mark>")
    h = re.sub(r"&lt;(PERSON|EMAIL|PHONE)_(\d+)&gt;", r'<span class="pii">\1 \2</span>', h)
    return f'<div class="vx-doc">{h}</div>'
