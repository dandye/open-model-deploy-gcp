locals {
  catalog_raw = jsondecode(file("${path.module}/../configs/models.json"))
  
  # Active model configuration from catalog
  selected_model = local.catalog_raw[var.model_flavor]

  # Compute mapping
  vertex_machine_type      = local.selected_model.compute.machineType
  vertex_accelerator_type  = local.selected_model.compute.acceleratorType
  vertex_accelerator_count = local.selected_model.compute.acceleratorCount

  # Cloud Run mapping
  cloudrun_model_repo      = local.selected_model.hfRepo
  cloudrun_max_model_len   = local.selected_model.runtime.maxModelLen
  cloudrun_gpu_utilization = local.selected_model.runtime.gpuMemoryUtilization
}
