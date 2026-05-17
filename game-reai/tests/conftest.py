"""Shared fixtures for all tests."""

from __future__ import annotations

import pytest

from packages.core.generator import PointerChain


@pytest.fixture
def single_offset_chain() -> PointerChain:
    return PointerChain(
        base_module="game.exe",
        base_offset=0x2A3B4C,
        offsets=[0x10],
        value_type="int",
        description="health",
    )


@pytest.fixture
def multi_offset_chain() -> PointerChain:
    return PointerChain(
        base_module="engine.dll",
        base_offset=0x1A2B3C,
        offsets=[0x20, 0x8, 0x10],
        value_type="float",
        description="player_x",
    )


@pytest.fixture
def no_offset_chain() -> PointerChain:
    return PointerChain(
        base_module="game.exe",
        base_offset=0x7FF80000,
        offsets=[],
        value_type="4 Bytes",
        description="score",
    )


# Sample CE XML export for parser tests
SAMPLE_CE_XML = """<?xml version="1.0" encoding="utf-8"?>
<CheatTable ContentVersion="37">
  <CheatEntries>
    <CheatEntry>
      <ID>0</ID>
      <Description>"Health"</Description>
      <Color>FF0000</Color>
      <VariableType>4 Bytes</VariableType>
      <Address>game.exe+2A3B4C</Address>
      <LastValue>100</LastValue>
      <CheatEntries>
        <CheatEntry>
          <ID>1</ID>
          <Description>"game.exe"+002A3B4C</Description>
          <VariableType>4 Bytes</VariableType>
          <Address>game.exe+2A3B4C</Address>
        </CheatEntry>
      </CheatEntries>
    </CheatEntry>
    <CheatEntry>
      <ID>2</ID>
      <Description>"Ammo"</Description>
      <VariableType>4 Bytes</VariableType>
      <Address>"engine.dll"+00123456</Address>
      <LastValue>30</LastValue>
      <CheatEntries>
        <CheatEntry>
          <ID>3</ID>
          <Description>engine.dll</Description>
          <VariableType>4 Bytes</VariableType>
          <Address>+0x0</Address>
        </CheatEntry>
        <CheatEntry>
          <ID>4</ID>
          <Description>engine.dll</Description>
          <VariableType>4 Bytes</VariableType>
          <Address>+0x10</Address>
        </CheatEntry>
        <CheatEntry>
          <ID>5</ID>
          <Description>engine.dll</Description>
          <VariableType>4 Bytes</VariableType>
          <Address>+0x20</Address>
        </CheatEntry>
      </CheatEntries>
    </CheatEntry>
    <CheatEntry>
      <ID>6</ID>
      <Description>"Score"</Description>
      <VariableType>Float</VariableType>
      <Address>0x7FF80000</Address>
      <LastValue>99.5</LastValue>
    </CheatEntry>
  </CheatEntries>
  <ProcessName>"game.exe"</ProcessName>
</CheatTable>
"""
