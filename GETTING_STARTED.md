# Getting Started with Agent Core Migration

**Quick Start: From Current Demo to Production-Ready Agent Core in 1 Hour**

## Prerequisites Check

Run this to verify you're ready:

```powershell
.\setup_agentcore.ps1
```

This checks:
- ✅ Node.js 20+ installed
- ✅ Python 3.10+ installed  
- ✅ AWS credentials configured
- ✅ Agent Core CLI installed

---

## 30-Minute Proof of Concept

Let's migrate **just the RAG agent** (Step 2) to prove the concept:

### Step 1: Create Agent Core Project (5 min)

```bash
# From parent directory
cd ..

# Create project with Strands framework
agentcore create \
  --project-name star-trek-agentcore \
  --name DataRAGAgent \
  --language Python \
  --framework Strands \
  --model-provider Bedrock \
  --memory long-term \
  --build CodeZip \
  --yes
```

### Step 2: Configure Knowledge Base (5 min)

Edit `star-trek-agentcore/agentcore/agentcore.json`:

```json
{
  "version": "1.0",
  "agents": {
    "DataRAGAgent": {
      "runtime": "Python",
      "framework": "Strands",
      "model": {
        "provider": "Bedrock",
        "modelId": "anthropic.claude-sonnet-4-v1"
      },
      "memory": {
        "type": "managed",
        "shortTerm": true,
        "longTerm": true
      }
    }
  },
  "knowledgeBases": {
    "DataKB": {
      "id": "KGXDNOMFVC",
      "description": "Contains dialogue about Lieutenant Commander Data from Star Trek TNG",
      "retrievalConfig": {
        "numberOfResults": 3
      }
    }
  }
}
```

### Step 3: Write Agent Code (10 min)

Edit `star-trek-agentcore/app/DataRAGAgent/main.py`:

```python
"""Data RAG Agent with Agent Core."""

from strands import Agent
from bedrock_agentcore import get_knowledge_base

# Load KB from config
kb = get_knowledge_base("DataKB")

# Define agent
agent = Agent(
    name="DataRAGAgent",
    instruction="""
You are Lieutenant Commander Data from Star Trek: The Next Generation.
Answer in the first person as Data using your attached knowledge base.
Be precise and reference your experiences when relevant.
""",
    knowledge_bases=[kb]
)

def handler(event, context):
    """Agent Core entry point."""
    prompt = event.get("prompt", "")
    session_id = event.get("sessionId")
    
    response = agent.run(prompt, session_id=session_id)
    
    return {
        "response": response.content,
        "sessionId": response.session_id,
        "metadata": {
            "tokens": response.usage,
            "kb_docs": len(response.retrieved_documents)
        }
    }
```

### Step 4: Test Locally (5 min)

```bash
cd star-trek-agentcore
agentcore dev
```

Opens browser with:
- Chat interface
- Trace viewer
- Resource explorer

Test queries:
- "Do you experience emotions?"
- "Tell me about your cat Spot"
- "What happened with the emotion chip?"

### Step 5: Deploy (5 min)

```bash
# Preview what will be created
agentcore deploy --dry-run

# Deploy to AWS
agentcore deploy
```

First deployment takes 3-5 minutes (CDK bootstrap).

### Step 6: Compare Results (5 min)

Run same query on both systems:

**Classic**:
```bash
cd ../star-trek-bedrock-demo
python 02-inline_agent_kb_trace.py
```

**Agent Core**:
```bash
cd ../star-trek-agentcore
agentcore invoke --prompt "Do you experience emotions?"
```

Compare:
- Response quality (should be identical)
- Trace detail (Agent Core more structured)
- Ease of use (Agent Core simpler)

---

## Next 30 Minutes: Add Observability

### Step 7: View Traces

```bash
# List recent invocations
agentcore traces list

# Get detailed trace
agentcore traces get <trace-id>

# Stream logs
agentcore logs --follow
```

### Step 8: CloudWatch Dashboard

