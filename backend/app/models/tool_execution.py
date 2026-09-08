"""Non-persistent, safe trace value for an allowlisted MCP call."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolExecution:
    tool_name: str
    status: str
    error_code: str | None = None
