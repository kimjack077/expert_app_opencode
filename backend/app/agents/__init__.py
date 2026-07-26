"""共享 Agent 运行时。

此前 EFIS 有三条各自为政的 LLM 调用路径（agent_service / evidence_agent_service /
audit_agent），各写各的提示词拼装、JSON 修复、模型选择、调用日志。本包把
「读取+推理」这一层收敛成一套可复用运行时：

- ``llm_gateway``：统一 LLM 调用入口，负责模型分层、重试、统一 ``LLMCallLog``。
- ``tool_registry``：可调用工具注册表，供对话 Agent 与规划器共用同一批工具。
- ``planner``：把目标拆解为多步工具调用的轻量规划器（人在回路）。

写操作的确认执行仍由 ``services.agent_actions``（动作注册表）负责，二者分工：
tool_registry 管「读取/推理」，agent_actions 管「经用户确认后的写入」。
"""

from app.agents.llm_gateway import LLMGateway, LLMTier, llm_gateway
from app.agents.tool_registry import AgentTool, tool_registry

__all__ = [
    "LLMGateway",
    "LLMTier",
    "llm_gateway",
    "AgentTool",
    "tool_registry",
]
