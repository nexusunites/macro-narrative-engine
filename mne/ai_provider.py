"""Provider-neutral boundary for the optional AI Analyst.

Path A deliberately contains no network-backed provider implementation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

DEFAULT_PROVIDER = "disabled"
DEFAULT_TIMEOUT_SECONDS = 12
DEFAULT_OUTPUT_TOKEN_CAP = 700


class AnalystProviderError(RuntimeError):
    """Base class for expected provider failures."""


class ProviderDisabledError(AnalystProviderError):
    """Signals that deterministic fallback should be used."""


class ProviderTimeoutError(AnalystProviderError):
    """Signals a provider timeout without triggering a retry."""


class AnalystProvider:
    provider_name = "unknown"
    model_name = "unknown"
    timeout = DEFAULT_TIMEOUT_SECONDS

    def generate_analysis(
        self, context: dict[str, Any], mode: str, question: str
    ) -> Any:
        raise NotImplementedError


class DisabledProvider(AnalystProvider):
    provider_name = "disabled"
    model_name = "none"

    def generate_analysis(
        self, context: dict[str, Any], mode: str, question: str
    ) -> Any:
        raise ProviderDisabledError("AI Analyst provider is disabled.")


@dataclass
class MockProvider(AnalystProvider):
    """Fixture provider for tests; it performs no I/O."""

    response: Any = None
    error: Exception | None = None
    provider_name: str = "mock"
    model_name: str = "fixture"
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    call_count: int = 0

    def generate_analysis(
        self, context: dict[str, Any], mode: str, question: str
    ) -> Any:
        self.call_count += 1
        if self.error:
            raise self.error
        return self.response


def provider_from_environment() -> AnalystProvider:
    """Return only the disabled provider in production Path A.

    MockProvider must be injected directly by tests. Environment values cannot
    enable a paid or network-backed adapter in this sprint.
    """
    _ = os.environ.get("MNE_AI_ANALYST_PROVIDER", DEFAULT_PROVIDER)
    return DisabledProvider()
