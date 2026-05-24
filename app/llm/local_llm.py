from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from app.normalizers import normalize_for_schema

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMProvider(Protocol):
    def generate_text(self, *, system: str, user: str) -> str: ...
    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        max_retries: int = 1,
        allow_fallback: bool = True,
    ) -> T: ...

    def embed_text(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


def redact_large_text(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[TRUNCATED]...\n"


def normalize_keyword_list(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for it in items:
        cleaned = re.sub(r"\s+", " ", it.strip())
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


@dataclass
class _JsonHelper:
    def _strip_code_fences(self, text: str) -> str:
        t = text.strip()
        t = re.sub(r"^\s*```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)
        return t.strip()

    def _extract_json_object(self, text: str) -> str:
        """
        Extract the first top-level JSON object/array from a possibly messy model output.
        Conservative: find the first '{' or '[' and bracket-match until balanced.
        """
        text = self._strip_code_fences(text)
        start = None
        for i, ch in enumerate(text):
            if ch in "{[":
                start = i
                break
        if start is None:
            raise LLMError("Model did not return JSON.")
        opening = text[start]
        closing = "}" if opening == "{" else "]"
        depth = 0
        for j in range(start, len(text)):
            if text[j] == opening:
                depth += 1
            elif text[j] == closing:
                depth -= 1
                if depth == 0:
                    return text[start : j + 1]
        raise LLMError("Unbalanced JSON in model output.")

    def _repair_json_text(self, raw_json: str) -> str:
        s = raw_json.strip()
        s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
        s = re.sub(r",(\s*[}\]])", r"\1", s)  # remove trailing commas
        return s

    def _loads_lenient(self, raw_json: str) -> Any:
        s = self._repair_json_text(raw_json)
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(s)
            except Exception as e:
                raise LLMError(f"Invalid JSON from model (repair failed): {e}") from e


@dataclass
class BaseProvider(_JsonHelper):
    timeout_s: int = 120

    def generate_text(self, *, system: str, user: str) -> str:  # pragma: no cover
        raise NotImplementedError

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        max_retries: int = 1,
        allow_fallback: bool = True,
    ) -> T:
        strict_suffix = (
            "\n\nCRITICAL:\n"
            "- Return VALID JSON only.\n"
            "- No markdown/code fences.\n"
            "- Match the exact field types specified.\n"
        )

        last_error: str | None = None
        for attempt in range(max_retries + 1):
            raw = self.generate_text(system=system, user=user + (strict_suffix if attempt > 0 else ""))
            raw = (raw or "").strip()
            try:
                raw_json = self._extract_json_object(raw)
                data = self._loads_lenient(raw_json)
            except LLMError as e:
                last_error = str(e)
                continue

            normalized = normalize_for_schema(schema.__name__, data)
            try:
                return schema.model_validate(normalized)
            except ValidationError as e:
                last_error = f"{e}"
                continue

        if not allow_fallback:
            raise LLMError(f"JSON did not match schema {schema.__name__}: {last_error}")

        normalized = normalize_for_schema(schema.__name__, {})
        try:
            return schema.model_validate(normalized)
        except ValidationError as e:
            raise LLMError(f"Schema fallback failed for {schema.__name__}: {e}") from e

    def embed_text(self, text: str) -> list[float]:  # pragma: no cover
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


@dataclass
class OllamaProvider(BaseProvider):
    base_url: str = "http://localhost:11434"
    chat_model: str = "llama3.2:3b"
    embed_model: str = "nomic-embed-text"

    def generate_text(self, *, system: str, user: str) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.chat_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout_s)
        except requests.RequestException as e:
            raise LLMError(f"Ollama request failed: {e}") from e
        if resp.status_code != 200:
            err_text = (resp.text or "")[:800]
            if resp.status_code == 404:
                try:
                    payload = resp.json()
                except Exception:
                    payload = {}
                msg = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(msg, str) and "not found" in msg and "model" in msg:
                    raise LLMError(
                        "Ollama model not found.\n"
                        f"- Requested: {self.chat_model}\n"
                        f"- Fix: run `ollama pull {self.chat_model}` or choose another installed model.\n"
                        f"- Ollama said: {msg}"
                    )
            raise LLMError(f"Ollama error {resp.status_code}: {err_text}")
        data = resp.json()
        return (data.get("message") or {}).get("content", "") or ""

    def embed_text(self, text: str) -> list[float]:
        """
        Best-effort embeddings via Ollama.
        Tries newer `/api/embed` first, then `/api/embeddings`.
        """
        payload = {"model": self.embed_model, "input": text}
        for endpoint in ("/api/embed", "/api/embeddings"):
            url = f"{self.base_url}{endpoint}"
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout_s)
            except requests.RequestException as e:
                raise LLMError(f"Ollama embed request failed: {e}") from e
            if resp.status_code == 404:
                continue
            if resp.status_code != 200:
                raise LLMError(f"Ollama embed error {resp.status_code}: {(resp.text or '')[:300]}")
            data = resp.json()
            if isinstance(data, dict):
                if "embedding" in data and isinstance(data["embedding"], list):
                    return [float(x) for x in data["embedding"]]
                if "embeddings" in data and isinstance(data["embeddings"], list) and data["embeddings"]:
                    first = data["embeddings"][0]
                    if isinstance(first, list):
                        return [float(x) for x in first]
            raise LLMError("Unexpected embedding response shape from Ollama.")
        raise LLMError("Ollama embeddings endpoint not available.")


@dataclass
class OpenAICompatibleProvider(BaseProvider):
    base_url: str = "https://api.openai.com/v1"
    api_key: str | None = None
    chat_model: str | None = None
    embed_model: str | None = None

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMError("Missing API key for OpenAI-compatible provider.")
        return {"Authorization": f"Bearer {self.api_key}"}

    def _url(self, path: str) -> str:
        return self.base_url.rstrip("/") + "/" + path.lstrip("/")

    def generate_text(self, *, system: str, user: str) -> str:
        if not self.chat_model:
            raise LLMError("Missing chat model for OpenAI-compatible provider.")
        url = self._url("/chat/completions")
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout_s)
        except requests.RequestException as e:
            raise LLMError(f"OpenAI-compatible request failed: {e}") from e
        if resp.status_code != 200:
            raise LLMError(f"OpenAI-compatible error {resp.status_code}: {(resp.text or '')[:800]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except Exception as e:
            raise LLMError(f"Unexpected OpenAI-compatible response shape: {e}") from e

    def embed_text(self, text: str) -> list[float]:
        if not self.embed_model:
            raise LLMError("Missing embedding model for OpenAI-compatible provider.")
        url = self._url("/embeddings")
        payload = {"model": self.embed_model, "input": text}
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout_s)
        except requests.RequestException as e:
            raise LLMError(f"OpenAI-compatible embeddings request failed: {e}") from e
        if resp.status_code != 200:
            raise LLMError(f"OpenAI-compatible embeddings error {resp.status_code}: {(resp.text or '')[:800]}")
        data = resp.json()
        try:
            emb = data["data"][0]["embedding"]
            return [float(x) for x in emb]
        except Exception as e:
            raise LLMError(f"Unexpected embeddings response shape: {e}") from e

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.embed_model:
            raise LLMError("Missing embedding model for OpenAI-compatible provider.")
        url = self._url("/embeddings")
        payload = {"model": self.embed_model, "input": texts}
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout_s)
        except requests.RequestException as e:
            raise LLMError(f"OpenAI-compatible embeddings request failed: {e}") from e
        if resp.status_code != 200:
            raise LLMError(f"OpenAI-compatible embeddings error {resp.status_code}: {(resp.text or '')[:800]}")
        data = resp.json()
        try:
            rows = data["data"]
            out: list[list[float]] = []
            for r in rows:
                out.append([float(x) for x in r["embedding"]])
            if len(out) != len(texts):
                raise LLMError("Embeddings response length mismatch.")
            return out
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Unexpected embeddings response shape: {e}") from e

