from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


Message = Dict[str, str]  # {"role": "system"|"user"|"assistant", "content": "..."}


class ChatProvider(Protocol):
    """Minimal provider interface used by the RLM runner."""

    def chat(
        self,
        messages: List[Message],
        *,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout_s: int = 120,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Return assistant text for the given messages."""


@dataclass
class OpenAIChatProvider:
    """HTTP-based OpenAI Chat Completions provider.

    This is intentionally lightweight and has no non-stdlib dependencies.

    Environment variables supported:
      - OPENAI_API_KEY
      - OPENAI_BASE_URL (optional)
      - OPENAI_ORG (optional)
      - OPENAI_PROJECT (optional)

    Note: If you already depend on the official OpenAI SDK, feel free to swap
    this implementation with SDK calls.
    """

    api_key: str
    base_url: str = "https://api.openai.com/v1/chat/completions"
    organization: Optional[str] = None
    project: Optional[str] = None

    @classmethod
    def from_env(cls) -> "OpenAIChatProvider":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        return cls(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL", cls.base_url),
            organization=os.environ.get("OPENAI_ORG"),
            project=os.environ.get("OPENAI_PROJECT"),
        )

    def chat(
        self,
        messages: List[Message],
        *,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout_s: int = 120,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra:
            payload.update(extra)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        if self.project:
            headers["OpenAI-Project"] = self.project

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = "<no body>"
            raise RuntimeError(
                f"OpenAI HTTPError {e.code}: {e.reason}. Body: {err_body}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"OpenAI request failed: {e}") from e
        finally:
            _ = time.time() - start

        data = json.loads(body)
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Unexpected OpenAI response: {data}") from e


@dataclass
class MockChatProvider:
    """Deterministic provider for tests/demos.

    Provide a list of outputs; each `.chat()` pops the next output.
    """

    outputs: List[str]

    def chat(
        self,
        messages: List[Message],
        *,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout_s: int = 120,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not self.outputs:
            raise RuntimeError("MockChatProvider has no more outputs")
        return self.outputs.pop(0)
