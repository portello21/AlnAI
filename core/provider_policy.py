from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class CostClass(str, Enum):
    LOCAL = "local"
    FREE = "free"
    PAID = "paid"
    UNKNOWN = "unknown"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    cost: CostClass
    local: bool = False
    supports_reasoning: bool = False
    supports_tools: bool = False
    supports_vision: bool = False


@dataclass
class ProviderHealth:
    state: HealthState = HealthState.HEALTHY
    failures: int = 0
    blocked_until: float = 0.0
    last_error: str = ""
    updated_at: float = field(default_factory=time.time)

    def available(self, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        return current >= self.blocked_until


PROVIDERS = {
    "docker-model-runner": ProviderSpec("docker-model-runner", CostClass.LOCAL, local=True),
    "nvidia": ProviderSpec("nvidia", CostClass.FREE, supports_reasoning=True, supports_tools=True, supports_vision=True),
    # DeepSeek is already part of the existing deployment. Treat it as paid
    # unless the owner explicitly enables paid providers or chooses it directly.
    "deepseek": ProviderSpec("deepseek", CostClass.PAID, supports_reasoning=True),
    "openai": ProviderSpec("openai", CostClass.PAID, supports_reasoning=True, supports_tools=True, supports_vision=True),
    "anthropic": ProviderSpec("anthropic", CostClass.PAID, supports_reasoning=True, supports_tools=True, supports_vision=True),
}


class ProviderHealthRegistry:
    """Small in-process circuit breaker; it never stores prompts or user data."""

    def __init__(self, failure_threshold: int = 2, cooldown_seconds: int = 45):
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = max(5, int(cooldown_seconds))
        self._health: dict[str, ProviderHealth] = {}

    def get(self, provider: str) -> ProviderHealth:
        return self._health.setdefault(provider, ProviderHealth())

    def can_attempt(self, provider: str) -> bool:
        return self.get(provider).available()

    def success(self, provider: str) -> None:
        health = self.get(provider)
        health.state = HealthState.HEALTHY
        health.failures = 0
        health.blocked_until = 0.0
        health.last_error = ""
        health.updated_at = time.time()

    def failure(self, provider: str, error_type: str = "error", *, rate_limited: bool = False) -> None:
        health = self.get(provider)
        health.failures += 1
        health.last_error = str(error_type or "error")[:80]
        health.updated_at = time.time()
        if rate_limited:
            health.state = HealthState.RATE_LIMITED
            health.blocked_until = time.time() + self.cooldown_seconds
        elif health.failures >= self.failure_threshold:
            health.state = HealthState.OFFLINE
            health.blocked_until = time.time() + self.cooldown_seconds
        else:
            health.state = HealthState.DEGRADED


def provider_allowed(provider: str, *, allow_paid: bool) -> bool:
    spec = PROVIDERS.get(provider)
    if spec is None or spec.cost is CostClass.UNKNOWN:
        return False
    if spec.cost is CostClass.PAID:
        return bool(allow_paid)
    return True
