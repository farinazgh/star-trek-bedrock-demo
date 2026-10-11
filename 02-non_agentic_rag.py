"""Step 2: Invoke one Bedrock inline agent with one Knowledge Base.

Approach: retrieve + invoke_model — explicit two-step RAG, no agent orchestrator.
The pipeline executes 2 steps per query:
  1. retrieve    - query the knowledge base directly and get chunks
  2. invoke_model - pass retrieved chunks to Claude as context and get the answer
"""

import json

import boto3

REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "KGXDNOMFVC"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
QUERY = "Do you experience emotions?"

agent_runtime_client = boto3.client("bedrock-agent-runtime", region_name=REGION)
runtime_client = boto3.client("bedrock-runtime", region_name=REGION)


def run_rag(query: str) -> str:
    """Retrieve chunks from the knowledge base, invoke Claude with context, and return the answer."""
    # Step 1: retrieve relevant chunks from the knowledge base
    kb_response = agent_runtime_client.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
    )
    chunks = [r["content"]["text"] for r in kb_response["retrievalResults"]]

    # Step 2: invoke Claude with the retrieved chunks as context
    context = "\n\n".join(chunks)
    model_response = runtime_client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(
            {
                "system": "You are an assistant that answers questions using the provided context.",
                "messages": [
                    {
                        "role": "user",
                        "content": f"<context>\n{context}\n</context>\n\n{query}",
                    }
                ],
                "max_tokens": 512,
                "anthropic_version": "bedrock-2023-05-31",
            }
        ),
    )
    return json.loads(model_response["body"].read())["content"][0]["text"]


if __name__ == "__main__":
    answer = run_rag(QUERY)
    print("\n--- ANSWER ---")
    print(answer)
