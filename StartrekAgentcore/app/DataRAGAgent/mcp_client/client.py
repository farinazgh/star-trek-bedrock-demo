"""IAM-authenticated MCP client for StarTrekGateway."""

from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

GATEWAY_URL = (
    "https://startrekagentcore-startrekgateway-321spmaima."
    "gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
)

REGION = "us-east-1"


def get_streamable_http_mcp_client() -> MCPClient:
    """Connect to StarTrekGateway using AWS SigV4."""

    return MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=GATEWAY_URL,
            aws_region=REGION,
            aws_service="bedrock-agentcore",
        )
    )
