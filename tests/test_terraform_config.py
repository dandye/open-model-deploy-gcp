"""Unit tests for Terraform configuration, model catalog compatibility, and Justfile integration."""

import json
from pathlib import Path
import unittest

ROOT_DIR = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = ROOT_DIR / "terraform"
CATALOG_PATH = ROOT_DIR / "configs" / "models.json"


class TestTerraformConfig(unittest.TestCase):
    """Test suite validating Terraform configurations and model catalog integration."""

    def test_models_json_schema_completeness_for_terraform(self):
        """Verify all Gemma and dedicated compute models in configs/models.json define required fields."""
        self.assertTrue(CATALOG_PATH.exists(), "configs/models.json not found")

        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        expected_gemma_models = [
            "gemma-2-2b-it",
            "gemma-2-9b-it",
            "gemma-2-27b-it",
            "gemma-3-1b-it",
            "gemma-3-4b-it",
            "gemma-3-12b-it",
            "gemma-3-27b-it",
            "gemma-4-31b-it",
            "gemma-4-e2b-it",
            "gemma-4-e4b-it",
        ]

        for model_key in expected_gemma_models:
            self.assertIn(model_key, catalog, f"Missing expected model {model_key} in catalog")
            model_data = catalog[model_key]

            # Top-level required keys
            self.assertIn("displayName", model_data, f"{model_key} missing displayName")
            self.assertIn("family", model_data, f"{model_key} missing family")
            self.assertIn("sourceUri", model_data, f"{model_key} missing sourceUri")
            self.assertIn("hfRepo", model_data, f"{model_key} missing hfRepo")
            self.assertIn("compute", model_data, f"{model_key} missing compute")
            self.assertIn("runtime", model_data, f"{model_key} missing runtime")
            self.assertIn("supportedTargets", model_data, f"{model_key} missing supportedTargets")

            # Compute keys
            compute = model_data["compute"]
            self.assertIn("machineType", compute, f"{model_key} missing machineType")
            self.assertIn("acceleratorType", compute, f"{model_key} missing acceleratorType")
            self.assertIn("acceleratorCount", compute, f"{model_key} missing acceleratorCount")

            # Runtime keys
            runtime = model_data["runtime"]
            self.assertIn("tensorParallelSize", runtime, f"{model_key} missing tensorParallelSize")
            self.assertIn("swapSpaceGb", runtime, f"{model_key} missing swapSpaceGb")
            self.assertIn("gpuMemoryUtilization", runtime, f"{model_key} missing gpuMemoryUtilization")
            self.assertIn("maxModelLen", runtime, f"{model_key} missing maxModelLen")

            # Target constraints
            targets = model_data["supportedTargets"]
            self.assertIsInstance(targets, list, f"{model_key} supportedTargets must be a list")
            self.assertIn("vertex", targets, f"{model_key} must support vertex")
            if compute["acceleratorCount"] > 1:
                self.assertNotIn(
                    "cloudrun",
                    targets,
                    f"{model_key} has {compute['acceleratorCount']} GPUs and must not support cloudrun",
                )

        # Also verify that all models with compute blocks define machineType and acceleratorType
        for model_key, model_data in catalog.items():
            if "compute" in model_data:
                compute = model_data["compute"]
                self.assertIn("machineType", compute, f"{model_key} missing machineType")
                self.assertIn("acceleratorType", compute, f"{model_key} missing acceleratorType")
                self.assertIn("acceleratorCount", compute, f"{model_key} missing acceleratorCount")

    def test_terraform_locals_file(self):
        """Verify terraform/locals.tf extracts required attributes and handles catalog fields."""
        locals_path = TERRAFORM_DIR / "locals.tf"
        self.assertTrue(locals_path.exists(), "terraform/locals.tf not found")

        content = locals_path.read_text(encoding="utf-8")

        self.assertIn("catalog_raw", content)
        self.assertIn("selected_model", content)
        self.assertIn("vertex_machine_type", content)
        self.assertIn("vertex_accelerator_type", content)
        self.assertIn("vertex_accelerator_count", content)
        self.assertIn("display_name", content)
        self.assertIn("family", content)
        self.assertIn("is_cloudrun_supported", content)
        self.assertIn("cloudrun_args", content)
        self.assertTrue("extra_flags_list" in content or "extra_vllm_flags" in content)

    def test_terraform_variables_file(self):
        """Verify terraform/variables.tf declares required variables and validation."""
        vars_path = TERRAFORM_DIR / "variables.tf"
        self.assertTrue(vars_path.exists(), "terraform/variables.tf not found")

        content = vars_path.read_text(encoding="utf-8")

        self.assertIn('variable "project_id"', content)
        self.assertIn('variable "region"', content)
        self.assertIn('variable "enable_vertex_endpoint"', content)
        self.assertIn('variable "enable_cloudrun_service"', content)
        self.assertIn('variable "model_flavor"', content)
        self.assertIn('variable "extra_vllm_flags"', content)

        # Check validation block contains all Gemma models and partner models
        for model_key in [
            "gemma-2-2b-it",
            "gemma-2-9b-it",
            "gemma-2-27b-it",
            "gemma-3-1b-it",
            "gemma-3-4b-it",
            "gemma-3-12b-it",
            "gemma-3-27b-it",
            "gemma-4-31b-it",
            "gemma-4-e2b-it",
            "gemma-4-e4b-it",
            "qwen3.8-27b",
            "llama-3.2-3b-instruct",
            "deepseek-v4-pro",
        ]:
            self.assertIn(f'"{model_key}"', content, f"variables.tf missing model flavor {model_key}")

    def test_terraform_cloudrun_guardrails(self):
        """Verify cloudrun.tf conditionally checks is_cloudrun_supported and uses dynamic args."""
        cloudrun_path = TERRAFORM_DIR / "cloudrun.tf"
        self.assertTrue(cloudrun_path.exists(), "terraform/cloudrun.tf not found")

        content = cloudrun_path.read_text(encoding="utf-8")

        self.assertIn("local.is_cloudrun_supported", content)
        self.assertTrue("local.cloudrun_args" in content or "local.cloudrun_model_repo" in content)

    def test_terraform_outputs_file(self):
        """Verify outputs.tf exposes model metadata and resource endpoints."""
        outputs_path = TERRAFORM_DIR / "outputs.tf"
        self.assertTrue(outputs_path.exists(), "terraform/outputs.tf not found")

        content = outputs_path.read_text(encoding="utf-8")

        self.assertIn('output "vertex_endpoint_id"', content)
        self.assertIn('output "model_flavor"', content)
        self.assertIn('output "model_family"', content)
        self.assertIn('output "cloudrun_supported"', content)

    def test_no_emojis_in_terraform_directory(self):
        """Verify no emojis are present across terraform directory files."""
        tf_files = list(TERRAFORM_DIR.glob("*"))
        for fpath in tf_files:
            if fpath.is_file():
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
