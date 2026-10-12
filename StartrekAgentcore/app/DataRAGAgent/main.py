"""
DataRAGAgent — AgentCore runtime entry point.

Mirrors the behaviour of 06-inline_agent_guardrail.py:
  • Lieutenant Commander Data persona
  • Knowledge base for Star Trek facts
  • Calculator tool (eval_expression) executed locally via return-control
  • Guardrail that blocks off-topic / unsafe queries
"""

import ast
import operator as op
from typing import Any
from strands import Agent, tool
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from mcp_client.client import get_streamable_http_mcp_client
from memory.session import get_memory_session_manager

app = BedrockAgentCoreApp()
log = app.logger

# ---------------------------------------------------------------------------
# Config — mirrors the constants in 06-inline_agent_guardrail.py
# ---------------------------------------------------------------------------
KNOWLEDGE_BASE_ID = "KGXDNOMFVC"
GUARDRAIL_ID = "uhgxs1ushv9z"
GUARDRAIL_VERSION = "DRAFT"

# ---------------------------------------------------------------------------
# Persona / system prompt — same instruction as the inline agent
# ---------------------------------------------------------------------------
DEFAULT_SYSTEM_PROMPT = """
You are Lieutenant Commander Data from Star Trek: The Next Generation.

Use the attached knowledge base for questions about Commander Data.

If the user asks for arithmetic or numeric computation,
use the calculator tool.
"""

# ---------------------------------------------------------------------------
# Safe arithmetic evaluator — mirrors eval_expression from 06-*
# Only allows whitelisted AST node types; no arbitrary code execution.
# ---------------------------------------------------------------------------
ALLOWED_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.Mod: op.mod,
}


def _eval_ast(node):
    """Recursively evaluate a whitelisted AST node."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    raise ValueError(f"Unsupported expression node: {type(node)}")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
mcp_clients = [get_streamable_http_mcp_client()]

tools = []

_INLINE_FUNCTION_NAMES = set()


@tool
def eval_expression(expression: str) -> str:
    """
    Safely evaluate an arithmetic expression.

    Supports + - * / % ** and parentheses.
    Example: "2 ** 10" → "1024"
    """
    tree = ast.parse(expression.replace("^", "**"), mode="eval")
    result = _eval_ast(tree.body)
    return str(result)


tools.append(eval_expression)

# Add MCP client to tools if available
for mcp_client in mcp_clients:
    if mcp_client:
        tools.append(mcp_client)


# ---------------------------------------------------------------------------
# Agent factory — one agent per (session_id, user_id) pair
# ---------------------------------------------------------------------------
def _make_conversation_manager():
    return NullConversationManager()


def agent_factory():
    cache = {}

    def get_or_create_agent(session_id, user_id):
        _actor_id = user_id
        key = f"{session_id}/{_actor_id}"
        if key not in cache:
            cache[key] = Agent(
                model=load_model(),
                session_manager=get_memory_session_manager(session_id, _actor_id),
                conversation_manager=_make_conversation_manager(),
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                tools=tools,
                hooks=[],
            )
        return cache[key]

    return get_or_create_agent


get_or_create_agent = agent_factory()


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------
def _extract_prompt(payload: dict):
    """Accept harness-style messages[], tool_results[], or plain prompt string payloads."""
    if "messages" in payload:
        return payload["messages"]
    if "tool_results" in payload:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": tr["toolUseId"],
                            "status": tr.get("status", "success"),
                            "content": tr.get("content", []),
                        }
                    }
                    for tr in payload["tool_results"]
                ],
            }
        ]
    return payload.get("prompt", "")


def _has_inline_function_call(messages) -> bool:
    """Return True if messages contains an assistant toolUse for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES or not isinstance(messages, list):
        return False
    for msg in messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("toolUse", {}).get("name") in _INLINE_FUNCTION_NAMES:
                    return True
    return False


def _is_inline_function_call(event: dict) -> bool:
    """Check if a contentBlockStart event is for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES:
        return False
    cbs = event.get("contentBlockStart", {})
    start = cbs.get("start", {})
    tool_use = start.get("toolUse") if isinstance(start, dict) else None
    return tool_use is not None and tool_use.get("name") in _INLINE_FUNCTION_NAMES


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")

    session_id = getattr(context, "session_id", "default-session")
    user_id = getattr(context, "user_id", "default-user")
    agent = get_or_create_agent(session_id, user_id)

    prompt = _extract_prompt(payload)

    async for event in agent.stream_async(prompt):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
