"""Test module for Amazon Bedrock Knowledge Base retrieval."""

import boto3


def search_knowledge_base() -> None:
    """Test function to retrieve information from a Bedrock Knowledge Base."""
    # Configuration constants
    REGION = "us-east-1"
    KNOWLEDGE_BASE_ID = "KGXDNOMFVC"

    # Initialize Bedrock Agent Runtime client
    client = boto3.client(
        "bedrock-agent-runtime",
        region_name=REGION,
    )

    # Perform knowledge base retrieval
    response = client.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": "Do you experience emotions?"},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
    )

    # Display results
    for i, result in enumerate(response["retrievalResults"], start=1):
        print(f"\n--- RESULT {i} ---")
        print(result["content"]["text"])
        print("Score:", result.get("score"))


if __name__ == "__main__":
    search_knowledge_base()
