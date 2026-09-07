/**
 * Audit historical evaluation artifacts and render a traceable comparison.
 *
 * This module deliberately treats absent values as unavailable. It never
 * substitutes zero for a missing metric, because that would turn incomplete
 * historical evidence into a misleading result.
 */

export type Lifecycle = "success" | "failed" | "unverified";
export type IssueSeverity = "error" | "warning" | "info";

export interface AuditIssue {
  severity: IssueSeverity;
  code: string;
  artifact?: string;
  message: string;
}

export interface MetricValue {
  value?: number;
  status: "observed" | "missing" | "invalid";
}

export interface ArtifactAudit {
  path: string;
  sha256?: string;
  parseOk: boolean;
  lifecycle: Lifecycle;
  provenanceComplete: boolean;
  caseCount?: number;
  failedCaseCount: number;
  metrics: Record<string, MetricValue>;
  issues: AuditIssue[];
  data?: Record<string, unknown>;
}

export interface ComparisonResult {
  baseline: ArtifactAudit;
  evolved: ArtifactAudit;
  issues: AuditIssue[];
  markdown: string;
}

const REQUIRED_PROVENANCE = [
  "source_commit",
  "model",
  "configuration_hash",
  "dataset",
  "runbook",
  "evaluator",
  "started_at",
  "completed_at",
  "logs",
  "lifecycle",
] as const;

