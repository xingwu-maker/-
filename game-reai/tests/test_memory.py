"""Tests for memory tools — with mocked pymem."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from packages.tools.memory import (
    FindPatternTool,
    FollowPointerChainTool,
    GetProcessInfoTool,
    MemoryReader,
    ReadMemoryTool,
)

_PATCH_TARGET = "packages.tools.memory.MemoryReader.attach"
_PATCH_ERR = RuntimeError("no process")


class TestMemoryReader:
    def test_follow_chain(self) -> None:
        reader = MemoryReader()

        call_count = [0]
        pointers = [0x7FF81000, 0x7FF82000, 0x100]

        def mock_read_pointer(address: int) -> int:
            val = pointers[call_count[0]]
            call_count[0] += 1
            return val

        reader.read_pointer = mock_read_pointer  # type: ignore[method-assign]

        chain = reader.follow_chain(0x7FF80000, [0x10, 0x20, 0x8])
        assert len(chain) == 3
        assert chain[0]["step"] == 0
        assert chain[0]["offset"] == 0x10
        assert chain[0]["value"] == 0x7FF81000
        assert chain[0]["is_valid"]

        assert chain[1]["step"] == 1
        assert chain[1]["offset"] == 0x20
        assert chain[1]["value"] == 0x7FF82000

        assert chain[2]["step"] == 2
        assert chain[2]["offset"] == 0x8
        assert chain[2]["value"] == 0x100

    def test_follow_chain_broken(self) -> None:
        reader = MemoryReader()

        def mock_read_pointer(address: int) -> int:
            return 0

        reader.read_pointer = mock_read_pointer  # type: ignore[method-assign]

        chain = reader.follow_chain(0x7FF80000, [0x10, 0x20, 0x8])
        assert len(chain) == 1
        assert not chain[0]["is_valid"]
        assert chain[0]["value"] == 0

    def test_scan_pattern_single_match(self) -> None:
        reader = MemoryReader()
        # pattern 11 22 33 at offset 0x10
        fake_memory = bytes([0xFF] * 0x10 + [0x11, 0x22, 0x33] + [0xFF] * 200)
        reader.read = lambda addr, size: fake_memory  # type: ignore[assignment]

        matches = reader.scan_pattern(0x1000, len(fake_memory), "11 22 33")
        assert len(matches) == 1
        assert matches[0] == 0x1010

    def test_scan_pattern_with_wildcards(self) -> None:
        reader = MemoryReader()
        fake_memory = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xAA, 0xBB, 0xEE, 0xFF])
        reader.read = lambda addr, size: fake_memory  # type: ignore[assignment]

        matches = reader.scan_pattern(0, 8, "AA BB ?? ??")
        assert len(matches) == 2
        assert matches[0] == 0
        assert matches[1] == 4

    def test_scan_pattern_no_match(self) -> None:
        reader = MemoryReader()
        fake_memory = bytes([0x00] * 100)
        reader.read = lambda addr, size: fake_memory  # type: ignore[assignment]

        matches = reader.scan_pattern(0, 100, "DE AD BE EF")
        assert len(matches) == 0


class TestGetProcessInfoTool:
    @pytest.mark.asyncio
    async def test_needs_pid_or_name(self) -> None:
        tool = GetProcessInfoTool()
        result = await tool.run()
        assert not result.success
        assert result.error is not None
        assert "需要 pid 或 name" in result.error


class TestReadMemoryTool:
    @pytest.mark.asyncio
    async def test_attach_failure(self) -> None:
        tool = ReadMemoryTool()
        with patch(_PATCH_TARGET, side_effect=_PATCH_ERR):
            result = await tool.run(pid=99999, address=0x1000, size=4)
            assert not result.success
            assert result.error is not None
            assert "附加进程失败" in result.error


class TestFollowPointerChainTool:
    @pytest.mark.asyncio
    async def test_attach_failure(self) -> None:
        tool = FollowPointerChainTool()
        with patch(_PATCH_TARGET, side_effect=_PATCH_ERR):
            result = await tool.run(pid=99999, base_address=0x1000, offsets=[0x10])
            assert not result.success
            assert result.error is not None
            assert "附加进程失败" in result.error


class TestFindPatternTool:
    @pytest.mark.asyncio
    async def test_attach_failure(self) -> None:
        tool = FindPatternTool()
        with patch(_PATCH_TARGET, side_effect=_PATCH_ERR):
            result = await tool.run(pid=99999, module_name="game.exe", pattern="48 8B ??")
            assert not result.success
            assert result.error is not None
            assert "附加进程失败" in result.error

    @pytest.mark.asyncio
    async def test_module_not_found(self) -> None:
        tool = FindPatternTool()
        reader = MemoryReader()

        def mock_attach(pid: int) -> None:
            reader._pm = MagicMock()
            reader._pid = pid

        def mock_find_module(name: str) -> None:
            return None

        reader.attach = mock_attach  # type: ignore[assignment]
        reader.find_module = mock_find_module  # type: ignore[method-assign]

        with patch("packages.tools.memory.MemoryReader", return_value=reader):
            result = await tool.run(pid=99999, module_name="nonexistent.dll", pattern="48 8B")
            assert not result.success
            assert result.error is not None
            assert "未找到" in result.error
