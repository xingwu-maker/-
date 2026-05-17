"""ReAct Agent for game reverse engineering.

Uses langchain + langchain-anthropic with custom tools.
The Agent observes memory state, decides next action, and iteratively
finds base addresses and pointer offsets.
"""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool as LCTool
from pydantic import SecretStr

from packages.core.base_tool import BaseTool
from packages.core.config import Config

SYSTEM_PROMPT = """你是一个游戏逆向工程专家。你有以下工具可用：

- get_process_info: 获取进程的模块信息（基址、大小）
- read_memory: 读取进程指定地址的内存
- follow_pointer_chain: 跟随指针链，找到最终值的路径
- find_pattern: 在模块中搜索字节模式（AOB scan）
- parse_ce_export: 解析 Cheat Engine 的 XML 导出文件

## 你的工作流程

当用户给你 Cheat Engine 的搜索结果时：

1. 先分析地址的分布 — 是否集中在某几个模块附近
2. 对于每个感兴趣的地址，用 read_memory 查看周围内存
3. 尝试用 follow_pointer_chain 找到稳定的基址+偏移路径
4. 如果有多条候选链，每条都要验证（read_memory 确认值）
5. 用 find_pattern 确认基址的特异性（是否唯一匹配）

## 重要规则

- 每一步指针读取后要检查有效性
- 基址必须用模块名+偏移表示，不要用绝对地址
- 如果信心不足，标注置信度并说明原因

## 输出格式

当你完成分析后，输出完整的 CE Lua 脚本，用 ```lua 代码块包裹。
脚本中必须包含：
1. 基址（模块+偏移）
2. 指针链的每一步（偏移值）
3. 最终值读取（类型正确）
4. 每一步的 nil check

示例：
```lua
-- 基址: game.exe+0x2A3B4C
-- 偏移链: 0x10 -> 0x20 -> 0x8
-- 值类型: 4 bytes (int)
local base = getAddress("game.exe+2A3B4C")
local p1 = readPointer(base)
if p1 then
  local p2 = readPointer(p1 + 0x10)
  local p3 = readPointer(p2 + 0x20)
  if p3 then
    local value = readInteger(p3 + 0x8)
    print(string.format("Value: %d", value))
  end
end
```
"""


class GameReverseAgent:
    """ReAct Agent that iteratively analyzes game memory to find pointer chains."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        if not self.config.is_configured:
            raise ValueError("ANTHROPIC_API_KEY 未设置。请设置环境变量或在 Config 中指定。")
        self._llm = ChatAnthropic(  # type: ignore[call-arg]
            model=self.config.model,
            api_key=SecretStr(self.config.anthropic_api_key),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        self._tools: list[BaseTool[Any]] = []
        self._lc_tools: list[LCTool] = []

    def register_tool(self, tool: BaseTool[Any]) -> None:
        """Register a tool for the Agent to use."""
        self._tools.append(tool)
        self._lc_tools.append(tool.to_langchain_tool())

    async def analyze(self, task_prompt: str) -> str:
        """Run the ReAct loop: observe → think → act → observe → ...

        Returns the final output (CE Lua script).
        """
        if not self._tools:
            return "错误：未注册任何 Tool。请先调用 register_tool()。"

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=task_prompt),
        ]

        # Bind tools to LLM
        llm_with_tools = self._llm.bind_tools(self._lc_tools)

        for _ in range(self.config.max_agent_iterations):
            response = await llm_with_tools.ainvoke(messages)

            # Check if LLM wants to call tools
            tool_calls = getattr(response, "tool_calls", None)
            if not tool_calls:
                # No tool calls — Agent is done
                return str(response.content)

            # Add assistant message
            messages.append(response)

            # Execute each tool call
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]

                tool = self._find_tool(tool_name)
                if tool is None:
                    result = f"Error: 未知工具 '{tool_name}'"
                else:
                    try:
                        result_obj = await tool.run(**tool_args)
                        result = (
                            str(result_obj.data)
                            if result_obj.success
                            else f"Error: {result_obj.error}"
                        )
                    except Exception as e:
                        result = f"Error: 工具执行异常: {e}"

                messages.append(
                    ToolMessage(
                        content=result,
                        tool_call_id=tc["id"],
                    )
                )

        return "达到最大迭代次数，Agent 未完成分析。"

    def _find_tool(self, name: str) -> BaseTool[Any] | None:
        for t in self._tools:
            if t.name == name:
                return t
        return None
