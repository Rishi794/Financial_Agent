# Free Autonomous Research Agent

A small autonomous research agent that runs on GitHub Actions with a local 4B model, no paid LLM API, durable Git-backed memory, multi-provider search, source verification, and a Saturday email digest.

## Model

Default model: **Qwen3.5-4B Q4_K_M** from the pinned Unsloth GGUF revision. The model is ~2.74 GB and is Apache-2.0 licensed. The agent runs it through a pinned llama.cpp binary. Qwen3.5-4B is positioned by its model card as an agentic/tool-capable model; llama.cpp has current Ubuntu x64 CPU binaries.

## What it can search

- General web: DuckDuckGo HTML
- News: Google News RSS search
- Papers: arXiv API
- Bibliography: Crossref API
- GitHub: GitHub REST API search
- Hacker News: Algolia API
- Arbitrary pages: direct HTTP fetch
- Feeds: RSS/Atom
- Persistent memory: SQLite FTS5 + recency/importance scoring

All external research is done without an LLM API.

## Persistence

Durable memory is plain text, intentionally unencrypted:

```text
memory/index/YYYY.ndjson              # compact retrieval corpus, sharded by year
memory/episodes/YYYY-Www.ndjson.gz   # full durable run records
memory/reports/YYYY-Www.ndjson.gz    # compressed detailed tool traces
memory/cache/YYYY-Www.ndjson.gz      # small search cache/source metadata
workspace/                            # agent-created durable files
```

The compact index is what gets searched. Full traces are retained separately so retrieval does not become slower as the repository grows.

## Schedule

The main agent runs every 30 minutes at :07 and :37 UTC. A concurrency lock prevents overlapping runs. A Saturday workflow builds and emails a weekly digest.

GitHub currently provides standard GitHub-hosted runners free and unlimited for public repositories. The standard Linux runner is 4 CPU / 16 GB RAM / 14 GB SSD. GitHub-hosted jobs are ephemeral, so persistence is achieved by committing memory into Git. See the official docs before relying on a free public-repo setup.

## One-time setup

1. Create a **public GitHub repository**.
2. Push this directory.
3. Edit `config/tasks.md` with your mission.
4. Add these Actions secrets for Saturday email:
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
   - `EMAIL_TO`
5. Run the `Autonomous Research Agent` workflow manually once.

For Gmail, use an App Password for `SMTP_PASSWORD`; do not put passwords in Git.

## Local smoke test

```bash
python3 -m compileall agent tools
python3 tools/view_memory.py --stats
```

You do not need Python packages for the agent itself; it uses the standard library.


## Reasoning / thinking

The agent runs Qwen3.5-4B with reasoning enabled. `llama-server` is started with a 2048-token reasoning budget and a 4096-token total generation limit so the model has room to think while still producing tool calls or a final JSON response. llama.cpp exposes `--reasoning on`, `--reasoning-budget N`, and `--reasoning-preserve` for this purpose.
