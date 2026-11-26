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
    deployment_timeout: int = 7200,
    shared_memory_size_mb: int = None,
    dry_run: bool = False,
):
    catalog = load_catalog()
    if flavor in catalog:
        spec = catalog[flavor]
        if spec.get("type") == "maas":
            maas_model_id = spec.get("maasModelId") or spec.get("modelId") or flavor
            maas_region = spec.get("region", "global")
            raise ValueError(
                f"Flavor '{flavor}' is a serverless Vertex OpenMaaS model "
                f"(type='maas', maasModelId='{maas_model_id}', region='{maas_region}') "
                f"and must not be deployed to a dedicated GPU endpoint. "
                f"Evaluate serverless OpenMaaS directly via:\n"
                f"  .venv/bin/python scripts/benchmark.py --maas-model {maas_model_id} --region {maas_region}\n"
                f"  .venv/bin/python scripts/eval_soc_agent.py --flavor {flavor}"
            )
        open_model_id = spec.get("openModelId", open_model_id)
        compute = spec.get("compute", {})
        machine_type = compute.get("machineType", machine_type)
        accelerator_type = compute.get("acceleratorType", accelerator_type)
        accelerator_count = compute.get("acceleratorCount", accelerator_count)
        runtime = spec.get("runtime", {})
        container_image = runtime.get("containerImage", container_image)
        if shared_memory_size_mb is None:
            shared_memory_size_mb = runtime.get("sharedMemorySizeMb")
        if deployment_timeout == 7200:
            deployment_timeout = runtime.get("deploymentTimeoutSeconds", deployment_timeout)

    timestamp = int(time.time() * 1000)
    safe_flavor = flavor.replace("-", "_").replace(".", "_")
    endpoint_display_name = endpoint_name or f"{safe_flavor}-mg-one-click-deploy"
    model_display_name = f"{safe_flavor}-{timestamp}"
    shared_mem_display = f"{shared_memory_size_mb} MB" if shared_memory_size_mb is not None else "default"

    print("==================================================================")
    print(f" Deploying OpenModel: {flavor} ({open_model_id})")
    print(f" Project:            {project_id}")
    print(f" Location:           {location}")
    print(f" Machine Type:       {machine_type}")
    print(f" Accelerator:        {accelerator_count}x {accelerator_type}")
    print(f" Container Image:    {container_image}")
    print(f" Shared Memory:      {shared_mem_display}")
    print(f" Deployment Timeout: {deployment_timeout}s")
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
    deploy_kwargs = {
        "accept_eula": True,
        "machine_type": machine_type,
        "accelerator_type": accelerator_type,
        "accelerator_count": accelerator_count,
        "endpoint_display_name": endpoint_display_name,
        "model_display_name": model_display_name,
        "use_dedicated_endpoint": True,
        "reservation_affinity_type": "NO_RESERVATION",
        "deploy_request_timeout": float(deployment_timeout),
        "serving_container_deployment_timeout": int(deployment_timeout),
    }
    if not str(open_model_id).startswith("publishers/"):
        deploy_kwargs["serving_container_image_uri"] = container_image
        if shared_memory_size_mb is not None:
            deploy_kwargs["serving_container_shared_memory_size_mb"] = int(shared_memory_size_mb)

    endpoint = model.deploy(**deploy_kwargs)

    print(">>> Deployment complete!")
    print(f"Endpoint Resource Name: {endpoint.resource_name}")
    return endpoint


def main():
    parser = argparse.ArgumentParser(description="Deploy OpenModel via Vertex AI Model Garden SDK.")
    parser.add_argument("--flavor", default="qwen3.8-27b", help="Model flavor key in catalog")
    parser.add_argument("--open-model-id", default="hf-qwen/qwen3.8-27b@001", help="OpenModel ID in Model Garden")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle"))
    parser.add_argument("--region", default=os.environ.get("GCP_REGION", "us-central1"))
    parser.add_argument(
        "--deployment-timeout",
        type=int,
        default=None,
        help="Deployment timeout in seconds (defaults to catalog deploymentTimeoutSeconds or 7200)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print configuration without deploying")
    args = parser.parse_args()

    deploy_call_kwargs = {
        "flavor": args.flavor,
        "project_id": args.project_id,
        "location": args.region,
        "open_model_id": args.open_model_id,
        "dry_run": args.dry_run,
    }
    if args.deployment_timeout is not None:
        deploy_call_kwargs["deployment_timeout"] = args.deployment_timeout

    try:
        deploy_open_model(**deploy_call_kwargs)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
