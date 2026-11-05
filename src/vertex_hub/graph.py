"""Knowledge graph built from the project, following ontology/core.yaml."""
import networkx as nx


def build_graph(p):
    G = nx.DiGraph()

    def add(n, kind, label):
        G.add_node(n, kind=kind, label=label)

    for s in p.systems.values():
        add(s["id"], "System", s["name"])
    for a in p.attributes.values():
        add(a["id"], "Attribute", a["canonical"])
    for i in p.interfaces.values():
        add(i["id"], "Interface", i["name"])
        G.add_edge(i["id"], i["from"], rel="FROM_SYSTEM")
        G.add_edge(i["id"], i["to"], rel="TO_SYSTEM")
        for a in i["carries"]:
            G.add_edge(i["id"], a, rel="CARRIES")
    for a in p.attributes.values():
        for s, d in a["definitions"].items():
            G.add_edge(a["id"], s, rel="DEFINED_IN", **d)
    for c in p.concepts.values():
        add(c["id"], "Concept", c["canonical"])
        if "maps_to_attribute" in c:
            G.add_edge(c["id"], c["maps_to_attribute"], rel="NAMES")
    for e in p.epics.values():
        add(e["id"], "Epic", e["title"])
    for c in p.capabilities.values():
        add(c["id"], "Capability", c["title"])
        G.add_edge(c["epic"], c["id"], rel="HAS_CAPABILITY")
    for f in p.features.values():
        add(f["id"], "Feature", f["title"])
        G.add_edge(f["capability"], f["id"], rel="HAS_FEATURE")
    for s in p.stories.values():
        add(s["id"], "UserStory", s["text"][:60])
        G.add_edge(s["feature"], s["id"], rel="HAS_STORY")
        for a in s["uses"]:
            G.add_edge(s["id"], a, rel="USES")
        for i in s["implements"]:
            G.add_edge(s["id"], i, rel="IMPLEMENTS")
    for t in p.tests.values():
        add(t["id"], "TestCase", t["title"])
        G.add_edge(t["id"], t["verifies"], rel="VERIFIES")
        for a in t["checks"]:
            G.add_edge(t["id"], a, rel="CHECKS")
        for i in t["exercises"]:
            G.add_edge(t["id"], i, rel="EXERCISES")
    return G


def preds(G, node, rel):
    return sorted(u for u, _, d in G.in_edges(node, data=True) if d["rel"] == rel)


def impact(G, attr_id):
    """Direct ring: what touches the attribute. Indirect ring: what touches its interfaces / stories."""
    ints = preds(G, attr_id, "CARRIES")
    us_direct = set(preds(G, attr_id, "USES"))
    us_via = {u for i in ints for u in preds(G, i, "IMPLEMENTS")} - us_direct
    tc_direct = set(preds(G, attr_id, "CHECKS"))
    tc_via = {t for u in us_direct for t in preds(G, u, "VERIFIES")} - tc_direct
    return {"interfaces": ints, "stories_direct": sorted(us_direct), "tests_direct": sorted(tc_direct),
            "stories_indirect": sorted(us_via), "tests_indirect": sorted(tc_via)}


def impact_subgraph(G, attr_id):
    r = impact(G, attr_id)
    nodes = [attr_id, *r["interfaces"], *r["stories_direct"], *r["tests_direct"]]
    nodes += sorted({s for i in r["interfaces"] for s in G.successors(i) if G.nodes[s]["kind"] == "System"})
    return G.subgraph(nodes), r
