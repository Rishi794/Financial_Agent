# Architecture

```text
                      GitHub Actions scheduler
                               |
                               v
                 +----------------------------+
                 | ephemeral Ubuntu runner    |
                 | 4 CPU / 16 GB RAM         |
                 +----------------------------+
                               |
                +--------------+--------------+
                |                             |
                v                             v
         llama.cpp server               research tools
                |                             |
        Qwen3.5-4B Q4_K_M          +---------+----------+
                |                   | web / news / RSS |
                +--------+          | arXiv / Crossref |
                         |          | GitHub / HN      |
                         v          +-------------------+
                  autonomous loop
                         |
                         v
                +-----------------+
                | memory_search   |
                | SQLite FTS5     |
                | lexical +       |
                | recency +        |
                | importance      |
                +--------+--------+
                         |
                         v
                   durable Git

memory/index.ndjson              compact retrieval corpus
memory/episodes/YYYY-Www.gz      durable episode records
memory/reports/YYYY-Www.gz      full tool traces
memory/cache/YYYY-Www.gz         small search/page cache
workspace/                       durable agent-created files
```

## Why this scales

The model never loads the entire history. Only the compact index is indexed into an in-memory SQLite FTS5 database per run. Full traces are sharded by week and are not scanned during normal retrieval. Every memory record has a stable UUID, timestamp, tags, importance, open loops and source URLs.

Retrieval score is a hybrid of lexical relevance, recency and importance. This is intentionally dependency-free; no embeddings service or vector database is needed.

## Research reliability

The agent has separate discovery and verification tools. Search snippets are treated as discovery evidence; important claims should be verified with `web_get` against primary sources. It can cross-check papers via arXiv/Crossref, software via GitHub, and recent events via news/RSS.

## Security

Memory is intentionally unencrypted because the user requested plain Git-backed persistence. Secrets are never written to files, and shell access blocks common credential-exfiltration and remote-execution patterns.

Do not use a public repository for anything confidential. Git history is permanent even after files are deleted.
