"""Cheat Engine XML export parser.

Handles both .xml (CE table) and .CT (binary) formats.
Extracts addresses, values, types, pointer chains, and process info.
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from packages.core.base_tool import BaseTool, ToolInput, ToolResult


class CEParseInput(ToolInput):
    file_path: str


@dataclass
class CheatEntry:
    address: int
    value: str
    type_name: str  # "4 Bytes", "Float", etc.
    description: str
    module: str | None = None
    offsets: list[int] = field(default_factory=list)


@dataclass
class CEParseOutput:
    process_name: str
    entries: list[CheatEntry]
    module_base_hints: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        modules = {e.module for e in self.entries if e.module}
        return (
            f"进程: {self.process_name}\n"
            f"地址数: {len(self.entries)}\n"
            f"涉及模块: {', '.join(sorted(modules)) if modules else '未知'}\n"
            f"带指针链: {sum(1 for e in self.entries if e.offsets)}"
        )


class CEParser(BaseTool[CEParseInput]):
    name = "parse_ce_export"
    description = "解析 Cheat Engine XML 导出文件，提取地址、值、类型、指针链。"
    input_schema = CEParseInput

    async def _run(self, input_data: CEParseInput) -> ToolResult:
        path = Path(input_data.file_path)
        if not path.exists():
            return ToolResult(success=False, error=f"文件不存在: {input_data.file_path}")

        try:
            tree = ElementTree.parse(path)
            root = tree.getroot()
            result = self._parse_xml(root)
            return ToolResult(success=True, data={"parsed": result, "summary": result.summary()})
        except ElementTree.ParseError:
            return ToolResult(success=False, error="XML 解析失败，请确认是 CE 导出的 .xml 文件")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _parse_xml(self, root: Any) -> CEParseOutput:
        entries: list[CheatEntry] = []
        process_name = "unknown"

        process_elem = root.find("ProcessName")
        if process_elem is not None and process_elem.text:
            process_name = process_elem.text.strip().strip('"')

        top_entries = root.find("CheatEntries")
        if top_entries is not None:
            for child in top_entries:
                if child.tag.lower() == "cheatentry":
                    entry = self._parse_entry(child)
                    if entry:
                        entries.append(entry)

        return CEParseOutput(process_name=process_name, entries=entries)

    def _parse_entry(self, elem: Any) -> CheatEntry | None:
        address_elem = elem.find("Address")
        if address_elem is None or not address_elem.text:
            return None

        address_str = address_elem.text.strip()
        address = self._resolve_address(address_str)

        description = ""
        desc_elem = elem.find("Description")
        if desc_elem is not None and desc_elem.text:
            description = desc_elem.text.strip('"')

        value = ""
        value_elem = elem.find("LastValue")
        if value_elem is not None and value_elem.text:
            value = value_elem.text.strip()
        if not value:
            cheat_value = elem.find("CheatValue") or elem.find("Value")
            if cheat_value is not None and cheat_value.text:
                value = cheat_value.text.strip()

        type_name = "4 Bytes"
        var_type = elem.find("VariableType")
        if var_type is not None and var_type.text:
            type_name = var_type.text.strip()

        module, offsets = self._extract_pointer_chain(elem, address_str)

        return CheatEntry(
            address=address,
            value=value,
            type_name=type_name,
            description=description,
            module=module,
            offsets=offsets,
        )

    def _resolve_address(self, raw: str) -> int:
        """Resolve 'module.exe+0x123' or '0x7FF8...' to int."""
        raw = raw.strip().strip('"')
        match = re.match(r"^.*?\+([0-9a-fA-Fx]+)$", raw)
        if match:
            return int(match.group(1), 16)
        try:
            return int(raw, 0)
        except ValueError:
            return 0

    def _extract_pointer_chain(self, elem: Any, address_str: str) -> tuple[str | None, list[int]]:
        """Extract module name and offset chain from a CheatEntry."""
        module: str | None = None
        offsets: list[int] = []

        module_match = re.match(r"^([a-zA-Z0-9_.-]+\.(?:exe|dll))\+.+", address_str)
        if module_match:
            module = module_match.group(1)

        cheat_entries = elem.find("CheatEntries")
        if cheat_entries is not None:
            for child in cheat_entries:
                child_addr_elem = child.find("Address")
                if child_addr_elem is not None and child_addr_elem.text:
                    child_addr = child_addr_elem.text.strip().strip('"')
                    offset_match = re.search(r"\+(0x[0-9a-fA-F]+)$", child_addr)
                    if offset_match:
                        offsets.append(int(offset_match.group(1), 16))
                    else:
                        with contextlib.suppress(ValueError):
                            offsets.append(int(child_addr, 0))
                if not module:
                    child_desc = child.find("Description")
                    if child_desc is not None and child_desc.text:
                        mod_match = re.match(
                            r"^([a-zA-Z0-9_.-]+\.(?:exe|dll))", child_desc.text.strip('"')
                        )
                        if mod_match:
                            module = mod_match.group(1)

        return module, offsets
