"""CLI entry point — typer app with analyze, scan, dump subcommands."""

from __future__ import annotations

from pathlib import Path

import typer

from packages.core.agent import GameReverseAgent
from packages.core.config import Config
from packages.tools.ce_parser import CEParser
from packages.tools.memory import (
    FindPatternTool,
    FollowPointerChainTool,
    GetProcessInfoTool,
    ReadMemoryTool,
)

app = typer.Typer(help="game-reai: AI 游戏逆向辅助工具")


@app.command()
def analyze(
    file: Path | None = typer.Option(None, "-f", "--file", help="CE XML 导出文件"),
    addresses: str | None = typer.Option(None, "-a", "--addresses", help="地址列表，逗号分隔"),
    pid: int | None = typer.Option(None, "-p", "--pid", help="目标进程 PID"),
    output: Path | None = typer.Option(None, "-o", "--output", help="输出脚本路径"),
    fmt: str = typer.Option("ce_lua", "--format", help="输出格式: ce_lua | python | cpp"),
    verbose: bool = typer.Option(False, "--verbose", help="输出 Agent 思考过程"),
) -> None:
    """分析游戏内存地址，自动生成基址+偏移遍历脚本。"""
    config = Config()
    if not config.is_configured:
        typer.echo("错误: 请设置 ANTHROPIC_API_KEY 环境变量", err=True)
        raise typer.Exit(1)

    agent = GameReverseAgent(config)
    agent.register_tool(CEParser())
    agent.register_tool(GetProcessInfoTool())
    agent.register_tool(ReadMemoryTool())
    agent.register_tool(FollowPointerChainTool())
    agent.register_tool(FindPatternTool())

    # Build task prompt
    prompt_parts = []
    if file:
        typer.echo(f"解析 CE 导出: {file}")
        parser = CEParser()
        import asyncio

        result = asyncio.run(parser.run(file_path=str(file)))
        if result.success:
            prompt_parts.append(f"CE 搜索结果:\n{result.data['summary']}")
            prompt_parts.append(f"详细数据:\n{result.data['parsed']}")
        else:
            typer.echo(f"解析失败: {result.error}", err=True)
            raise typer.Exit(1)

    if addresses:
        prompt_parts.append(f"目标地址: {addresses}")

    if not prompt_parts:
        prompt_parts.append("请帮我分析目标进程的内存布局，找出可能的基址和指针链。")

    task_prompt = "\n\n".join(prompt_parts)

    typer.echo("Agent 分析中...")
    import asyncio

    analysis_result = asyncio.run(agent.analyze(task_prompt))

    typer.echo("\n" + "=" * 60)
    typer.echo(analysis_result)

    if output:
        output.write_text(analysis_result, encoding="utf-8")
        typer.echo(f"\n脚本已保存到: {output}")


@app.command()
def scan(
    pid: int = typer.Option(..., "-p", "--pid", help="目标进程 PID"),
    module: str = typer.Option(..., "-m", "--module", help="模块名"),
    pattern: str = typer.Option(..., "--pattern", help="字节模式 (?? = 通配)"),
) -> None:
    """在进程模块中做 AOB 扫描。"""
    tool = FindPatternTool()
    import asyncio

    result = asyncio.run(tool.run(pid=pid, module_name=module, pattern=pattern))
    if result.success:
        typer.echo(f"匹配 {result.data['match_count']} 处:")
        for addr in result.data["matches"]:
            typer.echo(f"  {addr}")
    else:
        typer.echo(f"扫描失败: {result.error}", err=True)


@app.command()
def dump(
    pid: int = typer.Option(..., "-p", "--pid", help="目标进程 PID"),
    address: str = typer.Option(..., "-a", "--address", help="起始地址 (hex)"),
    size: int = typer.Option(256, "-s", "--size", help="dump 大小"),
    output: Path | None = typer.Option(None, "-o", "--output", help="输出文件"),
) -> None:
    """Dump 进程内存到文件或终端。"""
    tool = ReadMemoryTool()
    import asyncio

    addr_int = int(address, 0)
    result = asyncio.run(tool.run(pid=pid, address=addr_int, size=size))
    if result.success:
        typer.echo(f"Address: {result.data['address']}")
        typer.echo(f"Hex: {result.data['hex']}")
        if output:
            output.write_text(str(result.data), encoding="utf-8")
    else:
        typer.echo(f"Dump 失败: {result.error}", err=True)


if __name__ == "__main__":
    app()
