"""Vertex Hub: project cockpit. Run from the repo root:  streamlit run app/streamlit_app.py"""
import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent / "assets"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import ui  # noqa: E402
from vertex_hub import llm, run_pipeline  # noqa: E402
from vertex_hub.bootstrap import bootstrap  # noqa: E402
from vertex_hub.data import load_yaml  # noqa: E402
from vertex_hub.decisions import send_outbox  # noqa: E402
from vertex_hub.evaluate import gold_table, misses, score  # noqa: E402
from vertex_hub.extract import fact_key  # noqa: E402
from vertex_hub.impact import assess, assess_fact, tradeoff, version_upgrade  # noqa: E402
from vertex_hub.viz import impact_map  # noqa: E402

st.set_page_config(page_title=ui.BRAND, page_icon=str(ASSETS / "favicon.png"), layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)
st.logo(str(ASSETS / "vertex-logo-h.png"), size="large", icon_image=str(ASSETS / "vertex-mark-128.png"))


@st.cache_resource
def get_twin():
    return run_pipeline(ROOT)


twin = get_twin()
p = twin.project
LLM = llm.status()
ss = st.session_state
ss.setdefault("mode", "hybrid" if LLM["ok"] else "rules")
ss.setdefault("doc", next(iter(twin.sanitized)))
ss.setdefault("attr", "ATT-DESC")
ss.setdefault("proposed_terms", [])
MODE_LABEL = {"rules": "Rules", "ai": "Local AI", "hybrid": "Hybrid"}
SYS = {"SYS-PLM": "PLM", "SYS-ERP": "ERP", "SYS-MES": "MES", "SYS-CAD": "CAD", "SYS-JIRA": "Jira"}


# ------------------------------------------------------------------ helpers
def doc_meta(doc_id):
    d = p.documents.get(doc_id) or p.incoming.get(doc_id) or {}
    return {"title": d.get("title") or d.get("text", "")[:60], "date": str(d.get("date") or d.get("created") or ""),
            "type": d.get("type") or ("Jira story" if doc_id in p.incoming else "document"), "lang": d.get("language", "")}


def facts_for(doc_id):
    return twin.extract_doc(doc_id, ss.mode, allow_calls=False)


def show_map(attr, assessment=None, title=None):
    svg, _ = impact_map(p, twin.G, attr, assessment, title)
    st.html(f'<div class="vx-map">{svg}</div>')


def items_df(ids):
    return pd.DataFrame([{"Item": i, "Jira": p.item(i)["jira_key"], "Status": p.item(i)["status"],
                          "Summary": p.item(i).get("title") or p.item(i)["text"]} for i in ids])


def goto(page, **state):
    ss.update(state)
    st.switch_page(PAGES[page])


def change_text(f, r):
    name = p.attributes[f["attribute"]]["canonical"] if f.get("attribute") else "Platform version"
    unit = "characters" if f["property"] == "max_length" else ""
    cur = r["current"] if r else ""
    return f"{name} in {SYS.get(f.get('system'), '')}: {cur} → {f['value']} {unit}".strip()


def plural(n, word, many=None):
    return f"{n} {word if n == 1 else (many or word + 's')}"