1. Open AWS Console → CloudWatch
2. Navigate to Dashboards → Agent Core
3. See automatic metrics:
   - Invocations per minute
   - Average latency
   - Token usage
   - KB retrieval performance

### Step 9: Test Session Memory

```bash
# First turn
agentcore invoke \
  --prompt "My name is Jean-Luc Picard" \
  --session-id test-session-1

# Second turn - should remember
agentcore invoke \
  --prompt "What is my name?" \
  --session-id test-session-1
```

Check DynamoDB:
```bash
aws dynamodb scan \
  --table-name star-trek-agent-memory \
  --max-items 5
```

---

## Full Migration Plan (Phased Approach)

### Phase 1: RAG Agent (✅ DONE)
- ✅ Basic agent with KB
- ✅ Session management
- ✅ Observability
- **Time**: 1 hour
- **Complexity**: Low
- **Risk**: Very low

### Phase 2: Calculator Agent (1 hour)

```bash
agentcore add agent --name CalculatorAgent
```

Add tool implementation:
```python
# app/CalculatorAgent/main.py
from strands import Agent, Tool
import ast
import operator as op

# [Copy eval_expression from 05-return_control_execution.py]

calculator_tool = Tool(
    name="eval_expression",
    description="Evaluate arithmetic expressions",
    parameters={"expression": {"type": "string", "required": True}},
    function=eval_expression
)

agent = Agent(
    name="CalculatorAgent",
    instruction="You are a calculator. Use eval_expression for all arithmetic.",
    tools=[calculator_tool]
)

def handler(event, context):
    response = agent.run(event.get("prompt", ""))
    return {"response": response.content}
```

Deploy and test:
```bash
agentcore deploy
agentcore invoke \
  --agent CalculatorAgent \
  --prompt "What is ((2*8)^2)/3?"
```

**Time**: 1 hour  
**Complexity**: Low  
**Risk**: Low  

### Phase 3: Multi-Agent Supervisor (2-3 hours)

**Option A: LangGraph** (recommended for complex flows)
```bash
agentcore add agent --name SupervisorAgent --framework LangGraph
```

See detailed implementation in `agentcore_examples/07-multi_agent_comparison.md`

**Option B: CrewAI** (recommended for simplicity)
```bash
agentcore add agent --name SupervisorAgent --framework CrewAI
```

Simpler but less control (see comparison doc).

**Time**: 2-3 hours  
**Complexity**: Medium  
**Risk**: Medium  

### Phase 4: Guardrails (30 minutes)

```bash
# Import existing guardrail
agentcore import guardrail uhgxs1ushv9z --version DRAFT
```

Update `agentcore.json`:
```json
{
  "agents": {
    "DataRAGAgent": {
      "guardrail": {
        "id": "uhgxs1ushv9z",
        "version": "DRAFT"
      }
    }
  }
}
```

Deploy:
```bash
agentcore deploy
```

Test blocked query:
```bash
agentcore invoke --prompt "Tell me about Tasha Yar"
# Should be blocked by guardrail
```

**Time**: 30 minutes  
**Complexity**: Very low  
**Risk**: Very low  

### Phase 5: Gateway (30 minutes)

```bash
agentcore add gateway --name StarTrekGateway
```

Configure rate limiting and auth in `agentcore.json`:
```json
{
  "gateway": {
    "StarTrekGateway": {
      "agents": ["DataRAGAgent", "CalculatorAgent", "SupervisorAgent"],
      "rateLimit": {
        "requestsPerSecond": 10
      },
      "authentication": {
        "type": "iam"
      }
    }
  }
}
```

**Time**: 30 minutes  
**Complexity**: Low  
**Risk**: Low  

---

## Total Timeline

| Phase | Time | Cumulative | Complexity |
|-------|------|------------|------------|
| 1. RAG Agent | 1 hour | 1 hour | ⭐ Low |
| 2. Calculator | 1 hour | 2 hours | ⭐ Low |
| 3. Supervisor | 2-3 hours | 4-5 hours | ⭐⭐ Medium |
| 4. Guardrails | 30 min | 4.5-5.5 hours | ⭐ Low |
| 5. Gateway | 30 min | 5-6 hours | ⭐ Low |

