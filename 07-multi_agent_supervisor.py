"""Step 7: Inline multi-agent collaboration with a supervisor and specialist SUBAGENTs.

Approach: invoke_inline_agent with SUPERVISOR mode — the supervisor delegates to specialist
SUBAGENTs based on the query. RETURN_CONTROL bubbles up from a SUBAGENT through
the supervisor back to the caller.

Architecture:
  User
    -> DataSupervisor
         -> DataKnowledgeAgent -> Bedrock Knowledge Base
         -> CalculatorAgent    -> Calculator Action Group
                                    -> RETURN_CONTROL
                                    -> local Python calculator
                                    -> resume supervisor

The orchestrator produces these events per query:
  1. invocationInput        - supervisor delegates to the appropriate SUBAGENT
  2. [SUBAGENT runs]    - SUBAGENT queries KB or emits returnControl
  3. returnControl          - CalculatorAgent pauses and hands invocation to caller
  4. [local execution]      - caller runs eval_expression and gets the result
  5. invocationInput        - resumed supervisor receives the result
  6. modelInvocationInput   - result is packaged into a prompt and sent to Nova Pro
  7. modelInvocationOutput  - Nova Pro returns its final answer
  8. observation (FINISH)   - orchestrator emits the final cleaned-up response
"""

import ast
import json
import operator as op
import uuid

import boto3

REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "KGXDNOMFVC"
# Nova Pro is required for multi-agent collaboration — not all models support supervisor mode
MODEL_ID = "us.amazon.nova-pro-v1:0"
GUARDRAIL_ID = "YOUR_GUARDRAIL_ID"
GUARDRAIL_VERSION = "DRAFT"
QUERY = "Tell me whether Data experiences emotions, and also compute ((2*8)^2)/3."

# Inline means the agent is defined entirely in code (no pre-configured agent in the Bedrock console needed)
client = boto3.client("bedrock-agent-runtime", region_name=REGION)

# supervisor delegates to specialist SUBAGENTs — it does not answer directly
SUPERVISOR_INSTRUCTIONS = """
You are the supervisor for a team of specialist agents.

Delegate factual questions about Lieutenant Commander Data
to DataKnowledgeAgent.

Delegate arithmetic and numeric calculations
to CalculatorAgent.

Do not perform those specialist tasks yourself.

If a user request requires more than one SUBAGENT,
coordinate their results and produce one concise final answer.
"""

# RETURN_CONTROL means the agent will NOT execute the function itself;
# instead it pauses and hands the invocation request back to the caller
CALCULATOR_ACTION_GROUP = {
    "actionGroupName": "CalculatorActionGroup",
    "description": "Performs arithmetic calculations.",
    "actionGroupExecutor": {"customControl": "RETURN_CONTROL"},
    "functionSchema": {
        "functions": [
            {
                "name": "eval_expression",
                "description": (
                    "Evaluate an arithmetic expression using "
                    "+ - * / % ** and parentheses."
                ),
                "parameters": {
                    "expression": {
                        "description": "The arithmetic expression to evaluate.",
                        "type": "string",
                        "required": True,
                    }
                },
            }
        ]
    },
}

# guardrail intercepts blocked topics before the agent processes them;
# it stays attached on resume so the final answer is also filtered
GUARDRAIL_CONFIGURATION = {
    "guardrailIdentifier": GUARDRAIL_ID,
    "guardrailVersion": GUARDRAIL_VERSION,
}

# DataKnowledgeAgent — specialist for KB lookups about Lt. Commander Data
RAG_DATA_SUBAGENT = {
    "agentName": "DataKnowledgeAgent",
    "foundationModel": MODEL_ID,
    "instruction": (
        "You are an expert on Lieutenant Commander Data from "
        "Star Trek: The Next Generation. "
        "Use your attached knowledge base to answer factual "
        "questions about Data accurately and concisely."
    ),
    "knowledgeBases": [
        {
            "knowledgeBaseId": KNOWLEDGE_BASE_ID,
            "description": "Contains dialogue and information about Lieutenant Commander Data.",
            "retrievalConfiguration": {
                "vectorSearchConfiguration": {"numberOfResults": 3}
            },
        }
    ],
    "guardrailConfiguration": GUARDRAIL_CONFIGURATION,
    "agentCollaboration": "DISABLED",
}

# CalculatorAgent — specialist for arithmetic, uses RETURN_CONTROL to hand execution to caller
TOOL_CALCULATOR_SUBAGENT = {
    "agentName": "CalculatorAgent",
    "foundationModel": MODEL_ID,
    "instruction": (
        "You are a calculator specialist. "
        "For every arithmetic or numeric computation, use the "
        "eval_expression function from the calculator action group. "
        "Do not calculate the answer yourself."
    ),
    "actionGroups": [CALCULATOR_ACTION_GROUP],
    "guardrailConfiguration": GUARDRAIL_CONFIGURATION,
    "agentCollaboration": "DISABLED",
}

SUBAGENTS = [
    RAG_DATA_SUBAGENT,
    TOOL_CALCULATOR_SUBAGENT,
]

