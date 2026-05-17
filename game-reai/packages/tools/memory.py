"""Windows process memory reader via pymem.

Provides: get_process_info, read_memory, follow_pointer_chain, find_pattern.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from typing import Any

from packages.core.base_tool import BaseTool, ToolInput, ToolResult


class ProcessInfoInput(ToolInput):
    pid: int | None = None
    name: str | None = None


class ReadMemoryInput(ToolInput):
    pid: int
    address: int
    size: int
    as_type: str | None = None  # "int32" | "float" | "pointer" | "bytes" | "string"


class FollowPointerInput(ToolInput):
    pid: int
    base_address: int
    offsets: list[int]


class FindPatternInput(ToolInput):
    pid: int
    module_name: str
    pattern: str  # "48 8B ?? ?? ?? 48 85 C0"


@dataclass
class ModuleInfo:
    name: str
    base: int
    size: int
    path: str


@dataclass
class ProcessInfo:
    pid: int
    name: str
    arch: str
    modules: list[ModuleInfo] = field(default_factory=list)


class MemoryReader:
    """Low-level pymem wrapper. Not a BaseTool — tools delegate to this."""

    def __init__(self) -> None:
        self._pm: Any = None
        self._pid: int = 0

    def attach(self, pid: int) -> ProcessInfo:
        import pymem

        self._pid = pid
        self._pm = pymem.Pymem(pid)
        return ProcessInfo(
            pid=pid,
            name=self._pm.process_base.lpProcessName or "unknown",
            arch="x64" if self._is_64bit() else "x86",
            modules=self._enum_modules(),
        )

    def attach_by_name(self, name: str) -> ProcessInfo:
        import pymem

        self._pm = pymem.Pymem(name)
        self._pid = self._pm.process_id
        return ProcessInfo(
            pid=self._pid,
            name=name,
            arch="x64" if self._is_64bit() else "x86",
            modules=self._enum_modules(),
        )

    def _is_64bit(self) -> bool:
        try:
            handle = self._pm.process_handle
            kernel32 = ctypes.windll.kernel32
            is_wow64 = ctypes.c_bool(False)
            kernel32.IsWow64Process(handle, ctypes.byref(is_wow64))
            return not is_wow64.value
        except Exception:
            return True

    def _enum_modules(self) -> list[ModuleInfo]:
        modules: list[ModuleInfo] = []
        for name, module in self._pm.list_32bit_modules():
            modules.append(
                ModuleInfo(
                    name=name,
                    base=module.lpBaseOfDll or 0,
                    size=module.SizeOfImage or 0,
                    path=module.szExePath or "",
                )
            )
        return modules

    def find_module(self, name: str) -> ModuleInfo | None:
        name_lower = name.lower()
        for m in self._enum_modules():
            if m.name.lower() == name_lower:
                return m
        return None

    def read(self, address: int, size: int) -> bytes:
        if self._pm is None:
            raise RuntimeError("未附加到进程")
        return self._pm.read_bytes(address, size)  # type: ignore[no-any-return]

    def read_int32(self, address: int) -> int:
        raw = self.read(address, 4)
        return int.from_bytes(raw, "little", signed=True)

    def read_float(self, address: int) -> float:
        import struct

        raw = self.read(address, 4)
        return struct.unpack("<f", raw)[0]  # type: ignore[no-any-return]

    def read_pointer(self, address: int) -> int:
        raw = self.read(address, 8)
        return int.from_bytes(raw, "little")

    def read_string(self, address: int, max_len: int = 256) -> str:
        raw = self.read(address, max_len)
        null_pos = raw.find(b"\x00")
        if null_pos >= 0:
            raw = raw[:null_pos]
        return raw.decode("utf-8", errors="replace")

    def follow_chain(self, address: int, offsets: list[int]) -> list[dict[str, Any]]:
        """Follow a pointer chain. Returns each hop.

        [base] -> offset[0] -> offset[1] -> ... -> value
        """
        chain: list[dict[str, Any]] = []
        current = address
        for i, offset in enumerate(offsets):
            ptr = self.read_pointer(current + offset)
            chain.append(
                {
                    "step": i,
                    "offset": offset,
                    "address": current + offset,
                    "value": ptr,
                    "is_valid": ptr != 0,
                }
            )
            if ptr == 0:
                break
            current = ptr
        return chain

    def scan_pattern(self, module_base: int, module_size: int, pattern: str) -> list[int]:
        """AOB scan in module memory. Returns list of absolute addresses.

        pattern: "48 8B ?? ?? ?? 48 85 C0"
        """
        parts = pattern.strip().split()
        mask = bytearray()
        sig = bytearray()
        for p in parts:
            if p in ("?", "??"):
                mask.append(0)
                sig.append(0)
            else:
                mask.append(1)
                sig.append(int(p, 16))

        data = self.read(module_base, module_size)
        matches: list[int] = []

        for i in range(len(data) - len(sig) + 1):
            match = True
            for j in range(len(sig)):
                if mask[j] and data[i + j] != sig[j]:
                    match = False
                    break
            if match:
                matches.append(module_base + i)

        return matches


class GetProcessInfoTool(BaseTool[ProcessInfoInput]):
    name = "get_process_info"
    description = "获取进程基本信息：PID、架构、已加载模块列表（名称、基址、大小）。"
    input_schema = ProcessInfoInput

    async def _run(self, input_data: ProcessInfoInput) -> ToolResult:
        reader = MemoryReader()
        try:
            if input_data.pid:
                info = reader.attach(input_data.pid)
            elif input_data.name:
                info = reader.attach_by_name(input_data.name)
            else:
                return ToolResult(success=False, error="需要 pid 或 name")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        modules_data = [
            {"name": m.name, "base": hex(m.base), "size": hex(m.size)} for m in info.modules
        ]
        return ToolResult(
            success=True,
            data={
                "pid": info.pid,
                "name": info.name,
                "arch": info.arch,
                "module_count": len(info.modules),
                "modules": modules_data,
            },
        )


class ReadMemoryTool(BaseTool[ReadMemoryInput]):
    name = "read_memory"
    description = "读取进程指定地址的内存。可指定解码类型：int32/float/pointer/bytes/string。"
    input_schema = ReadMemoryInput

    async def _run(self, input_data: ReadMemoryInput) -> ToolResult:
        reader = MemoryReader()
        try:
            reader.attach(input_data.pid)
        except Exception as e:
            return ToolResult(success=False, error=f"附加进程失败: {e}")

        try:
            raw = reader.read(input_data.address, input_data.size)
            hex_str = raw.hex(" ")

            decoded: Any = None
            if input_data.as_type == "int32" and len(raw) >= 4:
                decoded = int.from_bytes(raw[:4], "little", signed=True)
            elif input_data.as_type == "float" and len(raw) >= 4:
                import struct

                decoded = struct.unpack("<f", raw[:4])[0]
            elif input_data.as_type == "pointer" and len(raw) >= 8:
                decoded = hex(int.from_bytes(raw[:8], "little"))
            elif input_data.as_type == "string":
                null_pos = raw.find(b"\x00")
                decoded = (
                    raw[:null_pos].decode("utf-8", errors="replace")
                    if null_pos >= 0
                    else raw.decode("utf-8", errors="replace")
                )

            return ToolResult(
                success=True,
                data={
                    "address": hex(input_data.address),
                    "hex": hex_str,
                    "decoded_value": decoded,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FollowPointerChainTool(BaseTool[FollowPointerInput]):
    name = "follow_pointer_chain"
    description = "从基址出发，逐步跟随指针链。返回每一步的偏移、地址、值和有效性。"
    input_schema = FollowPointerInput

    async def _run(self, input_data: FollowPointerInput) -> ToolResult:
        reader = MemoryReader()
        try:
            reader.attach(input_data.pid)
        except Exception as e:
            return ToolResult(success=False, error=f"附加进程失败: {e}")

        try:
            chain = reader.follow_chain(input_data.base_address, input_data.offsets)
            valid = all(step["is_valid"] for step in chain)
            last = chain[-1] if chain else None
            return ToolResult(
                success=True,
                data={
                    "chain": chain,
                    "is_valid": valid,
                    "final_address": hex(last["address"]) if last else None,
                    "final_value": hex(last["value"]) if last else None,
                    "depth": len(chain),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FindPatternTool(BaseTool[FindPatternInput]):
    name = "find_pattern"
    description = "在模块内存中搜索字节模式（AOB scan）。?? = 通配符。返回匹配地址列表。"
    input_schema = FindPatternInput

    async def _run(self, input_data: FindPatternInput) -> ToolResult:
        reader = MemoryReader()
        try:
            reader.attach(input_data.pid)
        except Exception as e:
            return ToolResult(success=False, error=f"附加进程失败: {e}")

        module = reader.find_module(input_data.module_name)
        if module is None:
            return ToolResult(success=False, error=f"模块 '{input_data.module_name}' 未找到")

        try:
            matches = reader.scan_pattern(module.base, module.size, input_data.pattern)
            return ToolResult(
                success=True,
                data={
                    "module": input_data.module_name,
                    "pattern": input_data.pattern,
                    "match_count": len(matches),
                    "matches": [hex(m) for m in matches[:20]],
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
