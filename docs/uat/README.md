# UAT Reports

This folder is the default output location for plain-text UAT snapshots.

The report script reads from a running backend API and writes a human-readable
text file. The output is intentionally committable so a UAT snapshot can be
reviewed in a PR or compared over time.

Default output:

```text
docs/uat/current-graph-status.txt
```

## Wave 4 Local Trace Reports

Wave 4 adds graph/database-free UAT scripts for inspecting the refined ingestion
process from local fixtures. These scripts load `src/my_digital_brain/.env`
before provider setup by default and use the project's provider/model
configuration, but do not require the backend API, graph database, vector
database, or persisted memory state.

Local conversation-entry trace:

```powershell
python scripts/render_uat_refined_ingestion_trace.py `
  --input docs/uat/examples/user-message.txt `
  --output docs/uat/refined-ingestion-trace.txt
```

```bash
python scripts/render_uat_refined_ingestion_trace.py \
  --input docs/uat/examples/user-message.txt \
  --output docs/uat/refined-ingestion-trace.txt
```

The report should show the user request, routing, reasoning
system-prompt/input/output, entity-planning system-prompt/input/output, entity
candidate preparation, resolved entity map, relationship-planning
system-prompt/input/output, relationship candidate preparation, and final
candidate summary.

Missing-entity relationship trace:

```powershell
python scripts/render_uat_missing_entity_trace.py `
  --input docs/uat/examples/missing-entity-request.txt `
  --entities docs/uat/examples/missing-entity-candidates.json `
  --output docs/uat/missing-entity-trace.txt
```

```bash
python scripts/render_uat_missing_entity_trace.py \
  --input docs/uat/examples/missing-entity-request.txt \
  --entities docs/uat/examples/missing-entity-candidates.json \
  --output docs/uat/missing-entity-trace.txt
```

The report should show the fictitious request, predefined entity candidates or
initial resolved map, relationship planner prompt/input/output,
`MissingEntityRequiredDraft`, missing-entity planning prompt/input/output,
supplemental entity candidate output, updated resolved map, resumed
relationship planning/extraction, and final entity plus relationship
candidates.

Use another env file or force file values over already-set shell variables:

```powershell
python scripts/render_uat_refined_ingestion_trace.py `
  --input local/user.txt `
  --output local/refined-ingestion-trace.txt `
  --env-file src/my_digital_brain/.env `
  --env-override
```

```bash
python scripts/render_uat_refined_ingestion_trace.py \
  --input local/user.txt \
  --output local/refined-ingestion-trace.txt \
  --env-file src/my_digital_brain/.env \
  --env-override
```

## Report Contents

The current report includes:

- reference memory/source text and reference chat history placeholders;
- graph analytics: node counts, relationship counts, connected nodes, emotion
  tags, unresolved contradictions;
- graph node sample: major display, lifecycle, privacy, trust, relationship,
  temporal, affective, and source-language fields;
- optional random graph sample: up to `N` random nodes and up to `N` random
  edges, without semantic search criteria;
- detected contradictions;
- proposed merges;
- hybrid retrieval probes with hit scores, graph assembly selection, rendered
  nodes, and rendered edges;
- review notes for prompt, validator, storage, and retrieval tuning.

By default the report hides technical references such as node ids, endpoint
URLs, and selected/excluded graph ids. Use `--include-technical` when debugging
API payloads or backend graph assembly. The script also redacts likely
secret-looking property keys such as tokens, secrets, passwords, credentials,
API keys, and authorization values.

## PowerShell

Generate the default report:

```powershell
python scripts/render_uat_graph_status.py
```

Use a specific backend and output path:

```powershell
python scripts/render_uat_graph_status.py `
  --api-base-url http://localhost:8000 `
  --output docs/uat/current-graph-status.txt
```

Add semantic/hybrid retrieval probes:

```powershell
python scripts/render_uat_graph_status.py `
  --probe "mio fratello" `
  --probe "coinquilino" `
  --probe "universita"
```

Include reference memory and reference chat history files:

