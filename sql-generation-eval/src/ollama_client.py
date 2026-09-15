"""Minimal local-only HTTP client; uses the Python standard library."""

from __future__ import annotations

import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 300):
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("This benchmark accepts only a local Ollama HTTP endpoint")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base_url + path, data=data, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def generate(self, model: str, prompt: str, options: dict) -> dict:
        return self.request("/api/generate", {"model": model, "prompt": prompt,
                                             "system": "You are a SQL generation assistant.",
                                             "options": options, "stream": False, "keep_alive": -1})

    def unload(self, model: str) -> None:
        self.request("/api/generate", {"model": model, "keep_alive": 0, "stream": False})
