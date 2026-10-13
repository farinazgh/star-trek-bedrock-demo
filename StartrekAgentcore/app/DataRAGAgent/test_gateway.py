"""Test StarTrekGateway MCP connection and tool discovery."""

from mcp_client.client import get_streamable_http_mcp_client

client = get_streamable_http_mcp_client()

print("\nConnecting to StarTrekGateway...")

with client:
    tools = client.list_tools_sync()

    print("\nMCP CONNECTION SUCCESSFUL")
    print(f"Discovered {len(tools)} tools:\n")

    for tool in tools:
        print(f"Tool: {tool.tool_name}")
        print(f"Description: {tool.tool_spec.get('description')}")
        print("-" * 50)

    names = [tool.tool_name for tool in tools]

    assert any(
        "Retrieve" in name for name in names
    ), "Knowledge Base retrieval tools not found!"

    print("\nSUCCESS: Knowledge Base tools discovered!")
