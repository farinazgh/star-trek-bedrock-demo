"""Step 2: Invoke one Bedrock inline agent with one Knowledge Base.

Approach: invoke_inline_agent — agent orchestrator manages KB retrieval and generation.
The orchestrator produces 5 trace events per query:
  1. invocationInput       - orchestrator decides to query the knowledge base
  2. observation (KB)      - KB returns the 3 retrieved chunks
  3. modelInvocationInput  - KB results are packaged into a prompt and sent to Claude
  4. modelInvocationOutput - Claude returns its answer with token usage
  5. observation (FINISH)  - orchestrator emits the final cleaned-up response
"""

import json

import boto3

REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "KGXDNOMFVC"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
QUERY = "Do you experience emotions?"

# Inline means the agent is defined entirely in code (no pre-configured agent in the Bedrock console needed)
client = boto3.client("bedrock-agent-runtime", region_name=REGION)


def run_inline_agent(query: str) -> str:
    """Invoke a Bedrock inline agent with a knowledge base and return the answer."""
    response = client.invoke_inline_agent(
        sessionId="data-demo-1",
        foundationModel=MODEL_ID,
        instruction=(
            "You are an assistant that answers questions using the "
            "attached knowledge base whenever relevant."
        ),
        inputText=query,
        knowledgeBases=[
            {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "description": (
                    "Contains dialogue and information about "
                    "Lieutenant Commander Data from Star Trek: TNG."
                ),
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {"numberOfResults": 3}
                },
            }
        ],
        enableTrace=True,
    )

    output = []

    for event in response["completion"]:

        # trace events show the agent's step-by-step orchestration:
        # KB lookups, model invocations, and intermediate reasoning
        if "trace" in event:
            print("\n========== AGENT TRACE ==========")
            print(json.dumps(event["trace"], indent=2, default=str))

        # chunk events carry the actual answer text, streamed in pieces;
        # collect them all and join at the end to form the full response
        if "chunk" in event:
            output.append(event["chunk"]["bytes"].decode("utf-8"))

    return "".join(output)


if __name__ == "__main__":
    answer = run_inline_agent(QUERY)
    print("\n--- ANSWER ---")
    print(answer)
