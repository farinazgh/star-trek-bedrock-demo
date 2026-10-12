# 05-return_control_execution.py — Explanation

## The core pattern — two `invoke_inline_agent` calls on the same session

1. **First call** — agent receives the query, decides to call `eval_expression`, emits a `returnControl` event and pauses
2. **Local execution** — your code catches the `returnControl`, extracts the function name and parameters, runs `eval_expression` locally
3. **Second call** — same `session_id` + `inlineSessionState` injects the result back, agent resumes and produces the final answer

## The safe evaluator (`eval_ast` / `eval_expression`)

- Replaces `^` with `**` for Python-style exponentiation
- Parses the expression into an AST instead of using `eval()`
- Only whitelisted node types (`Add`, `Sub`, `Mul`, `Div`, `Pow`, `Mod`, `USub`) are allowed — anything else raises `ValueError`, preventing arbitrary code execution

## The event loop handles 3 event types

- `trace` — orchestration steps
- `returnControl` — agent pausing and handing off tool execution
- `chunk` — streamed answer text

## Key difference from step 4

The `return_control is None` check — if the agent finished normally (KB question, no math),
it returns immediately. Only if `returnControl` was captured does it proceed to local
execution and resume.

---

## Why the two-call pattern looks like spaghetti — and how to fix it

**Why it's hardcoded in step 5:**
Step 5 is a teaching script. It assumes exactly one tool call will happen, so the resume
is written inline. In reality this is fragile — what if the agent needs to call the tool
twice? Or calls the KB first, then the calculator? The hardcoded pattern breaks.

**How it works in production — a loop:**
In real code you'd wrap the whole thing in a `while True` loop:

```python
while True:
    response = client.invoke_inline_agent(...)
    output, return_control = process_response(response)

    if return_control is None:
        break  # agent finished, exit loop

    result = execute_locally(return_control)  # run whatever tool was requested
    # next iteration resumes with the result
```

The loop keeps going until `return_control is None`, meaning the agent is done. You never
hardcode how many times it runs — the agent decides.

**Why agent over raw `invoke_model`:**
With raw `invoke_model` you'd have to implement this loop yourself — parse the response,
detect tool calls, execute them, re-inject results, call the model again. That's the real
spaghetti. The agent framework gives you the structured `returnControl` / resume pattern
so the orchestration is clean and consistent regardless of how many tool calls happen.

**Summary:**
- Step 5's two-call pattern is intentionally simplified for teaching
- Step 7 (multi-agent supervisor) is closer to production — it already has the loop abstracted into `invoke_supervisor`
- The agent pattern exists precisely to avoid managing this loop manually with raw `invoke_model`

---

## RETURN_CONTROL vs Lambda vs OpenAPI executor

**With Lambda:**
```python
"actionGroupExecutor": {"lambda": "arn:aws:lambda:us-east-1:123456789:function:my-calculator"}
```
- The agent calls the Lambda **directly** — no `returnControl` event is ever emitted
- The agent pauses internally, AWS invokes the Lambda, gets the result, and resumes **all within the same `invoke_inline_agent` call**
- Your event loop never sees a `returnControl` event — you only ever see `trace` and `chunk` events
- You have zero visibility or control over what the Lambda does before the agent sees the result

So the event loop in step 5 would simplify to just:
```python
for event in response["completion"]:
    if "trace" in event:
        ...
    if "chunk" in event:
        output.append(...)
# no returnControl handling needed at all
```

**The tradeoff:**

| | Lambda | RETURN_CONTROL |
|---|---|---|
| Execution | AWS invokes it automatically | You run it locally |
| Your code complexity | Simpler | More complex (the loop) |
| Control over result | None before agent sees it | Full — validate, transform, audit |
| Where function runs | AWS Lambda environment | Your environment |
| Sensitive operations | Delegated to AWS | Stays in your code |

**OpenAPI executor:**
Bedrock action groups also support an OpenAPI schema executor where the agent calls an
HTTP endpoint directly. Same principle as Lambda — no `returnControl`, the agent handles
the round-trip itself.

**Summary:**
`RETURN_CONTROL` exists specifically for when you don't want to delegate execution to AWS
infrastructure — you want the function to run in your environment, under your control,
before the agent ever sees the result.

---

## 05-lambda_executor.py vs 05-return_control_execution.py — Code level diff

What changed in the Lambda version:

- `LAMBDA_ARN` constant replaces the safe evaluator functions (`eval_ast`, `eval_expression`, `ALLOWED_OPS`)
- `actionGroupExecutor` is `{"lambda": LAMBDA_ARN}` instead of `{"customControl": "RETURN_CONTROL"}`
- The event loop has no `returnControl` handling — just `trace` and `chunk`
- Only **one** `invoke_inline_agent` call — no resume needed
- `run_inline_agent` is ~half the size

Running `diff` between the two files shows exactly the tradeoff: the Lambda version is
simpler caller code, but you give up all control over local execution.
