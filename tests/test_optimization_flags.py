import os
import re
import subprocess
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestOptimizationFlags(unittest.TestCase):

    def test_model_catalog_extracts_extra_args(self):
        res = subprocess.run(
            ["bash", "-c", 'source scripts/lib/model_catalog.sh && get_runtime_extra_args "gemma-3-27b-it"'],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--limit_mm_per_prompt=image=5", res.stdout)
        self.assertIn("--max-num-seqs=4", res.stdout)

    def test_model_catalog_empty_extra_args(self):
        res = subprocess.run(
            ["bash", "-c", 'source scripts/lib/model_catalog.sh && get_runtime_extra_args "gemma-2-9b-it"'],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "")

    def test_model_catalog_extra_args_csv(self):
        res = subprocess.run(
            ["bash", "-c", 'source scripts/lib/model_catalog.sh && catalog_get_extra_args_csv "gemma-3-12b-it"'],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "--limit_mm_per_prompt=image=5,--max-num-seqs=4")

        res_single = subprocess.run(
            ["bash", "-c", 'source scripts/lib/model_catalog.sh && catalog_get_extra_args_csv "gemma-4-31b-it"'],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_single.returncode, 0)
        self.assertEqual(res_single.stdout.strip(), "--max-num-seqs=16")

    def test_vertex_model_register_container_args_appends_extra_vllm_flags(self):
        # Test script snippet matching vertex_model_register.sh container args construction
        bash_script = """
        source scripts/lib/model_catalog.sh
        MODEL_FLAVOR="gemma-3-27b-it"
        SOURCE_URI=$(catalog_get_source_uri "$MODEL_FLAVOR")
        TP_SIZE=$(catalog_get_tp_size "$MODEL_FLAVOR")
        SWAP_SPACE=$(catalog_get_swap_space "$MODEL_FLAVOR")
        GPU_MEM_UTIL=$(catalog_get_gpu_mem_util "$MODEL_FLAVOR")
        MAX_LEN=$(catalog_get_max_len "$MODEL_FLAVOR")
        EXTRA_ARGS_JSON=$(catalog_get "$MODEL_FLAVOR" ".runtime.extraArgs")
        MODEL_FAMILY=$(catalog_get_family "$MODEL_FLAVOR")

        CONTAINER_ARGS="python,-m,vllm.entrypoints.api_server,--host=0.0.0.0,--port=8080,--model=${SOURCE_URI},--tensor-parallel-size=${TP_SIZE},--gpu-memory-utilization=${GPU_MEM_UTIL},--max-model-len=${MAX_LEN}"

        if [[ -n "$SWAP_SPACE" && "$SWAP_SPACE" -gt 0 ]]; then
          CONTAINER_ARGS="${CONTAINER_ARGS},--swap-space=${SWAP_SPACE}"
        fi

        if [[ "$MODEL_FAMILY" != "gemma4" ]]; then
          CONTAINER_ARGS="${CONTAINER_ARGS},--disable-log-stats"
        fi

        if [[ "$EXTRA_ARGS_JSON" != "[]" && -n "$EXTRA_ARGS_JSON" && "$EXTRA_ARGS_JSON" != "null" ]]; then
          EXTRA_ARGS_CSV=$(echo "$EXTRA_ARGS_JSON" | jq -r 'join(",")')
          if [[ -n "$EXTRA_ARGS_CSV" ]]; then
            CONTAINER_ARGS="${CONTAINER_ARGS},${EXTRA_ARGS_CSV}"
          fi
        fi

        if [[ -n "${EXTRA_VLLM_FLAGS:-}" ]]; then
          EXTRA_VLLM_CSV=$(echo "$EXTRA_VLLM_FLAGS" | tr ' ' '\\n' | tr ',' '\\n' | grep -v '^$' | paste -sd, -)
          if [[ -n "$EXTRA_VLLM_CSV" ]]; then
            CONTAINER_ARGS="${CONTAINER_ARGS},${EXTRA_VLLM_CSV}"
          fi
        fi

        echo "$CONTAINER_ARGS"
        """

        # Scenario 1: FP8 quantization flag
        res1 = subprocess.run(
            ["bash", "-c", f'EXTRA_VLLM_FLAGS="--quantization=fp8" {bash_script}'],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res1.returncode, 0)
        self.assertIn("--quantization=fp8", res1.stdout)
        self.assertIn("--limit_mm_per_prompt=image=5,--max-num-seqs=4,--quantization=fp8", res1.stdout)

        # Scenario 2: Multiple space-separated flags (chunked prefill + prefix caching)
        res2 = subprocess.run(
            ["bash", "-c", f'EXTRA_VLLM_FLAGS="--enable-chunked-prefill --enable-prefix-caching" {bash_script}'],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res2.returncode, 0)
        self.assertIn("--enable-chunked-prefill,--enable-prefix-caching", res2.stdout)

        # Scenario 3: Comma-separated flags
        res3 = subprocess.run(
            ["bash", "-c", f'EXTRA_VLLM_FLAGS="--quantization=fp8,--speculative-model=foo" {bash_script}'],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res3.returncode, 0)
        self.assertIn("--quantization=fp8,--speculative-model=foo", res3.stdout)

    def test_vertex_model_register_display_name_generation(self):
        bash_script = """
        MODEL_FLAVOR="gemma-3-27b-it"
        if [[ -n "${EXTRA_VLLM_FLAGS:-}" ]]; then
          FLAGS_SLUG=$(echo "$EXTRA_VLLM_FLAGS" | tr -cs 'a-zA-Z0-9' '-' | sed 's/^-//;s/-$//' | cut -c1-24)
          DEFAULT_DISPLAY_NAME="${MODEL_FLAVOR}-${FLAGS_SLUG}-model-garden"
        else
          DEFAULT_DISPLAY_NAME="${MODEL_FLAVOR}-model-garden"
        fi
        MODEL_DISPLAY_NAME="${3:-${VERTEX_MODEL_DISPLAY_NAME:-$DEFAULT_DISPLAY_NAME}}"
        echo "$MODEL_DISPLAY_NAME"
        """

        res_default = subprocess.run(
            ["bash", "-c", bash_script],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_default.stdout.strip(), "gemma-3-27b-it-model-garden")

        res_fp8 = subprocess.run(
            ["bash", "-c", f'EXTRA_VLLM_FLAGS="--quantization=fp8" {bash_script}'],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_fp8.stdout.strip(), "gemma-3-27b-it-quantization-fp8-model-garden")

    def test_no_emojis_in_source_and_configs(self):
        # Regex to detect emoji ranges in text files
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"  # Emoticons
            "\U0001F300-\U0001F5FF"  # Symbols & Pictographs
            "\U0001F680-\U0001F6FF"  # Transport & Map
            "\U0001F1E0-\U0001F1FF"  # Flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols
            "\U0001FA00-\U0001FA6F"  # Chess Symbols / Extended
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "]+",
            flags=re.UNICODE,
        )

        scanned_extensions = (".sh", ".py", ".json", ".md")
        scanned_dirs = ["scripts", "configs", "tests"]

        for d in scanned_dirs:
            dir_path = os.path.join(ROOT_DIR, d)
            if not os.path.exists(dir_path):
                continue
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.endswith(scanned_extensions):
                        file_path = os.path.join(root, file)
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            matches = emoji_pattern.findall(content)
                            self.assertFalse(matches, f"Emoji detected in {file_path}: {matches}")


if __name__ == "__main__":
    unittest.main()
