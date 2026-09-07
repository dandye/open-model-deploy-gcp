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
    schema_version: 1, workflow: "Synthetic fixture", reviewer: "Fixture reviewer",
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
});
afterEach(() => rmSync(dir, { recursive: true, force: true }));
describe("experiment preflight", () => {
  test("accepts complete synthetic inputs", () => expect(validateExperiment(manifest, dir)).toEqual([]));
  test("accepts the repository eval_id naming convention", () => {
    manifest.datasets.train = dataset("train", [{ eval_id: "repository-id", prompt: "Repository-shaped fixture" }]);
    expect(validateExperiment(manifest, dir)).toEqual([]);
  });
  test("rejects duplicate IDs across splits", () => {
    manifest.datasets.validation = dataset("validation", [{ id: "train", prompt: "Other" }]);
    expect(validateExperiment(manifest, dir).join()).toContain("duplicate case ID");
  });
  test("rejects reused content with renamed IDs", () => {
    manifest.datasets.validation = dataset("validation", [{ id: "renamed", prompt: "Distinct synthetic fixture 0" }]);
    expect(validateExperiment(manifest, dir).join()).toContain("duplicate case content");
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
