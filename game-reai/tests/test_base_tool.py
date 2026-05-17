"""Tests for base_tool.py — BaseTool, ToolInput, ToolResult."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.core.base_tool import BaseTool, ToolInput, ToolResult


class FakeInput(ToolInput):
    value: int
    label: str = "default"


class FakeTool(BaseTool[FakeInput]):
    name = "fake_tool"
    description = "A fake tool for testing."
    input_schema = FakeInput

    async def _run(self, input_data: FakeInput) -> ToolResult:
        return ToolResult(success=True, data={"doubled": input_data.value * 2})


class FailingTool(BaseTool[FakeInput]):
    name = "failing_tool"
    description = "Always fails."
    input_schema = FakeInput

    async def _run(self, input_data: FakeInput) -> ToolResult:
        return ToolResult(success=False, error="simulated failure")


class TestToolInput:
    def test_valid_input(self) -> None:
        inp = FakeInput(value=42)
        assert inp.value == 42
        assert inp.label == "default"

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            FakeInput(value=1, extra_field="no")  # type: ignore[call-arg]

    def test_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            FakeInput(label="x")  # type: ignore[call-arg]  # missing 'value'


class TestToolResult:
    def test_success_result(self) -> None:
        r = ToolResult(success=True, data={"key": "val"})
        assert r.success
        assert r.data == {"key": "val"}
        assert r.error is None

    def test_error_result(self) -> None:
        r = ToolResult(success=False, error="something went wrong")
        assert not r.success
        assert r.error == "something went wrong"

    def test_to_dict(self) -> None:
        r = ToolResult(success=True, data={"a": 1})
        d = r.to_dict()
        assert d == {"success": True, "data": {"a": 1}}

    def test_to_dict_with_error(self) -> None:
        r = ToolResult(success=False, error="fail")
        d = r.to_dict()
        assert d == {"success": False, "data": {}, "error": "fail"}


class TestBaseTool:
    @pytest.mark.asyncio
    async def test_run_calls_run(self) -> None:
        tool = FakeTool()
        result = await tool.run(value=5)
        assert result.success
        assert result.data == {"doubled": 10}

    @pytest.mark.asyncio
    async def test_run_validates_input(self) -> None:
        tool = FakeTool()
        with pytest.raises(ValidationError):
            await tool.run(bad_key=1)

    @pytest.mark.asyncio
    async def test_failing_tool(self) -> None:
        tool = FailingTool()
        result = await tool.run(value=1)
        assert not result.success
        assert result.error == "simulated failure"

    def test_to_langchain_tool(self) -> None:
        tool = FakeTool()
        lc_tool = tool.to_langchain_tool()
        assert lc_tool.name == "fake_tool"
        assert lc_tool.description == "A fake tool for testing."
