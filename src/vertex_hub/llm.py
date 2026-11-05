"""LLM backends with a disk cache. Default: Ollama (local, nothing leaves the machine).

Env vars:
  LLM_BACKEND   ollama (default) | openai (any OpenAI-compatible endpoint, via OPENAI_BASE_URL) | none
  LLM_MODEL     model name (default qwen2.5:7b for Ollama)
  OLLAMA_URL    default http://localhost:11434
"""
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MODELS = {"ollama": "qwen2.5:7b", "openai": "gpt-4o-mini"}
# If LLM_MODEL is not set, the first of these that is installed in Ollama is used, else any installed model.
OLLAMA_PREFERENCE = ["qwen2.5:7b", "qwen2.5:14b", "qwen2.5-coder:7b", "qwen3:8b", "llama3.1:8b", "mistral:latest", "mistral-nemo:latest"]
PROMPT_VERSION = "v2"
_TAGS = {"t": 0.0, "models": None}


def ollama_url():
    return os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def _tags(max_age=20):
    """Raw /api/tags entries (cached a few seconds; None if Ollama is not reachable)."""
    import time
    if time.time() - _TAGS["t"] > max_age:
        try:
            with urllib.request.urlopen(ollama_url() + "/api/tags", timeout=2) as r:
                _TAGS["models"] = json.loads(r.read()).get("models", [])
        except (urllib.error.URLError, OSError, ValueError):
            _TAGS["models"] = None
        _TAGS["t"] = time.time()
    return _TAGS["models"]


def installed_models(max_age=20):
    """Names of every model Ollama knows about, local or cloud-proxied (None if unreachable)."""
    tags = _tags(max_age)
    return None if tags is None else [m["name"] for m in tags]


def local_chat_models(max_age=20):
    """Names of models that both generate text and run entirely on this machine.

    Excludes embedding-only models (no "completion" capability) and Ollama Cloud models
    (they carry a remote_host and proxy the prompt to Ollama's servers over the network).
    """
    tags = _tags(max_age)
    if tags is None:
        return None
    def is_local_chat(m):
        if m.get("remote_host") or str(m.get("name", "")).endswith("-cloud") or ":cloud" in str(m.get("name", "")):
            return False
        caps = m.get("capabilities")
        if caps is None:  # older Ollama versions don't report capabilities: fall back to the name
            return "embed" not in m.get("name", "").lower()
        return "completion" in caps
    return [m["name"] for m in tags if is_local_chat(m)]


def config():
    backend = os.getenv("LLM_BACKEND", "ollama").lower()
    model = os.getenv("LLM_MODEL")
    if not model and backend == "ollama":
        models = local_chat_models() or []
        model = next((m for m in OLLAMA_PREFERENCE if m in models), models[0] if models else None)
    return backend, model or DEFAULT_MODELS.get(backend, "")


def status():
    """Is the configured backend usable right now? Returns dict(ok, backend, model, detail)."""
    backend, model = config()
    if backend == "none":
        return {"ok": False, "backend": backend, "model": "", "detail": "AI disabled (LLM_BACKEND=none)"}
    if backend == "ollama":
        models = local_chat_models()
        if models is None:
            return {"ok": False, "backend": backend, "model": model,
                    "detail": f"Ollama not reachable at {ollama_url()}. Start the Ollama app, then `ollama pull {model}`."}
        base = model if ":" in model else model + ":latest"
        if models and model not in models and base not in models and not os.getenv("LLM_MODEL"):
            os.environ["LLM_MODEL"] = model = next((m for m in models if m.startswith("qwen")), models[0])
            base = model
        if model not in models and base not in models:
            return {"ok": False, "backend": backend, "model": model, "models": models,
                    "detail": f"Model {model} not installed locally (embedding-only and Ollama Cloud models don't count). Run `ollama pull {model}`."}
        return {"ok": True, "backend": backend, "model": model, "models": models, "detail": "local model ready"}
    key = {"openai": "OPENAI_API_KEY"}.get(backend)
    ok = bool(key and os.getenv(key))
    return {"ok": ok, "backend": backend, "model": model, "detail": "API key found" if ok else f"{key} not set"}


def call(prompt, backend=None, model=None, json_mode=True, timeout=300):
    backend, model = (backend, model) if backend else config()
    if backend == "ollama":
        body = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0, "num_ctx": 8192}}
        if json_mode:
            body["format"] = "json"
        req = urllib.request.Request(ollama_url() + "/api/generate", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["response"]
    if backend == "openai":
        from openai import OpenAI
        kw = {"response_format": {"type": "json_object"}} if json_mode else {}
        r = OpenAI().chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0, **kw)
        return r.choices[0].message.content
    raise RuntimeError("no LLM backend configured")


def parse_json(reply):
    """Accept {"facts": [...]}, a bare list, or JSON wrapped in prose / code fences."""
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S)
    for pattern in (r"\{.*\}", r"\[.*\]"):
        m = re.search(pattern, reply, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except ValueError:
                continue
            if isinstance(data, dict):
                for k in ("facts", "items", "results", "extractions"):
                    if isinstance(data.get(k), list):
                        return data[k]
                return [data] if "quote" in data else []
            if isinstance(data, list):
                return data
    return []


class Cache:
    """One JSON file per (model, prompt version, document text). The live demo never waits on the model twice."""

    def __init__(self, root):
        self.dir = Path(root) / "cache" / "llm"

    def _path(self, model, doc_id, text):
        h = hashlib.sha1(f"{PROMPT_VERSION}|{model}|{text}".encode()).hexdigest()[:12]
        return self.dir / re.sub(r"[^\w.-]", "_", model) / f"{doc_id}_{h}.json"

    def get(self, model, doc_id, text):
        p = self._path(model, doc_id, text)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, model, doc_id, text, items):
        p = self._path(model, doc_id, text)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    def has(self, model, doc_id, text):
        return self._path(model, doc_id, text).exists()
