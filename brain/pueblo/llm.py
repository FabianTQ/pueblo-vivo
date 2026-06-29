"""Thin, robust client for a local Ollama server (chat + embeddings).

Design goals:
- Synchronous and simple: the cognitive core calls these directly; the server
  schedules calls on a worker so the simple sync API keeps the core testable.
- Tolerant JSON: small local models often wrap JSON in prose or code fences, so
  `generate_json` extracts the first balanced JSON value and retries on failure.
- Cheap to fake in tests: everything goes through `_post`, and higher layers accept
  an injected client, so tests can subclass or pass a stub.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import numpy as np

from .config import DEFAULT, LLMConfig


class LLMError(RuntimeError):
    """Raised when the LLM cannot satisfy a request after retries."""


def extract_json(text: str) -> Any:
    """Best-effort extraction of the first JSON object/array from model output.

    Handles code fences and leading/trailing prose. Raises ValueError if nothing
    parseable is found.
    """
    s = text.strip()
    # Fast path: already valid JSON.
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences if present.
    if "```" in s:
        parts = s.split("```")
        # The content after the first fence, dropping an optional language tag.
        for chunk in parts:
            chunk = chunk.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk[:1] in "{[":
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError:
                    continue

    # Scan for the first balanced {...} or [...] block.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = s.find(opener)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    candidate = s[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"No parseable JSON found in model output: {text[:200]!r}")


class OllamaClient:
    def __init__(self, cfg: LLMConfig | None = None, client: httpx.Client | None = None):
        self.cfg = cfg or DEFAULT.llm
        self._client = client or httpx.Client(timeout=self.cfg.request_timeout)

    # -- low level ---------------------------------------------------------
    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.cfg.host}{path}"
        last_err: Exception | None = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                resp = self._client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:  # noqa: BLE001 - want to retry on any transport error
                last_err = e
                if attempt < self.cfg.max_retries:
                    time.sleep(0.5 * (attempt + 1))
        raise LLMError(f"POST {path} failed after retries: {last_err}") from last_err

    # -- health ------------------------------------------------------------
    def is_up(self) -> bool:
        try:
            self._client.get(f"{self.cfg.host}/api/tags")
            return True
        except Exception:  # noqa: BLE001
            return False

    def available_models(self) -> list[str]:
        data = self._client.get(f"{self.cfg.host}/api/tags").json()
        return [m["name"] for m in data.get("models", [])]

    # -- chat --------------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        fmt: str | dict | None = None,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        msgs = list(messages)
        if system:
            msgs = [{"role": "system", "content": system}, *msgs]
        payload: dict[str, Any] = {
            "model": model or self.cfg.chat_model,
            "messages": msgs,
            "stream": False,
            "options": {
                "temperature": self.cfg.temperature if temperature is None else temperature
            },
        }
        if fmt is not None:
            payload["format"] = fmt
        data = self._post("/api/chat", payload)
        return data.get("message", {}).get("content", "")

    def complete(self, prompt: str, *, system: str | None = None, **kw) -> str:
        return self.chat([{"role": "user", "content": prompt}], system=system, **kw)

    def generate_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        model: str | None = None,
    ) -> Any:
        """Ask for JSON (format=json) and robustly parse it, retrying once on garbage."""
        for attempt in range(2):
            raw = self.chat(
                [{"role": "user", "content": prompt}],
                system=system,
                fmt="json",
                temperature=temperature,
                model=model,
            )
            try:
                return extract_json(raw)
            except ValueError:
                if attempt == 0:
                    prompt = prompt + "\n\nRespond with ONLY valid JSON, nothing else."
                    continue
                raise LLMError(f"Model did not return valid JSON: {raw[:200]!r}")

    # -- embeddings --------------------------------------------------------
    def embed(self, text: str, *, model: str | None = None) -> np.ndarray:
        data = self._post(
            "/api/embeddings",
            {"model": model or self.cfg.embed_model, "prompt": text},
        )
        vec = np.asarray(data.get("embedding", []), dtype=np.float32)
        if vec.size == 0:
            raise LLMError("Empty embedding returned (is the embed model pulled?)")
        return vec
