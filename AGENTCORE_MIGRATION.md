# Agent Core Migration Guide

This guide walks through migrating the Star Trek Bedrock demo from inline agents to Agent Core.

## Quick Start

```bash
# 1. Install Agent Core CLI
npm install -g @aws/agentcore

# 2. Verify installation
agentcore --version

# 3. Create new Agent Core project (in a new directory)
cd ..
agentcore create --project-name star-trek-agentcore \
  --name DataRAGAgent \
  --language Python \
  --framework Strands \
  --model-provider Bedrock \
  --memory long-term \
  --build CodeZip

# 4. Navigate to the new project
cd star-trek-agentcore

# 5. Test locally
agentcore dev

# 6. Deploy to AWS
agentcore deploy

# 7. Invoke your agent
agentcore invoke --prompt "Do you experience emotions?"
```

## Migration Phases

### Phase 1: Basic RAG Agent (Maps to 01-03 scripts)

**Goal**: Replace `02-inline_agent_kb_trace.py` with Agent Core + Strands

Create `app/DataRAGAgent/main.py`:

```python
from strands import Agent
from bedrock_agentcore import KnowledgeBase

# Knowledge Base configuration
kb = KnowledgeBase(
    knowledge_base_id="KGXDNOMFVC",
    description="Contains dialogue about Lieutenant Commander Data from Star Trek TNG",
    retrieval_config={
        "vectorSearchConfiguration": {"numberOfResults": 3}
    }
)

# Agent definition
agent = Agent(
    name="DataRAGAgent",
    model="anthropic.claude-sonnet-4-v1",
    instruction="""
You are Lieutenant Commander Data from Star Trek: The Next Generation.
Answer in the first person using your attached knowledge base.
""",
    knowledge_bases=[kb]
)

def handler(event, context):
    """
    Agent Core entry point.
    Observability (traces, metrics) is automatic via Gateway.
    """
    prompt = event.get("prompt", "")
    
    # Session ID from event or generate new
    session_id = event.get("sessionId")
    
    response = agent.run(prompt, session_id=session_id)
    
    return {
        "response": response.content,
        "sessionId": response.session_id,
        "metadata": {
            "kb_documents_used": len(response.retrieved_documents),
            "tokens_used": response.usage
        }
    }
```

**Benefits over inline agents**:
- ✅ Automatic CloudWatch tracing (no manual JSON logging)
- ✅ Built-in session management
- ✅ Gateway observability
- ✅ Structured deployment

### Phase 2: Add Memory (Replaces manual session tracking)

Update `agentcore/agentcore.json` to add memory:

```json
{
  "memory": {
    "DataMemory": {
      "type": "managed",
      "backend": "dynamodb",
      "config": {
        "tableName": "star-trek-agent-memory",
        "ttl": 2592000
      }
    }
  },
  "agents": {
    "DataRAGAgent": {
      "memory": "DataMemory",
      "framework": "Strands",
      ...
    }
  }
}
```

Deploy memory:
```bash
agentcore add memory --name DataMemory --type managed
agentcore deploy
```

### Phase 3: Tools / Action Groups (Maps to 04-05 scripts)

Create calculator tool in `app/CalculatorAgent/main.py`:

```python
from strands import Agent, Tool
import ast
import operator as op

ALLOWED_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.Mod: op.mod,
}

def eval_ast(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](eval_ast(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPS:
        return ALLOWED_OPS[type(node.op)](eval_ast(node.left), eval_ast(node.right))
    raise ValueError("Unsupported expression")

def eval_expression(expression: str) -> str:
    """Safely evaluate arithmetic expression"""
    tree = ast.parse(expression.replace("^", "**"), mode="eval")
    return str(eval_ast(tree.body))

# Define tool
calculator_tool = Tool(
    name="eval_expression",
    description="Evaluate arithmetic expressions using +, -, *, /, **, %, and parentheses",
    parameters={
        "expression": {
            "type": "string",
            "description": "The arithmetic expression to evaluate",
            "required": True
        }
    },
    function=eval_expression
)

# Agent with tool
agent = Agent(
    name="CalculatorAgent",
    model="anthropic.claude-sonnet-4-v1",
    instruction="You are a calculator. Use eval_expression for all arithmetic.",
    tools=[calculator_tool]
)

def handler(event, context):
    response = agent.run(event.get("prompt", ""))
    return {"response": response.content}
```

**Benefits over RETURN_CONTROL**:
- ✅ No manual pause/resume logic
- ✅ Automatic tool invocation tracing
- ✅ Cleaner code structure

### Phase 4: Multi-Agent with LangGraph (Maps to 07 script)

For complex multi-agent orchestration, use LangGraph:

