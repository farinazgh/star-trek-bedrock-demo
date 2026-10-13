"""Star Trek Data agent: AgentCore Runtime + Memory + Gateway MCP tools."""

import ast
import operator

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.agent.conversation_manager.null_conversation_manager import (
    NullConversationManager,
)

from mcp_client.client import get_streamable_http_mcp_client
from memory.session import get_memory_session_manager
from model.load import load_model

app = BedrockAgentCoreApp()
log = app.logger

# The MCP client must point to StarTrekGateway. Its Knowledge Base target
# (YVCCPJU5EN) is configured in AgentCore, not hardcoded in this file.
mcp_clients = [get_streamable_http_mcp_client()]

DEFAULT_SYSTEM_PROMPT = """
You are Lieutenant Commander Data from Star Trek: The Next Generation.

When asked about Data or Star Trek facts, use the knowledge-base retrieval
MCP tools exposed by StarTrekGateway before answering. Prefer Retrieve for
simple factual lookups; use AgenticRetrieveStream for complex research when
appropriate. Ground answers in retrieved evidence. If nothing relevant is
found, say so rather than inventing information.

When asked to perform arithmetic, call the eval_expression calculator tool.
If a question needs both facts and calculations, use both tools.
Be clear, accurate, and concise.
"""


# A small, safe arithmetic evaluator: no eval(), function calls, or variables.
ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
MAX_ABS_VALUE = 1_000_000_000_000


def _evaluate(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        result = node.value
    elif isinstance(node, ast.UnaryOp) and type(node.op) in (ast.USub, ast.UAdd):
        result = ALLOWED_OPERATORS[type(node.op)](_evaluate(node.operand))
    elif isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPERATORS:
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 10 or right < 0):
            raise ValueError("Exponent must be between 0 and 10")
        result = ALLOWED_OPERATORS[type(node.op)](left, right)
    else:
        raise ValueError("Unsupported arithmetic expression")

    if not isinstance(result, (int, float, complex)) or isinstance(result, complex):
        raise ValueError("Unsupported numeric result")
    if not (float("-inf") < result < float("inf")) or abs(result) > MAX_ABS_VALUE:
        raise ValueError("Result exceeds safe limits")
    return result


@tool
def eval_expression(expression: str) -> str:
    """Calculate an arithmetic expression using + - * / % ^ and parentheses.

    Examples: '(2 * 8)^2 / 3', '12 + 7', '10 % 3'.
    """
    try:
        if len(expression) > 100:
            raise ValueError("Expression is too long")
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
        return str(_evaluate(tree.body))
    except (
        SyntaxError,
        ValueError,
        ZeroDivisionError,
        OverflowError,
        RecursionError,
    ) as exc:
        return f"Calculation error: {exc}"


@tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers and return the result."""
    return a + b


# Strands orchestrates local Python tools and Gateway MCP tools automatically.
tools = [eval_expression, add_numbers]
for mcp_client in mcp_clients:
    if mcp_client:
        tools.append(mcp_client)


def _make_conversation_manager():
    return NullConversationManager()


def agent_factory():
    cache = {}

    def get_or_create_agent(session_id, user_id):
        key = f"{session_id}/{user_id}"
        if key not in cache:
            cache[key] = Agent(
                model=load_model(),
                session_manager=get_memory_session_manager(session_id, user_id),
                conversation_manager=_make_conversation_manager(),
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                tools=tools,
                hooks=[],
            )
        return cache[key]

    return get_or_create_agent


get_or_create_agent = agent_factory()


def _extract_prompt(payload: dict):
    """Accept harness-style messages, tool results, or plain prompts."""
    if "messages" in payload:
        return payload["messages"]
    if "tool_results" in payload:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": result["toolUseId"],
                            "status": result.get("status", "success"),
                            "content": result.get("content", []),
                        }
                    }
                    for result in payload["tool_results"]
                ],
            }
        ]
    return payload.get("prompt", "")


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking DataRAGAgent...")

    session_id = getattr(context, "session_id", "default-session")
    user_id = getattr(context, "user_id", "default-user")
    agent = get_or_create_agent(session_id, user_id)
    prompt = _extract_prompt(payload)

    async for event in agent.stream_async(prompt):
        if not isinstance(event, dict) or "event" not in event:
            continue
        block_start = event["event"].get("contentBlockStart")
        if block_start is not None and not block_start.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
