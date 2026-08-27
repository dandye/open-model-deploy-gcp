#!/usr/bin/env python3
"""Deploy Hugging Face / Model Garden OpenModels to Vertex AI using vertexai.model_garden.OpenModel."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

ROOT_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT_DIR / "configs" / "models.json"


def load_catalog():
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def deploy_open_model(
    flavor: str,
    project_id: str = "dandye-0324-chronicle",
    location: str = "us-central1",
    open_model_id: str = "hf-qwen/qwen3.8-27b@001",
    machine_type: str = "g4-standard-48",
    accelerator_type: str = "NVIDIA_RTX_PRO_6000",
    accelerator_count: int = 1,
    container_image: str = "us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20260713_0916_RC01",
    endpoint_name: str = None,
    dry_run: bool = False,
):
    catalog = load_catalog()
    if flavor in catalog:
        spec = catalog[flavor]
        open_model_id = spec.get("openModelId", open_model_id)
        compute = spec.get("compute", {})
        machine_type = compute.get("machineType", machine_type)
        accelerator_type = compute.get("acceleratorType", accelerator_type)
        accelerator_count = compute.get("acceleratorCount", accelerator_count)
        runtime = spec.get("runtime", {})
        container_image = runtime.get("containerImage", container_image)

    timestamp = int(time.time() * 1000)
    safe_flavor = flavor.replace("-", "_").replace(".", "_")
    endpoint_display_name = endpoint_name or f"{safe_flavor}-mg-one-click-deploy"
    model_display_name = f"{safe_flavor}-{timestamp}"

    print("==================================================================")
    print(f" Deploying OpenModel: {flavor} ({open_model_id})")
    print(f" Project:            {project_id}")
    print(f" Location:           {location}")
    print(f" Machine Type:       {machine_type}")
    print(f" Accelerator:        {accelerator_count}x {accelerator_type}")
    print(f" Container Image:    {container_image}")
    print(f" Endpoint Name:      {endpoint_display_name}")
    print("==================================================================")

    if dry_run:
        print("[DRY RUN] Skipping actual deployment.")
        return None

    import vertexai
    from vertexai import model_garden

    vertexai.init(project=project_id, location=location)

    print(">>> Initializing model_garden.OpenModel...")
    model = model_garden.OpenModel(open_model_id)

    print(">>> Deploying model to dedicated endpoint (this may take 10-15 minutes)...")
    endpoint = model.deploy(
        accept_eula=True,
        machine_type=machine_type,
        accelerator_type=accelerator_type,
        accelerator_count=accelerator_count,
        serving_container_image_uri=container_image,
        endpoint_display_name=endpoint_display_name,
        model_display_name=model_display_name,
        use_dedicated_endpoint=True,
        reservation_affinity_type="NO_RESERVATION",
    )

    print(">>> Deployment complete!")
    print(f"Endpoint Resource Name: {endpoint.resource_name}")
    return endpoint


def main():
    parser = argparse.ArgumentParser(description="Deploy OpenModel via Vertex AI Model Garden SDK.")
    parser.add_argument("--flavor", default="qwen3.8-27b", help="Model flavor key in catalog")
    parser.add_argument("--open-model-id", default="hf-qwen/qwen3.8-27b@001", help="OpenModel ID in Model Garden")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle"))
    parser.add_argument("--region", default=os.environ.get("GCP_REGION", "us-central1"))
    parser.add_argument("--dry-run", action="store_true", help="Print configuration without deploying")
    args = parser.parse_args()

    deploy_open_model(
        flavor=args.flavor,
        project_id=args.project_id,
        location=args.region,
        open_model_id=args.open_model_id,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
