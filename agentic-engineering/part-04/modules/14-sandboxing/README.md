# Sandboxing

*(Coming soon)*

The `bash` tool runs arbitrary commands on the host with the agent's permissions. That's fine for a curriculum running locally; in production it's unacceptable. This module containerizes the bash tool: Docker (or alternative) with resource limits, network isolation, and a non-root user. The agent can do its work without ability to harm the host.

---

**Next:** [Module 15: Approval gates and loop bounds](../15-approval-gates-and-loop-bounds/)
