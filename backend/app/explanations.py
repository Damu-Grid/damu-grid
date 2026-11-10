import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

import httpx

from backend.app.audit import AuditStore
from backend.app.schemas import Suggestion

logger = logging.getLogger(__name__)


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
            provider=os.getenv("LLM_PROVIDER") or "openai-compatible",
            model=os.getenv("LLM_MODEL") or None,
            api_key=os.getenv("LLM_API_KEY") or None,
            base_url=os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1",
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

    def rewrite(self, deterministic_text: str, *, timeout_seconds: float | None = None) -> str:
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
            timeout=(
                self.settings.timeout_seconds if timeout_seconds is None else timeout_seconds
            ),
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
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.audit = audit
        self.provider = provider or OpenAICompatibleProvider(settings)
        self.clock = clock
        self._explanation_cache: dict[tuple[str, int], Suggestion] = {}
        self._cache_lock = Lock()

    @staticmethod
    def _template(suggestion: Suggestion) -> Suggestion:
        return suggestion.model_copy(
            update={
                "reason_llm": None,
                "explanation_source": "template",
                "explanation_model": None,
                "latency_ms": None,
            }
        )

    def apply_many(
        self, suggestions: list[Suggestion], *, budget_seconds: float = 8.0
    ) -> list[Suggestion]:
        results: list[Suggestion] = []
        with self._cache_lock:
            deadline = self.clock() + budget_seconds
            for suggestion in suggestions:
                if not self.settings.enabled:
                    results.append(self._template(suggestion))
                    continue

                key = (suggestion.suggestion_id, suggestion.unit_version)
                cached = self._explanation_cache.get(key)
                if cached is not None:
                    results.append(
                        suggestion.model_copy(
                            update={
                                "reason_llm": cached.reason_llm,
                                "explanation_source": cached.explanation_source,
                                "explanation_model": cached.explanation_model,
                                "latency_ms": cached.latency_ms,
                            }
                        )
                    )
                    continue

                remaining = deadline - self.clock()
                if remaining <= 0:
                    results.append(self._template(suggestion))
                    continue

                explained = self.apply(suggestion, timeout_seconds=remaining)
                self._explanation_cache[key] = explained
                results.append(explained)
        return results

    def apply(
        self, suggestion: Suggestion, *, timeout_seconds: float | None = None
    ) -> Suggestion:
        if not self.settings.enabled:
            return self._template(suggestion)

        started = self.clock()
        text: str | None = None
        outcome = "error"
        try:
            if isinstance(self.provider, OpenAICompatibleProvider):
                candidate = self.provider.rewrite(
                    suggestion.reason_deterministic, timeout_seconds=timeout_seconds
                )
            else:
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

        latency_ms = round((self.clock() - started) * 1000)
        try:
            self.audit.append_llm_call(
                provider=self.settings.provider,
                model=self.settings.model,
                latency_ms=latency_ms,
                outcome=outcome,
            )
        except Exception:
            logger.warning("Failed to append LLM audit entry", exc_info=True)
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