const METRIC_PATHS: Record<string, string[]> = {
  total_cases: ["summary", "total_cases"],
  passed_cases: ["summary", "passed_cases"],
  pass_rate: ["summary", "pass_rate"],
  avg_rubric_score: ["summary", "avg_rubric_score"],
  avg_latency_s: ["summary", "avg_latency_s"],
  total_tokens: ["summary", "total_tokens"],
  total_tool_calls: ["summary", "total_tool_calls"],
  total_loss_usd: ["summary", "operational_loss", "total_loss_usd"],
  fp_loss_usd: ["summary", "operational_loss", "fp_loss_usd"],
  fn_loss_usd: ["summary", "operational_loss", "fn_loss_usd"],
  investigation_cost_usd: ["summary", "operational_loss", "investigation_cost_usd"],
  hit_rate: ["summary", "sdt_metrics", "hit_rate"],
  false_alarm_rate: ["summary", "sdt_metrics", "false_alarm_rate"],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getPath(root: Record<string, unknown>, path: string[]): unknown {
  let value: unknown = root;
  for (const key of path) {
    if (!isRecord(value) || !(key in value)) return undefined;
    value = value[key];
  }
  return value;
}

function numberMetric(root: Record<string, unknown>, path: string[]): MetricValue {
  const value = getPath(root, path);
  if (value === undefined || value === null) return { status: "missing" };
  return typeof value === "number" && Number.isFinite(value)
    ? { value, status: "observed" }
    : { status: "invalid" };
}

function findMissingProvenance(root: Record<string, unknown>): string[] {
  const provenance = isRecord(root.provenance) ? root.provenance : undefined;
  return REQUIRED_PROVENANCE.filter((field) => {
    const value = provenance?.[field];
    if (value === undefined || value === null) return true;
    if (typeof value === "string") return value.trim().length === 0;
    if (Array.isArray(value)) return value.length === 0;
    if (isRecord(value)) return Object.keys(value).length === 0;
    return false;
  });
}

function explicitLifecycle(root: Record<string, unknown>): Lifecycle {
  const candidates: unknown[] = [
    root.lifecycle_status,
    root.run_status,
    root.execution_status,
    root.result_status,
    root.status,
    root.exit_code,
  ];
  for (const lifecycle of [root.lifecycle, isRecord(root.provenance) ? root.provenance.lifecycle : undefined]) {
    if (isRecord(lifecycle)) candidates.push(...Object.values(lifecycle));
  }
  let sawSuccess = false;
  let sawUnverified = false;
  for (const candidate of candidates) {
    if (typeof candidate === "number") {
      if (candidate !== 0) return "failed";
      sawSuccess = true;
      continue;
    }
    if (typeof candidate !== "string") continue;
    const normalized = candidate.toLowerCase();
    if (["failed", "failure", "error", "cancelled", "canceled", "timeout", "aborted"].includes(normalized)) {
      return "failed";
    }
    if (["success", "succeeded", "complete", "completed", "ok"].includes(normalized)) {
      sawSuccess = true;
    } else if (["unverified", "running", "partial", "unknown", "pending"].includes(normalized)) {
      sawUnverified = true;
    }
  }
  if (typeof root.success === "boolean") {
    if (!root.success) return "failed";
    sawSuccess = true;
  }
  if (sawUnverified) return "unverified";
  if (sawSuccess) return "success";
  return "unverified";
}

function formatNumber(value: number | undefined, suffix = ""): string {
  if (value === undefined) return "Unavailable";
  return `${value.toLocaleString("en-US", { maximumFractionDigits: 4 })}${suffix}`;
}

function percentage(value: number): number {
  // SDT rates are fractions; pass_rate is already expressed as a percentage.
  return value >= 0 && value <= 1 ? value * 100 : value;
}

function metricValue(audit: ArtifactAudit, name: string): number | undefined {
  return audit.metrics[name]?.status === "observed" ? audit.metrics[name].value : undefined;
}

function parseMoney(value: string): number {
  return Number(value.replaceAll(",", ""));
}

function moneyEquals(a: number | undefined, b: number): boolean {
  return a !== undefined && Math.abs(a - b) < 0.005;
}

function narrativeIssues(
  narrative: string,
  baseline: ArtifactAudit,
  evolved: ArtifactAudit,
  narrativePath: string,
): AuditIssue[] {
  const issues: AuditIssue[] = [];
  const lossTransition = narrative.match(
    /operational financial loss[\s\S]{0,180}?from\s+\*?\*?\$([\d,.]+)\*?\*?[\s\S]{0,100}?to\s+\*?\*?\$([\d,.]+)\*?\*?/i,
  );
  if (lossTransition) {
    const claimedBaseline = parseMoney(lossTransition[1]);
    const claimedEvolved = parseMoney(lossTransition[2]);
    const actualBaseline = metricValue(baseline, "total_loss_usd");
    const actualEvolved = metricValue(evolved, "total_loss_usd");
    if (!moneyEquals(actualBaseline, claimedBaseline) || !moneyEquals(actualEvolved, claimedEvolved)) {
      issues.push({
        severity: "error",
        code: "narrative-json-mismatch",
        artifact: narrativePath,
        message: `Narrative claims $${claimedBaseline.toFixed(2)} → $${claimedEvolved.toFixed(2)} total loss, but selected JSON reports ${formatNumber(actualBaseline, " USD")} → ${formatNumber(actualEvolved, " USD")}.`,
      });
    }
  }

  const reduction = narrative.match(/(\d+(?:\.\d+)?)%\s+reduction in operational financial loss/i);
  const actualBaseline = metricValue(baseline, "total_loss_usd");
  const actualEvolved = metricValue(evolved, "total_loss_usd");
  if (reduction && actualBaseline !== undefined && actualEvolved !== undefined && actualBaseline !== 0) {
    const actualReduction = ((actualBaseline - actualEvolved) / actualBaseline) * 100;
    if (Math.abs(actualReduction - Number(reduction[1])) > 0.05) {
      issues.push({
        severity: "error",
        code: "narrative-reduction-mismatch",
        artifact: narrativePath,
        message: `Narrative claims a ${reduction[1]}% reduction, while selected JSON implies ${actualReduction.toFixed(2)}%.`,
      });
    }
  }

  // The historical analysis contains a four-configuration Markdown table.
  // Resolve the raw and evolved columns by their headers instead of assuming
  // a positional column, then compare only metrics represented in JSON.
  const tableLines = narrative.split(/\r?\n/);
  const headerIndex = tableLines.findIndex((line) => /Raw Playbooks/i.test(line) && /GEPA Generalized Playbooks/i.test(line));
  if (headerIndex >= 0) {
    const headerCells = tableLines[headerIndex].split("|").map((cell) => cell.trim().toLowerCase());
    const rawIndex = headerCells.findIndex((cell) => cell.includes("raw playbooks"));
    const evolvedIndex = headerCells.findIndex((cell) => cell.includes("gepa generalized playbooks"));
    const tableMetricNames: Record<string, { name: string; kind: "number" | "percent" | "money" }> = {
      "pass rate": { name: "pass_rate", kind: "percent" },
      "average rubric score": { name: "avg_rubric_score", kind: "number" },
      "empirical hit rate": { name: "hit_rate", kind: "percent" },
      "false alarm rate": { name: "false_alarm_rate", kind: "percent" },
      "false positive loss": { name: "fp_loss_usd", kind: "money" },
      "false negative loss": { name: "fn_loss_usd", kind: "money" },
      "total operational loss": { name: "total_loss_usd", kind: "money" },
      "total tool invocations": { name: "total_tool_calls", kind: "number" },
      "average latency": { name: "avg_latency_s", kind: "number" },
    };
    if (rawIndex >= 0 && evolvedIndex >= 0) {
      for (let rowIndex = headerIndex + 2; rowIndex < tableLines.length; rowIndex += 1) {
        const cells = tableLines[rowIndex].split("|").map((cell) => cell.trim());
        const metricLabel = cells[1]?.replaceAll("*", "").toLowerCase() ?? "";
        const metricEntry = Object.entries(tableMetricNames).find(([label]) => metricLabel.startsWith(label));
        if (!metricEntry || cells.length <= Math.max(rawIndex, evolvedIndex)) continue;
        const [, metric] = metricEntry;
        const extract = (cell: string): number | undefined => {
          const match = metric.kind === "money" ? cell.match(/\$([\d,.]+)/) : cell.match(/-?\d+(?:\.\d+)?/);
          return match ? parseMoney(match[1] ?? match[0]) : undefined;
        };
        const claimedRaw = extract(cells[rawIndex]);
        const claimedEvolved = extract(cells[evolvedIndex]);
        const actualRaw = metricValue(baseline, metric.name);
        const actualEvolvedValue = metricValue(evolved, metric.name);
        const rawMatches = claimedRaw !== undefined && (metric.kind === "percent" ? Math.abs(percentage(actualRaw ?? NaN) - claimedRaw) < 0.05 : Math.abs((actualRaw ?? NaN) - claimedRaw) < 0.005);
        const evolvedMatches = claimedEvolved !== undefined && (metric.kind === "percent" ? Math.abs(percentage(actualEvolvedValue ?? NaN) - claimedEvolved) < 0.05 : Math.abs((actualEvolvedValue ?? NaN) - claimedEvolved) < 0.005);
        if (!rawMatches || !evolvedMatches) {
          issues.push({
            severity: "error",
            code: "narrative-table-mismatch",
            artifact: narrativePath,
            message: `Narrative table ${metricEntry[0]} claims ${claimedRaw === undefined ? "Unavailable" : claimedRaw} → ${claimedEvolved === undefined ? "Unavailable" : claimedEvolved}, while selected JSON reports ${actualRaw === undefined ? "Unavailable" : actualRaw} → ${actualEvolvedValue === undefined ? "Unavailable" : actualEvolvedValue}.`,
          });
        }
      }
    }
  }

  if (/(?:\bsaved\b|\bavoided\b|\bprevented\b)/i.test(narrative) && !/simulat(?:ed|ion)|modeled|counterfactual/i.test(narrative)) {
    issues.push({
      severity: "warning",
      code: "unlabeled-savings-language",
      artifact: narrativePath,
      message: "Narrative uses savings/avoidance language without a nearby simulated or modeled qualifier; historical loss is not actual financial savings.",
    });
  } else if (/(?:\bsaved\b|\bavoided\b|\bprevented\b)/i.test(narrative)) {
    issues.push({
      severity: "warning",
      code: "simulated-savings-claim",
      artifact: narrativePath,
      message: "Narrative contains savings/avoidance claims. Treat them as simulated loss-model results, never as actual savings or avoided downtime.",
    });
  }
  return issues;
}

export async function auditArtifact(path: string): Promise<ArtifactAudit> {
  const issues: AuditIssue[] = [];
  let raw: string;
  try {
    raw = await Bun.file(path).text();
  } catch (error) {
    return {
      path,
      parseOk: false,
      lifecycle: "unverified",
      provenanceComplete: false,
      failedCaseCount: 0,
      metrics: {},
      issues: [{ severity: "error", code: "artifact-unreadable", artifact: path, message: String(error) }],
    };
  }

  const sha256 = new Bun.CryptoHasher("sha256").update(raw).digest("hex");
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    return {
      path,
      sha256,
      parseOk: false,
      lifecycle: "unverified",
      provenanceComplete: false,
      failedCaseCount: 0,
      metrics: {},
      issues: [{ severity: "error", code: "malformed-json", artifact: path, message: `Invalid JSON: ${String(error)}` }],
    };
  }
  if (!isRecord(parsed)) {
    return {
      path,
      sha256,
      parseOk: false,
      lifecycle: "unverified",
      provenanceComplete: false,
      failedCaseCount: 0,
      metrics: {},
      issues: [{ severity: "error", code: "invalid-root", artifact: path, message: "Artifact root must be a JSON object." }],
    };
  }

  const lifecycle = explicitLifecycle(parsed);
  const missingProvenance = findMissingProvenance(parsed);
  const provenanceComplete = missingProvenance.length === 0;
  if (!provenanceComplete) {
    issues.push({
      severity: "warning",
      code: "missing-provenance",
      artifact: path,
      message: `Missing provenance fields: ${missingProvenance.join(", ")}. Historical conclusions remain unverified.`,
    });
  }
  if (lifecycle === "unverified") {
    issues.push({
      severity: "warning",
      code: "unverified-lifecycle",
      artifact: path,
      message: "Run lifecycle evidence is missing or unresolved; this result cannot be treated as a verified successful run.",
    });
  } else if (lifecycle === "failed") {
    issues.push({
      severity: "error",
      code: "non-success-run",
      artifact: path,
      message: "Artifact explicitly records a non-success lifecycle outcome.",
    });
  }

  const metrics = Object.fromEntries(Object.entries(METRIC_PATHS).map(([name, pathParts]) => [name, numberMetric(parsed, pathParts)]));
  if (!isRecord(parsed.summary)) {
    issues.push({
      severity: "error",
      code: "missing-summary",
      artifact: path,
      message: "Artifact has no summary object; benchmark metrics are unavailable.",
    });
  }
  for (const [name, metric] of Object.entries(metrics)) {
    if (metric.status === "invalid") {
      issues.push({
        severity: "error",
        code: "invalid-metric",
        artifact: path,
        message: `Metric ${name} is present but is not a finite number.`,
      });
    }
  }
  const caseResults = Array.isArray(parsed.case_results) ? parsed.case_results : [];
  const failedCaseCount = caseResults.filter((item) => {
    if (!isRecord(item)) return true;
    const status = typeof item.status === "string" ? item.status.toLowerCase() : "";
    return ["failed", "failure", "error", "cancelled", "timeout"].includes(status);
  }).length;
  if (failedCaseCount > 0) {
    issues.push({
      severity: "error",
      code: "failed-case-results",
      artifact: path,
      message: `${failedCaseCount} case result(s) carry a non-success status.`,
    });
  }
  const caseCount = metricValue({ metrics } as ArtifactAudit, "total_cases");
  if (caseCount !== undefined && caseCount !== caseResults.length) {
    issues.push({
      severity: "warning",
      code: "case-count-mismatch",
      artifact: path,
      message: `Summary reports ${caseCount} cases but case_results contains ${caseResults.length}.`,
    });
  }

  return {
    path,
    sha256,
    parseOk: true,
    lifecycle,
    provenanceComplete,
    caseCount,
    failedCaseCount,
    metrics,
    issues,
    data: parsed,
  };
}

