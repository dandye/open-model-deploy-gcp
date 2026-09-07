/** Offline preflight only: structural checks cannot prove that a case was never exposed. */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

export function sha256(text: string | Buffer): string {
  return createHash("sha256").update(text).digest("hex");
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

const isRecord = (value: unknown): value is Record<string, any> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const filled = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;
const digest = (value: unknown): boolean => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);

export function validateExperiment(manifest: unknown, baseDir: string): string[] {
  const errors: string[] = [];
  if (!isRecord(manifest)) return ["Manifest must be a JSON object."];
  if (manifest.schema_version !== 1) errors.push("schema_version must be 1.");
  for (const field of ["workflow", "reviewer"]) {
    if (!filled(manifest[field])) errors.push(`${field} is required.`);
  }
  if (!/^[a-f0-9]{40}$/.test(manifest.source_commit ?? "")) errors.push("source_commit must be a full Git commit hash.");
  if (!Number.isInteger(manifest.repetitions) || manifest.repetitions < 2) errors.push("repetitions must be at least 2.");
  const acceptance = manifest.acceptance;
  if (!isRecord(acceptance) || !filled(acceptance.approved_by) || !filled(acceptance.approved_at)
      || !Number.isFinite(Date.parse(acceptance.approved_at))) {
    errors.push("Acceptance criteria need a named approver and valid approval timestamp.");
  }
  for (const field of ["min_task_completion_rate", "max_unsafe_action_rate"]) {
    const value = acceptance?.[field];
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) errors.push(`acceptance.${field} must be between 0 and 1.`);
  }
  for (const field of ["max_p95_latency_s", "max_cost_per_success_usd", "max_experiment_cost_usd"]) {
    const value = acceptance?.[field];
    if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) errors.push(`acceptance.${field} must be positive.`);
  }
  for (const name of ["open_model", "managed_baseline"]) {
    const config = manifest.configurations?.[name];
    if (!isRecord(config) || !filled(config.model_revision) || !filled(config.region)
        || !isRecord(config.parameters) || Object.keys(config.parameters).length === 0) errors.push(`configurations.${name} needs model_revision, region, and explicit parameters.`);
    if (name === "open_model" && (!filled(config?.hardware) || !/^.+@sha256:[a-f0-9]{64}$/.test(config?.container_image ?? ""))) {
      errors.push("Open model needs hardware and a container image pinned by sha256 digest.");
    }
  }
  const seenIds = new Map<string, string>();
  const seenContents = new Map<string, string>();
  for (const split of ["train", "validation", "final_test"]) {
    const input = manifest.datasets?.[split];
    if (!isRecord(input) || !filled(input.path) || !digest(input.sha256)) {
      errors.push(`datasets.${split} needs a path and sha256.`);
      continue;
    }
    let data: unknown;
    try {
      const bytes = readFileSync(resolve(baseDir, input.path));
      if (sha256(bytes) !== input.sha256) errors.push(`datasets.${split}: content hash mismatch.`);
      data = JSON.parse(bytes.toString("utf8"));
    } catch (error) {
      errors.push(`datasets.${split}: cannot read JSON (${String(error)}).`);
      continue;
    }
    const cases = isRecord(data) ? data.eval_cases : undefined;
    if (!Array.isArray(cases) || cases.length === 0) {
      errors.push(`datasets.${split}: eval_cases must be a nonempty array.`);
      continue;
    }
    for (const [index, item] of cases.entries()) {
      if (!isRecord(item)) { errors.push(`${split}[${index}] must be an object.`); continue; }
      const id = item.eval_id ?? item.id ?? item.case_id;
      const location = `${split}[${index}]`;
      if (!filled(id)) errors.push(`${location} needs a nonempty eval_id, id, or case_id.`);
      else if (seenIds.has(id)) errors.push(`${location}: duplicate case ID ${id} also in ${seenIds.get(id)}.`);
      else seenIds.set(id, location);
      const { eval_id: _evalId, id: _id, case_id: _caseId, ...body } = item;
      const contentHash = sha256(canonical(body));
      if (Object.keys(body).length === 0) errors.push(`${location}: case content is empty.`);
      if (seenContents.has(contentHash)) errors.push(`${location}: duplicate case content also in ${seenContents.get(contentHash)} (renaming IDs does not create a holdout).`);
      else seenContents.set(contentHash, location);
    }
  }
  const holdout = manifest.holdout_attestation;
  if (!isRecord(holdout) || !filled(holdout.reviewer) || !filled(holdout.evidence)
      || holdout.never_used_for_optimization !== true
      || !digest(holdout.dataset_sha256) || holdout.dataset_sha256 !== manifest.datasets?.final_test?.sha256) {
    errors.push("Final test needs a reviewer attestation, exposure-history evidence, and matching dataset hash.");
  }
  return errors;
}

if (import.meta.main) {
  const path = process.argv[2];
  if (!path || process.argv.length !== 3) {
    console.error("Usage: bun scripts/validate_experiment.ts <manifest.json>");
    process.exitCode = 2;
  } else {
    try {
      const errors = validateExperiment(JSON.parse(readFileSync(path, "utf8")), dirname(resolve(path)));
      if (errors.length) {
        console.error(errors.map(error => `FAIL: ${error}`).join("\n"));
        process.exitCode = 1;
      } else {
        console.log("Offline preflight passed. This does not verify reviewer identity, unseen-case history, cloud readiness, or measured outcomes.");
      }
    } catch (error) {
      console.error(`Cannot validate manifest: ${String(error)}`);
      process.exitCode = 2;
    }
  }
}
