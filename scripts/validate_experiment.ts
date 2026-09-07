/** Offline preflight only: structural checks cannot prove that a case was never exposed. */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

export function sha256(text: string | Buffer): string {
  return createHash("sha256").update(text).digest("hex");
}

export function parseJsonBytes(bytes: Buffer): unknown {
  // Preserve a BOM so JSON.parse rejects it, matching the evaluator's text reader.
  return JSON.parse(new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes));
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
      .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

const isRecord = (value: unknown): value is Record<string, any> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const filled = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;
const digest = (value: unknown): boolean => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);

export function inspectDataset(bytes: Buffer, label: string): { sha256: string; cases: Array<{ id: string; content_sha256: string }>; errors: string[] } {
  const errors: string[] = [];
  const cases: Array<{ id: string; content_sha256: string }> = [];
  let data: unknown;
  try { data = parseJsonBytes(bytes); }
  catch { return { sha256: sha256(bytes), cases, errors: [`${label}: cannot read JSON (invalid UTF-8 or malformed JSON).`] }; }
  const values = isRecord(data) ? data.eval_cases : undefined;
  if (!Array.isArray(values) || values.length === 0) return { sha256: sha256(bytes), cases, errors: [`${label}: eval_cases must be a nonempty array.`] };
  const ids = new Map<string, number>();
  const contents = new Map<string, number>();
  values.forEach((item, index) => {
    const location = `${label}[${index}]`;
    if (!isRecord(item)) { errors.push(`${location} must be an object.`); return; }
    const aliases = [item.eval_id, item.id, item.case_id].filter(value => value !== undefined);
    const named = aliases.filter(filled);
    if (!named.length || named.length !== aliases.length) errors.push(`${location} needs a nonempty eval_id, id, or case_id.`);
    if (new Set(named).size > 1) errors.push(`${location}: conflicting case ID aliases.`);
    const id = String(named[0] ?? "");
    const { eval_id: _evalId, id: _id, case_id: _caseId, ...body } = item;
    if (Object.keys(body).length === 0) errors.push(`${location}: case content is empty.`);
    const contentHash = sha256(canonical(body));
    if (ids.has(id)) errors.push(`${location}: duplicate case ID ${id} also in ${label}[${ids.get(id)}].`); else ids.set(id, index);
    if (contents.has(contentHash)) errors.push(`${location}: duplicate case content also in ${label}[${contents.get(contentHash)}].`); else contents.set(contentHash, index);
    cases.push({ id, content_sha256: contentHash });
  });
  return { sha256: sha256(bytes), cases, errors };
}

export function validateExperiment(manifest: unknown, baseDir: string): string[] {
  const errors: string[] = [];
  if (!isRecord(manifest)) return ["Manifest must be a JSON object."];
  if (manifest.schema_version !== 2) errors.push("schema_version must be 2.");
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
  const historyIds = new Map<string, string>();
  const historyContents = new Map<string, string>();
  let finalCases: Array<{ id: string; content_sha256: string }> = [];
  for (const split of ["train", "validation", "final_test"]) {
    const input = manifest.datasets?.[split];
    if (!isRecord(input) || !filled(input.path) || !digest(input.sha256)) {
      errors.push(`datasets.${split} needs a path and sha256.`);
      continue;
    }
    let bytes: Buffer;
    try {
      bytes = readFileSync(resolve(baseDir, input.path));
      if (sha256(bytes) !== input.sha256) errors.push(`datasets.${split}: content hash mismatch.`);
    } catch (error) {
      errors.push(`datasets.${split}: cannot read JSON (${String(error)}).`);
      continue;
    }
    const inspected = inspectDataset(bytes, `datasets.${split}`);
    if (split === "final_test") finalCases = inspected.cases;
    for (const problem of inspected.errors) errors.push(problem);
    for (const item of inspected.cases) {
      const location = `datasets.${split}`;
      if (seenIds.has(item.id)) errors.push(`${location}: duplicate case ID ${item.id} also in ${seenIds.get(item.id)}.`); else seenIds.set(item.id, location);
      if (seenContents.has(item.content_sha256)) errors.push(`${location}: duplicate case content also in ${seenContents.get(item.content_sha256)} (renaming IDs does not create a holdout).`); else seenContents.set(item.content_sha256, location);
    }
  }
  const exposure = manifest.exposure_history;
  if (!isRecord(exposure) || !filled(exposure.reviewer) || !filled(exposure.evidence) || !Array.isArray(exposure.datasets) || exposure.datasets.length === 0) {
    errors.push("exposure_history needs a named reviewer, evidence, and nonempty datasets.");
  }
  if (isRecord(exposure) && Array.isArray(exposure.datasets)) {
    for (const [index, item] of exposure.datasets.entries()) {
      if (!isRecord(item) || !filled(item.path) || !digest(item.sha256) || !filled(item.source)
          || !["optimization", "validation", "evaluation", "unknown"].includes(item.usage)) {
        errors.push(`exposure_history.datasets[${index}] is invalid.`); continue;
      }
      try {
        const bytes = readFileSync(resolve(baseDir, item.path));
        if (sha256(bytes) !== item.sha256) errors.push(`exposure_history.datasets[${index}]: content hash mismatch.`);
        const inspected = inspectDataset(bytes, `exposure_history.datasets[${index}]`);
        errors.push(...inspected.errors);
        for (const c of inspected.cases) { historyIds.set(c.id, item.path); historyContents.set(c.content_sha256, item.path); }
      } catch { errors.push(`exposure_history.datasets[${index}]: cannot read JSON.`); }
    }
  }
  for (const c of finalCases) {
    if (historyIds.has(c.id)) errors.push(`datasets.final_test: case ID ${c.id} appears in exposure history.`);
    if (historyContents.has(c.content_sha256)) errors.push("datasets.final_test: case content appears in exposure history.");
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
      const errors = validateExperiment(parseJsonBytes(readFileSync(path)), dirname(resolve(path)));
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
