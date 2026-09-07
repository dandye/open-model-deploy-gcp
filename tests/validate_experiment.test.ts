import { describe, test, expect, beforeEach, afterEach } from "bun:test";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { sha256, validateExperiment } from "../scripts/validate_experiment";

let dir: string;
let manifest: any;
function dataset(split: string, cases: any[]) {
  const text = JSON.stringify({ eval_cases: cases });
  writeFileSync(join(dir, `${split}.json`), text);
  return { path: `${split}.json`, sha256: sha256(text) };
}
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "experiment-preflight-"));
  manifest = {
    schema_version: 2, workflow: "Synthetic fixture", reviewer: "Fixture reviewer",
    source_commit: "a".repeat(40), repetitions: 3,
    acceptance: { approved_by: "Fixture reviewer", approved_at: "2026-09-06T00:00:00Z",
      min_task_completion_rate: .8, max_unsafe_action_rate: .01,
      max_p95_latency_s: 30, max_cost_per_success_usd: 1, max_experiment_cost_usd: 10 },
    configurations: {
      open_model: { model_revision: "fixed", region: "fixture", parameters: { concurrency: 1 }, hardware: "fixture", container_image: `fixture@sha256:${"b".repeat(64)}` },
      managed_baseline: { model_revision: "fixed", region: "fixture", parameters: { concurrency: 1 } },
    },
    datasets: Object.fromEntries(["train", "validation", "final_test"].map((split, i) =>
      [split, dataset(split, [{ id: split, prompt: `Distinct synthetic fixture ${i}` }])])),
  };
  manifest.holdout_attestation = { reviewer: "Fixture reviewer", evidence: "Synthetic test only",
    never_used_for_optimization: true, dataset_sha256: manifest.datasets.final_test.sha256 };
  const history = dataset("history", [{ id: "history-only", prompt: "Historical exposure fixture" }]);
  manifest.exposure_history = { reviewer: "Fixture reviewer", evidence: "Synthetic test only", datasets: [{ ...history, source: "fixture", usage: "unknown" }] };
});
afterEach(() => rmSync(dir, { recursive: true, force: true }));
describe("experiment preflight", () => {
  test("accepts complete synthetic inputs", () => expect(validateExperiment(manifest, dir)).toEqual([]));
  test("accepts the repository eval_id naming convention", () => {
    manifest.datasets.train = dataset("train", [{ eval_id: "repository-id", prompt: "Repository-shaped fixture" }]);
    expect(validateExperiment(manifest, dir)).toEqual([]);
  });
  test("accepts identical ID aliases and rejects conflicting or blank aliases", () => {
    manifest.datasets.train = dataset("train", [{ eval_id: "same", id: "same", case_id: "same", prompt: "aliases" }]);
    expect(validateExperiment(manifest, dir)).toEqual([]);
    manifest.datasets.train = dataset("train", [{ eval_id: "one", id: "two", prompt: "aliases" }]);
    expect(validateExperiment(manifest, dir).join()).toContain("conflicting case ID aliases");
    manifest.datasets.train = dataset("train", [{ eval_id: "", id: "two", prompt: "aliases" }]);
    expect(validateExperiment(manifest, dir).join()).toContain("needs a nonempty");
  });
  test("rejects duplicate IDs across splits", () => {
    manifest.datasets.validation = dataset("validation", [{ id: "train", prompt: "Other" }]);
    expect(validateExperiment(manifest, dir).join()).toContain("duplicate case ID");
  });
  test("rejects reused content with renamed IDs", () => {
    manifest.datasets.validation = dataset("validation", [{ id: "renamed", prompt: "Distinct synthetic fixture 0" }]);
    expect(validateExperiment(manifest, dir).join()).toContain("duplicate case content");
  });
  test("treats reordered nested content as the same frozen case", () => {
    manifest.datasets.train = dataset("train", [{ id: "nested-train", prompt: "Nested", metadata: { z: 1, a: { d: 2, c: 3 } } }]);
    manifest.datasets.validation = dataset("validation", [{ id: "nested-validation", prompt: "Nested", metadata: { a: { c: 3, d: 2 }, z: 1 } }]);
    expect(validateExperiment(manifest, dir).join()).toContain("duplicate case content");
  });
  test("rejects final IDs and renamed content found in exposure history", () => {
    manifest.datasets.final_test = dataset("final_test", [{ id: "history-only", prompt: "new" }]);
    expect(validateExperiment(manifest, dir).join()).toContain("case ID history-only appears in exposure history");
    manifest.datasets.final_test = dataset("final_test", [{ id: "renamed", prompt: "Historical exposure fixture" }]);
    expect(validateExperiment(manifest, dir).join()).toContain("case content appears in exposure history");
  });
  test("checks unknown history datasets and permits train overlap", () => {
    manifest.datasets.train = dataset("train", [{ id: "history-only", prompt: "Historical exposure fixture" }]);
    expect(validateExperiment(manifest, dir)).toEqual([]);
    manifest.datasets.final_test = dataset("final_test", [{ id: "new", prompt: "Historical exposure fixture" }]);
    expect(validateExperiment(manifest, dir).join()).toContain("case content appears in exposure history");
  });
  test("reports history file tampering, missing, malformed, and empty inputs", () => {
    writeFileSync(join(dir, "history.json"), JSON.stringify({ eval_cases: [{ id: "history-only", prompt: "tampered" }] }));
    expect(validateExperiment(manifest, dir).join()).toContain("exposure_history.datasets[0]: content hash mismatch");
    rmSync(join(dir, "history.json"));
    expect(validateExperiment(manifest, dir).join()).toContain("exposure_history.datasets[0]: cannot read JSON");
    writeFileSync(join(dir, "history.json"), "{");
    expect(validateExperiment(manifest, dir).join()).toContain("exposure_history.datasets[0]: cannot read JSON");
    manifest.exposure_history.datasets[0] = { ...dataset("history", []), source: "fixture", usage: "unknown" };
    expect(validateExperiment(manifest, dir).join()).toContain("eval_cases must be a nonempty array");
  });
  test("reports history data problems even when metadata is incomplete", () => {
    manifest.exposure_history.reviewer = "";
    manifest.exposure_history.evidence = "";
    manifest.datasets.final_test = dataset("final_test", [{ id: "new", prompt: "Historical exposure fixture" }]);
    const errors = validateExperiment(manifest, dir).join();
    expect(errors).toContain("named reviewer");
    expect(errors).toContain("case content appears in exposure history");
  });
  test("rejects schema version 1", () => {
    manifest.schema_version = 1;
    expect(validateExperiment(manifest, dir).join()).toContain("schema_version must be 2");
  });
  test("rejects changed frozen dataset", () => {
    writeFileSync(join(dir, "train.json"), JSON.stringify({ eval_cases: [{ id: "other", prompt: "tampered" }] }));
    expect(validateExperiment(manifest, dir).join()).toContain("content hash mismatch");
  });
  test("rejects missing files and malformed JSON", () => {
    rmSync(join(dir, "train.json")); writeFileSync(join(dir, "validation.json"), "{");
    expect(validateExperiment(manifest, dir).filter(e => e.includes("cannot read JSON"))).toHaveLength(2);
  });
  test("rejects empty test sets", () => {
    manifest.datasets.final_test = dataset("final_test", []);
    expect(validateExperiment(manifest, dir).join()).toContain("nonempty array");
  });
  test("requires actual acceptance input", () => {
    manifest.acceptance = null;
    expect(validateExperiment(manifest, dir).join()).toContain("named approver");
  });
  test("requires matching exposure attestation", () => {
    manifest.holdout_attestation.dataset_sha256 = "c".repeat(64);
    expect(validateExperiment(manifest, dir).join()).toContain("exposure-history evidence");
  });
  test("rejects non-finite thresholds and insufficient repetitions", () => {
    manifest.acceptance.max_p95_latency_s = NaN; manifest.repetitions = 1;
    expect(validateExperiment(manifest, dir).join()).toContain("must be positive");
    expect(validateExperiment(manifest, dir).join()).toContain("at least 2");
  });
  test("does not accept a mutable container tag", () => {
    manifest.configurations.open_model.container_image = "fixture:latest";
    expect(validateExperiment(manifest, dir).join()).toContain("pinned by sha256");
  });
});
