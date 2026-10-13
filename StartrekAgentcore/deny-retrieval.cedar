forbid(
    principal is AgentCore::IamEntity,
    action == AgentCore::Action::"LieutenantCommanderData___AgenticRetrieveStream",
    resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:339712939282:gateway/startrekagentcore-startrekgateway-321spmaima"
)
when {
    principal.id like "arn:aws:sts::339712939282:assumed-role/*"
};