```python
# app/SupervisorAgent/main.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from operator import add

class AgentState(TypedDict):
    messages: Annotated[list, add]
    next_agent: str

def supervisor_node(state: AgentState):
    """Route to appropriate specialist"""
    last_message = state["messages"][-1]
    
    if "emotion" in last_message.lower() or "data" in last_message.lower():
        return {"next_agent": "data_rag"}
    elif any(op in last_message for op in ["+", "-", "*", "/", "calculate"]):
        return {"next_agent": "calculator"}
    else:
        return {"next_agent": "end"}

def data_rag_node(state: AgentState):
    # Invoke DataRAGAgent
    from bedrock_agentcore import invoke_agent
    response = invoke_agent("DataRAGAgent", state["messages"][-1])
    return {"messages": [response], "next_agent": "supervisor"}

def calculator_node(state: AgentState):
    # Invoke CalculatorAgent
    from bedrock_agentcore import invoke_agent
    response = invoke_agent("CalculatorAgent", state["messages"][-1])
    return {"messages": [response], "next_agent": "supervisor"}

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("data_rag", data_rag_node)
workflow.add_node("calculator", calculator_node)

workflow.add_conditional_edges(
    "supervisor",
    lambda x: x["next_agent"],
    {
        "data_rag": "data_rag",
        "calculator": "calculator",
        "end": END
    }
)

workflow.add_edge("data_rag", "supervisor")
workflow.add_edge("calculator", "supervisor")

workflow.set_entry_point("supervisor")
graph = workflow.compile()

def handler(event, context):
    """Agent Core automatically traces the entire graph execution"""
    result = graph.invoke({
        "messages": [event.get("prompt", "")],
        "next_agent": "supervisor"
    })
    return {"response": result["messages"][-1]}
```

**Benefits over manual supervisor**:
- ✅ Visual graph representation
- ✅ Automatic state management
- ✅ Built-in error handling
- ✅ Full observability of graph execution

### Phase 5: Guardrails (Maps to 06 script)

Add guardrail to `agentcore/agentcore.json`:

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

**Benefits**:
- ✅ No code changes needed
- ✅ Applies to all agent interactions automatically
- ✅ Consistent enforcement

### Phase 6: Gateway & Observability

Enable gateway for all agents:

```bash
agentcore add gateway --name StarTrekGateway
```

Configure observability in `agentcore/agentcore.json`:

```json
{
  "gateway": {
    "StarTrekGateway": {
      "agents": ["DataRAGAgent", "CalculatorAgent", "SupervisorAgent"],
      "observability": {
        "traces": true,
        "metrics": true,
        "logs": true
      },
      "rateLimit": {
        "requestsPerSecond": 10
      }
    }
  }
}
```

View traces:
```bash
# List all traces
agentcore traces list

# Get specific session
agentcore traces get --session-id <session-id>

# Live tail logs
agentcore logs --follow

# View metrics
agentcore metrics --agent DataRAGAgent --metric InvocationCount
```

**Benefits over manual trace logging**:
- ✅ Structured, queryable traces in CloudWatch
- ✅ Automatic correlation IDs
- ✅ Visual trace viewer
- ✅ Performance metrics out-of-the-box

## Side-by-Side Comparison

| Feature | Classic Inline Agents | Agent Core |
|---------|----------------------|------------|
| **Deployment** | Manual Python scripts | `agentcore deploy` |
| **Session Management** | Manual UUID + DynamoDB code | Built-in with `memory` |
| **Traces** | Manual JSON logging | Automatic CloudWatch |
| **Tool Execution** | RETURN_CONTROL + resume | Automatic invocation |
| **Multi-Agent** | Manual coordination | Strands/LangGraph/CrewAI |
| **Guardrails** | Per-invocation config | Project-level config |
| **Local Testing** | Run Python scripts | `agentcore dev` with hot reload |
| **Observability** | Custom parsing | CloudWatch dashboard |

## Cost Considerations

Agent Core adds minimal infrastructure cost:
- **Runtime**: Pay per invocation (same as inline agents)
- **Memory**: DynamoDB on-demand (only if enabled)
- **Gateway**: No additional charge, same as API Gateway pricing
- **CloudWatch**: Standard logging/metrics pricing

## Recommended Migration Order

1. ✅ **Start**: Phase 1 (Basic RAG) - proves the pattern
2. ✅ **Add**: Phase 2 (Memory) - simplifies session management
3. ✅ **Expand**: Phase 3 (Tools) - cleaner than RETURN_CONTROL
4. ✅ **Scale**: Phase 6 (Gateway) - observability first
5. ✅ **Orchestrate**: Phase 4 (Multi-agent) - use LangGraph
6. ✅ **Secure**: Phase 5 (Guardrails) - apply policies

## Testing Strategy

```bash
# Local testing with hot reload
agentcore dev

# Run test suite
pytest tests/

# Load testing
agentcore invoke --prompt "Test query" --concurrency 10 --count 100

# View results
agentcore metrics --last 1h
```

## Rollback Plan

Keep your existing inline agent scripts. Agent Core is additive:
- Old scripts continue working
- Gradually migrate use cases
- Run both in parallel during transition
- Full rollback: delete Agent Core stack

## Next Steps

1. **Install CLI**: `npm install -g @aws/agentcore`
2. **Create project**: `agentcore create` (interactive)
3. **Test locally**: `agentcore dev`
4. **Deploy**: `agentcore deploy`
5. **Compare**: Run equivalent queries against both systems

## Resources

- [Agent Core Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [CLI Reference](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-cli-reference.html)
- [Strands Framework](https://github.com/aws/strands-agents)
- [LangGraph Integration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html)