# SUBAGENTInstruction is the routing signal — supervisor reads this to decide
# which SUBAGENT to delegate to, same principle as KB description in step 3
SUBAGENT_CONFIGURATIONS = [
    {
        "SUBAGENTName": "DataKnowledgeAgent",
        "SUBAGENTInstruction": (
            "Use this SUBAGENT for questions about Lieutenant "
            "Commander Data, including his history, behavior, ethics, "
            "emotions, experiences, and Star Trek TNG information."
        ),
        "relayConversationHistory": "TO_SUBAGENT",
    },
    {
        "SUBAGENTName": "CalculatorAgent",
        "SUBAGENTInstruction": (
            "Use this SUBAGENT whenever arithmetic or numeric "
            "computation is required."
        ),
        "relayConversationHistory": "TO_SUBAGENT",
    },
]

# safe arithmetic evaluator — only allows whitelisted AST node types,
# preventing arbitrary code execution via eval()
ALLOWED_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.Mod: op.mod,
}


def eval_ast(node):
    """Recursively evaluate a whitelisted AST node."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](eval_ast(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](eval_ast(node.left), eval_ast(node.right))
    raise ValueError("Unsupported expression")


def eval_expression(expression: str) -> str:
    """Safely evaluate an arithmetic expression string and return the result."""
    tree = ast.parse(expression.replace("^", "**"), mode="eval")
    return str(eval_ast(tree.body))


def process_response(response):
    """Consume the event stream and return the output text and returnControl payload."""
    return_control = None
    output = []

    for event in response["completion"]:

        # trace events show the agent's step-by-step orchestration:
        # KB lookups, model invocations, and intermediate reasoning
        if "trace" in event:
            print("\n========== AGENT TRACE ==========")
            print(json.dumps(event["trace"], indent=2, default=str))

        # returnControl events signal the agent has paused and is requesting
        # the caller to execute a function and return the result
        if "returnControl" in event:
            return_control = event["returnControl"]
            print("\n========== RETURN CONTROL ==========")
            print(json.dumps(return_control, indent=2, default=str))

        # chunk events carry the actual answer text, streamed in pieces;
        # collect them all and join at the end to form the full response
        if "chunk" in event:
            output.append(event["chunk"]["bytes"].decode("utf-8"))

    return "".join(output), return_control


def invoke_supervisor(session_id: str, input_text: str, inline_session_state=None):
    """Invoke the supervisor agent, optionally resuming with a tool result."""
    params = {
        "sessionId": session_id,
        "agentName": "DataSupervisor",
        "agentCollaboration": "SUPERVISOR",
        "foundationModel": MODEL_ID,
        "instruction": SUPERVISOR_INSTRUCTIONS,
        "inputText": input_text,
        "SUBAGENTs": SUBAGENTS,
        "SUBAGENTConfigurations": SUBAGENT_CONFIGURATIONS,
        "guardrailConfiguration": GUARDRAIL_CONFIGURATION,
        "enableTrace": True,
    }
    if inline_session_state is not None:
        params["inlineSessionState"] = inline_session_state
    return client.invoke_inline_agent(**params)


def run_inline_agent(query: str) -> str:
    """Invoke the supervisor, execute any SUBAGENT tool calls locally, resume, and return the answer."""
    session_id = str(uuid.uuid4())

    response = invoke_supervisor(session_id=session_id, input_text=query)
    output, return_control = process_response(response)

    # no tool call: supervisor finished normally or guardrail blocked the query
    if return_control is None:
        return output

    # extract the function invocation details from the returnControl payload
    invocation_id = return_control["invocationId"]
    function_input = return_control["invocationInputs"][0]["functionInvocationInput"]
    action_group = function_input["actionGroup"]
    function_name = function_input["function"]
    parameters = {p["name"]: p["value"] for p in function_input["parameters"]}
    # agentId identifies which SUBAGENT issued the returnControl —
    # must be included in the resume payload so the supervisor routes the result correctly
    agent_id = function_input.get("agentId")
    SUBAGENT_name = function_input.get("SUBAGENTName")

    # execute the requested function locally
    print("\n========== LOCAL FUNCTION EXECUTION ==========")
    print("SUBAGENT:", SUBAGENT_name)
    print("Function:", function_name)
    print("Parameters:", parameters)

    if function_name == "eval_expression":
        result = eval_expression(parameters["expression"])
    else:
        raise RuntimeError(f"Unknown function: {function_name}")

    print("Result:", result)

    # build the function result — include agentId so the supervisor knows
    # which SUBAGENT to resume (not needed in single-agent RETURN_CONTROL)
    function_result = {
        "actionGroup": action_group,
        "function": function_name,
        "responseBody": {"TEXT": {"body": result}},
    }
    if agent_id:
        function_result["agentId"] = agent_id

    # resume the SAME supervisor session with the function result injected
    resumed_response = invoke_supervisor(
        session_id=session_id,
        input_text="",
        inline_session_state={
            "invocationId": invocation_id,
            "returnControlInvocationResults": [{"functionResult": function_result}],
        },
    )

    final_output, _ = process_response(resumed_response)
    return final_output


if __name__ == "__main__":
    answer = run_inline_agent(QUERY)
    print("\n--- ANSWER ---")
    print(answer)
