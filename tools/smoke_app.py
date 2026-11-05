"""Run every page of the cockpit against a fake Streamlit (no browser, no streamlit install needed).
Renders each page with no click, then replays key clicks (approve, reject, send, navigation).
Catches code errors, not visual problems. Usage: python tools/smoke_app.py"""
import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class State(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


class Stop(Exception):
    pass


CACHE = {}


def cache_resource(fn):
    def wrapper(*a):
        if fn.__name__ not in CACHE:
            CACHE[fn.__name__] = fn(*a)
        return CACHE[fn.__name__]
    return wrapper


cache_resource.clear = CACHE.clear


class FakePage:
    def __init__(self, fn, title="", icon=None, default=False):
        self.fn, self.title = fn, title


def fake_streamlit(page_title, press=(), state=None):
    st = MagicMock(name="st")
    st.session_state = state if state is not None else State()
    st.cache_resource = cache_resource
    st.stop.side_effect = Stop
    st.rerun.side_effect = Stop
    st.switch_page.side_effect = lambda page: (_ for _ in ()).throw(Stop())
    st.Page.side_effect = FakePage

    class Nav:
        def __init__(self, pages):
            self.pages = pages

        def run(self):
            next(pg for pg in self.pages if pg.title == page_title).fn()

    st.navigation.side_effect = Nav

    def selectbox(label, options, index=0, format_func=str, **kw):
        options = list(options)
        for o in options:
            format_func(o)
        return options[index]

    def pressed(label, **kw):
        return any(str(label).startswith(x) for x in press)

    st.selectbox.side_effect = selectbox
    st.segmented_control.side_effect = lambda label, options, format_func=str, default=None, **kw: default
    st.text_input.side_effect = lambda label, value="", **kw: value
    st.text_area.side_effect = lambda label, value="", **kw: value
    st.chat_input.side_effect = lambda *a, **kw: None
    st.number_input.side_effect = lambda label, value=0, **kw: value
    st.date_input.side_effect = lambda label, value=None, **kw: value
    st.button.side_effect = pressed
    st.form_submit_button.side_effect = pressed
    st.download_button.side_effect = lambda *a, **kw: False
    st.columns.side_effect = lambda spec, **kw: [st for _ in range(spec if isinstance(spec, int) else len(spec))]
    st.tabs.side_effect = lambda labels: [st for _ in labels]
    st.popover.return_value = st
    st.container.return_value = st
    st.expander.return_value = st
    st.form.return_value = st
    st.__enter__ = lambda self: self
    st.__exit__ = lambda self, *a: False
    st.sidebar.button.side_effect = lambda label, **kw: False
    comps = MagicMock(name="components")
    sys.modules["streamlit"] = st
    sys.modules["streamlit.components"] = MagicMock(v1=comps)
    sys.modules["streamlit.components.v1"] = comps
    return st


def run(page, press=(), state=None):
    st = fake_streamlit(page, press, state)
    try:
        runpy.run_path(str(ROOT / "app" / "streamlit_app.py"), run_name="__main__")
    except Stop:
        pass
    return st


if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    pages = ["Cockpit", "Documents", "Impact", "Decisions", "Ask Vertex", "Library", "Glossary", "New client", "AI quality"]
    for page in pages:
        run(page)
        print("ok   render", page)
    # every document renders
    from vertex_hub import load_project
    docs = list(load_project(ROOT).corpus())
    for d in docs:
        run("Documents", state=State(doc=d))
    print(f"ok   render Documents x {len(docs)}")
    run("Documents", press=("Approve",), state=State(doc="DOC-03"))
    twin = CACHE["get_twin"]
    n_dec = len(twin.audit.df("decisions"))
    n_out = twin.audit.db.execute("SELECT COUNT(*) FROM outbox WHERE status='drafted'").fetchone()[0]
    assert n_dec == 1 and n_out == 9, (n_dec, n_out)
    run("Documents", press=("Reject",), state=State(doc="DOC-04"))
    assert (twin.audit.df("decisions").status == "rejected").sum() == 1
    run("Decisions", press=("Send",))
    sent = twin.audit.db.execute("SELECT COUNT(*) FROM outbox WHERE status='sent'").fetchone()[0]
    assert sent == 9, sent
    run("Cockpit")
    for page in pages:
        run(page)                      # every page still renders after decisions
    run("Glossary", press=("Propose",))
    st_state = State()
    run("Ask Vertex", press=("What is a Plant BOM?",), state=st_state)
    assert st_state["chat"] and "C-PBOM" in st_state["chat"][0]["cited"], st_state.get("chat")
    run("Ask Vertex", state=st_state)
    nc = State()
    run("New client", press=("Build the starter backlog",), state=nc)
    assert nc["described"]["landscape"]["plm"]["product"] == "Teamcenter"
    run("Cockpit", press=("Show impact",))
    run("AI quality", press=("Read",))
    print("ok   clicks: approve -> 9 drafts, reject, send -> 9 sent, propose, navigate, analyse; all pages re-render")
    print("APP SMOKE TEST PASSED")
