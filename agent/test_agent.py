#!/usr/bin/env python3
"""CLI test utility for GemmaAgent and Vertex AI Agent Engine."""

import os
import sys
import argparse
from pathlib import Path

# Add repo root to python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agent.gemma_agent import GemmaAgent

def main():
    parser = argparse.ArgumentParser(description="Test GemmaAgent locally or against Agent Engine.")
    parser.add_argument("prompt", nargs="?", default="Explain quantum computing in two concise sentences.", help="Input user prompt")
    parser.add_argument("--endpoint", default=None, help="Specific Vertex AI Endpoint ID")
    parser.add_argument("--region", default="us-central1", help="GCP Region")
    parser.add_argument("--cloudrun-url", default=None, help="Cloud Run HTTPS Service URL")
    parser.add_argument("--managed-model", default=None, help="Hosted MaaS model name")
    parser.add_argument("--remote-resource", default=None, help="Vertex AI Agent Engine resource name to query remotely")
    args = parser.parse_args()

    project_id = os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle")

    if args.remote_resource:
        import vertexai
        from vertexai.preview import reasoning_engines
        print(f"Connecting to remote Agent Engine resource: {args.remote_resource}...")
        vertexai.init(project=project_id, location=args.region)
        remote_agent = reasoning_engines.ReasoningEngine(args.remote_resource)
        res = remote_agent.query(prompt=args.prompt)
        print("\n--- Agent Engine Response ---")
        print(res)
        return

    print("==========================================")
    print(" Local GemmaAgent Test Runner")
    print("==========================================")
    print(f"Project:      {project_id}")
    print(f"Region:       {args.region}")
    print(f"Prompt:       {args.prompt}")
    print("==========================================")

    agent = GemmaAgent(
        project_id=project_id,
        region=args.region,
        endpoint_id=args.endpoint,
        cloudrun_url=args.cloudrun_url,
        managed_model=args.managed_model,
    )
    agent.set_up()

    print("\nScanning for active Gemma endpoints...")
    result = agent.query(prompt=args.prompt)
    print("\n--- Result ---")
    print(json.dumps(result, indent=2) if isinstance(result, dict) else result)

if __name__ == "__main__":
    import json
    main()
