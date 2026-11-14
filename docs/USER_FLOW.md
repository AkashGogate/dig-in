# User flow

The authoritative flow and gates are in [PROJECT_SPEC](../PROJECT_SPEC.md). For a runnable sequence use [DEMO_PLAN](DEMO_PLAN.md).

```text
Server session -> Start order -> manual table / optional mock suggestion
  -> structured draft -> deliberate read-back -> proposed diff / clarification
  -> reviewed current revision -> human Confirm and send
  -> submitted ticket -> cook acknowledge (voice OR tap) -> dish preparation
  -> partial plating evidence -> cook ready -> actionable running task
  -> lead claim + additional helpers if needed -> unambiguous pickup
  -> explicit staff served confirmation
```

Ingredient observations feed a separate review/accepted-movement path. Bay observations carry assignment versions and never assert contents or doneness. Shift overview exposes blockers, delays, uncertain inventory, and degraded adapters. All clients read the same backend; unavailable backend means visibly unsynced.
