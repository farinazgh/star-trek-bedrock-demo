permit(
    principal is AgentCore::IamEntity,
    action in [
        AgentCore::Action::"LieutenantCommanderData___Retrieve",
        AgentCore::Action::"LieutenantCommanderData___AgenticRetrieveStream"
    ],
    resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:339712939282:gateway/startrekagentcore-startrekgateway-321spmaima"
);