import os
import re
import unittest
from io import BytesIO
from concurrent.futures import Future
from unittest.mock import patch
from scripts.benchmark import (
    calculate_percentile,
    calculate_summary,
    BenchmarkRunner,
    format_benchmark_table,
    parse_output_details,
    send_streaming_request_detailed,
    _decode_stream_response,
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
        self.assertIsNone(summary["aggregate_tps"])
        self.assertEqual(summary["wall_clock_source"], "unavailable")
        self.assertAlmostEqual(summary["request_normalized_tps"], 100.0, places=1)

    def test_aggregate_throughput_uses_wall_clock_and_preserves_normalized_rate(self):
        summary = calculate_summary(
            latencies=[2.0, 2.0],
            token_counts=[100, 100],
            wall_clock_s=2.0,
            concurrency=2,
            token_count_sources=["actual", "actual"],
        )

        self.assertEqual(summary["token_count_source"], "actual")
        self.assertAlmostEqual(summary["aggregate_tps"], 100.0, places=1)
        self.assertAlmostEqual(summary["request_normalized_tps"], 50.0, places=1)
        self.assertAlmostEqual(summary["tps"], summary["aggregate_tps"], places=1)
        self.assertEqual(summary["wall_clock_s"], 2.0)

        legacy_table = format_benchmark_table(
            calculate_summary(latencies=[1.0], token_counts=[10])
        )
        self.assertIn("Wall-Clock Time:  unavailable", legacy_table)
        self.assertIn("Aggregate Rate:   unavailable", legacy_table)

    def test_token_count_and_timing_provenance_labels(self):
        text, count, source = parse_output_details(
            {"predictions": [{"content": "triage complete"}], "usage": {"completion_tokens": 7}}
        )
        self.assertEqual((text, count, source), ("triage complete", 7, "actual"))

        _, _, estimated_source = parse_output_details({"predictions": [{"content": "123456789"}]})
        _, _, empty_source = parse_output_details({"predictions": []})
        self.assertEqual(estimated_source, "estimated")
        self.assertEqual(empty_source, "none")

        summary = calculate_summary(
            latencies=[1.0],
            token_counts=[10],
            ttfts=[0.2],
            first_token_times=[0.5],
            token_count_sources=["estimated"],
        )
        self.assertEqual(summary["ttft_source"], "first_network_chunk")
        self.assertEqual(summary["first_token_source"], "verified_generated_token")
        self.assertEqual(summary["first_chunk_ms"], 200.0)
        self.assertEqual(summary["first_token_ms"], 500.0)

        chat_text, chat_count, chat_source = parse_output_details(
            {
                "choices": [{"message": {"role": "assistant", "content": "chat answer"}}],
                "usage": {"prompt_tokens": 80, "completion_tokens": 6, "total_tokens": 86},
            }
        )
        self.assertEqual((chat_text, chat_count, chat_source), ("chat answer", 6, "actual"))

        _, _, ambiguous_source = parse_output_details(
            {"predictions": [{"content": "answer", "token_count": 99}], "prompt_tokens": 400}
        )
        self.assertEqual(ambiguous_source, "estimated")
        _, _, fractional_source = parse_output_details(
            {"predictions": [{"content": "answer"}], "usage": {"completion_tokens": 7.5}}
        )
        self.assertEqual(fractional_source, "estimated")

    def test_sse_stream_merges_cumulative_text_and_final_usage(self):
        class Response:
            def __init__(self, body):
                self.chunks = [body[index:index + 17] for index in range(0, len(body), 17)]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size):
                return self.chunks.pop(0) if self.chunks else b""

        body = b"".join(
            [
                b'data: {"choices":[{"delta":{"content":"he"}}]}\n\n',
                b'data: {"choices":[{"delta":{"content":"llo"}}]}\n\n',
                b'data: {"choices":[{"delta":{"content":"ha"}}]}\n\n',
                b'data: {"choices":[{"delta":{"content":"ha"}}],"usage":{"prompt_tokens":20,"completion_tokens":7}}\n\n',
                b"data: [DONE]\n\n",
            ]
        )
        with patch("scripts.benchmark.urllib.request.urlopen", return_value=Response(body)):
            elapsed, first_chunk, first_token, response, error = send_streaming_request_detailed(
                "https://example.test", {}, {"instances": [{"prompt": "hi"}]}
            )

        self.assertIsNone(error)
        self.assertGreaterEqual(first_chunk, 0.0)
        self.assertIsNotNone(first_token)
        self.assertLessEqual(first_token, elapsed)
        text, count, source = parse_output_details(response)
        self.assertEqual(text, "hellohaha")
        self.assertEqual((count, source), (7, "actual"))

        cumulative = _decode_stream_response(
            'data: {"predictions":[{"content":"he"}]}\n\n'
            'data: {"predictions":[{"content":"hello"}]}\n\n'
        )
        self.assertEqual(parse_output_details(cumulative)[0], "hello")

    def test_sse_heartbeats_metadata_and_multiline_data_are_valid(self):
        body = (
            ': heartbeat\n'
            'id: 7\n'
            'retry: 1000\n'
            '\n'
            'data: {"choices":[{"delta":{\n'
            'data: "content":"hello"}}]}\n'
            '\n'
        )
        decoded = _decode_stream_response(body)
        self.assertEqual(parse_output_details(decoded)[0], "hello")

    def test_stream_error_after_partial_content_preserves_diagnostic_and_fails(self):
        class Response:
            status = 500

            def __init__(self, body):
                self.stream = BytesIO(body)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size):
                return self.stream.read(size)

        body = (
            b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            b'event: error\n'
            b'data: {"error":{"code":500,"message":"upstream exploded"}}\n\n'
        )
        with patch("scripts.benchmark.urllib.request.urlopen", return_value=Response(body)):
            elapsed, _, _, response, error = send_streaming_request_detailed(
                "https://example.test", {}, {"instances": [{"prompt": "hi"}]}
            )
        self.assertGreaterEqual(elapsed, 0.0)
        self.assertIsNotNone(error)
        self.assertIn("upstream exploded", error)
        self.assertEqual(parse_output_details(response)[0], "partial")

    def test_stream_error_envelope_and_immediate_error_are_failures(self):
        class Response:
            def __init__(self, body):
                self.stream = BytesIO(body)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size):
                return self.stream.read(size)

        for body, expected in [
            (b'data: {"error":"quota exceeded"}\n\n', "quota exceeded"),
            (b'event: error\ndata: {"data":{"error":{"message":"bad model"}}}\n\n', "bad model"),
            (b'data: {"error":{"code":500}}\n\n', "provider error (500)"),
            (b'data: {"error":{}}\n\n', "provider error"),
        ]:
            with patch("scripts.benchmark.urllib.request.urlopen", return_value=Response(body)):
                _, _, _, response, error = send_streaming_request_detailed(
                    "https://example.test", {}, {"instances": [{"prompt": "hi"}]}
                )
            self.assertIn(expected, error)
            self.assertEqual(parse_output_details(response)[2], "none")

    def test_malformed_stream_is_not_transport_text_or_success(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size):
                if getattr(self, "done", False):
                    return b""
                self.done = True
                return b'not-json-and-not-an-event'

        with patch("scripts.benchmark.urllib.request.urlopen", return_value=Response()):
            _, _, _, response, error = send_streaming_request_detailed(
                "https://example.test", {}, {"instances": [{"prompt": "hi"}]}
            )
        self.assertIn("malformed", error)
        self.assertEqual(parse_output_details(response)[2], "none")

    def test_runner_accounts_for_real_stream_failures_single_and_concurrent(self):
        class Response:
            def __init__(self, body):
                self.stream = BytesIO(body)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size):
                return self.stream.read(size)

        success = b'data: {"choices":[{"delta":{"content":"ok"}}],"usage":{"completion_tokens":2}}\n\n'
        failure = b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\nevent: error\ndata: {"error":{"message":"provider failed"}}\n\n'

        runner = BenchmarkRunner(endpoint_id="endpoint", concurrency=1, runs=2)
        with patch.object(runner, "get_token", return_value="token"), \
             patch("scripts.benchmark.urllib.request.urlopen", side_effect=[Response(success), Response(failure)]):
            summary = runner.run(concurrency=1, runs=2, stream=True)
        self.assertEqual(summary["successful_requests"], 1)
        self.assertEqual(summary["failed_requests"], 1)
        self.assertEqual(summary["avg_tokens"], 2.0)

        concurrent_runner = BenchmarkRunner(endpoint_id="endpoint", concurrency=2, runs=1)
        with patch.object(concurrent_runner, "get_token", return_value="token"), \
             patch("scripts.benchmark.urllib.request.urlopen", side_effect=[Response(failure), Response(failure)]):
            summary = concurrent_runner.run(concurrency=2, runs=1, stream=True)
        self.assertIsNone(summary)

    def test_concurrent_runner_keeps_success_when_one_stream_fails(self):
        class ImmediateExecutor:
            def __init__(self, max_workers):
                self.max_workers = max_workers

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def submit(self, fn, *args):
                future = Future()
                future.set_result(fn(*args))
                return future

        responses = iter([
            (0.4, 0.1, 0.2, {"predictions": [{"content": "ok"}], "usage": {"completion_tokens": 4}}, None),
            (0.3, 0.1, None, {"predictions": [{"content": "partial"}]}, "HTTP 500: provider failed"),
        ])
        runner = BenchmarkRunner(endpoint_id="endpoint", concurrency=2, runs=1)
        with patch("scripts.benchmark.ThreadPoolExecutor", ImmediateExecutor), \
             patch("scripts.benchmark.send_streaming_request_detailed", side_effect=lambda *args: next(responses)), \
             patch.object(runner, "get_token", return_value="token"):
            summary = runner.run(concurrency=2, runs=1, stream=True)
        self.assertEqual(summary["successful_requests"], 1)
        self.assertEqual(summary["failed_requests"], 1)
        self.assertEqual(summary["avg_tokens"], 4.0)

    def test_concurrent_run_counts_errors_and_uses_successful_requests(self):
        class ImmediateExecutor:
            def __init__(self, max_workers):
                self.max_workers = max_workers

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def submit(self, fn, *args):
                future = Future()
                future.set_result(fn(*args))
                return future

        responses = iter([
            (0.4, {"predictions": [{"content": "ok"}], "usage": {"completion_tokens": 4}}, None),
            (0.3, None, "upstream unavailable"),
        ])
        runner = BenchmarkRunner(endpoint_id="endpoint", concurrency=2, runs=1)
        with patch("scripts.benchmark.ThreadPoolExecutor", ImmediateExecutor), \
             patch("scripts.benchmark.send_single_request", side_effect=lambda *args: next(responses)), \
             patch.object(runner, "get_token", return_value="token"):
            summary = runner.run(concurrency=2, runs=1, stream=False)

        self.assertIsNotNone(summary)
        self.assertEqual(summary["successful_requests"], 1)
        self.assertEqual(summary["failed_requests"], 1)
        self.assertEqual(summary["token_count_source"], "actual")
        self.assertGreater(summary["aggregate_tps"], 0)

    def test_no_response_does_not_become_one_estimated_token(self):
        runner = BenchmarkRunner(endpoint_id="endpoint", runs=1)
        with patch("scripts.benchmark.send_single_request", return_value=(0.1, {"predictions": []}, None)), \
             patch.object(runner, "get_token", return_value="token"):
            self.assertIsNone(runner.run(runs=1, stream=False))

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
        self.assertIn("First Chunk", table_output)
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
