"""Step 5: Execute a RETURN_CONTROL action locally and resume the Bedrock agent.

Approach: invoke_inline_agent with RETURN_CONTROL — same as step 4, but the caller
catches the returnControl event, executes the function locally, and resumes the
agent on the same session with the result. This completes the full tool-use loop.

The orchestrator produces these events per query:
  1. invocationInput        - orchestrator decides to call the calculator tool
  2. observation (tool)     - agent emits returnControl and pauses
  3. [local execution]      - caller runs eval_expression and gets the result
  4. invocationInput        - resumed agent receives the result
  5. modelInvocationInput   - result is packaged into a prompt and sent to Claude
  6. modelInvocationOutput  - Claude returns its final answer
  7. observation (FINISH)   - orchestrator emits the final cleaned-up response
"""

import ast
import json
import operator as op
import uuid

import boto3

REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "KGXDNOMFVC"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
QUERY = "Compute ((2*8)^2)/3"

# Inline means the agent is defined entirely in code (no pre-configured agent in the Bedrock console needed)
client = boto3.client("bedrock-agent-runtime", region_name=REGION)

INSTRUCTION = """
You are Lieutenant Commander Data from Star Trek: The Next Generation.

Use the attached knowledge base for questions about Commander Data.

If the user asks for arithmetic or numeric computation,
use the calculator action group.
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

KNOWLEDGE_BASES = [
    {
        "knowledgeBaseId": KNOWLEDGE_BASE_ID,
        "description": "Contains information about Lieutenant Commander Data.",
        "retrievalConfiguration": {"vectorSearchConfiguration": {"numberOfResults": 3}},
    }
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


def run_inline_agent(query: str) -> str:
    """Invoke a Bedrock inline agent, execute any tool calls locally, resume, and return the answer."""
    session_id = str(uuid.uuid4())

    response = client.invoke_inline_agent(
        sessionId=session_id,
        foundationModel=MODEL_ID,
        instruction=INSTRUCTION,
        inputText=query,
        knowledgeBases=KNOWLEDGE_BASES,
        actionGroups=[CALCULATOR_ACTION_GROUP],
        enableTrace=True,
    )

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

    # step 5 lesson: agent paused and handed control back via returnControl,
    # the caller caught it, executed the function locally, and resumed the
    # agent on the same session — completing the full tool-use loop
    # no tool call: agent already finished normally
    if return_control is None:
        return "".join(output)

    # extract the function invocation details from the returnControl payload
    invocation_id = return_control["invocationId"]
    function_input = return_control["invocationInputs"][0]["functionInvocationInput"]
    action_group = function_input["actionGroup"]
    function_name = function_input["function"]
    parameters = {p["name"]: p["value"] for p in function_input["parameters"]}

    # execute the requested function locally
    print("\n========== LOCAL FUNCTION EXECUTION ==========")
    print("Function:", function_name)
    print("Parameters:", parameters)

    if function_name == "eval_expression":
        result = eval_expression(parameters["expression"])
    else:
        raise RuntimeError(f"Unknown function: {function_name}")

    print("Result:", result)

    # resume the SAME agent session with the function result injected
    resumed_response = client.invoke_inline_agent(
        sessionId=session_id,
        foundationModel=MODEL_ID,
        instruction=INSTRUCTION,
        inputText="",
        knowledgeBases=KNOWLEDGE_BASES,
        actionGroups=[CALCULATOR_ACTION_GROUP],
        inlineSessionState={
            "invocationId": invocation_id,
            "returnControlInvocationResults": [
                {
                    "functionResult": {
                        "actionGroup": action_group,
                        "function": function_name,
                        "responseBody": {"TEXT": {"body": result}},
                    }
                }
            ],
        },
        enableTrace=True,
    )

    final_output = []

    for event in resumed_response["completion"]:

        # trace events show the agent's step-by-step orchestration:
        # KB lookups, model invocations, and intermediate reasoning
        if "trace" in event:
            print("\n========== RESUMED AGENT TRACE ==========")
            print(json.dumps(event["trace"], indent=2, default=str))

        # chunk events carry the actual answer text, streamed in pieces;
        # collect them all and join at the end to form the full response
        if "chunk" in event:
            final_output.append(event["chunk"]["bytes"].decode("utf-8"))

    return "".join(final_output)


if __name__ == "__main__":
    answer = run_inline_agent(QUERY)
    print("\n--- ANSWER ---")
    print(answer)
