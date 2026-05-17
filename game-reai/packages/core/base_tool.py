"""Base classes for all Agent tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


class ToolInput(BaseModel):
    """All tool inputs inherit from this."""

    model_config = {"extra": "forbid"}


@dataclass
class ToolResult:
    """Standardized tool output."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"success": self.success, "data": self.data}
        if self.error:
            result["error"] = self.error
        return result


T = TypeVar("T", bound=ToolInput)


class BaseTool(ABC, Generic[T]):
    """All Agent tools inherit from this.

    Subclasses define:
    - name: str          — tool identifier (used by Agent)
    - description: str   — what the tool does (goes into Agent prompt)
    - input_schema: type[T] — Pydantic model for arguments
    """

    name: str
    description: str
    input_schema: type[T]

    @abstractmethod
    async def _run(self, input_data: T) -> ToolResult: ...

    async def run(self, **kwargs: Any) -> ToolResult:
        """Validate input and execute. This is what the Agent calls."""
        validated = self.input_schema(**kwargs)
        return await self._run(validated)

    def to_langchain_tool(self) -> Any:
        """Convert to a LangChain StructuredTool for the Agent."""
        from langchain_core.tools import StructuredTool

        async def _wrapper(**kwargs: Any) -> str:
            result = await self.run(**kwargs)
            if result.success:
                return str(result.data)
            return f"Error: {result.error}"

        return StructuredTool(
            name=self.name,
            description=self.description,
            args_schema=self.input_schema,
            coroutine=_wrapper,
        )
