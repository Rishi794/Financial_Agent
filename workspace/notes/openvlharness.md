OpenVLHarness: Real World Visual Agentic Tool-Use with Multimodal Memory

Problem: MLLMs struggle with tasks requiring external evidence and heterogeneous tool outputs. Simply increasing inference budget yields only modest gains.

Method: Capability layer + persistent multimodal memory
- Capability layer: combines task-level tool interfaces with evidence rendering
- Persistent memory: retains images, structured data, web references as addressable artifacts
- Coding interface: executes programs over stored data for computations

Supervision: External tool outputs (API responses, browser state, database results) provide ground truth
Memory: Persistent multimodal memory with evidence rendering
Retrieval: Addressable artifacts throughout each query
Update: Iterative process of acquiring, inspecting, and composing multimodal evidence

Results: +9.7-12.6 points over no-tool baselines on 22 benchmarks
- +11.2 with Qwen3-VL-8B
- +9.7 with Kimi K3
- +9.9 with GPT-6 Astra
- Outperforms base model, Codex, Visual Sketchpad at max effort by 7.7-8.5 points
- At most 37% of model-token cost

Key Insight: External evidence + persistent memory + coding interface enables genuine improvement over base models

Failure Modes: Not explicitly documented, but potential issues include:
- Memory retrieval quality
- Evidence rendering fidelity
- Tool output interpretation errors

Compute: Requires 8 open/proprietary backbones tested

Novelty: First comprehensive multimodal memory harness with coding interface for agent tool-use

Reproducibility: arXiv paper available, code likely in repository

Tags: memory, agent-memory, multimodal, tool-use, self-supervision

Importance: 5

Date: 2026-10-19

---

Next Research: Self-supervision mechanisms, self-evaluation, memory consolidation, agent improvement loops
