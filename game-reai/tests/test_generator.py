"""Tests for generator.py — CE Lua / Python / C++ script generation."""

from __future__ import annotations

from packages.core.generator import PointerChain, ScriptGenerator


class TestScriptGeneratorCELua:
    def setup_method(self) -> None:
        self.gen = ScriptGenerator()

    def test_no_offset_chain(self) -> None:
        chain = PointerChain(
            base_module="game.exe", base_offset=0x7FF80000, offsets=[], value_type="int"
        )
        code = self.gen.generate_ce_lua(chain)
        assert 'getAddress("game.exe+7FF80000")' in code
        assert "readInteger" in code

    def test_single_offset_chain(self) -> None:
        chain = PointerChain(
            base_module="game.exe", base_offset=0x2A3B4C, offsets=[0x10], value_type="int"
        )
        code = self.gen.generate_ce_lua(chain)
        assert 'getAddress("game.exe+2A3B4C")' in code
        assert "readPointer(base)" in code
        assert "p1 + 0x10" in code
        assert "readInteger" in code

    def test_multi_offset_chain(self) -> None:
        chain = PointerChain(
            base_module="engine.dll",
            base_offset=0x1A2B3C,
            offsets=[0x20, 0x8, 0x10],
            value_type="float",
        )
        code = self.gen.generate_ce_lua(chain)
        assert 'getAddress("engine.dll+1A2B3C")' in code
        assert "p1 = readPointer(base)" in code
        assert "p2 = readPointer(p1 + 0x20)" in code
        assert "p3 = readPointer(p2 + 0x8)" in code
        assert "readFloat" in code
        assert "p3 + 0x10" in code
        # nil checks
        assert "if p1 then" in code
        assert "end" in code

    def test_float_type(self) -> None:
        chain = PointerChain(
            base_module="game.exe", base_offset=0x1000, offsets=[0x4], value_type="float"
        )
        code = self.gen.generate_ce_lua(chain)
        assert "readFloat" in code

    def test_string_type(self) -> None:
        chain = PointerChain(
            base_module="game.exe", base_offset=0x1000, offsets=[0x4], value_type="string"
        )
        code = self.gen.generate_ce_lua(chain)
        assert "readString" in code

    def test_pointer_type(self) -> None:
        chain = PointerChain(
            base_module="game.exe", base_offset=0x1000, offsets=[0x8], value_type="pointer"
        )
        code = self.gen.generate_ce_lua(chain)
        assert "readPointer" in code

    def test_8_bytes_type(self) -> None:
        chain = PointerChain(
            base_module="game.exe", base_offset=0x1000, offsets=[0x8], value_type="8 Bytes"
        )
        code = self.gen.generate_ce_lua(chain)
        assert "readQword" in code

    def test_base_module_in_comment(self) -> None:
        chain = PointerChain(
            base_module="client.dll",
            base_offset=0xDEAD,
            offsets=[0x10, 0x20],
            value_type="int",
        )
        code = self.gen.generate_ce_lua(chain)
        assert "client.dll+DEAD" in code
        assert "0x10" in code
        assert "0x20" in code

    def test_generate_multi_format(self) -> None:
        chains = [
            PointerChain(base_module="game.exe", base_offset=0x100, offsets=[0x8], value_type="int")
        ]
        output = self.gen.generate(chains, fmt="ce_lua")
        assert output.format == "ce_lua"
        assert "game.exe+100" in output.code
        assert len(output.chains) == 1


class TestScriptGeneratorPython:
    def setup_method(self) -> None:
        self.gen = ScriptGenerator()

    def test_generates_valid_pymem(self) -> None:
        chain = PointerChain(
            base_module="game.exe",
            base_offset=0x2A3B4C,
            offsets=[0x10, 0x20, 0x8],
            value_type="int",
        )
        code = self.gen.generate_python(chain, process_name="test_game.exe")
        assert "import pymem" in code
        assert 'pymem.Pymem("test_game.exe")' in code
        assert "pm.read_longlong" in code
        assert "pm.read_int" in code
        assert "RuntimeError" in code

    def test_no_offset_python(self) -> None:
        chain = PointerChain(
            base_module="game.exe", base_offset=0x1000, offsets=[], value_type="int"
        )
        code = self.gen.generate_python(chain)
        assert "pm.read_int(base)" in code


class TestScriptGeneratorCpp:
    def setup_method(self) -> None:
        self.gen = ScriptGenerator()

    def test_generates_valid_cpp(self) -> None:
        chain = PointerChain(
            base_module="game.exe",
            base_offset=0x2A3B4C,
            offsets=[0x10, 0x8],
            value_type="int",
        )
        code = self.gen.generate_cpp(chain)
        assert "#include <windows.h>" in code
        assert "OpenProcess" in code
        assert "ReadProcessMemory" in code
        assert "CloseHandle" in code
        assert "指针链断裂" in code


class TestPointerChain:
    def test_defaults(self) -> None:
        chain = PointerChain(base_module="x.dll", base_offset=0x100, offsets=[1, 2])
        assert chain.value_type == "int"
        assert chain.description == ""

    def test_custom_values(self) -> None:
        chain = PointerChain(
            base_module="y.exe",
            base_offset=0x200,
            offsets=[3],
            value_type="float",
            description="player hp",
        )
        assert chain.value_type == "float"
        assert chain.description == "player hp"
