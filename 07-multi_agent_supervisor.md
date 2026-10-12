# 07-step7_multi_agent_supervisor.py — Explanation

## Architecture — three agents working together

```
User → DataSupervisor → DataKnowledgeAgent → KB
                      → CalculatorAgent    → RETURN_CONTROL → your code
```

The supervisor never answers directly — it reads the query and delegates to the right
specialist. This is the first genuinely non-deterministic multi-step orchestration in
the series.

---

## Two new concepts vs step 6

**1. `agentCollaboration: "SUPERVISOR"`**
Tells Bedrock this agent is a supervisor that can delegate to collaborators.

**2. `agentCollaboration: "DISABLED"` on each collaborator**
Prevents collaborators from spawning their own sub-agents — they are leaf nodes only.

---

## `COLLABORATOR_CONFIGURATIONS` is the routing signal

```python
"collaboratorInstruction": "Use this collaborator for questions about Lieutenant Commander Data..."
```

Same principle as the KB `description` from step 3 — the supervisor reads these
instructions to decide who to delegate to. Vague instructions cause misrouting.

---

## `agentId` in the resume payload — the key multi-agent difference vs step 5

```python
if agent_id:
    function_result["agentId"] = agent_id
```

In step 5 there is only one agent so the resume is unambiguous. Here the supervisor
needs to know which collaborator issued the `returnControl` so it can route the result
back to the right one. Without `agentId` the resume fails.

---

## Why Nova Pro instead of Claude

Not all models support supervisor mode — Nova Pro is required for
`agentCollaboration: "SUPERVISOR"`.

---

## `invoke_supervisor` helper

Extracted because the supervisor is called twice (first call + resume) with identical
params except `inlineSessionState`. Avoids repeating the full params dict.

---

## The query tests both collaborators at once

```
"Tell me whether Data experiences emotions, and also compute ((2*8)^2)/3."
```

The supervisor must coordinate two specialists and merge their answers into one response
— this is the payoff of the entire series.

---

## Orchestration events per query

| # | Event | What happens |
|---|-------|--------------|
| 1 | `invocationInput` | supervisor delegates to the appropriate collaborator |
| 2 | `[collaborator runs]` | collaborator queries KB or emits returnControl |
| 3 | `returnControl` | CalculatorAgent pauses and hands invocation to caller |
| 4 | `[local execution]` | caller runs `eval_expression` and gets the result |
| 5 | `invocationInput` | resumed supervisor receives the result |
| 6 | `modelInvocationInput` | result is packaged into a prompt and sent to Nova Pro |
| 7 | `modelInvocationOutput` | Nova Pro returns its final answer |
| 8 | `observation (FINISH)` | orchestrator emits the final cleaned-up response |

---

## Progression from step 5

| | Step 5 | Step 7 |
|---|---|---|
| Agents | 1 | 3 (supervisor + 2 collaborators) |
| `agentId` in resume | Not needed | Required — identifies which collaborator to resume |
| Model | Claude Sonnet | Nova Pro (supervisor mode requirement) |
| Tool routing | Single tool | Supervisor decides which collaborator handles the query |
| `invoke_supervisor` helper | No | Yes — called twice, params extracted to avoid repetition |