```powershell
python scripts/render_uat_graph_status.py `
  --reference-memory-file docs/uat/reference-memory.txt `
  --reference-chat-history-file docs/uat/reference-chat-history.txt
```

Render up to 12 random nodes and 12 random edges, without semantic criteria:

```powershell
python scripts/render_uat_graph_status.py `
  --random-limit 12
```

Render a reproducible random sample for a committable UAT snapshot:

```powershell
python scripts/render_uat_graph_status.py `
  --random-limit 12 `
  --random-seed "uat-2026-06-06"
```

Increase the random sampling pool before selecting the final random nodes:

```powershell
python scripts/render_uat_graph_status.py `
  --random-limit 20 `
  --random-pool-limit 200
```

Include archived/hidden graph data where the backend endpoint supports it:

```powershell
python scripts/render_uat_graph_status.py `
  --include-archived `
  --random-limit 20
```

Use a protected API deployment:

```powershell
python scripts/render_uat_graph_status.py `
  --api-base-url http://localhost:8000 `
  --token $env:MY_DIGITAL_BRAIN_TOKEN
```

Include technical references for backend debugging:

```powershell
python scripts/render_uat_graph_status.py `
  --include-technical
```

## Bash

Generate the default report:

```bash
python scripts/render_uat_graph_status.py
```

Use a specific backend and output path:

```bash
python scripts/render_uat_graph_status.py \
  --api-base-url http://localhost:8000 \
  --output docs/uat/current-graph-status.txt
```

Add semantic/hybrid retrieval probes:

```bash
python scripts/render_uat_graph_status.py \
  --probe "mio fratello" \
  --probe "coinquilino" \
  --probe "universita"
```

Include reference memory and reference chat history files:

```bash
python scripts/render_uat_graph_status.py \
  --reference-memory-file docs/uat/reference-memory.txt \
  --reference-chat-history-file docs/uat/reference-chat-history.txt
```

Render up to 12 random nodes and 12 random edges, without semantic criteria:

```bash
python scripts/render_uat_graph_status.py \
  --random-limit 12
```

Render a reproducible random sample for a committable UAT snapshot:

```bash
python scripts/render_uat_graph_status.py \
  --random-limit 12 \
  --random-seed "uat-2026-06-06"
```

Increase the random sampling pool before selecting the final random nodes:

```bash
python scripts/render_uat_graph_status.py \
  --random-limit 20 \
  --random-pool-limit 200
```

Include archived/hidden graph data where the backend endpoint supports it:

```bash
python scripts/render_uat_graph_status.py \
  --include-archived \
  --random-limit 20
```

Use a protected API deployment:

```bash
python scripts/render_uat_graph_status.py \
  --api-base-url http://localhost:8000 \
  --token "$MY_DIGITAL_BRAIN_TOKEN"
```

Include technical references for backend debugging:

```bash
python scripts/render_uat_graph_status.py \
  --include-technical
```

## Option Reference

```text
--api-base-url URL       Backend API base URL. Default: http://localhost:8000
--output PATH           Text report path. Default: docs/uat/current-graph-status.txt
--token TOKEN           Optional bearer token for protected API deployments.
--reference-memory TEXT Reference memory/source text to include.
--reference-memory-file PATH
                        File containing reference memory/source text.
--reference-chat-history TEXT
                        Reference chat history text to include.
--reference-chat-history-file PATH
                        File containing reference chat history.
--node-limit N          Number of sample graph nodes to include.
--issue-limit N         Number of contradiction/merge records to include.
--search-limit N        Retrieval hit limit for each probe query.
--probe TEXT            Hybrid retrieval probe query. Can be passed multiple times.
--random-limit N        Up to N random nodes and up to N random edges.
--random-pool-limit N   Maximum node pool fetched before random sampling.
--random-seed TEXT      Optional seed for reproducible random samples.
--include-archived      Include archived/hidden graph data when supported.
--include-technical     Include ids, endpoint URLs, and graph assembly ids.
--timeout SECONDS       HTTP timeout in seconds.
```