def group(key):
    return st.container(key=f"grp-{key}")


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    land = p.profile["landscape"]
    st.markdown(f'<div class="vx-side-client"><b>{ui.escape(p.profile["name"])}</b><br>'
                f'{land["plm"]["product"]} {land["plm"]["version"]}, {p.profile["delivery_framework"]}<br>Backlog in {twin.jira.name}</div>',
                unsafe_allow_html=True)
    picked = st.segmented_control("Reading mode", list(MODE_LABEL), format_func=MODE_LABEL.get, default=ss.mode, key="mode_pick",
                                  help="Rules: fast and transparent. Local AI: the model on this machine. Hybrid: both, checked by the same gate.")
    if picked and picked != ss.mode:
        ss.mode = picked
    installed = [m for m in (LLM.get("models") or []) if "embed" not in m]
    if installed:
        cur = LLM["model"] if LLM["model"] in installed else None
        chosen = st.selectbox("Local model", installed, index=installed.index(cur) if cur else 0,
                              help="Models installed with `ollama pull`. Answers are cached per model.")
        if chosen != LLM["model"]:
            os.environ["LLM_MODEL"] = chosen
            st.rerun()
    state = "ok" if LLM["ok"] else "warn"
    st.markdown(f'<div class="vx-status">{ui.dot(state)}{ui.escape(LLM["detail"].capitalize())}</div>', unsafe_allow_html=True)
    if ss.mode != "rules" and not LLM["ok"]:
        st.caption("Documents are read with rules until the local model is available.")
    st.write("")
    if st.button("Reset demo", icon=":material/restart_alt:", width="stretch"):
        if hasattr(twin.jira, "reset"):
            twin.jira.reset()
        st.cache_resource.clear()
        ss.clear()
        st.rerun()
    st.caption(ui.TAGLINE)


# ------------------------------------------------------------------ cockpit
def alert_row(a, n):
    srcs = ", ".join(s["doc"] + (f" ({s['date']})" if s["date"] else "") for s in a["sources"])
    meta = f"Seen in {srcs}. First visible {a['first_seen'] or 'today'}. Affects {plural(len(a['stories']), 'story', 'stories')} and {plural(len(a['tests']), 'test')}."
    for x in a["resolutions"]:
        meta += f"<br>Proposed fix in {x['doc']}: {ui.escape(x['change'].replace('SYS-', '').replace('max_length', 'max length').replace('->', '→'))}"
        if x["side_effects"]:
            meta += f", which makes {', '.join(x['side_effects'])} outdated"
    if n:
        st.markdown(ui.SEP, unsafe_allow_html=True)
    st.markdown(ui.row(a["title"], ui.escape(a["human"]), meta, ui.dot(a["severity"])), unsafe_allow_html=True)
    b1, b2, _ = st.columns([1.1, 1.1, 3])
    if b1.button("Show impact", key=f"imp-{a['id']}", type="tertiary", icon=":material/account_tree:"):
        goto("impact", attr=a["attribute"])
    doc = a["doc_sources"][-1] if a["doc_sources"] else None
    if doc and b2.button("Open source", key=f"src-{a['id']}", type="tertiary", icon=":material/description:"):
        goto("docs", doc=doc)


