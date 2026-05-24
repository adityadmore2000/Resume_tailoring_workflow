from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from app.normalizers import normalize_for_schema


T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


@dataclass
class OllamaClient:
    base_url: str
    model: str
    timeout_s: int = 120

    def chat(self, system: str, user: str) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
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
            # Improve the common "model not found" case with actionable guidance.
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
                        f"- Requested: {self.model}\n"
                        f"- Fix: run `ollama pull {self.model}` or choose another installed model "
                        "(CLI `--model`, UI sidebar).\n"
                        f"- Ollama said: {msg}"
                    )
            raise LLMError(f"Ollama error {resp.status_code}: {err_text}")
        data = resp.json()
        return (data.get("message") or {}).get("content", "") or ""

    def _strip_code_fences(self, text: str) -> str:
        # Remove leading/trailing markdown fences if present.
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
        # Common repairs: smart quotes, trailing commas.
        s = raw_json.strip()
        s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
        s = re.sub(r",(\s*[}\]])", r"\1", s)  # remove trailing commas
        return s

    def _loads_lenient(self, raw_json: str) -> Any:
        s = self._repair_json_text(raw_json)
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # Fallback for Python-ish dicts using single quotes (safe literal evaluation).
            try:
                return ast.literal_eval(s)
            except Exception as e:
                raise LLMError(f"Invalid JSON from model (repair failed): {e}") from e

    def generate_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        max_retries: int = 1,
        allow_fallback: bool = True,
    ) -> T:
        """
        Robust JSON generation:
        - Extract JSON from messy outputs (markdown fences, extra text)
        - Repair common JSON issues (trailing commas, smart quotes, single quotes via literal_eval)
        - Normalize output shape before validation (schema-specific)
        - Retry once with stricter instruction if needed
        - Optionally fall back to an empty normalized object instead of crashing
        """
        strict_suffix = (
            "\n\nCRITICAL:\n"
            "- Return VALID JSON only.\n"
            "- No markdown/code fences.\n"
            "- Match the exact field types specified.\n"
        )

        last_error: str | None = None
        for attempt in range(max_retries + 1):
            raw = self.chat(system=system, user=user + (strict_suffix if attempt > 0 else ""))
            raw = raw.strip()
            try:
                raw_json = self._extract_json_object(raw)
                data = self._loads_lenient(raw_json)
            except LLMError as e:
                last_error = str(e)
                continue

            # Normalize before validation to match realistic LLM output shapes.
            normalized = normalize_for_schema(schema.__name__, data)
            try:
                return schema.model_validate(normalized)
            except ValidationError as e:
                last_error = f"{e}"
                # If the normalized dict still doesn't validate, retry once.
                continue

        if not allow_fallback:
            raise LLMError(f"JSON did not match schema {schema.__name__}: {last_error}")

        # Safe fallback: validate an empty normalized object (schemas should have defaults).
        normalized = normalize_for_schema(schema.__name__, {})
        try:
            return schema.model_validate(normalized)
        except ValidationError as e:
            raise LLMError(f"Schema fallback failed for {schema.__name__}: {e}") from e


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
