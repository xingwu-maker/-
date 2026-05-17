"""Configuration management via env vars and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Global config for game-reai."""

    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    temperature: float = 0.1
    max_agent_iterations: int = 15
    log_level: str = "INFO"

    @property
    def is_configured(self) -> bool:
        return bool(self.anthropic_api_key)
