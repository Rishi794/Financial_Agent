AgentSSL (NeurIPS 2026) - Self-Supervision in MLE Agents

Problem: MLE agents studied only in fully supervised settings; unlabeled data abundant but unlabeled data acquisition and manual pipeline engineering are bottlenecks.

Method: Frames SSL as program search problem; agents navigate this space under limited supervision.

Supervision: Weak feedback from agent-generated programs; matched compute with human baselines.

Memory: Program selection based on agent feedback metric.

Retrieval: ProgramSelectBench with 16,977 agent-generated and human-engineered SSL programs.

Update: Agents synthesize code combining/adapting established SSL techniques.

Evaluation: Exceeds strongest human-engineered baselines in 8/12 settings by up to +21.8%.

Ablation: Program selection causes 47% performance drop when selecting based on agent feedback metric.

Failure Modes: Program selection bottleneck; self-feedback may not be reliable.

Compute: Matched compute with human baselines.

Reproducibility: ProgramSelectBench available.

Novelty: First systematic study of SSL in MLE agents; ProgramSelectBench benchmark.

Key Insight: Self-supervision works but program selection is the critical bottleneck.

