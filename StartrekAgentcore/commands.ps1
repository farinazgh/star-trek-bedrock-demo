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
agentcore invoke --runtime DataRAGAgent --session-id $sid2 --prompt "What is the name of my imaginary starship? If you don't remember, please say so."