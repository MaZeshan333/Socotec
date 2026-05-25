# Socotec

# Advanced Multi-Agent Text-to-SQL Framework

An enterprise-grade, highly adaptive Multi-Agent system designed to turn natural language questions into ultra-accurate PostgreSQL queries. Equipped with automatic schema linking, parallel path generation, multi-candidate execution-fingerprint voting, self-correcting fallback loops, and dynamic column exploration.

---

## 🛠️ Architecture Overview

The pipeline leverages specialized autonomous agents working in orchestration to achieve high execution accuracy (Execution Match), preventing hallucinations and broken references.

```bash
              ┌──────────────────────────────┐
              │   Natural Language Question  │
              └──────────────┬───────────────┘
                             │
              ┌──────────────▼───────────────┐
              │       Snapshot Manager       │  <-- Dynamically compresses &
              │  (Adaptive Schema Linking)   │      links relational schema
              └──────────────┬───────────────┘
                             │
              ┌──────────────▼───────────────┐
              │      SQL Generator Agent     │  <-- Spawns 'k' concurrent paths
              │ (Multi-Candidate & Feedback) │      with dynamic self-repair loops
              └──────────────┬───────────────┘
                             │ [Executes & Fetches Result Dfs]
              ┌──────────────▼───────────────┐
              │       SQL Voter Agent        │  <-- Groups results via MD5 data
              │  (Fingerprint Voting Engine) │      fingerprints to choose top choice
              └──────────────┬───────────────┘
                             │
                ┌────────────┴────────────┐
        [High Confidence]                  [Low Confidence / Tie]
                │                                 │
                │                         ┌───────▼──────────────┐
                │                         │  SQL Explorer Agent  │ <-- Resolves deep keys
                │                         │ (Iterative Probe)    │     (JSONB/Complex types)
                │                         └───────┬──────────────┘
                │                                 │
                └────────────────┬────────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │ Output Verified SQL & Data  │
                  └─────────────────────────────┘
 ```

### Core Agents & Components:
* **Snapshot Manager (`snapshot_manager.py`)**: Assesses database scale. For small DBs (e.g., our 3-table Spider playground), it automatically extracts the full schema profile to ensure complete JOIN paths. For massive schemas, it filters down contextual tokens via LLM heuristics.
* **SQL Generator Agent (`agent_generator.py`)**: Triggers multi-threaded worker pipelines via a concurrent pool to output $k$ candidate implementations. Includes an adaptive `_self_correct_loop` tracking execution exceptions to re-prompt code iterations natively.
* **SQL Voter Agent (`agent_voter.py`)**: Runs consensus logic against dataset responses. To protect server buffers from memory spikes, it computes a deterministic 32-character MD5 hash representing response matrices, column types, and data distribution boundaries.
* **SQL Explorer Agent (`agent_explorer.py`)**: Acts as a runtime diagnostic rollback router. When confidence is low or voting paths tie, it deploys non-destructive query probes (`LIMIT 5`) to inspect unknown schemas or complex layout parameters (like `JSONB` structures) dynamically.

---

## 📂 Codebase Directory

```bash
├── New/                        # Cleaned relational dataset storage (generated via analytics scripts)
├── Origin/                     # Unstructured raw source data workspace
├── agent_explorer.py           # Deep exploration layer resolving low-confidence patterns
├── agent_generator.py          # Parallel worker generating multi-threaded code paths
├── agent_voter.py              # MD5 execution-fingerprint consensus engine
├── benchmark_aws.py            # Complete evaluation pipeline using AWS Claude 4.5 Sonnet
├── chat_bedrock.py             # Client wrapper handling cloud requests via AWS Bedrock Endpoints
├── chat_local.py               # Local server routing via OpenAI API proxy specs (Ollama)
├── create_newfile.py           # Ingestion parsing helper to clean datasets and purge NULL values
├── setup_db.py                 # Structural PostgreSQL schema initializer (tables & strategic indexes)
├── import_data_30.py           # High-speed data streamer capping database testing bounds safely
├── run.py                      # Interactive ad-hoc query entrypoint backed by Local Ollama
├── run_AWS.py                  # Interactive ad-hoc query entrypoint backed by AWS Bedrock Claude
├── snapshot_manager.py         # Handles automated context layout compilation and schema linking
└── sql_engine.py               # Interface processing execution tasks securely using Psycopg2 & Pandas
 ```

