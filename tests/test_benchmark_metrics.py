import os
import re
import unittest
from scripts.benchmark import (
    calculate_percentile,
    calculate_summary,
    BenchmarkRunner,
    format_benchmark_table,
)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestBenchmarkMetrics(unittest.TestCase):

    def test_calculate_percentile_known_values(self):
        # Odd number of samples
        data_odd = [10.0, 20.0, 30.0, 40.0, 50.0]
        self.assertAlmostEqual(calculate_percentile(data_odd, 50), 30.0, places=2)
        self.assertAlmostEqual(calculate_percentile(data_odd, 90), 46.0, places=2)
        self.assertAlmostEqual(calculate_percentile(data_odd, 99), 49.6, places=2)
        self.assertAlmostEqual(calculate_percentile(data_odd, 0), 10.0, places=2)
        self.assertAlmostEqual(calculate_percentile(data_odd, 100), 50.0, places=2)

        # Even number of samples
        data_even = [1.0, 2.0, 3.0, 4.0]
        self.assertAlmostEqual(calculate_percentile(data_even, 50), 2.5, places=2)

        # Single sample
        self.assertEqual(calculate_percentile([42.0], 50), 42.0)
        self.assertEqual(calculate_percentile([42.0], 99), 42.0)

        # Empty data
        self.assertEqual(calculate_percentile([], 50), 0.0)

    def test_calculate_summary_metrics_basic(self):
        latencies = [1.0, 2.0, 3.0]
        token_counts = [100, 200, 300]
        summary = calculate_summary(latencies=latencies, token_counts=token_counts, concurrency=1)

        self.assertIn("avg_latency_s", summary)
        self.assertIn("p50_latency_s", summary)
        self.assertIn("p90_latency_s", summary)
        self.assertIn("p99_latency_s", summary)
        self.assertIn("avg_tokens", summary)
        self.assertIn("tps", summary)
        self.assertIn("tpm", summary)

        self.assertAlmostEqual(summary["avg_latency_s"], 2.0, places=2)
        self.assertAlmostEqual(summary["p50_latency_s"], 2.0, places=2)
        self.assertAlmostEqual(summary["avg_tokens"], 200.0, places=1)
        self.assertAlmostEqual(summary["tps"], 100.0, places=1)  # 600 tokens / 6.0 sec = 100.0 TPS
        self.assertAlmostEqual(summary["tpm"], 6000.0, places=1)

    def test_calculate_summary_empty_lists(self):
        summary = calculate_summary(latencies=[], token_counts=[], concurrency=1)
        self.assertEqual(summary["total_requests"], 0)
        self.assertEqual(summary["avg_latency_s"], 0.0)
        self.assertEqual(summary["tps"], 0.0)

    def test_calculate_summary_streaming_ttft_and_itl(self):
        latencies = [1.5, 1.2, 1.8]  # seconds
        token_counts = [100, 100, 100]
        ttfts = [0.3, 0.2, 0.4]  # seconds

        summary = calculate_summary(
            latencies=latencies,
            token_counts=token_counts,
            ttfts=ttfts,
            concurrency=1,
        )

        self.assertIn("ttft_ms", summary)
        self.assertIn("itl_ms", summary)

        # Expected avg TTFT: (0.3 + 0.2 + 0.4) / 3 = 0.3s -> 300.0 ms
        self.assertAlmostEqual(summary["ttft_ms"], 300.0, places=1)

        # Expected ITL:
        # Run 1: (1.5 - 0.3) / 99 = 1.2 / 99 = 0.01212s = 12.12ms
        # Run 2: (1.2 - 0.2) / 99 = 1.0 / 99 = 0.01010s = 10.10ms
        # Run 3: (1.8 - 0.4) / 99 = 1.4 / 99 = 0.01414s = 14.14ms
        # Avg ITL: ~12.12ms
        self.assertAlmostEqual(summary["itl_ms"], 12.1, places=1)

    def test_benchmark_runner_class_interface(self):
        runner = BenchmarkRunner(
            project_id="test-project",
            region="us-central1",
            endpoint_id="1234567890",
            prompt="Hello world",
            max_tokens=150,
            runs=4,
            concurrency=2,
        )
        latencies = [1.2, 1.0, 1.1, 1.05]
        token_counts = [50, 50, 50, 50]
        metrics = runner.calculate_summary(token_counts=token_counts, latencies=latencies)

        self.assertIn("tps", metrics)
        self.assertIn("tpm", metrics)
        self.assertIn("avg_latency_s", metrics)
        self.assertIn("p50_latency_s", metrics)
        self.assertIn("p90_latency_s", metrics)
        self.assertIn("p99_latency_s", metrics)
        self.assertEqual(metrics["endpoint_id"], "1234567890")
        self.assertEqual(metrics["region"], "us-central1")
        self.assertEqual(metrics["concurrency"], 2)

    def test_format_benchmark_table(self):
        summary = {
            "endpoint_id": "999888777",
            "region": "us-central1",
            "concurrency": 1,
            "avg_latency_s": 1.25,
            "p50_latency_s": 1.20,
            "p90_latency_s": 1.35,
            "p99_latency_s": 1.40,
            "avg_tokens": 120.0,
            "tps": 96.0,
            "tpm": 5760.0,
            "ttft_ms": 180.0,
            "itl_ms": 8.9,
            "sample_output": "Quantum computing uses superposition and entanglement.",
        }
        table_output = format_benchmark_table(summary)
        self.assertIn("Benchmark Summary", table_output)
        self.assertIn("P50 Latency", table_output)
        self.assertIn("P90 Latency", table_output)
        self.assertIn("P99 Latency", table_output)
        self.assertIn("TTFT", table_output)
        self.assertIn("ITL", table_output)
        self.assertIn("96.0 tokens/sec (TPS)", table_output)

    def test_prefix_caching_speedup_calculation(self):
        runner = BenchmarkRunner(
            project_id="test-project",
            region="us-central1",
            endpoint_id="12345",
        )
        cold_run = {
            "latency": 3.0,
            "ttft": 1.5,
            "tokens": 100,
            "tps": 33.3,
        }
        warm_runs = [
            {"latency": 1.5, "ttft": 0.3, "tokens": 100, "tps": 66.7},
            {"latency": 1.4, "ttft": 0.25, "tokens": 100, "tps": 71.4},
        ]
        res = runner.calculate_prefix_caching_summary(cold_run=cold_run, warm_runs=warm_runs)
        self.assertIn("cold_latency_s", res)
        self.assertIn("warm_avg_latency_s", res)
        self.assertIn("latency_speedup_ratio", res)
        self.assertIn("cold_ttft_ms", res)
        self.assertIn("warm_avg_ttft_ms", res)
        self.assertIn("ttft_reduction_pct", res)

        # Cold latency 3.0s, warm avg 1.45s -> speedup ~ 2.07x
        self.assertAlmostEqual(res["latency_speedup_ratio"], 3.0 / 1.45, places=2)
        # Cold TTFT 1500ms, warm avg 275ms -> reduction ~ 81.67%
        self.assertAlmostEqual(res["ttft_reduction_pct"], ((1500 - 275) / 1500) * 100.0, places=1)

    def test_no_emojis_in_source_and_tests(self):
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "]+",
            flags=re.UNICODE,
        )
        target_files = [
            os.path.join(ROOT_DIR, "scripts", "benchmark.py"),
            os.path.join(ROOT_DIR, "tests", "test_benchmark_metrics.py"),
        ]
        for fpath in target_files:
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    matches = emoji_pattern.findall(content)
                    self.assertFalse(matches, f"Emoji detected in {fpath}: {matches}")


if __name__ == "__main__":
    unittest.main()
