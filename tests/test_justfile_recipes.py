"""Unit tests for Justfile SOC and Terraform recipes and documentation integration."""

from pathlib import Path
import subprocess
import unittest

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestJustfileRecipes(unittest.TestCase):
    """Test suite validating Justfile recipes, syntax, and documentation integration."""

    def test_justfile_contains_soc_recipes(self):
        """Verify Justfile contains agent-soc-test, agent-soc-eval, and agent-soc-deploy recipes."""
        justfile_path = ROOT_DIR / "Justfile"
        self.assertTrue(justfile_path.exists(), "Justfile not found")

        content = justfile_path.read_text(encoding="utf-8")

        # Assert recipe definitions exist
        self.assertIn("agent-soc-test", content, "Recipe 'agent-soc-test' not defined in Justfile")
        self.assertIn("agent-soc-eval", content, "Recipe 'agent-soc-eval' not defined in Justfile")
        self.assertIn("agent-soc-deploy", content, "Recipe 'agent-soc-deploy' not defined in Justfile")

        # Assert recipes are present in the help menu
        self.assertIn("just agent-soc-test", content, "Help menu missing 'just agent-soc-test'")
        self.assertIn("just agent-soc-eval", content, "Help menu missing 'just agent-soc-eval'")
        self.assertIn("just agent-soc-deploy", content, "Help menu missing 'just agent-soc-deploy'")

        # Assert recipes invoke expected Python targets
        self.assertIn("deploy_soc_tier1", content, "Recipe agent-soc-deploy must call deploy_soc_tier1")
        self.assertIn("eval_soc_agent", content, "Recipe agent-soc-eval must call eval_soc_agent")

    def test_justfile_contains_terraform_recipes(self):
        """Verify Justfile contains tf-init, tf-plan, tf-apply, and tf-destroy recipes."""
        justfile_path = ROOT_DIR / "Justfile"
        self.assertTrue(justfile_path.exists(), "Justfile not found")

        content = justfile_path.read_text(encoding="utf-8")

        # Assert recipe definitions exist
        self.assertIn("tf-init:", content, "Recipe 'tf-init' not defined in Justfile")
        self.assertIn("tf-plan", content, "Recipe 'tf-plan' not defined in Justfile")
        self.assertIn("tf-apply", content, "Recipe 'tf-apply' not defined in Justfile")
        self.assertIn("tf-destroy:", content, "Recipe 'tf-destroy' not defined in Justfile")

        # Assert recipes are present in the help menu
        self.assertIn("just tf-init", content, "Help menu missing 'just tf-init'")
        self.assertIn("just tf-plan", content, "Help menu missing 'just tf-plan'")
        self.assertIn("just tf-apply", content, "Help menu missing 'just tf-apply'")
        self.assertIn("just tf-destroy", content, "Help menu missing 'just tf-destroy'")

    def test_justfile_contains_overnight_sweep_recipe(self):
        """Verify Justfile contains overnight-sweep recipe with logging and optional filtering."""
        justfile_path = ROOT_DIR / "Justfile"
        self.assertTrue(justfile_path.exists(), "Justfile not found")

        content = justfile_path.read_text(encoding="utf-8")

        # Assert recipe definition and help menu presence
        self.assertIn("overnight-sweep", content, "Recipe 'overnight-sweep' not defined in Justfile")
        self.assertIn("just overnight-sweep", content, "Help menu missing 'just overnight-sweep'")

        # Assert recipe creates logs directory and runs orchestrator with tee logging
        self.assertIn("mkdir -p logs", content, "Recipe must ensure logs/ directory exists")
        self.assertIn("run_overnight_sweep.py", content, "Recipe must invoke run_overnight_sweep.py")
        self.assertTrue(
            "overnight_sweep_" in content and ".log" in content,
            "Recipe must log to timestamped log file",
        )
        self.assertIn("tee", content, "Recipe must use tee for live output and logfile capture")

<<<<<<< HEAD
    def test_justfile_contains_gce_spot_recipes(self):
        """Verify Justfile contains gce-spot-run, gce-spot-sweep, gce-spot-status, and gce-spot-cleanup recipes."""
=======
    def test_justfile_contains_gke_ray_recipes(self):
        """Verify Justfile contains GKE Ray and Kueue sweep recipes and help menu entries."""
>>>>>>> 3b205d9 (feat(gke-ray): add Justfile recipes and GKE Ray documentation)
        justfile_path = ROOT_DIR / "Justfile"
        self.assertTrue(justfile_path.exists(), "Justfile not found")

        content = justfile_path.read_text(encoding="utf-8")

        # Assert recipe definitions exist
