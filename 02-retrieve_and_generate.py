"""Step 2: Invoke one Bedrock inline agent with one Knowledge Base.

Approach: retrieve_and_generate — single API call, Bedrock manages KB retrieval and generation internally.
The pipeline executes 1 step per query:
  1. retrieve_and_generate - Bedrock retrieves chunks and generates the answer in one call
"""

import boto3

REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "KGXDNOMFVC"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
QUERY = "Do you experience emotions?"

client = boto3.client("bedrock-agent-runtime", region_name=REGION)


def run_retrieve_and_generate(query: str) -> str:
    """Retrieve chunks and generate an answer in a single Bedrock API call."""
    response = client.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "modelArn": f"arn:aws:bedrock:{REGION}::foundation-model/{MODEL_ID}",
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {"numberOfResults": 3}
                },
            },
        },
    )
    return response["output"]["text"]


if __name__ == "__main__":
    answer = run_retrieve_and_generate(QUERY)
    print("\n--- ANSWER ---")
    print(answer)
