# Evolving SecOps MCP tool descriptions with GEPA

**Author:** Dan Dye  
**Date:** October 2026  
**Series:** Security Operations & Model Context Protocol  
**Repositories:** [github.com/dandye/gusto-mcp-gepa](https://github.com/dandye/gusto-mcp-gepa), [github.com/google/mcp-security (#270)](https://github.com/google/mcp-security/pull/270), [github.com/dandye/open-model-deploy-gcp](https://github.com/dandye/open-model-deploy-gcp)  
**Topics:** Google SecOps, Chronicle SIEM, Model Context Protocol, GEPA, Gemini, Agent Evaluation  

When you connect an agent to the Google Security Operations Model Context Protocol (MCP) ecosystem, the model does not see your Python modules, class hierarchy, or REST client wrappers. It sees a flat list of tool names, JSON input schemas, and docstrings.

Across the local `google/mcp-security` servers (`secops-mcp` for Chronicle SIEM, `gti-mcp` for Google Threat Intelligence, and `secops-soar-mcp` for SOAR) and the remote Google SecOps OneMCP server, a security agent faces 34 to 71 tool declarations on every turn. Those docstrings were originally written by engineers as human reference documentation. Models consume them as a routing table.

When human documentation doubles as an LLM routing table, small ambiguities turn into wrong tool calls, malformed Unified Data Model (UDM) queries, and wasted context tokens.

To fix this systematically rather than tweaking docstrings by hand, I built [`gusto-mcp-gepa`](https://github.com/dandye/gusto-mcp-gepa) and upstreamed the findings to [`google/mcp-security` (#270)](https://github.com/google/mcp-security/pull/270). Using GEPA, the [Genetic Engine for Prompt Ad-hoc Optimization](https://gepa-ai.github.io/gepa/), we evolved tool descriptions across Chronicle SIEM, Google Threat Intelligence (GTI), and SecOps SOAR.

On our 43-case single-server Chronicle SIEM benchmark running on `gemini-3.8-flash`, GEPA-evolved tool descriptions raised end-to-end tool and argument accuracy from **62.79%** (`27/43`) on baseline local docstrings and **65.12%** (`28/43`) on remote OneMCP descriptions to **93.02%** (`40/43`), with **100%** correct tool selection. On our 36-case multi-server routing benchmark across SIEM, GTI, and SOAR, GEPA reached **100.0%** (`36/36`). Finally, when we plugged those evolved descriptions into our multi-turn `SocTier1Agent` evaluation suite (`open-model-deploy-gcp`) on `gemini-2.5-flash`, the agent caught **7/7** active threats (`0` missed breaches), increased signal detection sensitivity ($d'$) by **26.7%** (`1.50` to `1.90`), cut simulated breach and disruption loss by **99.0%** (`\$5,250.24` down to `\$50.21`), saved **10.6%** in total tokens, and reduced average case latency by **12.8%**.

Here is what breaks in baseline MCP tool descriptions, how the GEPA optimization loop works, what the benchmarks showed, and where tool description optimization hits its architectural limit.

---

## The problem: MCP tool docstrings are written for humans, but consumed as a routing table by models

A Python docstring in a FastMCP server has two jobs that pull in opposite directions. For a human developer reading Sphinx docs, a helpful docstring explains general concepts, suggests next steps in an investigation, and stays forgiving about string formats. For an LLM choosing between 40 functions in a single inference pass, that conversational prose blurs the boundary between neighboring tools.

While auditing failures across `secops-mcp`, `gti-mcp`, `secops-soar-mcp`, and remote OneMCP, every routing mistake fell into one of three categories.

### 1. Boundary collisions across tools and servers

Several SecOps tools operate on the same indicators, such as IP addresses, domains, file hashes, and usernames, at different stages of an investigation:

- **Entity profiling vs. raw telemetry search.** In `secops-mcp`, both `lookup_entity` and `search_security_events` accept an indicator and an `hours_back` integer. `lookup_entity` calls Chronicle's `summarize_entity` endpoint to return a high-level prevalence and alert summary. `search_security_events` translates a natural language question into a UDM search over raw event logs. Because the baseline `lookup_entity` docstring says it *"provides a comprehensive summary of an entity's activity based on historical log data within Chronicle"*, models routinely call `lookup_entity` when asked whether any internal corporate host connected to a malicious domain in network logs.
- **Natural language search vs. syntactic UDM search.** `secops-mcp` exposes `search_security_events` for natural language to UDM translation, `search_udm` for raw UDM query execution, and `export_udm_search_csv`. Note that Chronicle SIEM detection rules and UDM searches use **YARA-L 2.0**, which is Chronicle SIEM's rule language for UDM event detection and is completely distinct from standard YARA file or payload pattern matching exposed in GTI via `yara_rules` relationships. Without strict negative constraints, models pass raw UDM syntax like `metadata.event_type = "NETWORK_CONNECTION"` into the natural language translator or use `search_security_events` when the user asked for a CSV export.
- **SIEM alerts vs. SOAR cases.** In multi-server deployments, `secops-mcp` manages SIEM-layer alerts (`get_security_alerts`, `get_security_alert_by_id`, `do_update_security_alert`) while `secops-soar-mcp` manages SOAR-layer incident cases (`list_cases`, `get_case_full_details`, `list_alerts_by_case`, `change_case_priority`). When an analyst asks to check the active queue for duplicate incidents before escalating, vague descriptions cause the model to query raw SIEM detections instead of inspecting the SOAR case queue.

### 2. Undocumented parameter contracts

FastMCP generates JSON Schema types (`string`, `integer`, `boolean`) from Python type annotations, but the underlying Chronicle and VirusTotal REST APIs enforce stricter domain contracts:

- **Protobuf enum prefixes.** In `do_update_security_alert`, the `priority` parameter is typed as `Optional[str]`. When asked to set an alert to critical priority, a model naturally passes `priority="CRITICAL"`. The Chronicle REST API expects the protobuf enum literal `priority="PRIORITY_CRITICAL"`.
- **Natural language translator phrasing.** `search_security_events` calls Chronicle's natural-language-to-UDM translation endpoint. If the model passes a conversational sentence with prefixes and time clauses like `"Search AWS CloudTrail logs for DeleteAnalyzer resource deletion events in the last 48 hours"`, the translator produces a weaker UDM filter than if the model passes a keyword-dense phrase containing the vendor, product, API call, and canonical UDM event type: `"AWS CloudTrail DeleteAnalyzer RESOURCE_DELETION"`.
- **Vendor vs. product UDM field mapping.** In `export_udm_search_csv`, third-party log sources map to specific UDM metadata fields. Suricata IDS logs map to `metadata.vendor_name = "Suricata"`, whereas AWS CloudTrail logs require both `metadata.vendor_name = "AMAZON"` and `metadata.product_name = "AWS CloudTrail"`. When docstrings omit these conventions, the model guesses `metadata.product_name = "Suricata"` and gets zero rows back.

### 3. Context window tax

Every connected MCP tool injects its name, description, and `inputSchema` into the model context on every turn.

In the local `google/mcp-security` servers, baseline docstrings include multi-paragraph `"Workflow Integration"`, `"Use Cases"`, and `"Next Steps (using MCP-enabled tools)"` sections that repeat generic triage advice across all 40 tools. In the 71-tool remote OneMCP catalog (`harvested_onemcp_tools.json`), the compact `inputSchema` payload alone is `246,347` bytes, with `create_feed` (`83,527` bytes) and `update_feed` (`83,637` bytes) consuming `67.86%` of the entire schema budget, or roughly `42,155` tokens, because of 134 inlined vendor `$defs`.

Trimming redundant tutorial prose out of tool descriptions and replacing it with compact routing rules reduces prompt size on every step of a multi-turn investigation.

---

## How GEPA optimizes MCP tool descriptions (`gusto-mcp-gepa` and `google/mcp-security#270`)

[GEPA](https://gepa-ai.github.io/gepa/) (Genetic Engine for Prompt Ad-hoc Optimization) treats prompt optimization as an evolutionary search over a Pareto frontier. Instead of rewriting prompts blindly or relying on a single scalar reward that encourages bloated instructions, GEPA evaluates candidate tool descriptions against a benchmark batch, captures full execution trajectories for failed cases, builds a targeted reflective dataset per tool component, and uses a reflection model to mutate only the descriptions involved in routing or argument errors.

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 1. Benchmark Dataset (43 SIEM cases / 36 Multi-Server cases)         │
│    User Query + Expected Tool + Expected Arguments                   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 2. Evaluation Pass (SecOpsMCPAdapter / CompositeMCPAdapter)          │
│    Task Model (gemini-3.8-flash) selects tool & args from catalog    │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 3. Trajectory Attribution (make_reflective_dataset)                  │
│    Isolates failures where score < 1.0 to two components:            │
│    - tool_description_<expected_tool> (missed target)                │
│    - tool_description_<selected_tool> (false attractor)              │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 4. Reflective Mutation & Pareto Selection                            │
│    Inserts negative boundaries ("Use when / Do NOT use when")        │
│    and parameter formatting rules while pruning redundant prose      │
└──────────────────────────────────────────────────────────────────────┘
```

In `gusto-mcp-gepa`, we implemented two GEPA adapters:

1. **`SecOpsMCPAdapter` (`server/secops/gepa_opt/optimize_secops_mcp.py`).** Connects to `secops_mcp` over stdio, applying a 10 MB `asyncio.create_subprocess_exec` buffer patch so large MCP tool catalogs never trigger `LimitOverrunError`, and evaluates single-server tool selection and argument synthesis.
2. **`CompositeMCPAdapter` (`src/gusto_mcp_gepa/composite_adapter.py`).** Loads the 34-tool multi-server catalog harvested across `secops-mcp`, `gti-mcp`, and `secops-soar-mcp` (`server/secops/gepa_opt/composite_tool_catalog.json`) and evaluates cross-server routing.

The core attribution logic lives in `CompositeMCPAdapter.make_reflective_dataset()`. When the task model routes a query to the wrong tool, both the tool that *should* have been called and the tool that *was* called contributed to the collision. We attribute the failure to both components:

```python
if score < 1.0:
    data_inst = self.dataset_by_query.get(traj["user_query"], {})
    expected_tool = data_inst.get("reference_answer", "")
    expected_server = data_inst.get("target_server", "")
    domain_intent = data_inst.get("domain_intent", "")
    selected_tool = traj.get("selected_tool")

    is_expected = component == f"tool_description_{expected_tool}"
    is_selected = (
        selected_tool
        and component == f"tool_description_{selected_tool}"
    )

    if is_expected or is_selected:
        examples.append({
            "user_query": traj["user_query"],
            "expected_tool": expected_tool,
            "expected_server": expected_server,
            "selected_tool": selected_tool,
            "domain_intent": domain_intent,
            "model_output": traj["model_first_pass_output"],
            "score": score,
            "feedback": (
                f"Task failed. Expected tool '{expected_tool}' on server '{expected_server}'. "
                f"Model selected '{selected_tool}'. "
                f"Domain context: {domain_intent}. "
                "Please add explicit negative constraints and boundary differentiation so the model "
                f"does not confuse '{expected_tool}' with '{selected_tool}'."
            ),
        })
```

### Before and after: what GEPA actually changes

Looking at the evolved descriptions across `src/gusto_mcp_gepa/defaults.py`, `gepa_optimization_results.json`, and `multiserver_optimization_results.json`, GEPA consistently performs two edits: it strips generic tutorial advice to save tokens, and it adds explicit negative routing boundaries (`Do NOT use...`) plus parameter formatting rules where models actually failed.

#### Example 1: `lookup_entity` (resolving the SIEM profiling vs. telemetry search collision)

In upstream `google/mcp-security` (`server/secops/secops_mcp/tools/entity_lookup.py`), `lookup_entity` is a 50-line docstring full of general advice:

```text
# BEFORE (Upstream baseline docstring, 50 lines)
Look up an entity (IP, domain, hash, user, etc.) in Chronicle SIEM for enrichment.

Provides a comprehensive summary of an entity's activity based on historical log data
within Chronicle over a specified time period. This tool queries Chronicle SIEM directly.
Chronicle automatically attempts to detect the entity type from the value provided.

**Workflow Integration:**
- Use this tool after identifying key entities (IPs, domains, users, hashes) from any source
  (e.g., an alert, a SOAR case, threat intelligence report, cloud posture finding).
- Provides historical context and activity summary for an entity directly from SIEM logs.
- Complements information available in other security platforms (SOAR, EDR, Cloud Security)
  by offering a log-centric perspective.

**Use Cases:**
- Quickly understand the context and prevalence of indicators (e.g., '192.168.1.1',
  'evil.com', 'user@example.com', 'hashvalue') by examining SIEM log data.
[...]
Next Steps (using MCP-enabled tools):
- Analyze the summary for suspicious patterns or relationships.
- If more detailed event logs are needed, use a tool to search SIEM events
  (like `search_security_events`) targeting this entity's value.
```

For the compact default registry (`src/gusto_mcp_gepa/defaults.py`), we condense the core definition to three sentences (`38` words instead of `290+`), and in the multi-server optimization (`multiserver_optimization_results.json`), GEPA injects a sharp boundary between `lookup_entity` and `search_security_events`:

```text
# AFTER (GEPA compact default in src/gusto_mcp_gepa/defaults.py)
Look up an entity (IP, domain, hash, user, etc.) in Chronicle SIEM for enrichment.
Provides a comprehensive summary of an entity's activity based on historical log data
within Chronicle over a specified time period. This tool queries Chronicle SIEM directly.

# AFTER (GEPA multi-server boundary-hardened description)
Look up an entity (IP address, domain, file hash, username, etc.) in Chronicle SIEM
specifically for contextual profiling and entity enrichment. This tool provides a
high-level, comprehensive summary of an entity's historical presence, prevalence,
and known activity within Chronicle over a specified time window.

### Tool Selection & Boundary Differentiation:
- USE `lookup_entity` when:
  - The objective is entity enrichment, profiling, or reputation assessment
    (e.g., "Tell me about domain X", "Enrich IP Y", "Summarize activity for user Z").
  - You need metadata, prevalence, or summarized context about a single entity itself.

- DO NOT USE `lookup_entity` (USE `search_security_events` instead) when:
  - The objective is searching or querying internal enterprise telemetry, raw security
    events, or communication logs (e.g., "Did any internal endpoints connect to domain X?",
    "Find network connections to IP Y over the last 72 hours").
  - The query asks to determine whether specific endpoints initiated traffic or
    communicated with an indicator within network or endpoint telemetry.
```

#### Example 2: `search_security_events` (negative routing constraints + translator query synthesis)

The upstream `search_security_events` docstring (`server/secops/secops_mcp/tools/security_events.py`) spans 80 lines, including a `"Troubleshooting & Iterative Searching"` tutorial. However, it never tells the model *when not to call it*, nor how Chronicle's natural language translator expects cloud and endpoint queries to be phrased.

GEPA replaced the tutorial prose with five negative routing rules (`Scope and Differentiation`) and seven concrete query-synthesis templates (`Parameter Guidelines`):

```text
# AFTER (GEPA evolved description in server/secops/gepa_opt/gepa_optimization_results.json)
Search for security events in Chronicle SIEM using natural language queries that are
automatically translated into UDM queries. Ideal for deep log investigations after an
initial alert, case, or entity has been identified.

### Scope and Differentiation:
- Use this tool ONLY when searching Chronicle event logs using natural language
  descriptions or when hunting for specific activity/telemetry.
- Do NOT use this tool if the query contains a raw/syntactic UDM filter
  (e.g., `metadata.event_type = ...` or `principal.ip = ...`); use `search_udm` or
  `export_udm_search_csv` instead.
- Do NOT use for single entity reputation, profile, or entity history lookups by IP,
  domain, hash, or user; use `lookup_entity` instead.
- Do NOT use for alert management (`get_security_alerts`, `get_security_alert_by_id`,
  `do_update_security_alert`), detection rule management (`list_security_rules`,
  `search_security_rules`), threat intelligence queries (`get_threat_intel`),
  IoC retrieval (`get_ioc_matches`), or autocomplete (`find_udm_field_values`).
- Do NOT use when the user explicitly requests exporting results to CSV;
  use `export_udm_search_csv`.

### Parameter Guidelines:
1. `hours_back` (integer):
   - Relative timeframe in hours (e.g., 24 for past day, 168 for past 7 days, 48, 72).
     Omit if explicit ISO start/end timestamps are used.
2. `text` (string):
   - Formulate concise, high-signal, keyword-dense search phrases rather than verbatim
     conversational sentences. Strip out query prefixes (e.g., "Search for", "Find",
     "Look for", "Hunt for") and time phrases (e.g., "in the past 24 hours").
   - Include specific vendor/product names, canonical event types, and exact API or log
     operation names:
     * AWS CloudTrail: Use product name, API call, and UDM event type in uppercase
       (e.g., 'AWS CloudTrail DeleteAnalyzer RESOURCE_DELETION').
     * Microsoft Graph API: Formulate as 'Microsoft Graph Activity <endpoint_url>'
       (e.g., 'Microsoft Graph Activity https://graph.microsoft.com/v1.0/applications').
     * Office 365 / M365: Include specific operations and audit types
       (e.g., 'Office 365 MailItemsAccessed via unapproved application').
     * Azure / Entra ID: Use canonical audit log and action terms
       (e.g., 'Azure AD Directory Audit Add application').
     * Windows endpoint events: Include vendor, product, and canonical event type
       (e.g., 'Microsoft Windows USER_LOGIN blocked').
     * Network / Zeek telemetry: Frame clearly with protocol and action
       (e.g., 'Zeek HTTP network connections from 10.10.20.60').
```

#### Example 3: `get_case_full_details` (token compression without losing aggregation semantics)

In `secops-soar-mcp` (`case_management.py`), `get_case_full_details` had a 33-line docstring with 14 bullet points telling the model how to conduct a general SOC investigation after calling the tool. In `src/gusto_mcp_gepa/defaults.py`, we compressed it to a single 74-word paragraph that preserves every detail about what the function aggregates (`status`, `priority`, `description`, linked alerts, and comment history) while cutting 65% of the characters:

```text
# AFTER (GEPA default in src/gusto_mcp_gepa/defaults.py)
Retrieve comprehensive details for a specific case by aggregating its core information,
associated alerts, and comments. This tool provides a consolidated view of a security
case by fetching its primary details (like status, priority, description), all linked
security alerts, and the full history of comments added by analysts or automation. This
aggregated information is essential for getting a complete understanding of an incident's
context, scope, investigation progress, and collaborative notes without making multiple
separate API calls.
```

---

## Experiment 1: Single-server SIEM and multi-server routing benchmarks (`gusto-mcp-gepa`)

Before testing inside a multi-turn agent loop, we isolated the routing and argument generation layer in `gusto-mcp-gepa`.

### Single-server Chronicle SIEM benchmark (43 cases on `gemini-3.8-flash`)

To build a realistic evaluation dataset rather than synthetic toy prompts, I wrote `scripts/harvest_chronicle_searches.py` to pull 209 saved and shared UDM searches from our live `secops-demo-env` Chronicle tenant via the UserData `searchQueries` REST API. From those 209 real analyst queries, we curated a 43-case benchmark (`server/secops/gepa_opt/mcp_dataset.json`) covering AWS CloudTrail resource deletions, Microsoft Graph API recon, Entra ID directory audits, Office 365 audit log tampering, Zeek network telemetry, YARA-L 2.0 detection rule searches, entity lookups, and SIEM alert updates.

We ran a three-way comparison (`scripts/benchmark_tool_variants.py`) on `gemini-3.8-flash` on Vertex AI `global` with `temperature=0.0` across:
1. **Baseline Local.** Original docstrings in `google/mcp-security`.
2. **Remote OneMCP.** Live tool descriptions harvested from `https://chronicle.us.rep.googleapis.com/mcp`.
3. **GEPA Evolved.** Pareto-optimized descriptions from `gusto-mcp-gepa`.

| Tool Description Profile | Correct Cases | Total Cases | Accuracy | Tool Selection Accuracy | Delta vs. Baseline |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline Local (`mcp-security`)** | 27 | 43 | 62.79% | 95.35% | 0.00% (Baseline) |
| **Remote OneMCP** | 28 | 43 | 65.12% | 95.35% | +2.33% |
| **GEPA Evolved (`gemini-3.8-flash`)** | **40** | **43** | **93.02%** | **100.0%** | **+30.23%** |
| **GEPA Evolved (`gemini-3.7-flash` + `gemini-2.5-pro` reflection)** | **41** | **43** | **95.35%** | **100.0%** | **+32.56%** |

With `gemini-3.8-flash` acting as both task model and reflection model, GEPA resolved 13 of the 16 baseline failures, lifting accuracy by **+30.23 percentage points** (`62.79%` to `93.02%`) and achieving **100% tool selection accuracy** (`0` wrong tools selected across all 43 cases). When we paired `gemini-3.7-flash` as the task model with `gemini-2.5-pro` as the reflection model, accuracy reached **95.35%** (`41/43`).

#### Inspecting the 3 remaining misses on `gemini-3.8-flash`

The 3 remaining misses in `comparative_benchmark_results.json` (`40/43`) are instructive because the model picked the right tool every time and failed only on undocumented API parameter conventions:

1. **Case #8 (`do_update_security_alert`).** For the query *"Mark alert 'de_9988776655' as TRUE_POSITIVE with critical priority, severity 95, and root cause 'Phishing email leading to credential theft'"*, the model called `do_update_security_alert` with `alert_id="de_9988776655"`, `verdict="TRUE_POSITIVE"`, `severity=95`, and `priority="CRITICAL"`. The Chronicle API requires the `PRIORITY_` prefix (`priority="PRIORITY_CRITICAL"`).
2. **Case #33 (`export_udm_search_csv`).** For *"Export CSV of AWS CloudTrail resource deletions for DeleteAnalyzer with metadata.event_timestamp, principal.user.userid, and target.resource.name"*, GEPA improved the model's query from baseline's bare `metadata.product_event_type = "DeleteAnalyzer"` to `metadata.event_type = "RESOURCE_DELETION" AND metadata.product_name = "AWS CloudTrail" AND metadata.product_event_type = "DeleteAnalyzer"`. However, the strict reference answer also required `metadata.vendor_name = "AMAZON"`.
3. **Case #40 (`export_udm_search_csv`).** For *"Export a CSV of Suricata IDS detection events including event timestamp, rule name, source IP, and destination IP for the last 24 hours"*, the model selected `export_udm_search_csv` and extracted all four UDM columns accurately, but wrote `metadata.product_name = "Suricata"` instead of `metadata.vendor_name = "Suricata"`.

All three misses come down to schema-level enum and vendor-field conventions that were absent from `do_update_security_alert` and `export_udm_search_csv` docstrings during that run.

### Multi-server routing benchmark across SIEM, GTI, and SOAR (36 cases on `gemini-3.8-flash`)

In a real SOC, an agent does not talk to Chronicle SIEM in isolation. It connects to `secops-mcp` for SIEM, `gti-mcp` for Google Threat Intelligence, and `secops-soar-mcp` for SOAR at the same time.

To test cross-server routing, we harvested all 34 active tools across the three servers over stdio into `server/secops/gepa_opt/composite_tool_catalog.json` and built a balanced 36-case benchmark (`server/secops/gepa_opt/multiserver_dataset.json`: 12 SIEM cases, 12 GTI cases, 12 SOAR cases).

| Profile | SIEM (`secops`) | Threat Intel (`gti`) | Case Mgmt (`soar`) | Total Correct | Accuracy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline Multi-Server** | 11 / 12 | 12 / 12 | 12 / 12 | 35 / 36 | 97.22% |
| **GEPA Evolved Multi-Server** | **12 / 12** | **12 / 12** | **12 / 12** | **36 / 36** | **100.0%** |

On baseline descriptions (`multiserver_benchmark_results.json`), the model got `35/36` (`97.22%`), failing on Case #0:

- **Query.** *"Did any internal corporate endpoints connect to malicious domain 'update-service-cdn.com' in our network telemetry over the past 72 hours?"*
- **Expected.** `search_security_events` on `secops`
- **Baseline Actual.** `lookup_entity(entity_value="update-service-cdn.com", hours_back=72)` on `secops`

After one evolutionary pass with `CompositeMCPAdapter`, GEPA added the explicit `USE lookup_entity when` and `DO NOT USE lookup_entity (USE search_security_events instead) when` block shown above, pushing multi-server routing accuracy to **100.0%** (`36/36`).

---

## Experiment 2: End-to-end multi-turn SOC agent evaluation (`gemma_deploy` Gen 3 interactive suite)

Single-turn routing benchmarks prove that a model picks the right tool on step 1. They do not tell you what happens over a multi-turn investigation where the agent has to inspect an alert, query threat intelligence, check for duplicate SOAR cases, handle HTTP 503 tool outages, and decide whether to isolate a production host.

To measure the end-to-end operational effect of GEPA tool descriptions, I wired `gusto-mcp-gepa` into our Gen 3 Interactive SOC Evaluation Engine in [`open-model-deploy-gcp`](https://github.com/dandye/open-model-deploy-gcp) (`gemma_deploy`).

### Dynamic description injection via `McpToolProvider`

In `agent/mcp_provider.py`, I implemented `McpToolProvider` to dynamically resolve tool descriptions from either `--mcp-provider default` for baseline docstrings or `--mcp-provider gepa` for Pareto-optimized descriptions from `gusto-mcp-gepa`, while mapping tool aliases between our local sandbox tools and remote FastMCP names:

```python
# Aliases between local/remote MCP tools and canonical GEPA descriptions
TOOL_ALIASES: Dict[str, str] = {
    "get_case": "get_case_full_details",
    "create_case_comment": "post_case_comment",
    "update_case_comment": "post_case_comment",
    "summarize_entity": "lookup_entity",
    "udm_search": "search_udm",
    "fetch_alert_data": "get_security_alert_by_id",
}
```

Inside `SocTier1Agent._build_tools_description()`, every tool registered in the agent's prompt queries `self.mcp_provider.get_description(name, default_doc=doc)`. That lets us hold the model (`gemini-2.5-flash`), temperature, system prompt, sandbox telemetry, and evaluation harness completely fixed while swapping only the MCP tool descriptions.

### Head-to-head scorecard: default MCP vs. Gusto GEPA MCP

We ran `gemini-2.5-flash` across the 10-case **Gen 3 Interactive SOC Agent Evaluation Suite** (`configs/evals/gen3/soc_tier1_interactive.json`). Our Gen 3 cost engine (`scripts/eval_cost_engine.py`) scores agents using Signal Detection Theory, calculating sensitivity $d'$ and decision criterion bias $c$ with the Macmillan & Kaplan 1985 half-count correction, alongside an asymmetric blast-radius financial loss model where missing an active adversary breach (`FALSE_NEGATIVE`) costs `\$5,000` to `\$250,000` depending on asset criticality, and unnecessary containment on benign traffic (`FALSE_POSITIVE`) incurs `\$50` to `\$50,000` in business disruption loss.

| Evaluation Dimension | Default Baseline MCP | Gusto GEPA MCP | Delta / Impact |
| :--- | :--- | :--- | :--- |
| **Sensitivity Index ($d'$)** | **1.50** | **1.90** | **+0.40 (+26.7%)** |
| **Decision Criterion Bias ($c$)** | -0.32 | -0.52 | -0.20 (More decisive threat response) |
| **True Positive Hit Rate** | 85.7% (6 Hits / 1 Miss) | **92.9% (7 Hits / 0 Misses)** | **+7.2% (Zero breach escapes)** |
| **False Alarm Rate** | 33.3% (1 FA / 2 CR) | 33.3% (1 FA / 2 CR) | 0.0% (Maintained) |
| **Total Expected Operational Loss** | **\$5,250.24** | **\$50.21** | **-\$5,200.03 (-99.0%)** |
| - Adversary Breach Loss (FN) | \$5,000.00 | **\$0.00** | **-\$5,000.00 (Zero uncontained breach)** |
| - Business Disruption Loss (FP) | \$250.00 | \$50.00 | -\$200.00 |
| **Pass Rate** | 40.0% (4/10) | 30.0% (3/10) | -10.0% (Strict rubric / assertion nuance) |
| **Average Rubric Score** | 74.5 / 100 | 65.3 / 100 | -9.2 pts |
| **Total Token Usage** | 111,826 tokens | 100,025 tokens | **-11,801 tokens (-10.6%)** |
| **Average Case Latency** | 24.71 s | 21.54 s | **-3.17 s (-12.8% Faster)** |
| **Generation TPS** | 70.59 tok/s | 68.50 tok/s | -2.09 tok/s |
| **Total Tool Invocations** | 12 | 12 | 1.2 tools/case |
| **Counterfactual Consistency** | 100.0% | 100.0% | 100% Consistent |

### Case-by-case breakdown across the 10 interactive scenarios

| Case ID | Case Scenario | Default MCP Outcome | GEPA MCP Outcome | Operational Loss Change |
| :--- | :--- | :--- | :--- | :--- |
| `CASE-GEN3-01-LOKIBOT-C2` | Lokibot C2 InfoStealer Host Containment | TRUE_POSITIVE (\$0) | TRUE_POSITIVE (\$0) | \$0 |
| `CASE-GEN3-02-RFC5737-BENIGN-IP` | RFC-5737 Documentation IP Safe Resolution | TRUE_NEGATIVE (\$0) | FALSE_POSITIVE (\$50) | +\$50 (Cautious containment) |
| `CASE-GEN3-03-PHISHING-CRED-HARVEST` | Credential Harvesting Phishing Domain Block | TRUE_POSITIVE (\$0) | TRUE_POSITIVE (\$0) | \$0 |
| `CASE-GEN3-04-DUPLICATE-SOAR-CASE` | Duplicate SOAR Case Detection & Appending | **FALSE_NEGATIVE (\$5,000)** | **TRUE_POSITIVE (\$0)** | **-\$5,000 (Breach caught)** |
| `CASE-GEN3-05-RANSOMWARE-ESCALATION` | Critical Production Ransomware Host Isolation | TRUE_POSITIVE (\$0, 40/100) | **TRUE_POSITIVE (\$0, 98/100)** | \$0 (Rubric score 40 to 98) |
| `CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL` | Ambiguous DNS Tunneling on Critical Asset | TRUE_POSITIVE (\$0, 100/100) | TRUE_POSITIVE (\$0, 100/100) | \$0 |
| `CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC` | PsExec Lateral Movement & Host Isolation | TRUE_POSITIVE (\$0) | TRUE_POSITIVE (\$0) | \$0 |
| `CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT` | Supply Chain Binary Revoked Certificate | TRUE_POSITIVE (\$0) | TRUE_POSITIVE (\$0) | \$0 |
| `CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE`| Degraded Tool Outage Handling | FALSE_POSITIVE (\$250) | **TRUE_NEGATIVE (\$0)** | **-\$250 (Clean degradation)** |
| `CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE` | Authorized Qualys Scanner Noise Triage | TRUE_NEGATIVE (\$0, 100/100) | TRUE_NEGATIVE (\$0, 100/100) | \$0 |

### Where GEPA tool descriptions made the difference

1. **Catching the duplicate SOAR case (`CASE-GEN3-04-DUPLICATE-SOAR-CASE`, `-\$5,000` loss).** Under baseline docstrings, the agent failed to correlate the incoming alert with the existing active SOAR investigation and missed the required containment workflow, resulting in a `FALSE_NEGATIVE` and a `\$5,000` simulated breach penalty. With the GEPA-evolved descriptions for `list_cases`, `get_case_full_details`, and `post_case_comment`, which maps to `create_case_comment` and `update_case_comment`, the agent checked the SOAR queue, identified the duplicate case, appended its telemetry findings, and completed the threat response as a `TRUE_POSITIVE` (`\$0` loss).
2. **Clean degradation during an HTTP 503 outage (`CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE`, `-\$250` loss).** When the enrichment backend returned an injected `HTTP 503 Service Unavailable` fault, the baseline agent panicked and executed an unverified containment action, resulting in a `FALSE_POSITIVE` and a `\$250` disruption penalty. Under GEPA MCP, clearer tool scope definitions helped the agent recognize that its SIEM and threat intel lookup had failed without fabricating evidence, flipping the outcome to `TRUE_NEGATIVE` (`\$0` loss).
3. **Production ransomware escalation quality (`CASE-GEN3-05-RANSOMWARE-ESCALATION`, rubric score `40/100` to `98/100`).** Both runs isolated the ransomware host, but the GEPA run gathered the exact case and entity context needed to satisfy the LLM judge rubric, jumping from `40/100` to `98/100`.
4. **Token and latency reduction (`-10.6%` tokens, `-12.8%` latency).** Across the 10 scenarios, replacing verbose baseline docstrings with compact GEPA descriptions trimmed total token usage from `111,826` to `100,025` (`-11,801` tokens) and cut average wall-clock latency per case from `24.71` seconds to `21.54` seconds.

### Honest trade-off analysis: why tool descriptions alone cannot replace runbooks

Look closely at the three metrics that moved in the other direction on the scorecard:

- **Decision criterion bias ($c$)** shifted from `-0.32` to `-0.52`. In Signal Detection Theory, a more negative $c$ means the agent has a lower threshold for taking containment action.
- On **`CASE-GEN3-02-RFC5737-BENIGN-IP`**, that extra aggressiveness caused the GEPA agent to execute a cautious indicator block (`block_indicator`) on `192.0.2.100`, an RFC-5737 `TEST-NET-1` documentation IP address, incurring a `\$50` false positive penalty where the baseline agent resolved it as a `TRUE_NEGATIVE`.
- **Average rubric score** dipped from `74.5` to `65.3`, and the composite pass rate moved from `4/10` to `3/10`. Why? Because our Gen 3 composite pass gate requires both a `>= 70.0` prose rubric score from the semantic judge and strict epistemic step gating. When GEPA made the tool descriptions more action-oriented and concise, `gemini-2.5-flash` moved faster to tool execution and wrote shorter final summaries that omitted secondary narrative points expected by the prose rubric.

This highlights an architectural boundary that every agent engineer runs into eventually. **Optimizing tool descriptions fixes how an agent selects and parameterizes tools, defining what a tool does and how to call it, but it does not govern multi-step investigative policy or the order in which evidence must be verified before isolating a host.**

Telling a model not to isolate hosts for RFC-5737 documentation subnets or authorized vulnerability scanners does not belong inside the docstring of `lookup_entity` or `isolate_host`. That is procedural domain logic. In our companion work on GEPA runbook evolution (`agent/gepa_runbook_optimizer.py`), evolving the incident response playbooks with a 4-stage epistemic verification sequence covering CMDB asset role, network routing classification, threat intel reputation, and behavioral corroboration eliminated the RFC-5737 and scanner false alarms while preserving `92.9%` threat recall.

Use GEPA on MCP tool descriptions to make your tool routing sharp and token-efficient. Use procedural runbooks and supervisor-worker gating to control containment blast radius.

---

## Operationalizing GEPA profiles (`--profile gepa|onemcp|baseline` and `just eval-compare-gepa`)

All 40 GEPA-optimized tool descriptions across Chronicle SIEM (`12` tools), Google Threat Intelligence (`18` tools), and SecOps SOAR (`10` tools) are packaged in `gusto-mcp-gepa` (`src/gusto_mcp_gepa/defaults.py`) with namespace-safe server entrypoints (`gusto-gepa-secops-mcp`, `gusto-gepa-gti-mcp`, `gusto-gepa-secops-soar-mcp`, and `gusto-gepa-scc-mcp`) pinned to `mcp<2.0`.

### 1. Inspecting, verifying, and serving GEPA descriptions in `gusto-mcp-gepa`

You can inspect the optimized descriptions, verify compliance against the upstream `external/mcp-security` submodule, and launch any of the MCP servers using `manage.py` or `just`:

```bash
GUSTO_REPO_DIR="$HOME/Projects/gusto-mcp-gepa__worktrees/main"
CHRONICLE_PROJECT_ID="dandye-0324-chronicle"
CHRONICLE_CUSTOMER_ID="7e977ce4-f45d-43b2-aea0-52f8b66acd80"
CHRONICLE_REGION="us"
GUSTO_MCP_PROFILE="gepa"

# Verify that all 40 tracked tools across SIEM, GTI, and SOAR match GEPA defaults
uv --directory "$GUSTO_REPO_DIR" run python manage.py gepa verify

# Compare local GEPA descriptions against the upstream google/mcp-security submodule
uv --directory "$GUSTO_REPO_DIR" run python manage.py gepa compare

# List GEPA-optimized tool descriptions for Chronicle SIEM
uv --directory "$GUSTO_REPO_DIR" run python manage.py gepa list --suite secops

# Launch the SecOps SIEM MCP server with GEPA defaults
CHRONICLE_PROJECT_ID="$CHRONICLE_PROJECT_ID" \
CHRONICLE_CUSTOMER_ID="$CHRONICLE_CUSTOMER_ID" \
CHRONICLE_REGION="$CHRONICLE_REGION" \
GUSTO_MCP_PROFILE="$GUSTO_MCP_PROFILE" \
uv --directory "$GUSTO_REPO_DIR" run python manage.py serve --server secops
```

When benchmarking MCP clients such as Gemini CLI, Antigravity, or Claude Code against different prompt variants, switching between `--profile gepa` for evolved descriptions, `--profile onemcp` for harvested remote OneMCP descriptions, and `--profile baseline` for upstream docstrings via `GUSTO_MCP_PROFILE` lets you run controlled A/B tests over stdio without editing server code.

### 2. Running the head-to-head SOC evaluation in `open-model-deploy-gcp`

To reproduce the 10-case Gen 3 Interactive SOC evaluation comparing `--mcp-provider default` against `--mcp-provider gepa`, run the `eval-compare-gepa` recipe from `open-model-deploy-gcp`:

```bash
DEPLOY_REPO_DIR="$HOME/Projects/gemma_deploy__worktrees/main"
GUSTO_MCP_GEPA_DIR="$HOME/Projects/gusto-mcp-gepa__worktrees/main"
MODEL_FLAVOR="gemini-2.5-flash"
EVAL_GEN="3"

# Run single GEPA evaluation pass
GUSTO_MCP_GEPA_DIR="$GUSTO_MCP_GEPA_DIR" \
just --justfile "$DEPLOY_REPO_DIR/Justfile" --working-directory "$DEPLOY_REPO_DIR" \
  eval-gepa "$MODEL_FLAVOR" "$EVAL_GEN"

# Run full back-to-back A/B comparison (Default Baseline MCP vs. Gusto GEPA MCP)
GUSTO_MCP_GEPA_DIR="$GUSTO_MCP_GEPA_DIR" \
just --justfile "$DEPLOY_REPO_DIR/Justfile" --working-directory "$DEPLOY_REPO_DIR" \
  eval-compare-gepa "$MODEL_FLAVOR"
```

This generates side-by-side Markdown scorecards in `docs/soc_eval_results/gen3_baseline_gemini-2.5-flash_report.md` and `docs/soc_eval_results/gen3_gepa_gemini-2.5-flash_report.md`, complete with Signal Detection Theory metrics ($d'$, $c$), dollar-weighted operational loss breakdowns, and per-case tool trajectories.
