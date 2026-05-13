# Well Structured Agent Projects

## A well-structured LangGraph system should:

✅ 1. Separate concerns cleanly

- Graph wiring ≠ agent logic ≠ tool calls
- No hidden side effects
  ✅ 2. Use typed state explicitly
- Treat state like a contract
- Avoid “mystery dicts”
  ✅ 3. Keep nodes small + deterministic
- One responsibility per node
- Easy to test in isolation
  ✅ 4. Make control flow explicit
- Routing functions, not LLM guessing everywhere
  ✅ 5. Be observable + debuggable
- You should be able to replay a run

## Separate “Decision” From “Execution”

```console
[LLM decides] → [router] → [tool executes]
```
