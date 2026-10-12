# Amazon Bedrock Agents — Step 6 vs Step 7

## Step 6 — One agent, two capabilities

**Architecture:** User → **Inline Agent** → Knowledge Base / Calculator Action Group

- **1 agent** decides whether to retrieve knowledge or request a calculation.
- The calculator uses **`RETURN_CONTROL`**: the agent pauses, the caller runs the calculation, and the **same agent resumes** with the result.
- The agent handles routing and produces the final answer. A **guardrail** is attached to it.

## Step 7 — One supervisor, two specialist agents

**Architecture:** User → **Supervisor** → **DataKnowledgeAgent** (Knowledge Base) / **CalculatorAgent** (Action Group)

- **3 agents:** one parent **Supervisor** and two specialist collaborators.
- The Supervisor **routes** questions to the appropriate specialist.
- The specialists return their findings; the **Supervisor synthesizes** them into one final answer. **Synthesis is part of the Supervisor**, not a separate agent.
- The guardrail is configured on the Supervisor **and** both collaborators.
- The CalculatorAgent still uses **`RETURN_CONTROL`** and must resume after the calculation result is provided.

## What actually changed?

| | Step 6 | Step 7 |
|---|---|---|
| Agents | **1 general-purpose agent** | **1 supervisor + 2 specialists** |
| Who routes tasks? | The single agent | The Supervisor |
| Who combines results? | The single agent | The Supervisor (synthesis) |
| Calculator `RETURN_CONTROL` | Pauses and resumes | **Still** pauses and resumes |

**Fan-out means delegating work to different agents; it does not necessarily mean running tasks in parallel.** Step 7 separates responsibilities, but **does not automatically remove waiting or guarantee faster execution**.

### Why use Step 7?

**Better specialization, clearer responsibilities, and easier extension** when a request needs multiple kinds of expertise. The Supervisor coordinates the specialists and unifies their answers.

**Trade-off:** More agent-orchestration complexity. For simple requests, Step 6 may be all you need.

**Remember:** **Step 6 = one agent with multiple capabilities. Step 7 = one supervisor coordinating specialized agents.**
