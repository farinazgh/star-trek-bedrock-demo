"""Step 4: Bedrock inline agent with a calculator action group.

Approach: invoke_inline_agent with RETURN_CONTROL — agent decides to call a tool
and emits a returnControl event, but execution stops there. The function is never
run and the agent never resumes. This is intentionally incomplete to contrast with step 5.

The orchestrator produces these events per query:
  1. invocationInput       - orchestrator decides to call the calculator tool
  2. observation (tool)    - agent emits returnControl and pauses, waiting for execution
"""

import json
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


def run_inline_agent(query: str) -> str:
    """Invoke a Bedrock inline agent with an action group and return the answer."""
    response = client.invoke_inline_agent(
        sessionId=str(uuid.uuid4()),
        foundationModel=MODEL_ID,
        instruction=INSTRUCTION,
        inputText=query,
        knowledgeBases=KNOWLEDGE_BASES,
        actionGroups=[CALCULATOR_ACTION_GROUP],
        enableTrace=True,
    )

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
            print("\n========== RETURN CONTROL ==========")
            print(json.dumps(event["returnControl"], indent=2, default=str))

        # chunk events carry the actual answer text, streamed in pieces;
        # collect them all and join at the end to form the full response
        if "chunk" in event:
            output.append(event["chunk"]["bytes"].decode("utf-8"))

    # step 4 lesson: agent paused and handed control back via returnControl,
    # but nobody caught it — the function was never executed and the agent
    # never resumed, so no final answer is produced
    return "".join(output)


if __name__ == "__main__":
    answer = run_inline_agent(QUERY)
    print("\n--- ANSWER ---")
    print(answer)