def page_cockpit():
    alerts = twin.alerts(ss.mode)
    current = [a for a in alerts if a["state"] == "current"]
    future = [a for a in alerts if a["state"] != "current"]
    proposed = twin.pending(ss.mode)
    outbox = twin.audit.db.execute("SELECT COUNT(*) FROM outbox WHERE status='drafted'").fetchone()[0]
    ai_docs = sum(twin.ai_ready(d) for d in twin.sanitized)
    lead = max(((dt.date.fromisoformat(max(s["date"] for s in a["sources"] if s["date"])) - dt.date.fromisoformat(a["first_seen"])).days
                for a in current if len(a["doc_sources"]) >= 2), default=0)

    land = p.profile["landscape"]
    head = (f"{plural(len(current), 'problem')} need{'s' if len(current) == 1 else ''} attention today" if current
            else "Nothing needs attention today")
    st.markdown(ui.hero(head, f"{p.profile['name']}, {p.profile['industry']}: {land['plm']['product']} {land['plm']['version']} with "
                              f"{land['erp']['product']} and {land['mes']['product']}, delivered in {p.profile['delivery_framework']}."),
                unsafe_allow_html=True)
    st.markdown(ui.figures([
        (len(current), "open problems across PLM, ERP and MES", bool(current)),
        (len(proposed), "proposals waiting for a decision", False),
        (f"{ai_docs}/{len(twin.sanitized)}", "documents read by the local model", False),
        (f"{lead} days", "earlier than the teams raised it", False),
    ]), unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown(ui.title("Needs attention", len(current)), unsafe_allow_html=True)
        with group("now"):
            if not current:
                st.markdown(ui.row("All clear", "No conflict in today's landscape."), unsafe_allow_html=True)
            for n, a in enumerate(current):
                alert_row(a, n)
        st.write("")
        st.markdown(ui.title("If proposals are applied as written", len(future)), unsafe_allow_html=True)
        with group("future"):
            if not future:
                st.markdown(ui.row("No risk in pending proposals"), unsafe_allow_html=True)
            for n, a in enumerate(future):
                alert_row(a, n)
    with right:
        st.markdown(ui.title("Waiting for a decision", len(proposed)), unsafe_allow_html=True)
        with group("decide"):
            if not proposed:
                st.markdown(ui.row("Nothing waiting", "Every proposal has been approved or rejected."), unsafe_allow_html=True)
            for n, (f, r) in enumerate(proposed):
                if n:
                    st.markdown(ui.SEP, unsafe_allow_html=True)
                c1, c2 = st.columns([3, 1], vertical_alignment="center")
                c1.markdown(ui.row(change_text(f, r), "", f"{f['doc']}, {doc_meta(f['doc'])['date']}. "
                                   f"{plural(len(r['conflicts']), 'conflict')}, {len(r['resolves'])} resolved."), unsafe_allow_html=True)
                if c2.button("Review", key=f"rev-{fact_key(f)}", type="tertiary"):
                    goto("docs", doc=f["doc"])
        st.write("")
        st.markdown(ui.title("Inbox", len(twin.sanitized)), unsafe_allow_html=True)
        with group("inbox"):
            for n, d in enumerate(sorted(twin.sanitized, key=lambda x: doc_meta(x)["date"], reverse=True)):
                m = doc_meta(d)
                acc, _, _ = facts_for(d)
                tags = ui.pill(m["type"]) + (ui.pill(m["lang"].upper()) if m["lang"] else "")
                tags += ui.pill("read by local model", "blue") if twin.ai_ready(d) else ""
                tags += ui.pill("injection blocked", "red") if twin.blocked.get(d) else ""
                if n:
                    st.markdown(ui.SEP, unsafe_allow_html=True)
                c1, c2 = st.columns([3, 1], vertical_alignment="center")
                c1.markdown(ui.row(f"{d}  {m['title']}", "", f"{m['date']}, {plural(len(acc), 'fact')}<br>{tags}"), unsafe_allow_html=True)
                if c2.button("Open", key=f"open-{d}", type="tertiary"):
                    goto("docs", doc=d)
        if outbox:
            st.write("")
            st.info(f"{plural(outbox, 'Jira comment')} drafted and waiting to be sent.", icon=":material/outbox:")


# ------------------------------------------------------------------ documents
def page_documents():
    docs = list(twin.sanitized)
    top = st.columns([3, 1], vertical_alignment="bottom")
    doc = top[0].selectbox("Document", docs, index=docs.index(ss.doc) if ss.doc in docs else 0,
                           format_func=lambda d: f"{d}  {doc_meta(d)['title']}")
    ss.doc = doc
    with top[1].popover("Add a document", icon=":material/add:", width="stretch"):
        title = st.text_input("Title", "Meeting minutes")
        date = st.date_input("Date", dt.date.today())
        raw = st.text_area("Text", height=180, placeholder="Paste minutes, an email or a ticket")
        if st.button("Add and read", type="primary") and raw.strip():
            new_id = f"NEW-{sum(d.startswith('NEW-') for d in twin.sanitized) + 1:02d}"
            twin.ingest(new_id, raw, title, str(date))
            ss.doc = new_id
            st.rerun()

    m = doc_meta(doc)
    row = next(r for r in twin.guard_rows if r["doc"] == doc)
    acc, rej, info = facts_for(doc)
    st.markdown(ui.hero(m["title"], f"{doc}, {m['type']} dated {m['date']}. {row['PERSON']} names and {row['EMAIL'] + row['PHONE']} "
                                    f"contact details were masked before the model read it; read with {MODE_LABEL.get(info['mode_used'], info['mode_used']).lower()}."),
                unsafe_allow_html=True)
    st.write("")
    for s in twin.blocked.get(doc, []):
        st.error(f"An instruction aimed at the AI was found and quarantined before reading: “{s}”", icon=":material/shield:")
    if info["warning"]:
        st.warning(info["warning"].capitalize(), icon=":material/info:")
        if LLM["ok"] and st.button("Read with the local model", icon=":material/memory:"):
            with st.spinner(f"{LLM['model']} is reading {doc}"):
                twin.extract_doc(doc, "ai", allow_calls=True)
            st.rerun()

    t1, t2, t3 = st.tabs(["Facts and decisions", "What the model reads", "Original"])
    with t1:
        if not acc:
            st.caption("No length, unit or version decision in this document.")
        for n, f in enumerate(acc):
            r = assess_fact(p, twin.G, f)
            dec = twin.decision_of(f)
            with group(f"fact-{doc}-{n}"):
                pills = "".join(ui.pill("local model" if s == "ai" else s, "blue" if s == "ai" else "") for s in f["source"].split("+"))
                pills += ui.pill("quote matched to source", "") if f.get("repaired") else ""
                if dec:
                    pills += ui.pill(f"{dec['status']} ({dec['id']})", "green" if dec["status"] == "approved" else "red")
                verdict = "" if r is None else ("Confirms the current model." if r["current"] == r["new"] else "Proposes a change to the model.")
                st.markdown(ui.row(change_text(f, r), verdict) + ui.quote(f["quote"], f"{doc}, {m['date']}") + pills, unsafe_allow_html=True)
                if r is None:
                    st.caption("A platform upgrade. Its impact is on the Impact page, under Platform upgrade.")
                    if st.button("Open upgrade impact", key=f"up-{n}", type="tertiary"):
                        goto("impact")
                    continue
                eff = "".join(ui.pill(f"{i} {k}", "red") for i, k, _ in r["conflicts"]) + \
                    "".join(ui.pill(f"fixes {i} {k}", "green") for i, k, _ in r["resolves"]) + \
                    "".join(ui.pill(f"{t} test data outdated", "orange") for t in r["outdated_tests"])
                if eff:
                    st.markdown(eff, unsafe_allow_html=True)
                with st.expander(f"Impact on {plural(len(r['stories_direct']), 'story', 'stories')}, "
                                 f"{plural(len(r['tests_direct']), 'test')} and {plural(len(r['interfaces']), 'interface')}"):
                    show_map(f["attribute"], r)
                if r["current"] != r["new"] and not dec:
                    c1, c2, c3, c4 = st.columns([2, 3, 1, 1], vertical_alignment="bottom")
                    who = c1.text_input("Approver", "PLM product owner", key=f"who-{doc}-{n}")
                    note = c2.text_input("Reason", "", key=f"note-{doc}-{n}", placeholder="Optional")
                    if c3.button("Approve", key=f"ok-{doc}-{n}", type="primary"):
                        dec_id, drafts = twin.decide(f, "approved", f"apply {f['value']}", who, note)
                        st.toast(f"Approved as {dec_id}. Model updated, {plural(len(drafts), 'Jira comment')} drafted.", icon=":material/check:")
                        st.rerun()
                    if c4.button("Reject", key=f"no-{doc}-{n}"):
                        dec_id, _ = twin.decide(f, "rejected", "keep current", who, note)
                        st.toast(f"Rejected as {dec_id}.", icon=":material/block:")
                        st.rerun()
        if rej:
            with st.expander(f"{plural(len(rej), 'candidate')} stopped by the source check"):
                df = pd.DataFrame(rej)
                st.dataframe(df[[c for c in ("source", "attribute", "value", "quote", "reason") if c in df]], hide_index=True, width="stretch")
    with t2:
        st.caption("Personal data masked, AI-directed instructions removed, extracted sentences highlighted. Nothing else reaches the model.")
        st.markdown(ui.doc_html(twin.sanitized[doc], [f["quote"] for f in acc]), unsafe_allow_html=True)
    with t3:
        st.caption("Stays inside the client's perimeter.")
        st.markdown(ui.doc_html(p.corpus().get(doc) or p.documents[doc]["text"]), unsafe_allow_html=True)


# ------------------------------------------------------------------ impact
def page_impact():
    st.markdown(ui.hero("Impact", "See what a change touches before anyone makes it: interfaces, user stories and test cases."),
                unsafe_allow_html=True)
    st.write("")
    t1, t2, t3 = st.tabs(["What if", "Compare two options", "Platform upgrade"])
    attrs = list(p.attributes)
    with t1:
        c = st.columns([2, 1, 1, 1])
        attr = c[0].selectbox("Attribute", attrs, index=attrs.index(ss.attr), format_func=lambda a: p.attributes[a]["canonical"])
        ss.attr = attr
        defs = p.attributes[attr]["definitions"]
        system = c[1].selectbox("System", list(defs), format_func=lambda s: SYS.get(s, s))
        props = [k for k in ("max_length", "unit") if k in defs[system]]
        if not props:
            st.caption("No length or unit for this attribute in that system. Showing who uses it.")
            show_map(attr)
            return
        prop = c[2].selectbox("Property", props, format_func=lambda x: "Max length" if x == "max_length" else "Unit")
        cur = defs[system][prop]
        val = (c[3].number_input("New value", value=int(cur), step=1) if prop == "max_length"
               else c[3].selectbox("New value", ["kg", "g"], index=["kg", "g"].index(cur) if cur in ("kg", "g") else 0))
        r = assess(p, twin.G, attr, system, prop, val)
        eff = "".join(ui.pill(f"{i}: {d.replace('SYS-', '')}", "red") for i, k, d in r["conflicts"]) + \
            "".join(ui.pill(f"fixes {i}", "green") for i, k, _ in r["resolves"]) + \
            "".join(ui.pill(f"{t} test data outdated", "orange") for t in r["outdated_tests"])
        st.markdown(eff or ui.pill("No conflict", "green"), unsafe_allow_html=True)
        show_map(attr, r, f"If {SYS.get(system)} {p.attributes[attr]['canonical'].lower()} becomes {val}"
                          + (" characters" if prop == "max_length" else ""))
        a, b = st.columns(2, gap="large")
        a.markdown(ui.title("Directly affected"), unsafe_allow_html=True)
        a.dataframe(items_df(r["stories_direct"] + r["tests_direct"]), hide_index=True, width="stretch")
        b.markdown(ui.title("Second ring"), unsafe_allow_html=True)
        b.dataframe(items_df(r["stories_indirect"] + r["tests_indirect"]), hide_index=True, width="stretch")
    with t2:
        st.caption("Two values for the same field, side by side. The engine shows the consequences; people decide.")
        c = st.columns(4)
        attr2 = c[0].selectbox("Attribute ", attrs, index=attrs.index("ATT-DESC"), format_func=lambda a: p.attributes[a]["canonical"])
        defs2 = p.attributes[attr2]["definitions"]
        sys2 = c[1].selectbox("System ", list(defs2), format_func=lambda s: SYS.get(s, s))
        prop2 = "max_length" if "max_length" in defs2[sys2] else "unit"
        cast = int if prop2 == "max_length" else str
        va = cast(c[2].text_input("Option A", "40" if prop2 == "max_length" else "g"))
        vb = cast(c[3].text_input("Option B", str(defs2[sys2].get(prop2, ""))))
        rows = tradeoff(p, twin.G, attr2, sys2, prop2, [(f"Option A: {va}", va, ""), (f"Option B: {vb}", vb, "")])
        st.dataframe(pd.DataFrame(rows).drop(columns="risk").set_index("option").T, width="stretch")
        if attr2 == "ATT-DESC":
            st.info("A third option: keep 80 in PLM and send the full text to an SAP long text, with the 40-character short text "
                    "derived by rule. Neither team loses data.", icon=":material/lightbulb:")
    with t3:
        diff = load_yaml(ROOT / "ontology" / "editors" / "3dexperience_R2026x.yaml")["changes"]
        st.caption("Decided at the steering committee (DOC-05). The R2026x differences are illustrative, not real release notes.")
        st.dataframe(pd.DataFrame(version_upgrade(p, twin.G, diff)), hide_index=True, width="stretch")


# ------------------------------------------------------------------ decisions
def page_decisions():
    dec = twin.audit.df("decisions")
    outbox = twin.audit.df("outbox")
    drafted = outbox[outbox.status == "drafted"] if len(outbox) else outbox
    st.markdown(ui.hero("Decisions", f"Every decision is traced to its source sentence and to the person who made it. Jira target: {twin.jira.name}."),
                unsafe_allow_html=True)
    st.markdown(ui.figures([(len(dec), "decisions logged", False),
                            ((dec.status == "approved").sum() if len(dec) else 0, "approved and applied to the model", False),
                            (len(drafted), "Jira comments waiting to be sent", False),
                            (len(twin.audit.df()), "events in the audit trail", False)]), unsafe_allow_html=True)
    st.markdown(ui.title("Decision log"), unsafe_allow_html=True)
    if len(dec):
        st.dataframe(dec.drop(columns=["fact_key"]), hide_index=True, width="stretch")
    else:
        st.caption("No decision yet. Approve or reject a proposal from a document.")
    st.markdown(ui.title("Jira outbox"), unsafe_allow_html=True)
    if len(outbox):
        st.dataframe(outbox, hide_index=True, width="stretch")
        if len(drafted) and st.button(f"Send {plural(len(drafted), 'comment')} to {twin.jira.name}", type="primary", icon=":material/send:"):
            sent, errors = send_outbox(twin.audit, twin.jira)
            st.toast(f"Sent {plural(sent, 'comment')}.", icon=":material/check:")
            for e in errors:
                st.error(e)
            st.rerun()
    else:
        st.caption("Empty. Approved decisions draft their Jira comments here.")
    if hasattr(twin.jira, "comments") and twin.jira.comments():
        with st.expander("Comments now on Jira issues"):
            for key, cs in twin.jira.comments().items():
                st.markdown(f"**{key}**")
                for c in cs:
                    st.caption(c)
    with st.expander("Audit trail"):
        st.dataframe(twin.audit.df(), hide_index=True, width="stretch")


# ------------------------------------------------------------------ glossary
def page_glossary():
    st.markdown(ui.hero("Glossary", "One concept, every name it goes by: ours, the editor's, the client's, in English and French."),
                unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns([2, 3], gap="large")
    with c1:
        term = st.text_input("Look up a term", "Plant BOM")
        r = twin.glossary.lookup(term)
        cls = {"known": "green", "proposed, needs validation": "orange"}.get(r["status"], "red")
        with group("lookup"):
            st.markdown(ui.row(r["canonical"] or "Unknown term", f"Matched as {ui.escape(str(r['matched_as']))}" if r["matched_as"] else
                               "Not in the glossary yet.", "", "") + ui.pill(r["status"], cls), unsafe_allow_html=True)
        st.write("")
        with st.form("propose"):
            st.markdown("**Propose a term**")
            new = st.text_input("Term", "")
            target = st.selectbox("Means", list(p.concepts), format_func=lambda c: p.concepts[c]["canonical"])
            if st.form_submit_button("Propose") and new:
                ss.proposed_terms.append({"term": new, "concept": target, "status": "waiting for validation"})
                twin.audit.log("glossary_proposal", None, {"term": new, "concept": target})
        if ss.proposed_terms:
            st.dataframe(pd.DataFrame(ss.proposed_terms), hide_index=True)
    with c2:
        rows = [{"Concept": c["canonical"], **{k.capitalize(): ", ".join(v) for k, v in c["terms"].items()}} for c in p.concepts.values()]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=560)


# ------------------------------------------------------------------ new client
def page_new_client():
    st.markdown(ui.hero("New client", "A client profile, our capability catalogue and the editor's vocabulary give a starter backlog in seconds."),
                unsafe_allow_html=True)
    st.write("")
    clients = sorted(d.name for d in (ROOT / "data").iterdir() if (d / "client_profile.yaml").exists())
    cid = st.selectbox("Client profile", clients, index=clients.index("medtech") if "medtech" in clients else 0)
    prof = load_yaml(ROOT / "data" / cid / "client_profile.yaml")["client"]
    land = prof["landscape"]
    st.markdown("".join(ui.pill(x) for x in [prof["name"], prof["industry"], land["plm"]["product"], prof["delivery_framework"],
                                              f"MES: {land['mes']['product']}"]), unsafe_allow_html=True)
    starter = bootstrap(ROOT, prof)
    st.markdown(ui.figures([(starter.epic.nunique(), "epics", False), (starter.capability.nunique(), "capabilities", False),
                            (len(starter), "features with a first user story", False), (land["plm"]["product"], "vocabulary applied", False)]),
                unsafe_allow_html=True)
    st.dataframe(starter, hide_index=True, width="stretch", height=480)
    st.download_button("Download for Jira import", starter.to_csv(index=False), f"{cid}_starter_backlog.csv", icon=":material/download:")


# ------------------------------------------------------------------ quality
def page_quality():
    st.markdown(ui.hero("AI quality", "Measured against a ground truth, including a holdout document the rules were never tuned on."),
                unsafe_allow_html=True)
    st.write("")
    with group("model"):
        st.markdown(ui.row(f"{LLM['model'] or 'No model'} on {LLM['backend']}", ui.escape(LLM["detail"].capitalize()),
                           "Runs on this machine. Change it in the sidebar, or with LLM_MODEL and OLLAMA_URL before launching.",
                           ui.dot("ok" if LLM["ok"] else "warn")), unsafe_allow_html=True)
    todo = [d for d in twin.sanitized if not twin.ai_ready(d)]
    if LLM["ok"] and todo and st.button(f"Read {plural(len(todo), 'document')} with the local model", type="primary", icon=":material/memory:"):
        bar = st.progress(0.0)
        for k, d in enumerate(todo, 1):
            twin.extract_doc(d, "ai", allow_calls=True)
            bar.progress(k / len(todo), text=d)
        st.rerun()
    gold = gold_table(p.truth)
    rows = []
    for mode in ("rules", "ai", "hybrid"):
        acc, _, infos = twin.extract(mode=mode, allow_calls=False)
        if mode != "rules" and any(i["mode_used"] == "rules" for i in infos.values()):
            continue
        rows += score(acc, gold, MODE_LABEL[mode])
    st.markdown(ui.title("Extraction quality"), unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if len(rows) == 2:
        st.caption("Local model and hybrid rows appear once every document has been read by the model.")
    acc, _, _ = twin.extract(mode=ss.mode, allow_calls=False)
    st.markdown(ui.title(f"Still missed in {MODE_LABEL[ss.mode].lower()} mode"), unsafe_allow_html=True)
    st.dataframe(misses(acc, gold)[["id", "doc", "holdout", "key"]], hide_index=True, width="stretch")


PAGES = {
    "cockpit": st.Page(page_cockpit, title="Cockpit", icon=":material/space_dashboard:", default=True),
    "docs": st.Page(page_documents, title="Documents", icon=":material/description:"),
    "impact": st.Page(page_impact, title="Impact", icon=":material/account_tree:"),
    "decisions": st.Page(page_decisions, title="Decisions", icon=":material/gavel:"),
    "glossary": st.Page(page_glossary, title="Glossary", icon=":material/translate:"),
    "client": st.Page(page_new_client, title="New client", icon=":material/add_business:"),
    "quality": st.Page(page_quality, title="AI quality", icon=":material/insights:"),
}
st.navigation(list(PAGES.values())).run()