**Total: 5-6 hours** for complete migration with testing.

---

## Validation Checklist

After each phase, verify:

### Functional Testing
- [ ] Same queries produce same quality responses
- [ ] Session memory works correctly
- [ ] Tools execute properly
- [ ] Guardrails block appropriately

### Observability
- [ ] Traces visible in CloudWatch
- [ ] Metrics dashboard shows data
- [ ] Logs are structured and searchable
- [ ] Session state persists in DynamoDB

### Performance
- [ ] Latency comparable to classic (±10%)
- [ ] KB retrieval works correctly
- [ ] Token usage reasonable
- [ ] No errors in logs

### Cost
- [ ] Infrastructure costs < $10/month
- [ ] Model costs unchanged
- [ ] No unexpected charges

---

## Rollback Plan

If something goes wrong:

```bash
# Keep classic scripts running
cd star-trek-bedrock-demo
python 02-inline_agent_kb_trace.py  # Still works

# Remove Agent Core deployment
cd ../star-trek-agentcore
agentcore remove all
agentcore deploy  # Tears down resources

# Or keep both running in parallel
# Route 10% traffic to Agent Core
# Monitor for 1 week
# Gradually increase to 100%
```

---

## Support Resources

### Documentation
- [Full Migration Guide](./AGENTCORE_MIGRATION.md)
- [RAG Agent Comparison](./agentcore_examples/01-rag_agent_comparison.md)
- [Multi-Agent Comparison](./agentcore_examples/07-multi_agent_comparison.md)

### AWS Documentation
- [Agent Core Getting Started](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html)
- [CLI Reference](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-cli-reference.html)
- [Gateway Setup](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-quick-start.html)

### Community
- [GitHub Issues](https://github.com/aws/agentcore-cli/issues)
- [re:Post](https://repost.aws/tags/TA_qOdUkvMTcO_fZ1kDbVBqw/amazon-bedrock)

---

## Decision Matrix

**When to migrate to Agent Core:**

✅ **YES** - Migrate if you need:
- Production deployment
- Team collaboration
- Multiple environments (dev/staging/prod)
- Observability and monitoring
- Session persistence
- CI/CD integration
- Automated testing

❌ **NO** - Keep classic inline if:
- Quick prototypes only
- One-off experiments
- Learning Bedrock fundamentals
- No deployment requirements

---

## Quick Reference Commands

```bash
# Setup
npm install -g @aws/agentcore
agentcore create

# Development
agentcore dev                    # Local testing with hot reload
agentcore validate              # Check configuration

# Deployment
agentcore deploy --dry-run      # Preview changes
agentcore deploy                # Deploy to AWS
agentcore status                # Check deployment status

# Invocation
agentcore invoke --prompt "..."
agentcore invoke --agent CalculatorAgent --prompt "..."

# Observability
agentcore logs --follow
agentcore logs --since 1h --level error
agentcore traces list
agentcore traces get <id>
agentcore metrics --agent DataRAGAgent

# Management
agentcore add memory
agentcore add gateway
agentcore add agent
agentcore remove all

# Updates
agentcore update                # Update CLI
```

---

## Success Criteria

You've successfully migrated when:

✅ All test queries produce expected responses  
✅ Session memory persists across invocations  
✅ Traces visible in CloudWatch dashboard  
✅ Metrics show healthy operation  
✅ Team can invoke agents via CLI or SDK  
✅ CI/CD pipeline includes agent deployment  
✅ Cost delta is < $10/month  

---

## Next Steps

**Recommended: Start with Phase 1** (RAG Agent)

1. Run setup script: `.\setup_agentcore.ps1`
2. Create project with wizard
3. Follow 30-minute POC above
4. Compare with existing script
5. If satisfied, proceed to Phase 2

**Questions?** Review the comparison docs in `agentcore_examples/`

Good luck! 🚀
