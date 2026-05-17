"""Streamlit Web UI for game-reai."""

from __future__ import annotations

import asyncio
from pathlib import Path

import streamlit as st

# ── Helper: Run analyze with XML content ─────────────────────────────────


def _run_analyze_xml(
    api_key: str,
    model: str,
    max_iterations: int,
    temperature: float,
    xml_content: str,
) -> None:
    """Parse XML, run Agent, display result."""
    import tempfile

    from packages.core.agent import GameReverseAgent
    from packages.core.config import Config
    from packages.tools.ce_parser import CEParser
    from packages.tools.memory import (
        FindPatternTool,
        FollowPointerChainTool,
        GetProcessInfoTool,
        ReadMemoryTool,
    )

    # Save XML to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(xml_content)
        tmp_path = Path(f.name)

    try:
        # Parse
        with st.spinner("解析 CE XML..."):
            parser = CEParser()
            parse_result = asyncio.run(parser.run(file_path=str(tmp_path)))

        if not parse_result.success:
            st.error(f"XML 解析失败: {parse_result.error}")
            return

        st.info(parse_result.data["summary"])

        with st.expander("解析详情"):
            entries = parse_result.data["parsed"].entries
            for e in entries:
                offs = " → ".join(f"0x{o:x}" for o in e.offsets) if e.offsets else "无"
                st.text(
                    f"  {e.description:20s}  {e.address:#x}  {e.type_name:10s}  "
                    f"={e.value:10s}  偏移: {offs}"
                )

        # Run Agent
        config = Config(
            anthropic_api_key=api_key,
            model=model,
            max_agent_iterations=max_iterations,
            temperature=temperature,
        )

        agent = GameReverseAgent(config)
        agent.register_tool(CEParser())
        agent.register_tool(GetProcessInfoTool())
        agent.register_tool(ReadMemoryTool())
        agent.register_tool(FollowPointerChainTool())
        agent.register_tool(FindPatternTool())

        task_prompt = (
            f"CE 搜索结果:\n{parse_result.data['summary']}\n\n"
            f"详细数据:\n{parse_result.data['parsed']}\n\n"
            "请找出这些地址的基址+偏移，生成 CE Lua 遍历脚本。"
        )

        with st.spinner("🤖 Claude Agent 分析中..."):
            analysis = asyncio.run(agent.analyze(task_prompt))

        st.subheader("生成的 CE Lua 脚本")

        # Extract lua blocks from analysis
        if "```lua" in analysis:
            parts = analysis.split("```lua")
            for part in parts[1:]:
                end = part.find("```")
                if end > 0:
                    lua_code = part[:end].strip()
                    st.code(lua_code, language="lua")
                    st.download_button(
                        "⬇️ 下载脚本",
                        lua_code,
                        file_name="generated_script.lua",
                        mime="text/plain",
                    )
        else:
            st.markdown(analysis)

    finally:
        tmp_path.unlink(missing_ok=True)


# ── Page config ──────────────────────────────────────────────────────────

st.set_page_config(page_title="game-reai", page_icon="🎮", layout="wide")

st.title("🎮 game-reai — AI 游戏逆向辅助工具")
st.caption("上传 CE 搜索结果 → Claude 自动生成基址+偏移遍历脚本")

# ── Sidebar ──────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ 配置")

    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="存储在会话中，不会上传到服务器",
    )

    model = st.selectbox(
        "模型",
        ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"],
        index=0,
    )

    max_iterations = st.slider("Agent 最大迭代", 3, 30, 15)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.1, 0.05)

    st.divider()

    if not api_key:
        st.warning("⚠️ 请输入 API Key 才能使用 AI 分析功能")
        st.info("💡 内存读取和 AOB 扫描不需要 API Key")

    st.divider()
    st.caption("game-reai v0.1.0")

# ── Tabs ─────────────────────────────────────────────────────────────────

tab_analyze, tab_memory, tab_scan = st.tabs(["🔍 分析地址", "📟 内存查看", "🔎 AOB 扫描"])

# ── Tab 1: Analyze ───────────────────────────────────────────────────────

