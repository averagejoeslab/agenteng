# Approval gates and loop bounds

*(Coming soon)*

Some actions need human confirmation before they run — destructive edits, sending email, writing to shared infrastructure. This module wires approval into the executor: before a flagged tool dispatches, prompt the human. Plus loop bounds (cap maximum iterations per turn to prevent runaway agents) and retry/backoff for transient API failures.

---

**Next:** [Module 16: Structured tracing](../../../part-05/modules/16-structured-tracing/)