function displayMetric(audit: ArtifactAudit, name: string, kind: "number" | "percent" | "money" = "number"): string {
  const metric = audit.metrics[name];
  if (!metric || metric.status !== "observed" || metric.value === undefined) return "Unavailable";
  if (kind === "money") return `$${metric.value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (simulated loss)`;
  if (kind === "percent") return `${percentage(metric.value).toFixed(2)}%`;
  return formatNumber(metric.value);
}

function delta(a: ArtifactAudit, b: ArtifactAudit, name: string, kind: "number" | "percent" | "money" = "number"): string {
  const av = metricValue(a, name);
  const bv = metricValue(b, name);
  if (av === undefined || bv === undefined) return "Unavailable";
  const value = kind === "percent" ? percentage(bv) - percentage(av) : bv - av;
  if (kind === "money") return `${value >= 0 ? "+" : "−"}$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} simulated loss`;
  if (kind === "percent") return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)} pp`;
  return `${value >= 0 ? "+" : "−"}${formatNumber(Math.abs(value))}`;
}

function sourceLabel(audit: ArtifactAudit): string {
  return audit.path.replace(/^.*\//, "");
}

export function renderComparison(
  baseline: ArtifactAudit,
  evolved: ArtifactAudit,
  narrativePath?: string,
  narrativeText?: string,
): string {
  const issues = [...baseline.issues, ...evolved.issues];
  if (narrativePath && narrativeText) issues.push(...narrativeIssues(narrativeText, baseline, evolved, narrativePath));
  const metricRows: [string, string, "number" | "percent" | "money"][] = [
    ["Total cases", "total_cases", "number"],
    ["Passed cases", "passed_cases", "number"],
    ["Pass rate", "pass_rate", "percent"],
    ["Average rubric score", "avg_rubric_score", "number"],
    ["Average latency (s/case)", "avg_latency_s", "number"],
    ["Total tokens", "total_tokens", "number"],
    ["Tool invocations", "total_tool_calls", "number"],
    ["Hit rate", "hit_rate", "percent"],
    ["False alarm rate", "false_alarm_rate", "percent"],
    ["Total operational loss", "total_loss_usd", "money"],
    ["False-positive loss", "fp_loss_usd", "money"],
    ["False-negative loss", "fn_loss_usd", "money"],
    ["Investigation cost", "investigation_cost_usd", "money"],
  ];
  const issueLines = issues.length === 0
    ? ["- None"]
    : issues.map((issue) => `- **${issue.severity.toUpperCase()}** \`${issue.code}\`: ${issue.message}`);
  const generatedAt = new Date().toISOString();
  const lines = [
    "# Evaluation Evidence Reconciliation",
    "",
    `Generated: ${generatedAt}`,
    "",
    "This report is generated directly from the source JSON artifacts. Dollar amounts are outputs of the simulated operational-loss model; they do not establish actual savings, avoided downtime, or realized business impact.",
    "",
    "## Artifacts",
    "",
    `| Role | Artifact | SHA-256 | Lifecycle | Provenance |`,
    `| --- | --- | --- | --- | --- |`,
    `| Baseline / raw-playbook comparison | ${sourceLabel(baseline)} | \`${baseline.sha256 ?? "Unavailable"}\` | ${baseline.lifecycle} | ${baseline.provenanceComplete ? "complete" : "missing fields"} |`,
    `| Evolved / GEPA runbooks | ${sourceLabel(evolved)} | \`${evolved.sha256 ?? "Unavailable"}\` | ${evolved.lifecycle} | ${evolved.provenanceComplete ? "complete" : "missing fields"} |`,
    "",
    "## Side-by-side metrics",
    "",
    "`Unavailable` means the source did not provide a valid finite value. It is not a zero.",
    "",
    "| Metric | Baseline | Evolved | Evolved − baseline |",
    "| --- | ---: | ---: | ---: |",
    ...metricRows.map(([label, name, kind]) => `| ${label} | ${displayMetric(baseline, name, kind)} | ${displayMetric(evolved, name, kind)} | ${delta(baseline, evolved, name, kind)} |`),
    "",
    "## Evidence status",
    "",
    `- Baseline case results: ${baseline.caseCount === undefined ? "Unavailable" : baseline.caseCount}; non-success case statuses: ${baseline.failedCaseCount}`,
    `- Evolved case results: ${evolved.caseCount === undefined ? "Unavailable" : evolved.caseCount}; non-success case statuses: ${evolved.failedCaseCount}`,
    `- Historical result verification: ${baseline.lifecycle === "success" && evolved.lifecycle === "success" && baseline.provenanceComplete && evolved.provenanceComplete ? "eligible for verification review" : "unverified; lifecycle and/or provenance evidence is incomplete"}`,
    "",
    "## Audit findings",
    "",
    ...issueLines,
    "",
    "## Interpretation limits",
    "",
    "The source reports are historical artifacts. This reconciliation does not rerun an evaluator, validate an untouched final test set, prove that a cloud run completed successfully, or turn modeled loss into financial savings. A future run record should satisfy the provenance contract in `docs/evidence/EXPERIMENT_PROVENANCE_SCHEMA.json`.",
    "",
  ];
  return lines.join("\n");
}

