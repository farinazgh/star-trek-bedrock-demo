# Star Trek Bedrock Demo

A progressive series of Python scripts demonstrating Amazon Bedrock capabilities using
Lieutenant Commander Data from Star Trek: TNG as the knowledge domain.

Each step builds on the previous one, introducing one new concept at a time.

---

## The Knowledge Base

The knowledge base (`KGXDNOMFVC`) is built on Star Trek: TNG dialogue stored in
`s3://lieutenant-commander-data/data_lines.txt`. All scripts query this same KB,
asking questions about Data's experiences, emotions, and behavior.

---

## Step 1 — `01-search_knowledge_base.py` — Pure Retrieval

**What it does:** queries the knowledge base directly and prints the raw matching chunks.
No LLM is involved. This is the "R" in RAG — retrieval only.

```
client.retrieve() → top 3 chunks + relevance scores
```

- Uses `bedrock-agent-runtime` with `client.retrieve()`
- Sends the query text through **vector/semantic search** — the query is converted to an
  embedding and matched against stored document embeddings by similarity
- Returns each chunk's text and a relevance score (0–1, higher = more relevant)
- No generation, no synthesis — just raw document chunks

This is the foundation. Every subsequent step builds on top of this retrieval capability.

---

## Step 2 — `02-inline_agent_kb_trace.py` — Inline Agent with KB + Trace

**What it does:** introduces the Bedrock inline agent, which manages KB retrieval and
LLM generation automatically. Enables tracing to expose the internal orchestration steps.

```
invoke_inline_agent() → 5 trace events → final answer
```

**"Inline" means** the agent is defined entirely in code — no pre-configured agent in
the Bedrock console is needed. The KB, instructions, and model are all passed at runtime.

**The 5 trace events produced per query:**

| # | Event | What it means |
|---|-------|---------------|
| 1 | `invocationInput` | orchestrator decides to query the knowledge base |
| 2 | `observation (KB)` | KB returns the 3 retrieved chunks (374ms) |
| 3 | `modelInvocationInput` | chunks are packaged into a prompt and sent to Claude |
| 4 | `modelInvocationOutput` | Claude returns its answer (1,783 input / 291 output tokens) |
| 5 | `observation (FINISH)` | orchestrator emits the final cleaned-up response |

**The streaming event loop** produces two event types:
- `trace` events — step-by-step orchestration logs showing KB lookups, model invocations,
  and intermediate reasoning
- `chunk` events — the actual answer text, streamed in pieces and joined at the end

**Key insight:** the 5 traces are always the same, in the same order, every single run.
This pipeline is **deterministic** — the agent has no real decision to make. It always
retrieves from the KB and always calls Claude. This is managed RAG plumbing, not true
agentic behavior.

**Comparison of the three RAG approaches:**

| Approach | API calls | You manage prompt | Streaming |
|----------|-----------|-------------------|-----------|
| `01` — `retrieve` + `invoke_model` | 2 | Yes | Optional |
| `02` — `invoke_inline_agent` | 1 | No | Yes |
| `02-retrieve_and_generate` — `retrieve_and_generate` | 1 | No | No |

**When to separate retrieve from generate** (instead of using a single call):
- Filtering/re-ranking chunks before sending to the LLM
- Logging/auditing exactly what was retrieved for compliance
- Combining KB results with another source (database, API)
- Full control over prompt construction
- Cost optimization — inspect chunks first, decide if an LLM call is needed
- Querying multiple knowledge bases and merging results

---

## Step 3 — `03-inline_agent_instructions.py` — Persona + KB Description

**What it does:** same pipeline as step 2, with two meaningful differences:
a full persona instruction and a more precise KB description.

**Difference 1 — Persona instruction:**

Step 2 used a generic instruction:
> "You are an assistant that answers questions using the attached knowledge base whenever relevant."

Step 3 uses a full persona:
> "You are Lieutenant Commander Data from Star Trek: The Next Generation. Answer in the first person as Data..."

This changes the answer from third-person summary ("Data experienced anger...") to
first-person roleplay ("I experienced anger..."). The instruction/system prompt is the
**primary lever for changing agent behavior** — the code itself doesn't change.

**Difference 2 — KB description:**

Step 2:
> "Contains dialogue and information about Lieutenant Commander Data from Star Trek: TNG."

Step 3:
> "Use this knowledge base for questions about Lieutenant Commander Data, including his experiences, history, ethics, emotions, behavior, and Star Trek TNG lore."

The `description` field is what the agent's LLM reads to decide **whether to query the KB at all**.
Three semantic differences that matter:

- **Passive vs directive** — "Contains..." describes the KB; "Use this KB when..." instructs
  the agent. The agent reads this as an action trigger, so directive phrasing is more reliable.
- **Topic enumeration** — explicitly listing `experiences, history, ethics, emotions, behavior`
  lets the agent pattern-match the user's query against known topics. A query like
  "do you feel jealousy?" maps clearly to `emotions`; the agent retrieves. A query like
  "what is warp speed?" doesn't match; the agent skips the KB.
- **Multi-KB routing** — in a setup with multiple knowledge bases (step 7), the description
  is the routing signal. Vague descriptions cause misrouting or unnecessary lookups.
  Precise descriptions make routing deterministic and reliable.

**Difference 3 — Session ID:**

Step 2 uses a hardcoded `sessionId="data-demo-1"`. Step 3 uses `str(uuid.uuid4())` to
generate a fresh session per run, ensuring no conversation memory carries over between runs.

---

## Step 4 — `04-inline_agent_action_group.py` — Action Group with RETURN_CONTROL (incomplete)

**What it does:** introduces action groups — tools the agent can call. Uses `RETURN_CONTROL`
to hand tool execution back to the caller. **Intentionally incomplete** to contrast with step 5.

```
invoke_inline_agent() → returnControl event → nobody catches it → no answer
```

An **action group** defines a tool the agent can choose to invoke. The agent decides
based on the user's query whether to call it — this is where genuine non-determinism
begins. For a math question it calls the calculator; for a question about Data's history
it queries the KB instead.

`RETURN_CONTROL` means the agent will **not** execute the function itself. Instead it
pauses, emits a `returnControl` event with the function name and parameters, and waits.
The caller is responsible for running the function and returning the result.

**What step 4 does with the `returnControl` event:**
```python
if "returnControl" in event:
    print(event["returnControl"])  # just prints it and moves on
```

The agent paused and handed control back — but nobody caught it. The function was never
executed, the agent never resumed, and no final answer is produced. This is intentionally
broken to set up the lesson in step 5.

---

## Step 5 — `05-return_control_execution.py` — RETURN_CONTROL with Local Execution + Resume

**What it does:** completes the pattern from step 4. Catches the `returnControl` event,
executes the function locally, and resumes the agent on the same session with the result.

```
invoke_inline_agent() → returnControl → local execution → invoke_inline_agent() (resume) → answer
```

**The full tool-use loop:**

| # | Event | What happens |
|---|-------|--------------|
| 1 | `invocationInput` | agent decides to call the calculator tool |
| 2 | `returnControl` | agent pauses and hands invocation request to caller |
| 3 | `[local execution]` | caller runs `eval_expression` locally and gets the result |
| 4 | `invocationInput` | resumed agent receives the result |
| 5 | `modelInvocationInput` | result is packaged into a prompt and sent to Claude |
| 6 | `modelInvocationOutput` | Claude returns its final answer |
| 7 | `observation (FINISH)` | orchestrator emits the final cleaned-up response |

**Resuming the session:**
```python
client.invoke_inline_agent(
    sessionId=session_id,          # same session ID — critical for continuity
    inputText="",                  # ignored when returnControlInvocationResults is supplied
    inlineSessionState={
        "invocationId": invocation_id,
        "returnControlInvocationResults": [...]  # inject the local result back
    }
)
```

The same `session_id` is reused so the agent resumes exactly where it paused, with full
context of the original query.

**Why RETURN_CONTROL exists — use it when:**
- The function needs to run in **your environment** (local DB, internal API, filesystem)
- You need to **validate or transform** the result before the agent sees it
- The tool involves **sensitive operations** you don't want delegated to a Lambda
- You need an **audit trail** of every tool call and result before it reaches the model

**Safe arithmetic evaluator:**
The `eval_expression` function uses Python's `ast` module instead of `eval()` to safely
parse and compute arithmetic expressions. Only whitelisted AST node types (`Add`, `Sub`,
`Mul`, `Div`, `Pow`, `Mod`, `USub`) are allowed, preventing arbitrary code execution.

---

## Progression Summary

```
01  retrieve()                          pure vector search, no LLM
02  invoke_inline_agent() + KB          managed RAG, deterministic, 5 fixed trace events
03  invoke_inline_agent() + persona     same pipeline, persona changes the voice of the answer
04  invoke_inline_agent() + tool        non-deterministic tool selection, RETURN_CONTROL introduced
05  invoke_inline_agent() + tool loop   full tool-use loop: pause → execute locally → resume
```
