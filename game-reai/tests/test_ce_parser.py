"""Tests for ce_parser.py — Cheat Engine XML export parsing."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from packages.tools.ce_parser import CEParser
from tests.conftest import SAMPLE_CE_XML


@pytest.fixture
def sample_xml_file() -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_CE_XML)
        return Path(f.name)


class TestCEParser:
    @pytest.mark.asyncio
    async def test_parse_sample_xml(self, sample_xml_file: Path) -> None:
        parser = CEParser()
        result = await parser.run(file_path=str(sample_xml_file))
        assert result.success
        data = result.data
        parsed = data["parsed"]
        assert parsed.process_name == "game.exe"
        assert len(parsed.entries) == 3

    @pytest.mark.asyncio
    async def test_extracts_module_names(self, sample_xml_file: Path) -> None:
        parser = CEParser()
        result = await parser.run(file_path=str(sample_xml_file))
        entries = result.data["parsed"].entries

        modules = {e.module for e in entries if e.module}
        assert "game.exe" in modules
        assert "engine.dll" in modules

    @pytest.mark.asyncio
    async def test_extracts_values(self, sample_xml_file: Path) -> None:
        parser = CEParser()
        result = await parser.run(file_path=str(sample_xml_file))
        entries = result.data["parsed"].entries

        values = {e.description: e.value for e in entries}
        assert values["Health"] == "100"
        assert values["Ammo"] == "30"
        assert values["Score"] == "99.5"

    @pytest.mark.asyncio
    async def test_extracts_types(self, sample_xml_file: Path) -> None:
        parser = CEParser()
        result = await parser.run(file_path=str(sample_xml_file))
        entries = result.data["parsed"].entries

        types = {e.description: e.type_name for e in entries}
        assert types["Health"] == "4 Bytes"
        assert types["Score"] == "Float"

    @pytest.mark.asyncio
    async def test_extracts_pointer_offsets(self, sample_xml_file: Path) -> None:
        parser = CEParser()
        result = await parser.run(file_path=str(sample_xml_file))
        entries = result.data["parsed"].entries

        ammo_entry = next(e for e in entries if e.description == "Ammo")
        assert len(ammo_entry.offsets) == 3
        # offsets from child entries: +0x0, +0x10, +0x20
        assert ammo_entry.offsets == [0x0, 0x10, 0x20]

    @pytest.mark.asyncio
    async def test_summary(self, sample_xml_file: Path) -> None:
        parser = CEParser()
        result = await parser.run(file_path=str(sample_xml_file))
        summary = result.data["summary"]
        assert "game.exe" in summary
        assert "3" in summary  # 3 entries

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        parser = CEParser()
        result = await parser.run(file_path="/nonexistent/file.xml")
        assert not result.success
        assert result.error is not None
        assert "文件不存在" in result.error

    @pytest.mark.asyncio
    async def test_invalid_xml(self) -> None:
        parser = CEParser()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write("not valid xml <<<>>>")
            path = Path(f.name)

        result = await parser.run(file_path=str(path))
        assert not result.success
        assert result.error is not None
        assert "XML 解析失败" in result.error

    @pytest.mark.asyncio
    async def test_address_resolution(self, sample_xml_file: Path) -> None:
        parser = CEParser()
        result = await parser.run(file_path=str(sample_xml_file))
        entries = result.data["parsed"].entries

        # game.exe+2A3B4C -> 0x2A3B4C
        health = next(e for e in entries if e.description == "Health")
        assert health.address == 0x2A3B4C

        # 0x7FF80000 -> 0x7FF80000
        score = next(e for e in entries if e.description == "Score")
        assert score.address == 0x7FF80000