export async function buildComparison(options: {
  baselinePath: string;
  evolvedPath: string;
  narrativePath?: string;
}): Promise<ComparisonResult> {
  const [baseline, evolved] = await Promise.all([auditArtifact(options.baselinePath), auditArtifact(options.evolvedPath)]);
  let narrativeText: string | undefined;
  if (options.narrativePath) {
    try {
      narrativeText = await Bun.file(options.narrativePath).text();
    } catch (error) {
      baseline.issues.push({ severity: "error", code: "narrative-unreadable", artifact: options.narrativePath, message: String(error) });
    }
  }
  const markdown = renderComparison(baseline, evolved, options.narrativePath, narrativeText);
  const issues = [...baseline.issues, ...evolved.issues];
  if (options.narrativePath && narrativeText) issues.push(...narrativeIssues(narrativeText, baseline, evolved, options.narrativePath));
  return { baseline, evolved, issues, markdown };
}

function argumentValue(args: string[], flag: string): string | undefined {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : undefined;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const baselinePath = argumentValue(args, "--baseline") ?? "docs/soc_eval_results/gemini-2.5-flash-lite_approach3_report.json";
  const evolvedPath = argumentValue(args, "--evolved") ?? "docs/soc_eval_results/gemini-2.5-flash-lite_gepa_evolved_report.json";
  const narrativePath = argumentValue(args, "--narrative") ?? "docs/soc_eval_results/GEPA_RUNBOOK_EVALUATION_ANALYSIS.md";
  const outputPath = argumentValue(args, "--output");
  const comparison = await buildComparison({ baselinePath, evolvedPath, narrativePath });
  if (outputPath) {
    await Bun.write(outputPath, comparison.markdown);
    console.log(`Wrote ${outputPath}`);
  } else {
    console.log(comparison.markdown);
  }
  const errorCount = comparison.issues.filter((issue) => issue.severity === "error").length;
  if (args.includes("--strict") && errorCount > 0) process.exitCode = 1;
}

if (import.meta.main) await main();
