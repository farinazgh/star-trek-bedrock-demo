import json

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from mcp_client.client import GATEWAY_URL

REGION = "us-east-1"

session = boto3.Session(region_name=REGION)
credentials = session.get_credentials().get_frozen_credentials()

print("AWS Caller:", session.client("sts").get_caller_identity()["Arn"])
print("Gateway URL:", GATEWAY_URL)

payload = json.dumps(
    {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
).encode("utf-8")

request = AWSRequest(
    method="POST",
    url=GATEWAY_URL,
    data=payload,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    },
)

SigV4Auth(credentials, "bedrock-agentcore", REGION).add_auth(request)

response = httpx.post(
    GATEWAY_URL,
    content=payload,
    headers=dict(request.headers),
    timeout=30,
    follow_redirects=False,
)

print("\nHTTP Status:", response.status_code)
print("Content Type:", response.headers.get("content-type"))
print("\nResponse Body:")
print(response.text[:4000])
