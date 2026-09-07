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
      expect(content).not.toContain('ARTIFACT_UPLOAD_STATUS="UPLOADED"');
      expect(content).not.toContain("Creating minimal benchmark scorecard");
      expect(content).not.toContain('"avg_rubric_score": 90.0');
    }
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
