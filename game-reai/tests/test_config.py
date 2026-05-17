"""Tests for config.py."""

from __future__ import annotations

import pytest

from packages.core.config import Config


class TestConfig:
    def test_defaults(self) -> None:
        config = Config()
        assert config.model == "claude-sonnet-4-6"
        assert config.max_tokens == 4096
        assert config.temperature == 0.1
        assert config.max_agent_iterations == 15
        assert config.log_level == "INFO"

    def test_is_configured_false_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = Config()
        assert not config.is_configured

    def test_is_configured_true_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        config = Config()
        assert config.is_configured
        assert config.anthropic_api_key == "sk-ant-test-key"

    def test_custom_values(self) -> None:
        config = Config(
            model="claude-opus-4-7",
            max_tokens=8192,
            temperature=0.5,
            max_agent_iterations=30,
        )
        assert config.model == "claude-opus-4-7"
        assert config.max_tokens == 8192
        assert config.temperature == 0.5
        assert config.max_agent_iterations == 30