<<<<<<< HEAD
        self.assertIn("gce-spot-run", content, "Recipe 'gce-spot-run' not defined in Justfile")
        self.assertIn("gce-spot-sweep", content, "Recipe 'gce-spot-sweep' not defined in Justfile")
        self.assertIn("gce-spot-status", content, "Recipe 'gce-spot-status' not defined in Justfile")
        self.assertIn("gce-spot-cleanup", content, "Recipe 'gce-spot-cleanup' not defined in Justfile")

        # Assert recipes are present in the help menu
        self.assertIn("just gce-spot-run", content, "Help menu missing 'just gce-spot-run'")
        self.assertIn("just gce-spot-sweep", content, "Help menu missing 'just gce-spot-sweep'")
        self.assertIn("just gce-spot-status", content, "Help menu missing 'just gce-spot-status'")
        self.assertIn("just gce-spot-cleanup", content, "Help menu missing 'just gce-spot-cleanup'")

        # Assert recipes invoke expected Python / gcloud targets
        self.assertIn("run_gce_spot_sweep.py", content, "Recipe must call run_gce_spot_sweep.py")
        self.assertIn("scheduling.provisioningModel=SPOT", content, "Status recipe must filter for SPOT provisioning")
        self.assertIn("name:(spot-* OR gemma-spot-*)", content, "Cleanup recipe must filter for spot-* and gemma-spot-* benchmark instances")

    def test_justfile_contains_custom_job_recipes(self):
        """Verify Justfile contains custom-job-build, custom-job-run, custom-job-sweep, and custom-job-status recipes."""
        justfile_path = ROOT_DIR / "Justfile"
        self.assertTrue(justfile_path.exists(), "Justfile not found")

        content = justfile_path.read_text(encoding="utf-8")

        # Assert recipe definitions exist
        self.assertIn("custom-job-build", content, "Recipe 'custom-job-build' not defined in Justfile")
        self.assertIn("custom-job-run", content, "Recipe 'custom-job-run' not defined in Justfile")
        self.assertIn("custom-job-sweep", content, "Recipe 'custom-job-sweep' not defined in Justfile")
        self.assertIn("custom-job-status", content, "Recipe 'custom-job-status' not defined in Justfile")

        # Assert recipes are present in the help menu
        self.assertIn("just custom-job-build", content, "Help menu missing 'just custom-job-build'")
        self.assertIn("just custom-job-run", content, "Help menu missing 'just custom-job-run'")
        self.assertIn("just custom-job-sweep", content, "Help menu missing 'just custom-job-sweep'")
        self.assertIn("just custom-job-status", content, "Help menu missing 'just custom-job-status'")

        # Assert recipes invoke expected underlying commands
        self.assertIn("run_vertex_custom_job_sweep.py", content, "Recipe must invoke run_vertex_custom_job_sweep.py")
        self.assertIn("Dockerfile.custom_job", content, "Recipe custom-job-build must reference Dockerfile.custom_job")
        self.assertIn("gcloud ai custom-jobs list", content, "Recipe custom-job-status must call gcloud ai custom-jobs list")

    def test_justfile_contains_gke_ray_recipes(self):
        """Verify Justfile contains gke-ray-init, gke-ray-run, gke-ray-sweep, gke-ray-status, and gke-ray-cleanup recipes."""
        justfile_path = ROOT_DIR / "Justfile"
        self.assertTrue(justfile_path.exists(), "Justfile not found")

        content = justfile_path.read_text(encoding="utf-8")

        self.assertIn("gke-ray-init", content, "Recipe 'gke-ray-init' not defined in Justfile")
        self.assertIn("gke-ray-run", content, "Recipe 'gke-ray-run' not defined in Justfile")
        self.assertIn("gke-ray-sweep", content, "Recipe 'gke-ray-sweep' not defined in Justfile")
        self.assertIn("gke-ray-status", content, "Recipe 'gke-ray-status' not defined in Justfile")
        self.assertIn("gke-ray-cleanup", content, "Recipe 'gke-ray-cleanup' not defined in Justfile")

        # Assert recipes are present in the help menu
        self.assertIn("just gke-ray-init", content, "Help menu missing 'just gke-ray-init'")
        self.assertIn("just gke-ray-run", content, "Help menu missing 'just gke-ray-run'")
        self.assertIn("just gke-ray-sweep", content, "Help menu missing 'just gke-ray-sweep'")
        self.assertIn("just gke-ray-status", content, "Help menu missing 'just gke-ray-status'")
        self.assertIn("just gke-ray-cleanup", content, "Help menu missing 'just gke-ray-cleanup'")

        # Assert recipe commands and integrations
        self.assertIn("k8s/kueue_queues.yaml", content, "Recipe gke-ray-init must reference kueue_queues.yaml")
        self.assertIn("run_gke_ray_sweep.py", content, "Recipe gke-ray-sweep must invoke run_gke_ray_sweep.py")
        self.assertIn("kubectl get rayclusters", content, "Recipe gke-ray-status must query rayclusters via kubectl")
        self.assertIn("kubectl delete rayclusters", content, "Recipe gke-ray-cleanup must delete rayclusters via kubectl")

    def test_justfile_syntax(self):
        """Verify Justfile parses without syntax errors using the just CLI."""
        res = subprocess.run(
            ["just", "--dump"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Justfile syntax error: {res.stderr}")
        self.assertIn("agent-soc-test", res.stdout)
        self.assertIn("agent-soc-eval", res.stdout)
        self.assertIn("agent-soc-deploy", res.stdout)
        self.assertIn("overnight-sweep", res.stdout)
        self.assertIn("tf-plan", res.stdout)
        self.assertIn("tf-apply", res.stdout)
        self.assertIn("gce-spot-run", res.stdout)
        self.assertIn("gce-spot-sweep", res.stdout)
        self.assertIn("gce-spot-status", res.stdout)
        self.assertIn("gce-spot-cleanup", res.stdout)
        self.assertIn("custom-job-build", res.stdout)
        self.assertIn("custom-job-run", res.stdout)
        self.assertIn("custom-job-sweep", res.stdout)
        self.assertIn("custom-job-status", res.stdout)
        self.assertIn("gke-ray-init", res.stdout)
        self.assertIn("gke-ray-run", res.stdout)
        self.assertIn("gke-ray-sweep", res.stdout)
        self.assertIn("gke-ray-status", res.stdout)
        self.assertIn("gke-ray-cleanup", res.stdout)

    def test_experiments_status_contains_track_e(self):
        """Verify docs/experiments_status.md contains Track E for Gemma SOC evaluation."""
        doc_path = ROOT_DIR / "docs" / "experiments_status.md"
        self.assertTrue(doc_path.exists(), "docs/experiments_status.md not found")

        content = doc_path.read_text(encoding="utf-8")
        self.assertIn("Track E: Gemma Model Size vs. SOC Triage Capabilities", content)
        self.assertIn("soc_tier1_evalset.json", content)
        self.assertTrue("gemini-2.5-pro" in content or "LLM-as-a-judge" in content)
        self.assertIn("gemma-3-1b-it", content)
        self.assertIn("gemma-3-4b-it", content)
        self.assertIn("gemma-2-9b-it", content)
        self.assertIn("gemma-4-31b-it", content)

    def test_no_emojis_in_justfile_and_docs(self):
        """Verify no emojis are present in Justfile, tests, or documentation files."""
        files_to_check = [
            ROOT_DIR / "Justfile",
            ROOT_DIR / "docs" / "experiments_status.md",
            ROOT_DIR / "docs" / "benchmarking_vertex_custom_jobs.md",
            ROOT_DIR / "docs" / "benchmarking_gke_ray_serve.md",
            Path(__file__),
        ]
        spot_doc = ROOT_DIR / "docs" / "benchmarking_gce_ephemeral_spot_vms.md"
        if spot_doc.exists():
            files_to_check.append(spot_doc)

        for fpath in files_to_check:
            if not fpath.exists():
                continue
            text = fpath.read_text(encoding="utf-8")
            for char in text:
                code = ord(char)
                is_emoji = (
                    (0x1F600 <= code <= 0x1F64F)
                    or (0x1F300 <= code <= 0x1F5FF)
                    or (0x1F680 <= code <= 0x1F6FF)
                    or (0x1F700 <= code <= 0x1F77F)
                    or (0x1F780 <= code <= 0x1F7FF)
                    or (0x1F800 <= code <= 0x1F8FF)
                    or (0x1F900 <= code <= 0x1F9FF)
                    or (0x1FA00 <= code <= 0x1FA6F)
                    or (0x1FA70 <= code <= 0x1FAFF)
                    or (0x2600 <= code <= 0x26FF)
                    or (0x2700 <= code <= 0x27BF)
                )
                self.assertFalse(is_emoji, f"Emoji character '{char}' (code {code}) found in {fpath.name}")


if __name__ == "__main__":
    unittest.main()