with tab_analyze:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("输入")

        input_mode = st.radio("输入方式", ["上传 CE XML 文件", "手动输入"], horizontal=True)

        ce_content: str | None = None

        if input_mode == "上传 CE XML 文件":
            uploaded = st.file_uploader("选择 Cheat Engine 导出的 .xml 文件", type=["xml"])
            if uploaded is not None:
                ce_content = uploaded.getvalue().decode("utf-8")
                st.success(f"已加载: {uploaded.name} ({len(ce_content)} 字节)")
                with st.expander("预览 XML"):
                    st.code(ce_content[:2000], language="xml")

        else:
            process_input = st.text_input("进程名", placeholder="game.exe")
            st.caption("或")
            pid_input = st.number_input("PID", min_value=0, step=1, format="%d")
            address_input = st.text_area(
                "地址列表（一行一个）",
                placeholder="game.exe+0x2A3B4C\nengine.dll+0x123456\n0x7FF80000",
            )

        run_clicked = st.button("🚀 开始分析", type="primary", use_container_width=True)

    with col_right:
        st.subheader("结果")

        if run_clicked:
            if not api_key:
                st.error("请先在侧栏输入 API Key")
            elif ce_content:
                _run_analyze_xml(api_key, model, max_iterations, temperature, ce_content)
            else:
                st.error("请上传 CE XML 文件")
        else:
            st.info("点击「开始分析」后，Claude Agent 会分析地址并生成 CE Lua 脚本")

# ── Tab 2: Memory Viewer ─────────────────────────────────────────────────

with tab_memory:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("附加进程")

        attach_mode = st.radio("附加方式", ["进程名", "PID"], horizontal=True)
        if attach_mode == "进程名":
            proc_name = st.text_input("进程名", "notepad.exe")
        else:
            proc_pid = st.number_input("PID", min_value=0, step=1, format="%d")

        addr_hex = st.text_input("起始地址 (hex)", "0x7FF80000")
        read_size = st.number_input("读取大小 (bytes)", 16, 4096, 256, 16)

        read_clicked = st.button("📟 读取内存", use_container_width=True)

    with col2:
        st.subheader("内存数据")

        if read_clicked:
            try:
                from packages.tools.memory import MemoryReader

                reader = MemoryReader()
                if attach_mode == "进程名" and proc_name:
                    info = reader.attach_by_name(proc_name)
                elif attach_mode == "PID" and proc_pid > 0:
                    info = reader.attach(proc_pid)
                else:
                    st.error("请输入进程名或 PID")
                    st.stop()

                st.success(f"已附加: {info.name} (PID: {info.pid}, {info.arch})")

                addr = int(addr_hex, 0)
                data = reader.read(addr, read_size)

                # Hex dump
                hex_lines = []
                for i in range(0, len(data), 16):
                    chunk = data[i : i + 16]
                    hex_part = " ".join(f"{b:02x}" for b in chunk)
                    ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                    hex_lines.append(f"{addr + i:016X}  {hex_part:<48}  {ascii_part}")

                st.code("\n".join(hex_lines), language="text")

                # Module info
                with st.expander(f"已加载模块 ({len(info.modules)})"):
                    for m in info.modules[:50]:
                        st.text(f"{m.name:40s}  base={m.base:#018x}  size={m.size:#x}")

            except Exception as e:
                st.error(f"读取失败: {e}")

# ── Tab 3: AOB Scanner ───────────────────────────────────────────────────

with tab_scan:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("扫描参数")

        scan_pid = st.number_input("进程 PID", min_value=0, step=1, format="%d", key="scan_pid")
        scan_module = st.text_input("模块名", "game.exe")
        scan_pattern = st.text_input(
            "字节模式",
            placeholder="48 8B 05 ?? ?? ?? ?? 48 85 C0",
            help="用 ?? 表示通配符，空格分隔",
        )

        scan_clicked = st.button("🔎 扫描", use_container_width=True)

    with col2:
        st.subheader("匹配结果")

        if scan_clicked:
            if not scan_pid or not scan_module or not scan_pattern:
                st.error("请填写完整参数")
            else:
                try:
                    from packages.tools.memory import MemoryReader

                    reader = MemoryReader()
                    reader.attach(scan_pid)

                    module = reader.find_module(scan_module)
                    if module is None:
                        st.error(f"模块 '{scan_module}' 未找到")
                    else:
                        st.info(f"模块基址: {module.base:#x}, 大小: {module.size:#x}")

                        matches = reader.scan_pattern(module.base, module.size, scan_pattern)

                        st.success(f"找到 {len(matches)} 处匹配")

                        for addr in matches[:100]:
                            offset = addr - module.base
                            st.code(f"{scan_module}+{offset:#x}  ({addr:#018x})")

                        if len(matches) > 100:
                            st.caption(f"... 以及另外 {len(matches) - 100} 处")

                except Exception as e:
                    st.error(f"扫描失败: {e}")
