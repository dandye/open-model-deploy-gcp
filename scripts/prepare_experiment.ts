/** Freeze explicitly supplied dataset bytes into a private review packet; never approve or launch. */
import { closeSync, constants, existsSync, fstatSync, mkdirSync, openSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { inspectDataset, sha256, validateExperiment } from "./validate_experiment";

const splits = ["train", "validation", "final_test"] as const;
const record = (value: unknown): value is Record<string, any> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const limit = 16 * 1024 * 1024;

export function prepareExperiment(inputPath: string, destination: string) {
  inputPath = resolve(inputPath);
  destination = resolve(destination);
  if (existsSync(destination)) throw new Error("Destination already exists; use a new review directory.");
  const manifest = JSON.parse(readFileSync(inputPath, "utf8"));
  if (!record(manifest) || manifest.schema_version !== 2) throw new Error("Use an experiment schema_version 2 manifest.");
  if (!record(manifest.datasets)) throw new Error("datasets must be an object.");
  if (!record(manifest.exposure_history) || !Array.isArray(manifest.exposure_history.datasets)) {
    throw new Error("exposure_history.datasets must be an array (it may be empty in a draft).");
  }
  if (manifest.exposure_history.datasets.length > 100) throw new Error("At most 100 exposure datasets are supported.");
  const snapshots: Array<{ path: string; bytes: Buffer; inventory: any }> = [];
  let totalBytes = 0;
  function snapshot(descriptor: unknown, outputPath: string, label: string) {
    if (!record(descriptor) || descriptor.path == null || descriptor.path === "") return;
    if (typeof descriptor.path !== "string") throw new Error(`${label}: path must be a string.`);
    const source = resolve(dirname(inputPath), descriptor.path);
    // Open once without following a leaf symlink; hash and copy the same bytes.
    const fd = openSync(source, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    let bytes: Buffer;
    try {
      const stat = fstatSync(fd);
      if (!stat.isFile() || stat.size > limit) throw new Error(`${label}: expected a regular file at most 16 MiB.`);
      bytes = readFileSync(fd);
    } finally { closeSync(fd); }
    totalBytes += bytes.length;
    if (bytes.length > limit || totalBytes > 64 * 1024 * 1024) throw new Error("Dataset packet exceeds the 64 MiB total or 16 MiB file limit.");
    const digest = sha256(bytes);
    if (descriptor.sha256 != null && descriptor.sha256 !== digest) throw new Error(`${label}: supplied hash does not match; refusing to rebind frozen input.`);
    const inventory = inspectDataset(bytes, label);
    snapshots.push({ path: outputPath, bytes, inventory: {
      ...inventory, path: outputPath, original_path: descriptor.path,
      source: descriptor.source ?? null, usage: descriptor.usage ?? null,
    } });
    descriptor.path = outputPath;
    descriptor.sha256 = digest;
  }
  for (const split of splits) snapshot(manifest.datasets[split], `datasets/${split}.json`, split);
  manifest.exposure_history.datasets.forEach((item: unknown, index: number) =>
    snapshot(item, `history/${index}.json`, `exposure_history[${index}]`));

  // Claim a new directory exclusively. Never replace another packet, even in a race.
  mkdirSync(dirname(destination), { recursive: true });
  mkdirSync(destination, { mode: 0o700 });
  try {
    writeFileSync(join(destination, "preparation.json"), JSON.stringify({ status: "INCOMPLETE" }) + "\n", { flag: "wx", mode: 0o600 });
    for (const item of snapshots) {
      mkdirSync(dirname(join(destination, item.path)), { recursive: true, mode: 0o700 });
      writeFileSync(join(destination, item.path), item.bytes, { flag: "wx", mode: 0o600 });
      if (sha256(readFileSync(join(destination, item.path))) !== item.inventory.sha256) throw new Error("Snapshot verification failed.");
    }
    const errors = validateExperiment(manifest, destination);
    const report = { schema_version: 1, status: errors.length ? "DRAFT" : "READY_FOR_REVIEW",
      scope: "offline_dataset_preparation", manifest_sha256: "", errors,
      datasets: snapshots.map(item => item.inventory),
      limitations: ["This packet does not approve or launch an experiment.",
        "Exposure history is supplied by the reviewer; completeness and semantic equivalence are not proven.",
        "Existing exposed cases cannot become untouched by renaming or copying them."] };
    const manifestBytes = JSON.stringify(manifest, null, 2) + "\n";
    report.manifest_sha256 = sha256(manifestBytes);
    writeFileSync(join(destination, "manifest.json"), manifestBytes, { flag: "wx", mode: 0o600 });
    writeFileSync(join(destination, "preparation.json"), JSON.stringify(report, null, 2) + "\n", { mode: 0o600 });
    return report;
  } catch (error) {
    rmSync(destination, { recursive: true, force: true });
    throw error;
  }
}

if (import.meta.main) {
  if (process.argv.length !== 4) {
    console.error("Usage: bun scripts/prepare_experiment.ts <draft-manifest.json> <new-output-directory>");
    process.exitCode = 2;
  } else {
    try {
      const report = prepareExperiment(process.argv[2], process.argv[3]);
      console.log(JSON.stringify(report, null, 2));
      process.exitCode = report.status === "READY_FOR_REVIEW" ? 0 : 1;
    } catch (error) {
      console.error(`Cannot prepare experiment: ${String(error)}`);
      process.exitCode = 2;
    }
  }
}
