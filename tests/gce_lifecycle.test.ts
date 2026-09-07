import { describe, expect, it } from "bun:test";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const root = join(import.meta.dir, "..");
const helper = join(root, "scripts", "lib", "gce_lifecycle.sh");
const startupScripts = [
  join(root, "scripts", "gce_startup_script.sh"),
  join(root, "scripts", "templates", "gce_startup_template.sh"),
];

function runBash(source: string) {
  const process = Bun.spawnSync(["bash", "-c", source], {
    stdout: "pipe",
    stderr: "pipe",
  });
  return {
    status: process.exitCode,
    stdout: new TextDecoder().decode(process.stdout),
    stderr: new TextDecoder().decode(process.stderr),
  };
}

describe("GCE evaluation lifecycle", () => {
  it("keeps evaluator failure status when output is tee'd", () => {
    const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
    try {
      const log = join(dir, "evaluator.log");
      const result = runBash(`
        set -euo pipefail
        source ${JSON.stringify(helper)}
        if run_with_tee_status ${JSON.stringify(log)} bash -c 'printf evaluator-output; exit 23'; then
          exit 99
        fi
        printf 'command=%s tee=%s\\n' "$LIFECYCLE_COMMAND_STATUS" "$LIFECYCLE_LOG_STATUS"
      `);
      expect(result.status).toBe(0);
      expect(result.stdout).toContain("command=23 tee=0");
      expect(readFileSync(log, "utf8")).toBe("evaluator-output");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("writes an explicit failed result when the evaluator is missing", () => {
    const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
    try {
      const report = join(dir, "report.md");
      const result = join(dir, "result.json");
      const shell = runBash(`
        set -euo pipefail
        source ${JSON.stringify(helper)}
        write_evaluation_failure ${JSON.stringify(report)} ${JSON.stringify(result)} missing-model 'Evaluator script missing' 127
      `);
      expect(shell.status).toBe(0);
      expect(readFileSync(report, "utf8")).toContain("Status: FAILED");
      const parsed = JSON.parse(readFileSync(result, "utf8"));
      expect(parsed.status).toBe("FAILED");
      expect(parsed.summary).toBeNull();
      expect(parsed.evaluation.evaluator_exit_status).toBe(127);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("propagates experiment identity into failed artifacts", () => {
    const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
    try {
      const report = join(dir, "report.md");
      const result = join(dir, "result.json");
      const shell = runBash(`
        set -euo pipefail
        source ${JSON.stringify(helper)}
        export EXPERIMENT_RUN_ID=0123456789abcdef0123456789abcdef
        export EXPERIMENT_CONFIGURATION_HASH=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        write_evaluation_failure ${JSON.stringify(report)} ${JSON.stringify(result)} model 'interrupted' 143
      `);
      expect(shell.status).toBe(0);
      const parsed = JSON.parse(readFileSync(result, "utf8"));
      expect(parsed.run_id).toBe("0123456789abcdef0123456789abcdef");
      expect(parsed.configuration_hash).toBe("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
      expect(parsed.status).toBe("FAILED");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("embeds identity in fallback failures for both boot paths", () => {
    for (const path of startupScripts) {
      const prefix = readFileSync(path, "utf8").split("# ==============================================================================", 1)[0];
      const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
      try {
        const result = join(dir, "result.json");
        const shell = runBash(`${prefix}
          set -euo pipefail
          export EXPERIMENT_RUN_ID=0123456789abcdef0123456789abcdef
          export EXPERIMENT_CONFIGURATION_HASH=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
          write_evaluation_failure ${JSON.stringify(join(dir, "report.md"))} ${JSON.stringify(result)} model interrupted 143
          python3 -c 'import json; d=json.load(open("${result}")); assert d["run_id"] == "0123456789abcdef0123456789abcdef"; assert d["configuration_hash"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"'
        `);
        expect(shell.status).toBe(0);
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    }
  });

  it("preserves the evaluator's rich failed JSON and report", () => {
    const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
    try {
      const report = join(dir, "report.md");
      const result = join(dir, "result.json");
      const originalReport = "# Rich failure\n\nerror: judge unavailable\n";
      const originalResult = JSON.stringify({
        status: "FAILED",
        error: { type: "RuntimeError", message: "judge unavailable" },
        provenance: { run_id: "run-123" },
      }, null, 2) + "\n";
      writeFileSync(report, originalReport);
      writeFileSync(result, originalResult);
      const shell = runBash(`
        set -euo pipefail
        source ${JSON.stringify(helper)}
        write_evaluation_failure ${JSON.stringify(report)} ${JSON.stringify(result)} model 'wrapper observed exit 1' 1
      `);
      expect(shell.status).toBe(0);
      expect(readFileSync(report, "utf8")).toBe(originalReport);
      expect(readFileSync(result, "utf8")).toBe(originalResult);
      expect(() => readFileSync(`${result}.pre_failure`)).toThrow();
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("preserves rich failed JSON and synthesizes a missing report", () => {
    const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
    try {
      const report = join(dir, "report.md");
      const result = join(dir, "result.json");
      const originalResult = JSON.stringify({
        status: "FAILED",
        error: { type: "RuntimeError", message: "judge unavailable" },
        provenance: { run_id: "run-456" },
      }, null, 2) + "\n";
      writeFileSync(result, originalResult);
      const shell = runBash(`
        set -euo pipefail
        source ${JSON.stringify(helper)}
        write_evaluation_failure ${JSON.stringify(report)} ${JSON.stringify(result)} model 'wrapper observed exit 1' 1
      `);
      expect(shell.status).toBe(0);
      expect(readFileSync(result, "utf8")).toBe(originalResult);
      expect(readFileSync(report, "utf8")).toContain("Status: FAILED");
      expect(readFileSync(report, "utf8")).toContain("Evaluator exit status: 1");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("moves stale success and malformed artifacts to sidecars before fallback", () => {
    for (const originalResult of [
      JSON.stringify({ status: "COMPLETED", summary: { pass_rate: 100 } }),
      "{ malformed json",
    ]) {
      const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
      try {
        const report = join(dir, "report.md");
        const result = join(dir, "result.json");
        const originalReport = "old report\n";
        writeFileSync(report, originalReport);
        writeFileSync(result, originalResult);
        const shell = runBash(`
          set -euo pipefail
          source ${JSON.stringify(helper)}
          write_evaluation_failure ${JSON.stringify(report)} ${JSON.stringify(result)} model 'evaluator exited with status 7' 7
        `);
        expect(shell.status).toBe(0);
        expect(readFileSync(`${report}.pre_failure`, "utf8")).toBe(originalReport);
        expect(readFileSync(`${result}.pre_failure`, "utf8")).toBe(originalResult);
        const fallback = JSON.parse(readFileSync(result, "utf8"));
        expect(fallback.status).toBe("FAILED");
        expect(fallback.evaluation.evaluator_exit_status).toBe(7);
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    }
  });

  it("makes a failed fallback authoritative after a successful artifact", () => {
    const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
    try {
      const report = join(dir, "report.md");
      const result = join(dir, "result.json");
      writeFileSync(report, "successful report\n");
      writeFileSync(result, JSON.stringify({ status: "COMPLETED", summary: { pass_rate: 100 } }));
      const shell = runBash(`
        set -euo pipefail
        source ${JSON.stringify(helper)}
        write_evaluation_failure ${JSON.stringify(report)} ${JSON.stringify(result)} model 'nonzero after stale success' 23
      `);
      expect(shell.status).toBe(0);
      expect(JSON.parse(readFileSync(result, "utf8")).status).toBe("FAILED");
      expect(readFileSync(`${report}.pre_failure`, "utf8")).toBe("successful report\n");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("preserves successful evaluator output without inventing scores", () => {
    const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
    try {
      const log = join(dir, "evaluator.log");
      const result = runBash(`
        set -euo pipefail
        source ${JSON.stringify(helper)}
        run_with_tee_status ${JSON.stringify(log)} bash -c 'printf evaluator-success; exit 0'
      `);
      expect(result.status).toBe(0);
      expect(readFileSync(log, "utf8")).toBe("evaluator-success");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("distinguishes a delete request from verified absence", () => {
    const result = runBash(`
      set -euo pipefail
      source ${JSON.stringify(helper)}
      verify_delete_absent bash -c 'printf "resource was not found" >&2; exit 1'
      if verify_delete_absent bash -c 'exit 0'; then exit 17; fi
      if verify_delete_absent bash -c 'printf "permission denied" >&2; exit 1'; then exit 18; fi
    `);
    expect(result.status).toBe(0);
  });

  it("keeps both boot paths self-contained and free of fabricated fallback scores", () => {
    for (const path of startupScripts) {
      const content = readFileSync(path, "utf8");
      expect(content).toContain("PIPESTATUS");
      expect(content).toContain("normalized_output");
      expect(content).toContain('"status": "FAILED"');
      expect(content).toContain("delete_verified");
      expect(content).toContain("COMMAND_SUCCEEDED");
      expect(content).toContain("REQUESTED");
      expect(content).toContain('instance/attributes/run_id');
      expect(content).toContain('instance/attributes/configuration_hash');
      expect(content).toContain('OUTPUT_DIR="/tmp/eval_results/${EXPERIMENT_RUN_ID}/${MODEL_FLAVOR}"');
      expect(content).toContain('"run_id": ${json_run_id}');
      expect(content).toContain('"configuration_hash": ${json_configuration_hash}');
      expect(content).toContain('"requested_source_commit": ${json_source_commit}');
      expect(content).toContain('lifecycle_status.json" || upload_status=$?');
      expect(content).toContain('return "${upload_status}"');
      expect(content).not.toContain('ARTIFACT_UPLOAD_STATUS="UPLOADED"');
      expect(content).not.toContain("Creating minimal benchmark scorecard");
      expect(content).not.toContain('"avg_rubric_score": 90.0');
    }
  });

  it("publishes the final lifecycle marker after bulk upload", () => {
    for (const path of startupScripts) {
      const content = readFileSync(path, "utf8");
      const bulk = content.indexOf('gcloud storage cp -r "${OUTPUT_DIR}"/*');
      const marker = content.indexOf('gcloud storage cp "${LIFECYCLE_PATH}"');
      const failedReturn = content.indexOf('return "${upload_status}"');
      expect(bulk).toBeGreaterThan(-1);
      expect(marker).toBeGreaterThan(bulk);
      expect(failedReturn).toBeGreaterThan(marker);
      expect(content).toContain('UPLOAD_FAILED=true');
    }
  });

  it("does not export empty identity to legacy evaluator processes", () => {
    for (const path of startupScripts) {
      const content = readFileSync(path, "utf8");
      const start = content.indexOf('EXPERIMENT_RUN_ID="$(get_metadata');
      const end = content.indexOf("\n\nCONTAINER_NAME", start);
      const identityBlock = content.slice(start, end);
      const result = runBash(`
        export EXPERIMENT_RUN_ID=old EXPERIMENT_CONFIGURATION_HASH=old
        get_metadata() { printf ''; }
        ${identityBlock}
        set -euo pipefail
        python3 -c 'import os; assert "EXPERIMENT_RUN_ID" not in os.environ; assert "EXPERIMENT_CONFIGURATION_HASH" not in os.environ'
      `);
      expect(result.status).toBe(0);
    }
  });

  it("exports populated identity and preserves one-sided failure semantics", () => {
    const content = readFileSync(startupScripts[0], "utf8");
    const start = content.indexOf('EXPERIMENT_RUN_ID="$(get_metadata');
    const end = content.indexOf("\n\nCONTAINER_NAME", start);
    const identityBlock = content.slice(start, end);
    const populated = runBash(`
      get_metadata() { case "$1" in instance/attributes/run_id) printf '0123456789abcdef0123456789abcdef';; instance/attributes/configuration_hash) printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';; *) printf ''; esac; }
      ${identityBlock}
      python3 -c 'import os; assert os.environ["EXPERIMENT_RUN_ID"] == "0123456789abcdef0123456789abcdef"; assert len(os.environ["EXPERIMENT_CONFIGURATION_HASH"]) == 64'
    `);
    expect(populated.status).toBe(0);
    const oneSided = runBash(`
      get_metadata() { case "$1" in instance/attributes/run_id) printf '0123456789abcdef0123456789abcdef';; *) printf ''; esac; }
      ${identityBlock}
      python3 -c 'import os; assert os.environ["EXPERIMENT_RUN_ID"]; assert os.environ["EXPERIMENT_CONFIGURATION_HASH"] == ""'
    `);
    expect(oneSided.status).toBe(0);
  });

  it("embeds the same status and deletion verification behavior in each boot path", () => {
    for (const path of startupScripts) {
      const prefix = readFileSync(path, "utf8").split("# ==============================================================================", 1)[0];
      const result = runBash(`${prefix}
        set -euo pipefail
        log=$(mktemp)
        if run_with_tee_status "$log" bash -c 'exit 19'; then exit 20; fi
        test "$LIFECYCLE_COMMAND_STATUS" = 19
        verify_delete_absent bash -c 'printf "resource not found" >&2; exit 1'
        if verify_delete_absent bash -c 'printf "permission denied" >&2; exit 1'; then exit 21; fi
        rm -f "$log"
      `);
      expect(result.status).toBe(0);
    }
  });

  it("embeds rich failure preservation in each boot path", () => {
    for (const path of startupScripts) {
      const prefix = readFileSync(path, "utf8").split("# ==============================================================================", 1)[0];
      const dir = mkdtempSync(join(tmpdir(), "gce-lifecycle-"));
      try {
        const report = join(dir, "report.md");
        const result = join(dir, "result.json");
        const originalResult = JSON.stringify({
          status: "FAILED",
          error: { type: "RuntimeError", message: "embedded evaluator failure" },
          provenance: { run_id: "embedded-789" },
        }, null, 2) + "\n";
        writeFileSync(result, originalResult);
        const shell = runBash(`${prefix}
          set -euo pipefail
          write_evaluation_failure ${JSON.stringify(report)} ${JSON.stringify(result)} model 'wrapper failure' 9
        `);
        expect(shell.status).toBe(0);
        expect(readFileSync(result, "utf8")).toBe(originalResult);
        expect(readFileSync(report, "utf8")).toContain("Status: FAILED");
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    }
  });
});
