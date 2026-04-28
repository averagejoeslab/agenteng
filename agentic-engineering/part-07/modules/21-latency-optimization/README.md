# Latency optimization

*(Coming soon)*

Module 20 reduced cost; this module reduces wall time. Wrap blocking tool bodies in `asyncio.to_thread` so they don't stall the event loop. Stream the final assistant response (not tool-use turns) so the user sees output as it lands. Profile where the time goes — LLM latency vs. tool latency — and target the bottleneck. The agent feels faster without doing less.

---

**Next:** [Module 22: Prompt design](../../../part-08/modules/22-prompt-design/)
