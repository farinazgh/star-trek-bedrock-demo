"""Step 5 (Lambda variant): Same as 05-return_control_execution.py but using a Lambda executor.

Approach: invoke_inline_agent with Lambda executor — the agent calls the Lambda directly.
No returnControl event is emitted. AWS invokes the Lambda, gets the result, and resumes
all within the same invoke_inline_agent call. No second call needed.

The orchestrator produces these events per query:
  1. invocationInput        - orchestrator decides to call the calculator tool
  2. [Lambda invocation]    - AWS invokes the Lambda automatically, no caller involvement
  3. invocationInput        - agent receives the Lambda result
  4. modelInvocationInput   - result is packaged into a prompt and sent to Claude
  5. modelInvocationOutput  - Claude returns its final answer
  6. observation (FINISH)   - orchestrator emits the final cleaned-up response

Compared to RETURN_CONTROL:
  - no returnControl event, no second invoke_inline_agent call, no local execution
  - simpler caller code, but zero control over what the Lambda does before agent sees it
"""

import json
import uuid

import boto3

REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "KGXDNOMFVC"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
LAMBDA_ARN = "arn:aws:lambda:us-east-1:<account-id>:function:calculator"
QUERY = "Compute ((2*8)^2)/3"

# Inline means the agent is defined entirely in code (no pre-configured agent in the Bedrock console needed)
client = boto3.client("bedrock-agent-runtime", region_name=REGION)

INSTRUCTION = """
You are Lieutenant Commander Data from Star Trek: The Next Generation.

Use the attached knowledge base for questions about Commander Data.

If the user asks for arithmetic or numeric computation,
use the calculator action group.
"""

# Lambda executor means the agent invokes the Lambda directly —
# no returnControl event is emitted, no second invoke_inline_agent call needed
CALCULATOR_ACTION_GROUP = {
    "actionGroupName": "CalculatorActionGroup",
    "description": "Performs arithmetic calculations.",
    "actionGroupExecutor": {"lambda": LAMBDA_ARN},
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
    """Invoke a Bedrock inline agent with a Lambda executor and return the answer."""
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

        # no returnControl handling needed — Lambda is invoked automatically by AWS;
        # the agent resumes internally without any caller involvement

        # chunk events carry the actual answer text, streamed in pieces;
        # collect them all and join at the end to form the full response
        if "chunk" in event:
            output.append(event["chunk"]["bytes"].decode("utf-8"))

    return "".join(output)


if __name__ == "__main__":
    answer = run_inline_agent(QUERY)
    print("\n--- ANSWER ---")
    print(answer)
