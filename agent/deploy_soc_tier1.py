#!/usr/bin/env python3
"""Deploy SocTier1Agent to Vertex AI Agent Engine (Reasoning Engines)."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

import vertexai
from vertexai.preview import reasoning_engines
from agent.soc_tier1_agent import SocTier1Agent

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle")
REGION = os.environ.get("GCP_REGION", "us-central1")
STAGING_BUCKET = os.environ.get("GCS_STAGING_BUCKET", f"gs://{PROJECT_ID}-soc-agent-artifacts")



def get_deployment_config() -> Dict[str, Any]:
    """Returns deployment parameters and required pip packages."""
    return {
        "display_name": "gemma-soc-tier1-agent",
        "description": "Gemma-powered Tier 1 SOC Analyst Agent with live Google SecOps Remote MCP tools.",
        "requirements": [
            "google-cloud-aiplatform>=1.60.0",
            "google-genai>=0.1.1",
            "google-auth>=2.0.0",
            "pydantic>=2.0.0",
            "requests>=2.31.0",
        ],
    }


def deploy(
    project_id: Optional[str] = None,
    region: Optional[str] = None,
    staging_bucket: Optional[str] = None,
    use_live_mcp: bool = True,
):
    """Deploys SocTier1Agent to Vertex AI Agent Engine."""
    target_project = project_id or PROJECT_ID
    target_region = region or REGION
    target_bucket = staging_bucket or (
        os.environ.get("GCS_STAGING_BUCKET") or f"gs://{target_project}-agent-engine-staging"
    )

    print("==========================================")
    print(" Deploying SOC Tier 1 Agent to Agent Engine")
    print("==========================================")
    print(f"Project:        {target_project}")
    print(f"Region:         {target_region}")
    print(f"Staging Bucket: {target_bucket}")
    print(f"Live SecOps:    {'Enabled' if use_live_mcp else 'Disabled (Local Mock Tools)'}")
    print("==========================================")

    vertexai.init(
        project=target_project,
        location=target_region,
        staging_bucket=target_bucket,
    )

    config = get_deployment_config()
    agent_instance = SocTier1Agent(
        project_id=target_project,
        region=target_region,
        use_live_mcp=use_live_mcp,
    )

    os.chdir(ROOT_DIR)
    remote_agent = reasoning_engines.ReasoningEngine.create(
        reasoning_engine=agent_instance,
        requirements=config["requirements"],
        extra_packages=["agent"],
        display_name=config["display_name"],
        description=config["description"],
    )



    print("\n==========================================")
    print(" SOC Agent Deployment Successful!")
    print(f" Resource Name: {remote_agent.resource_name}")
    print("==========================================")
    return remote_agent


if __name__ == "__main__":
    live_mcp_flag = os.environ.get("USE_LIVE_MCP", "true").lower() in ("1", "true", "yes")
    deploy(use_live_mcp=live_mcp_flag)

