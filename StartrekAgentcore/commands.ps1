agentcore add gateway --name StarTrekGateway --authorizer-type AWS_IAM
agentcore add gateway-target --name LieutenantCommanderData --type connector --connector bedrock-knowledge-bases --knowledge-base-id KGXDNOMFVC --gateway StarTrekGateway
agentcore invoke --runtime DataRAGAgent --prompt "Who created Lieutenant Commander Data?" 
agentcore invoke --session-id 792e3581-69a9-4f78-ae78-4dfc3e305376 --prompt "What other androids did he create?" 
# Generate a fresh session ID
$sid = (New-Guid).Guid

# Tell Data something completely new
agentcore invoke --runtime DataRAGAgent --session-id $sid --prompt "For this experiment, my imaginary starship is named Purple Penguin 47. Please acknowledge."
agentcore invoke --runtime DataRAGAgent --session-id $sid --prompt "What is the name of my imaginary starship?"

# Create a completely NEW session to test cross session memory
$sid2 = (New-Guid).Guid

# Ask without providing the starship name again
agentcore invoke --runtime DataRAGAgent --session-id $sid2 --prompt "What is the name of my imaginary starship? If you don't remember, please say so."agentcore add policy-engine --name StarTrekPolicy --attach-to-gateways StarTrekGateway --attach-mode LOG_ONLY

aws bedrock-agentcore-control get-gateway --gateway-identifier startrekagentcore-startrekgateway-321spmaima --region us-east-1 --query '{GatewayArn:gatewayArn,Policy:policyEngineConfiguration,Status:status}' --output json
agentcore add policy --name PermitStarTrekRetrieval --engine StarTrekPolicy --source permit-retrieval.cedar

agentcore add policy --name DenyStarTrekRetrieval --engine StarTrekPolicy --source deny-retrieval.cedar

################################
# 1. Ensure CloudFormation has recovered from the failed deployment
#$stack = "AgentCore-StartrekAgentcore-default"
#$status = aws cloudformation describe-stacks     --stack-name $stack     --region us-east-1     --query "Stacks[0].StackStatus"     --output text

# 3. Replace the locally registered policy
agentcore remove policy --name DenyStarTrekRetrieval --engine StarTrekPolicy
agentcore add policy     --name DenyStarTrekRetrieval     --engine StarTrekPolicy     --source deny-retrieval.cedar     --validation-mode FAIL_ON_ANY_FINDINGS

# 4. Validate and deploy
agentcore validate
agentcore deploy --yes
agentcore status