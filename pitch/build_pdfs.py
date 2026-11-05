"""Builds T103_DPLM_OnePager.pdf and T103_DPLM_Slides.pdf from HTML with headless Chrome.
Fill SCORES once measured with tools/llm_eval.py, then run: python pitch/build_pdfs.py"""
import base64
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent
ASSETS = REPO / "app" / "assets"

SCORES = {  # None = not measured yet -> shown as a visible placeholder
    "ai_holdout": None,     # e.g. "4/4"
    "hybrid_holdout": None,  # e.g. "4/4"
    "model": "qwen2.5:7b",
}

TEAM = ["Houssam ElMouedden", "Pietro Tirante", "Muhammad Ali", "Govinda Bhattarai",
        "Aymeric Slaouti", "Mohamed Taleb Moustaph", "Kishore Kannan Prabakaran"]


def svg_uri(name):
    return "data:image/svg+xml;base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


def val(key, fallback="to measure"):
    v = SCORES[key]
    return v if v else f'<span class="tbd">{fallback}</span>'


LOGO, MARK, CAP = svg_uri("vertex-logo-h.svg"), svg_uri("vertex-mark.svg"), svg_uri("partner-logo.svg")

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Inter, 'DejaVu Sans', sans-serif; color: #1D1D1F; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
b, strong { font-weight: 650; }
.blue { color: #0A6CFF; } .red { color: #D92D20; } .green { color: #1E7B39; } .muted { color: #6E6E73; }
.tbd { background: #FFF4E0; color: #A05A00; border-radius: 4px; padding: 0 4px; font-weight: 600; }
.pill { display: inline-block; border-radius: 999px; padding: 2px 8px; background: #F2F2F7; color: #3A3A3C; font-weight: 600; white-space: nowrap; }
.pill.b { background: #E8F0FF; color: #0A50C2; } .pill.g { background: #E7F8EC; color: #1E7B39; } .pill.o { background: #FFF4E0; color: #A05A00; }
.pill.d { background: #1D1D1F; color: #fff; }
table { border-collapse: collapse; width: 100%; }
"""

# ----------------------------------------------------------------------------- pipeline strip (shared)
def pipeline(size):
    steps = [("Sources", "minutes, tickets, specs, emails", "#8E8E93"),
             ("Guardrails", "mask personal data, quarantine injections", "#1D1D1F"),
             ("AI reads", "rules + local model, verbatim-quote gate", "#0A6CFF"),
             ("Graph reasons", "ontology, impact, conflicts, alerts", "#3D3BD6"),
             ("Person decides", "approve / reject, logged", "#1E7B39"),
             ("Tools updated", "Jira backlog, no migration", "#8E8E93")]
    cells = "".join(
        f'<div class="ps"><div class="pt" style="background:{c}">{t}</div><div class="pd">{d}</div></div>'
        + ('<div class="pa">&#8250;</div>' if i < len(steps) - 1 else "")
        for i, (t, d, c) in enumerate(steps))
    return f'<div class="pipe pipe-{size}">{cells}</div>'


PIPE_CSS = """
.pipe { display: flex; align-items: stretch; }
.ps { flex: 1; text-align: center; }
.pt { color: #fff; border-radius: 8px; font-weight: 650; }
.pd { color: #3A3A3C; line-height: 1.3; }
.pa { color: #AEAEB2; display: flex; align-items: center; font-weight: 300; }
.pipe-s .pt { font-size: 8.6pt; padding: 5px 2px; } .pipe-s .pd { font-size: 7pt; margin-top: 4px; } .pipe-s .pa { font-size: 16pt; padding: 0 2px; }
.pipe-l .pt { font-size: 15px; padding: 10px 4px; border-radius: 10px; } .pipe-l .pd { font-size: 12.5px; margin-top: 7px; } .pipe-l .pa { font-size: 30px; padding: 0 4px; }
"""

# ----------------------------------------------------------------------------- one-pager
REQS = [
    ("1", "Framework from client data and method", "One sentence &rarr; client profile &rarr; backlog in the client's PLM vocabulary, structured for SAFe, Scrum or Waterfall"),
    ("2", "Ontologies, bilingual glossary, updates", "15 FR/EN concepts, editor profiles for 3DEXPERIENCE, Windchill and Teamcenter; new terms proposed, validated by a steward"),
    ("3", "Ingest and detect inconsistencies", "Minutes, tickets, specs, emails &rarr; facts with source quote &rarr; conflicts and dated alerts"),
    ("4", "Connect without migration", "Reads the files teams already write; pushes decisions to Jira (mock in demo, cloud connector ready)"),
    ("5", "Multi-criteria decision support", "Impact map, trade-offs per proposal, approve / reject with an audit trail"),
    ("6", "No hallucination, no leak", "Quote must exist verbatim, IDs must exist; local model; personal data masked; injections quarantined"),
    ("7", "Governance and billing", "Named owners and release gates; Build / Run / Support pricing (below)"),
]


def onepager():
    req_rows = "".join(f'<tr><td class="rn">{n}</td><td class="rt">{t}</td><td>{d}</td></tr>' for n, t, d in REQS)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 0; }}
{BASE_CSS}{PIPE_CSS}
body {{ width: 210mm; height: 297mm; padding: 11mm 12mm 9mm; font-size: 8.4pt; line-height: 1.38; display: flex; flex-direction: column; }}
header {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #E5E5EA; padding-bottom: 6px; }}
header .l img {{ height: 34px; }}
header .r {{ text-align: right; font-size: 7.6pt; color: #6E6E73; }}
header .r img {{ height: 17px; display: block; margin: 0 0 3px auto; }}
h1 {{ font-size: 15.5pt; letter-spacing: -0.2px; margin: 8px 0 2px; line-height: 1.2; }}
.sub {{ font-size: 9pt; color: #3A3A3C; }}
h2 {{ font-size: 9.6pt; text-transform: uppercase; letter-spacing: 0.6px; color: #0A6CFF; margin: 9px 0 4px; }}
.cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0 9mm; }}
ul {{ padding-left: 11px; }} li {{ margin: 1.5px 0; }}
.box {{ background: #F5F5F7; border-radius: 9px; padding: 7px 9px; }}
.req td {{ padding: 3px 4px; border-bottom: 0.5px solid #E5E5EA; vertical-align: top; font-size: 7.8pt; }}
.req .rn {{ width: 13px; font-weight: 700; color: #0A6CFF; }} .req .rt {{ width: 36mm; font-weight: 600; }}
.figs {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }}
.fig {{ background: #F5F5F7; border-radius: 8px; padding: 6px 7px; }}
.fig .n {{ font-size: 14pt; font-weight: 700; letter-spacing: -0.3px; line-height: 1.1; }}
.fig .t {{ font-size: 7pt; color: #3A3A3C; margin-top: 2px; line-height: 1.25; }}
.bill td {{ padding: 3px 4px; border-bottom: 0.5px solid #E5E5EA; font-size: 7.8pt; vertical-align: top; }}
footer {{ margin-top: auto; border-top: 1px solid #E5E5EA; padding-top: 5px; font-size: 7.2pt; color: #6E6E73; display: flex; justify-content: space-between; }}
</style></head><body>
<header><div class="l"><img src="{LOGO}"></div>
<div class="r"><img src="{CAP}">DPM/PLM Hackathon &middot; Project 1 &middot; Team 103</div></header>

<h1>Vertex Hub: an AI-driven PLM project accelerator</h1>
<div class="sub"><b>V.E.R.T.E.X. AI</b>, Value Extraction and Reconciliation for Technical Excellence. <i>The intersection of PLM ontologies and agile delivery.</i></div>

<div class="cols">
<div>
<h2>Problem</h2>
<ul>
<li><b>Every PLM project starts from zero.</b> Each client has its own editor (3DEXPERIENCE, Windchill, Teamcenter), vocabulary (FR/EN, &ldquo;Plant BOM&rdquo; vs MBOM), tools and method. Setting up the framework takes weeks.</li>
<li><b>Decisions are scattered</b> across minutes, tickets, specs and emails. Nobody sees that a decision in one meeting breaks an interface agreed in another.</li>
<li><b>Inconsistencies surface in test, not in the meeting:</b> rework on interfaces, test cases and data migration.</li>
<li><b>Generic AI is not an option:</b> it invents facts and sends client data outside.</li>
</ul>
<h2>Approach and methodology</h2>
<ul>
<li><b>Built as a PLM project would be run:</b> CR/CO/CA change process, EBOM/MBOM/PBOM, ERP and MES interfaces, a change board that decides.</li>
<li><b>Realistic synthetic data:</b> an automotive client (ACME, 3DEXPERIENCE + SAP + MES) with minutes, workshops, status reports, backlog, tickets and tests, and a medtech client (Windchill, Scrum) to prove reuse.</li>
<li><b>Measured, not claimed:</b> a ground truth with a <b>holdout</b> the rules never saw; 45 automated tests; an injection benchmark.</li>
<li><b>Security first:</b> local model, masking and quarantine before any AI call, every action audited.</li>
</ul>
</div>
<div>
<h2>Solution</h2>
<div class="box" style="margin-bottom:6px">{pipeline("s")}</div>
<table class="req">{req_rows}</table>
</div>
</div>

<h2>Results on the demo project</h2>
<div class="figs">
<div class="fig"><div class="n blue">14 days</div><div class="t">earlier warning: the 80&rarr;40 character truncation flagged on 21 Sept, not at test on 5 Oct</div></div>
<div class="fig"><div class="n">1 fixed, 2 new</div><div class="t">ERP proposal analysed: fixes INT-01, but outdates TC-205 and breaks a naming rule; 5 stories, 4 tests impacted</div></div>
<div class="fig"><div class="n">35 / 1</div><div class="t">personal-data items masked / injection quarantined before any AI call</div></div>
<div class="fig"><div class="n">7&middot;15&middot;27</div><div class="t">epics, capabilities, features generated for a new medtech client in seconds</div></div>
<div class="fig"><div class="n">2 / 3 / 6</div><div class="t">R2026x upgrade: new truncation risks / interfaces to retest / tests to rerun</div></div>
<div class="fig"><div class="n">0 / 18</div><div class="t">false alarms of the injection filter on real project language (0% on benchmark)</div></div>
<div class="fig"><div class="n">8/8 &rarr; 0/4</div><div class="t">rules alone: perfect on seen docs, blind on the holdout. Why the AI is needed</div></div>
<div class="fig"><div class="n">{val("hybrid_holdout")}</div><div class="t">holdout facts found by rules + local model ({SCORES["model"]}); local model alone: {val("ai_holdout")}</div></div>
</div>

<div class="cols" style="margin-top:2px">
<div>
<h2>Governance</h2>
<ul>
<li>The AI proposes, <b>a named person approves</b>; every decision is logged.</li>
<li>Client-side ontology steward validates new terms; the integrator owns catalogue, editor profiles and connectors.</li>
<li>Release gates: a new model or rule ships only if holdout recall holds and false alarms stay at 0.</li>
</ul>
</div>
<div>
<h2>Billing model <span class="muted" style="text-transform:none;letter-spacing:0;font-weight:400">(assumptions to validate)</span></h2>
<table class="bill">
<tr><td><b>Build</b>, once per client</td><td>connectors, vocabulary, framework in their method</td><td><b>~&euro;15k</b> fixed</td></tr>
<tr><td><b>Run</b>, per project</td><td>local model, ingestion, alerts, audit trail</td><td><b>~&euro;1.5k</b>/month</td></tr>
<tr><td><b>Support</b>, yearly</td><td>new connectors, ontology, model upgrades re-measured</td><td><b>~15%</b> of build</td></tr>
</table>
</div>
</div>

<h2>Limits we state openly</h2>
<div style="font-size:7.8pt">Synthetic data only &middot; Jira connector tested as a mock &middot; name detection relies on known names &middot; injection filter tuned for zero false alarms, so it catches only obvious attacks (12% recall on the benchmark) &middot; prices are working assumptions.</div>

<footer><span>Team 103: {" &middot; ".join(TEAM)}</span><span>Python, local LLM (Ollama), networkx, Streamlit</span></footer>
</body></html>"""


# ----------------------------------------------------------------------------- slides
def slide(n, title, kicker, body):
    return f"""<section class="slide"><div class="top"><div><div class="kick">{kicker}</div><h1>{title}</h1></div>
<div class="logos"><img class="cap" src="{CAP}"><img class="vx" src="{LOGO}"></div></div>
<div class="body">{body}</div>
<div class="foot"><span>Team 103 &middot; Project 1 &middot; AI-driven PLM project accelerator</span><span>{n} / 3</span></div></section>"""


def slides():
    s1 = """
<p class="lead">A PLM integrator loses the first weeks of every project rebuilding the same framework, and finds inconsistencies at test, when they are expensive.</p>
<div class="three">
 <div class="card"><div class="ic">1</div><h3>Every client is different</h3><p>Editor (3DEXPERIENCE, Windchill, Teamcenter), vocabulary in two languages (<i>nomenclature de fabrication</i> = Plant BOM = MBOM), method (SAFe, Scrum, Waterfall).</p></div>
 <div class="card"><div class="ic">2</div><h3>Decisions live in documents</h3><p>Minutes, tickets, specs, emails. A decision in one meeting silently breaks an interface agreed in another.</p></div>
 <div class="card"><div class="ic">3</div><h3>AI must be trustworthy</h3><p>A generic chatbot invents facts and sends design data outside. For an industrial client, that ends the conversation.</p></div>
</div>
<div class="ask">
 <div class="asklbl">What the client asks for</div>
 <div class="chips"><span class="pill b">Framework in 48 h</span><span class="pill b">Bilingual ontology</span><span class="pill b">Detect inconsistencies</span>
 <span class="pill b">No migration</span><span class="pill b">Decision support + traceability</span><span class="pill b">No hallucination, no leak</span><span class="pill b">Governance + billing</span></div>
</div>
<div class="example"><b>The case we built:</b> ACME, an automotive supplier on 3DEXPERIENCE + SAP + MES. The PLM part description is 80 characters; the ERP field holds 40.
Agreed in one meeting, contradicted in another, discovered at test. <b class="red">That is the failure we prevent.</b></div>
"""
    s2 = f"""
<p class="lead"><b>Vertex Hub</b>: the AI reads, the graph reasons, a person decides.</p>
<div class="pipewrap">{pipeline("l")}</div>
<div class="two">
 <div>
  <div class="lbl">Proof on the demo project</div>
  <table class="proof">
   <tr><td class="n blue">14 days</td><td>earlier warning on the 80&rarr;40 truncation (21 Sept vs test on 5 Oct)</td></tr>
   <tr><td class="n">1 fixed, 2 new</td><td>ERP proposal: fixes INT-01, outdates TC-205, breaks a naming rule. The board sees the trade-off before approving</td></tr>
   <tr><td class="n">7&middot;15&middot;27</td><td>epics, capabilities, features for a new medtech client, in its method and Windchill vocabulary</td></tr>
   <tr><td class="n">35 / 1 / 0</td><td>personal data masked / injection quarantined / false alarms on project language</td></tr>
   <tr><td class="n">{val("hybrid_holdout")}</td><td>holdout facts found by rules + local model, every one with a verbatim source quote (rules alone: 0/4)</td></tr>
  </table>
 </div>
 <div>
  <div class="lbl">Why a client adopts it</div>
  <ul class="why">
   <li><b>No migration:</b> reads what teams already write, writes back to Jira.</li>
   <li><b>Nothing leaves the site:</b> the model runs locally.</li>
   <li><b>Reused across clients:</b> catalogue, 3 editor profiles, 15 FR/EN concepts.</li>
   <li><b>Governed:</b> a steward validates terms, a board approves changes, every action audited.</li>
  </ul>
  <div class="lbl" style="margin-top:12px">Billing <span class="muted" style="font-weight:400;text-transform:none;letter-spacing:0">(assumptions)</span></div>
  <div class="bill"><div><b>Build</b><br>~&euro;15k per client</div><div><b>Run</b><br>~&euro;1.5k per project / month</div><div><b>Support</b><br>~15% of build / year</div></div>
 </div>
</div>
"""
    learned = [
        ("How a PLM project really runs", "Change requests become change orders and actions; a change board decides; EBOM, MBOM and PBOM feed ERP and MES; an editor upgrade (R2025x &rarr; R2026x) is itself an impact analysis."),
        ("PLM vocabulary is the real integration problem", "The same object has a different name per editor, per language and per team. Reconciling terms had to come before any AI."),
        ("The security trade-off", "Our first injection filter flagged 10 of 11 normal project sentences. We chose zero false alarms over recall (12%) and said so, because a filter that blocks real minutes gets switched off."),
        ("Measure on data you never tuned on", "Rules scored 8/8 on known documents and 0/4 on the holdout. Without a holdout we would have pitched a number that was false."),
        ("Local AI has limits you design around", "A 7B model on a laptop needs strict JSON, a source-quote check and a cache. The guardrails make it usable, not the model size."),
        ("Keep a person in the loop", "Clients trust a tool that proposes and logs. They don't trust one that changes their model on its own."),
    ]
    items = "".join(f'<div class="ln"><div class="lt">{t}</div><div class="ld">{d}</div></div>' for t, d in learned)
    team = "".join(f'<span class="pill{" d" if i == 0 else ""}">{n}</span>' for i, n in enumerate(TEAM))
    s3 = f"""
<div class="grid6">{items}</div>
<div class="next"><b>Next, if we win the contract:</b> run on one real project's documents, connect the client's live Jira, and measure the holdout on their data before any rollout.</div>
<div class="team"><span class="lbl" style="margin-right:6px">Team 103</span>{team}</div>
"""
    body = slide(1, "What I Understood", "The client's problem", s1) + slide(2, "What I Propose", "Vertex Hub", s2) + slide(3, "What I Learned", "From building it", s3)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: 1280px 720px; margin: 0; }}
{BASE_CSS}{PIPE_CSS}
.slide {{ width: 1280px; height: 720px; padding: 40px 56px 28px; display: flex; flex-direction: column; page-break-after: always; overflow: hidden; }}
.top {{ display: flex; justify-content: space-between; align-items: flex-start; }}
.kick {{ font-size: 14px; font-weight: 650; color: #0A6CFF; text-transform: uppercase; letter-spacing: 1px; }}
h1 {{ font-size: 44px; letter-spacing: -1px; line-height: 1.1; margin-top: 4px; }}
.logos {{ display: flex; align-items: center; gap: 18px; }} .logos .cap {{ height: 24px; }} .logos .vx {{ height: 40px; }}
.body {{ flex: 1; margin-top: 20px; display: flex; flex-direction: column; }}
.foot {{ display: flex; justify-content: space-between; font-size: 12px; color: #8E8E93; border-top: 1px solid #E5E5EA; padding-top: 10px; }}
.lead {{ font-size: 22px; line-height: 1.35; color: #1D1D1F; max-width: 1100px; letter-spacing: -0.2px; }}
.three {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 24px; }}
.card {{ background: #F5F5F7; border-radius: 18px; padding: 20px 22px; }}
.card .ic {{ width: 30px; height: 30px; border-radius: 50%; background: #0A6CFF; color: #fff; font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 15px; }}
.card h3 {{ font-size: 19px; margin: 12px 0 6px; letter-spacing: -0.2px; }} .card p {{ font-size: 15px; line-height: 1.45; color: #3A3A3C; }}
.ask {{ margin-top: 22px; }} .asklbl, .lbl {{ font-size: 12.5px; font-weight: 650; text-transform: uppercase; letter-spacing: 0.8px; color: #6E6E73; margin-bottom: 8px; }}
.chips .pill {{ font-size: 14px; padding: 5px 12px; margin: 0 6px 6px 0; }}
.example {{ margin-top: auto; margin-bottom: 16px; background: #FFF6F5; border-left: 4px solid #D92D20; border-radius: 10px; padding: 14px 18px; font-size: 16px; line-height: 1.45; }}
.pipewrap {{ background: #F5F5F7; border-radius: 18px; padding: 18px 16px; margin-top: 16px; }}
.two {{ display: grid; grid-template-columns: 1.25fr 1fr; gap: 36px; margin-top: 20px; }}
.proof td {{ padding: 7px 8px 7px 0; border-bottom: 1px solid #E5E5EA; font-size: 14.5px; line-height: 1.35; vertical-align: top; }}
.proof .n {{ font-size: 19px; font-weight: 700; white-space: nowrap; width: 150px; letter-spacing: -0.3px; }}
.why {{ list-style: none; }} .why li {{ font-size: 15px; line-height: 1.4; margin-bottom: 7px; padding-left: 16px; position: relative; }}
.why li:before {{ content: ""; position: absolute; left: 0; top: 8px; width: 7px; height: 7px; border-radius: 50%; background: #0A6CFF; }}
.bill {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }} .bill div {{ background: #F5F5F7; border-radius: 12px; padding: 10px 12px; font-size: 13.5px; line-height: 1.35; }}
.grid6 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px 22px; }}
.ln {{ background: #F5F5F7; border-radius: 16px; padding: 16px 18px; }}
.lt {{ font-size: 17.5px; font-weight: 650; letter-spacing: -0.2px; line-height: 1.25; }} .ld {{ font-size: 14px; line-height: 1.45; color: #3A3A3C; margin-top: 7px; }}
.next {{ margin-top: 18px; font-size: 16px; line-height: 1.4; background: #E8F0FF; border-radius: 12px; padding: 12px 16px; }}
.team {{ margin-top: auto; margin-bottom: 14px; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }} .team .pill {{ font-size: 13.5px; padding: 4px 11px; }}
</style></head><body>{body}</body></html>"""


def render(html, out):
    import tempfile
    src = Path(tempfile.mkdtemp()) / (out.stem + ".html")
    src.write_text(html, encoding="utf-8")
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", src.as_uri()], check=True, capture_output=True)
    print("wrote", out)


if __name__ == "__main__":
    out = HERE
    render(onepager(), out / "T103_DPLM_OnePager.pdf")
    render(slides(), out / "T103_DPLM_Slides.pdf")
