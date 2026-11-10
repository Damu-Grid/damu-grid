import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from backend.app.audit import AuditStore
from backend.app.schemas import Suggestion


@dataclass(frozen=True)
class ExplanationSettings:
    enabled: bool = False
    provider: str = "openai-compatible"
    model: str | None = None
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 5.0

    @classmethod
    def from_environment(cls) -> "ExplanationSettings":
        return cls(
            enabled=os.getenv("LLM_ENABLED", "false").lower() in {"1", "true", "yes"},
            provider=os.getenv("LLM_PROVIDER", "openai-compatible"),
            model=os.getenv("LLM_MODEL") or None,
            api_key=os.getenv("LLM_API_KEY") or None,
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        )


class ExplanationAudit(Protocol):
    def append_llm_call(
        self,
        *,
        provider: str,
        model: str | None,
        latency_ms: int,
        outcome: str,
    ) -> None: ...


class ProviderRateLimited(Exception):
    """The provider rejected a request due to its rate limit."""


class OpenAICompatibleProvider:
    def __init__(self, settings: ExplanationSettings) -> None:
        self.settings = settings

    def rewrite(self, deterministic_text: str) -> str:
        if not self.settings.model or not self.settings.api_key:
            raise RuntimeError("LLM model and API key must be configured")
        response = httpx.post(
            f"{self.settings.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.api_key}"},
            json={
                "model": self.settings.model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Rewrite the supplied operational explanation in plain language. "
                            "Preserve every number exactly. Add no facts, recommendations, "
                            "clinical claims, or implied transfusion clearance. Return only "
                            "the rewritten sentence."
                        ),
                    },
                    {"role": "user", "content": deterministic_text},
                ],
            },
            timeout=self.settings.timeout_seconds,
        )
        if response.status_code == 429:
            raise ProviderRateLimited
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("provider returned an empty explanation")
        return text.strip()


_NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?%?(?![A-Za-z])")
_UNSAFE_CLAIM = re.compile(
    r"\b(?:transfusion|transfuse|compatible|compatibility|clearance|released?|safe)\b",
    re.IGNORECASE,
)


def _numbers(text: str) -> list[str]:
    return sorted(_NUMBER.findall(text))


class ExplanationService:
    def __init__(
        self,
        settings: ExplanationSettings,
        audit: ExplanationAudit,
        provider: Callable[[str], str] | None = None,
    ) -> None:
        self.settings = settings
        self.audit = audit
        self.provider = provider or OpenAICompatibleProvider(settings).rewrite

    def apply(self, suggestion: Suggestion) -> Suggestion:
        if not self.settings.enabled:
            return suggestion.model_copy(
                update={
                    "reason_llm": None,
                    "explanation_source": "template",
                    "explanation_model": None,
                    "latency_ms": None,
                }
            )

        started = time.monotonic()
        text: str | None = None
        outcome = "error"
        try:
            candidate = self.provider(suggestion.reason_deterministic)
            if _numbers(candidate) != _numbers(suggestion.reason_deterministic):
                outcome = "rejected_numeric_mismatch"
            elif _UNSAFE_CLAIM.search(candidate):
                outcome = "rejected_unsafe_claim"
            else:
                text = candidate
                outcome = "success"
        except ProviderRateLimited:
            outcome = "rate_limited"
        except httpx.TimeoutException:
            outcome = "timeout"
        except httpx.HTTPStatusError as exc:
            outcome = "rate_limited" if exc.response.status_code == 429 else "http_error"
        except Exception:
            outcome = "error"

        latency_ms = round((time.monotonic() - started) * 1000)
        self.audit.append_llm_call(
            provider=self.settings.provider,
            model=self.settings.model,
            latency_ms=latency_ms,
            outcome=outcome,
        )
        if text is None:
            return suggestion.model_copy(
                update={
                    "reason_llm": None,
                    "explanation_source": "template",
                    "explanation_model": self.settings.model,
                    "latency_ms": latency_ms,
                }
            )
        return suggestion.model_copy(
            update={
                "reason_llm": text,
                "explanation_source": "llm",
                "explanation_model": self.settings.model,
                "latency_ms": latency_ms,
            }
        )


def default_explanation_service(action_database_path: str) -> ExplanationService:
    from pathlib import Path

    return ExplanationService(
        ExplanationSettings.from_environment(),
        AuditStore(Path(action_database_path)),
    )
