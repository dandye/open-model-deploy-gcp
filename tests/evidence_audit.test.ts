import { afterEach, describe, expect, test } from "bun:test";
import { unlink } from "node:fs/promises";
import { auditArtifact, buildComparison, renderComparison } from "../tools/evidence_audit.ts";

const tempFiles: string[] = [];

async function fixture(name: string, value: string): Promise<string> {
  const path = `/tmp/evidence-audit-${process.pid}-${name}`;
  await Bun.write(path, value);
  tempFiles.push(path);
  return path;
}

afterEach(async () => {
  await Promise.all(tempFiles.splice(0).map((path) => unlink(path).catch(() => undefined)));
});

describe("evidence artifact audit", () => {
  test("flags successful-looking summaries with no case evidence", async () => {
    const path = await fixture("empty-cases.json", JSON.stringify({ status: "COMPLETED", summary: { total_cases: 1, passed_cases: 1, pass_rate: 100 }, case_results: [] }));
    const audit = await auditArtifact(path);
    expect(audit.issues.some(issue => issue.code === "case-count-mismatch")).toBe(true);
  });
  test("audits real baseline/evolved artifacts without inventing missing values", async () => {
    const result = await buildComparison({
      baselinePath: "docs/soc_eval_results/gemini-2.5-flash-lite_approach3_report.json",
      evolvedPath: "docs/soc_eval_results/gemini-2.5-flash-lite_gepa_evolved_report.json",
      narrativePath: "docs/soc_eval_results/GEPA_RUNBOOK_EVALUATION_ANALYSIS.md",
    });
    expect(result.baseline.metrics.total_loss_usd.value).toBe(250051.11);
    expect(result.evolved.metrics.total_loss_usd.value).toBe(100.82);
    expect(result.baseline.provenanceComplete).toBe(false);
    expect(result.evolved.provenanceComplete).toBe(false);
    expect(result.issues.some((issue) => issue.code === "narrative-json-mismatch")).toBe(true);
    expect(result.markdown).toContain("$250,051.11 (simulated loss)");
    expect(result.markdown).toContain("`Unavailable` means the source did not provide");
  });

  test("reports malformed JSON and missing fields as issues", async () => {
    const malformed = await fixture("malformed.json", "{ definitely not json");
    const audit = await auditArtifact(malformed);
    expect(audit.parseOk).toBe(false);
    expect(audit.issues.map((issue) => issue.code)).toContain("malformed-json");

    const incomplete = await fixture("incomplete.json", JSON.stringify({ flavor: "fixture", summary: { total_cases: null } }));
    const incompleteAudit = await auditArtifact(incomplete);
    expect(incompleteAudit.metrics.total_cases.status).toBe("missing");
    expect(incompleteAudit.metrics.total_loss_usd.status).toBe("missing");
    expect(renderComparison(incompleteAudit, incompleteAudit)).toContain("Total operational loss | Unavailable");

    const noSummary = await fixture("no-summary.json", JSON.stringify({ flavor: "fixture" }));
    const noSummaryAudit = await auditArtifact(noSummary);
    expect(noSummaryAudit.issues.map((issue) => issue.code)).toContain("missing-summary");
  });

  test("does not treat a failed run as a successful historical result", async () => {
    const failed = await fixture("failed.json", JSON.stringify({
      status: "FAILED",
      summary: { total_cases: 2, passed_cases: 0, pass_rate: 0 },
      case_results: [{ status: "ERROR" }, { status: "FAILED" }],
    }));
    const audit = await auditArtifact(failed);
    expect(audit.lifecycle).toBe("failed");
    expect(audit.failedCaseCount).toBe(2);
    expect(audit.issues.map((issue) => issue.code)).toEqual(expect.arrayContaining(["non-success-run", "failed-case-results", "missing-provenance"]));
  });

  test("failure wins when lifecycle signals contradict", async () => {
    const contradictory = await fixture("contradictory.json", JSON.stringify({
      status: "COMPLETED",
      exit_code: 9,
      provenance: { lifecycle: { status: "failed" } },
      summary: {},
    }));
    const audit = await auditArtifact(contradictory);
    expect(audit.lifecycle).toBe("failed");
    expect(audit.provenanceComplete).toBe(false);
  });

  test("an unresolved cleanup outcome prevents success classification", async () => {
    const partial = await fixture("partial-cleanup.json", JSON.stringify({
      provenance: {
        source_commit: "abc",
        model: "fixture",
        configuration_hash: "hash",
        dataset: "fixture",
        runbook: "fixture",
        evaluator: "fixture",
        started_at: "2026-09-06T00:00:00Z",
        completed_at: "2026-09-06T00:01:00Z",
        logs: [{ "uri": "log", "kind": "evaluator" }],
        lifecycle: { status: "completed", evaluation: "completed", artifact_collection: "completed", cleanup: "unverified" },
      },
      summary: { total_cases: 1 },
    }));
    const audit = await auditArtifact(partial);
    expect(audit.lifecycle).toBe("unverified");
  });
});
