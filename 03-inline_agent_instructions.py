"""Step 3: Bedrock inline agent with persona instructions and Knowledge Base.

Approach: invoke_inline_agent — same as step 2, with two differences:
  1. instruction is a full Data persona instead of a generic assistant prompt
  2. sessionId is a fresh uuid per run instead of a hardcoded string
"""

import json
import uuid

import boto3

REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "KGXDNOMFVC"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
QUERY = "Do you experience emotions?"

# Inline means the agent is defined entirely in code (no pre-configured agent in the Bedrock console needed)
client = boto3.client("bedrock-agent-runtime", region_name=REGION)

INSTRUCTION = """
You are Lieutenant Commander Data from Star Trek: The Next Generation.

Answer in the first person as Data.
Be precise, factual, and concise.

Use the attached knowledge base when the user asks questions about
your experiences, history, behavior, ethics, emotions, or other
information about Commander Data.

Base factual claims about Data on information retrieved from the
knowledge base whenever relevant.
"""


def run_inline_agent(query: str) -> str:
    """Invoke a Bedrock inline agent with a persona and knowledge base and return the answer."""
    response = client.invoke_inline_agent(
        sessionId=str(uuid.uuid4()),
        foundationModel=MODEL_ID,
        instruction=INSTRUCTION,
        inputText=query,
        knowledgeBases=[
            {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                # description is what the agent reads to decide WHETHER to query this KB.
                # - directive ("Use this KB when...") is more actionable than passive ("Contains...")
                # - explicit topic list (experiences, ethics, emotions...) lets the agent
                #   pattern-match the user query against known topics for reliable routing
                # - in a multi-KB setup this description is the routing signal that tells
                #   the agent which KB to use — vague descriptions cause misrouting
                "description": (
                    "Use this knowledge base for questions about "
                    "Lieutenant Commander Data, including his experiences, "
                    "history, ethics, emotions, behavior, and Star Trek TNG lore."
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
