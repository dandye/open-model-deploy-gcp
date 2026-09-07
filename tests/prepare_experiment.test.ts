import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { prepareExperiment } from "../scripts/prepare_experiment";
import { sha256, validateExperiment } from "../scripts/validate_experiment";

let dir: string;
let manifest: any;
function save() { writeFileSync(join(dir, "draft.json"), JSON.stringify(manifest)); }
function prepare() { save(); return prepareExperiment(join(dir, "draft.json"), join(dir, "packet")); }
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "dataset-freeze-test-"));
  const datasets: any = {};
  for (const split of ["train", "validation", "final_test", "history"]) {
    const text = JSON.stringify({ eval_cases: [{ eval_id: split, prompt: `Distinct ${split} fixture` }] });
    writeFileSync(join(dir, split + ".json"), text);
    datasets[split] = { path: split + ".json", sha256: sha256(text) };
  }
  manifest = { schema_version: 2, workflow: "Fixture", reviewer: "Fixture", source_commit: "a".repeat(40), repetitions: 2,
    acceptance: { approved_by: "Fixture", approved_at: "2026-09-07T00:00:00Z", min_task_completion_rate: .8,
      max_unsafe_action_rate: 0, max_p95_latency_s: 30, max_cost_per_success_usd: 1, max_experiment_cost_usd: 10 },
    configurations: { open_model: { model_revision: "fixture", region: "fixture", hardware: "fixture", parameters: { temperature: 0 },
      container_image: `registry/fixture@sha256:${"b".repeat(64)}` }, managed_baseline: { model_revision: "fixture", region: "fixture", parameters: { temperature: 0 } } },
    datasets: { train: datasets.train, validation: datasets.validation, final_test: datasets.final_test },
    exposure_history: { reviewer: "Fixture", evidence: "Fixture only", datasets: [{ ...datasets.history, source: "Fixture", usage: "evaluation" }] },
    holdout_attestation: { reviewer: "Fixture", evidence: "Fixture only", never_used_for_optimization: true, dataset_sha256: datasets.final_test.sha256 } };
});
afterEach(() => rmSync(dir, { recursive: true, force: true }));

describe("dataset preparation", () => {
  test("creates portable byte-identical snapshots with separate review status", () => {
    const original = readFileSync(join(dir, "train.json"));
    const report = prepare();
    expect(report.status).toBe("READY_FOR_REVIEW");
    expect(readFileSync(join(dir, "packet/datasets/train.json"))).toEqual(original);
    expect(report.manifest_sha256).toBe(sha256(readFileSync(join(dir, "packet/manifest.json"))));
    expect(statSync(join(dir, "packet")).mode & 0o777).toBe(0o700);
    expect(statSync(join(dir, "packet/manifest.json")).mode & 0o777).toBe(0o600);
    rmSync(join(dir, "train.json")); rmSync(join(dir, "history.json"));
    const frozen = JSON.parse(readFileSync(join(dir, "packet/manifest.json"), "utf8"));
    expect(validateExperiment(frozen, join(dir, "packet"))).toEqual([]);
    expect(frozen.acceptance).toEqual(manifest.acceptance);
    expect(frozen.holdout_attestation).toEqual(manifest.holdout_attestation);
  });
  test("keeps incomplete inputs and approvals visibly pending", () => {
    manifest.acceptance.approved_by = null;
    manifest.datasets.final_test = { path: null, sha256: null };
    manifest.holdout_attestation = null;
    manifest.exposure_history.reviewer = null;
    const report = prepare();
    expect(report.status).toBe("DRAFT");
    const frozen = JSON.parse(readFileSync(join(dir, "packet/manifest.json"), "utf8"));
    expect(frozen.acceptance.approved_by).toBeNull();
    expect(frozen.holdout_attestation).toBeNull();
    expect(frozen.datasets.final_test.sha256).toBeNull();
    expect(report.errors.length).toBeGreaterThan(0);
  });
  test("fills missing hashes without inventing a matching holdout attestation", () => {
    manifest.datasets.final_test.sha256 = null;
    manifest.holdout_attestation.dataset_sha256 = null;
    const report = prepare();
    expect(report.status).toBe("DRAFT");
    const frozen = JSON.parse(readFileSync(join(dir, "packet/manifest.json"), "utf8"));
    expect(frozen.datasets.final_test.sha256).toHaveLength(64);
    expect(frozen.holdout_attestation.dataset_sha256).toBeNull();
  });
  test("does not silently update a changed frozen input", () => {
    writeFileSync(join(dir, "train.json"), "{}");
    expect(prepare).toThrow("refusing to rebind");
    expect(existsSync(join(dir, "packet"))).toBeFalse();
  });
  test("never overwrites an existing packet", () => {
    prepare();
    const before = readFileSync(join(dir, "packet/manifest.json"));
    expect(prepare).toThrow("already exists");
    expect(readFileSync(join(dir, "packet/manifest.json"))).toEqual(before);
  });
  test("missing supplied files fail without a partial output", () => {
    rmSync(join(dir, "history.json"));
    expect(prepare).toThrow();
    expect(existsSync(join(dir, "packet"))).toBeFalse();
  });
  test("rejects symlink inputs", () => {
    symlinkSync(join(dir, "train.json"), join(dir, "link.json"));
    manifest.datasets.train.path = "link.json";
    expect(prepare).toThrow();
    expect(existsSync(join(dir, "packet"))).toBeFalse();
  });
  test("malformed dataset bytes remain a draft with useful errors", () => {
    writeFileSync(join(dir, "train.json"), "{"); manifest.datasets.train.sha256 = null;
    const report = prepare();
    expect(report.status).toBe("DRAFT");
    expect(report.datasets[0].errors.length).toBeGreaterThan(0);
  });
  test("rejects legacy manifests and excessive history", () => {
    manifest.schema_version = 1; expect(prepare).toThrow("schema_version 2");
    manifest.schema_version = 2;
    manifest.exposure_history.datasets = Array(101).fill(manifest.exposure_history.datasets[0]);
    expect(prepare).toThrow("At most 100");
  });
  test("CLI returns nonzero for draft preparation", () => {
    manifest.acceptance = null; save();
    const result = Bun.spawnSync(["bun", "scripts/prepare_experiment.ts", join(dir, "draft.json"), join(dir, "packet")]);
    expect(result.exitCode).toBe(1);
    expect(JSON.parse(result.stdout.toString()).status).toBe("DRAFT");
  });
});
