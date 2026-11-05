"""Connectors: one interface per tool type, so the framework adapts to the client's tools.

Jira: JiraMock by default (comments stored in cache/jira_mock.json).
Real Jira Cloud when JIRA_URL, JIRA_EMAIL and JIRA_API_TOKEN are set (REST API v3; tested only against the mock).
"""
import base64
import json
import os
import urllib.request
from pathlib import Path


class JiraMock:
    name = "Jira (mock)"

    def __init__(self, project, path=None):
        self.p = project
        self.path = Path(path or project.root / "cache" / "jira_mock.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {"comments": {}}

    def _save(self):
        self.path.write_text(json.dumps(self.state, indent=1, ensure_ascii=False))

    def issues(self):
        items = [*self.p.epics.values(), *self.p.capabilities.values(), *self.p.features.values(),
                 *self.p.stories.values(), *self.p.tests.values()]
        return [{"key": i["jira_key"], "id": i["id"], "summary": i.get("title") or i.get("text", "")[:90],
                 "status": i.get("status", ""), "comments": len(self.state["comments"].get(i["jira_key"], []))} for i in items]

    def new_items(self):
        """Items created in Jira since the last sync (here: data/<client>/incoming)."""
        return list(self.p.incoming.values())

    def add_comment(self, key, body):
        if key not in {i["key"] for i in self.issues()}:
            raise KeyError(f"unknown issue {key}")
        self.state["comments"].setdefault(key, []).append(body)
        self._save()
        return {"key": key, "ok": True}

    def comments(self, key=None):
        c = self.state["comments"]
        return c.get(key, []) if key else c

    def reset(self):
        self.state = {"comments": {}}
        self._save()


class JiraCloud:
    name = "Jira Cloud"

    def __init__(self, url, email, token):
        self.url = url.rstrip("/")
        self.auth = "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()

    def _req(self, method, path, body=None):
        req = urllib.request.Request(self.url + path, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": self.auth, "Content-Type": "application/json", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")

    def add_comment(self, key, body):
        adf = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]}
        return self._req("POST", f"/rest/api/3/issue/{key}/comment", {"body": adf})

    def issue(self, key):
        return self._req("GET", f"/rest/api/3/issue/{key}?fields=summary,status")


def get_jira(project):
    url, email, token = os.getenv("JIRA_URL"), os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN")
    return JiraCloud(url, email, token) if url and email and token else JiraMock(project)
