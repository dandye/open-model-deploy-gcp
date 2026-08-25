#!/usr/bin/env python3
"""Deployment script to package and deploy GemmaAgent to Vertex AI Agent Engine."""

import os
import sys
from pathlib import Path

# Add repo root to python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import vertexai
from vertexai.preview import reasoning_engines
from agent.gemma_agent import GemmaAgent, get_current_time, calculate

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle")
REGION = os.environ.get("GCP_REGION", "us-central1")
STAGING_BUCKET = os.environ.get("GCS_STAGING_BUCKET", f"gs://{PROJECT_ID}-agent-engine-staging")

def deploy():
    print("==========================================")
    print(" Deploying ADK Agent to Agent Engine")
    print("=========================================="
    print(f"Project:        {PROJECT_ID}")
    print(f"Region:         {REGION}")
    print(f"Staging Bucket: {STAGING_BUCKET}")
    print("==========================================")

    vertexai.init(
        project=PROJECT_ID,
        location=REGION,
        staging_bucket=STAGING_BUCKET,
    )

    requirements = [
        "google-cloud-aiplatform>=1.60.0",
        "google-genai>=0.1.1",
        "requests>=2.31.0",
        "pydantic>=2.0.0",
    ]

    print("\nStep 1/2: Initializing local GemmaAgent instance...")
    agent_instance = GemmaAgent(
        project_id=PROJECT_ID,
        region=REGION,
        system_instruction=(
            "You are a helpful and versatile AI assistant powered by Google Gemma models. "
            "You dynamically discover and route queries to active Gemma endpoints across GCP."
        ),
        tools=[get_current_time, calculate],
    )

    print("\nStep 2/2: Deploying to Vertex AI Agent Engine (Reasoning Engines)...")
    remote_agent = reasoning_engines.ReasoningEngine.create(
        reasoning_engine=agent_instance,
        requirements=requirements,
        display_name="gemma-adk-agent",
        description="ADK Agent powered dynamically by Google Gemma endpoints with scale-to-zero awareness.",
    )

    print("\n==========================================")
    print(" Deployment Successful!")
    print(f" Resource Name: {remote_agent.resource_name}")
    print("==========================================")
    return remote_agent

if __name__ == "__main__":
    deploy()
