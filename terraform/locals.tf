locals {
  catalog_raw = jsondecode(file("${path.module}/../configs/models.json"))

  # Active model configuration from catalog
  selected_model = local.catalog_raw[var.model_flavor]

  # Model metadata
  display_name = lookup(local.selected_model, "displayName", var.model_flavor)
  family       = lookup(local.selected_model, "family", "unknown")
  params       = lookup(local.selected_model, "params", "N/A")
  model_type   = lookup(local.selected_model, "type", "model_garden")
  provider     = lookup(local.selected_model, "provider", "google")

  # Compute mapping (handles dedicated GPU models with fallback for serverless/MaaS)
  compute_block            = lookup(local.selected_model, "compute", {})
  vertex_machine_type      = lookup(local.compute_block, "machineType", null)
  vertex_accelerator_type  = lookup(local.compute_block, "acceleratorType", null)
  vertex_accelerator_count = lookup(local.compute_block, "acceleratorCount", 0)
  vertex_source_uri        = lookup(local.selected_model, "sourceUri", lookup(local.selected_model, "openModelId", lookup(local.selected_model, "hfRepo", "")))
  hourly_cost_usd          = lookup(local.compute_block, "hourlyCostUsd", 0.0)

  # Runtime and container image resolution
  runtime_block             = lookup(local.selected_model, "runtime", {})
  default_container_image   = "us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01"
  effective_container_image = lookup(local.runtime_block, "containerImage", local.default_container_image)
  swap_space_gb             = lookup(local.runtime_block, "swapSpaceGb", 0)
  tensor_parallel_size      = lookup(local.runtime_block, "tensorParallelSize", 1)
  gpu_memory_utilization    = lookup(local.runtime_block, "gpuMemoryUtilization", 0.90)
  max_model_len             = lookup(local.runtime_block, "maxModelLen", 8192)
  extra_args                = lookup(local.runtime_block, "extraArgs", [])

  # Target compatibility
  supported_targets     = lookup(local.selected_model, "supportedTargets", [])
  is_cloudrun_supported = contains(local.supported_targets, "cloudrun")

  # Cloud Run arguments construction
  cloudrun_model_repo = lookup(local.selected_model, "hfRepo", lookup(local.selected_model, "openModelId", ""))
  extra_flags_list    = var.extra_vllm_flags != "" ? split(" ", var.extra_vllm_flags) : []

  cloudrun_args = concat(
    [
      "--model=${local.cloudrun_model_repo}",
      "--swap-space=${local.swap_space_gb}",
      "--gpu-memory-utilization=${local.gpu_memory_utilization}",
      "--max-model-len=${local.max_model_len}",
      "--port=8000"
    ],
    local.extra_args,
    local.extra_flags_list
  )
}
