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
});
