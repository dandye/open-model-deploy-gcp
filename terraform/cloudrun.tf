# ------------------------------------------------------------------------------
# Cloud Run Serverless GPU Service (Scale-to-Zero)
# ------------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "gemma_service" {
  count    = var.enable_cloudrun_service ? 1 : 0
  provider = google-beta

  name     = var.cloudrun_service_name
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    timeout               = "${var.cloudrun_timeout_seconds}s"

    scaling {
      min_instance_count = var.cloudrun_min_instances
      max_instance_count = var.cloudrun_max_instances
    }

    node_selector {
      accelerator = var.cloudrun_gpu_type
    }

    containers {
      image = var.cloudrun_container_image

      args = [
        "--model=${var.cloudrun_model_name}",
        "--swap-space=${var.cloudrun_swap_space}",
        "--gpu-memory-utilization=${var.cloudrun_gpu_memory_utilization}",
        "--max-model-len=${var.cloudrun_max_model_len}",
        "--port=8000"
      ]

      resources {
        limits = {
          cpu              = var.cloudrun_cpu
          memory           = var.cloudrun_memory
          "nvidia.com/gpu" = var.cloudrun_gpu_count
        }
      }

      ports {
        container_port = 8000
      }

      env {
        name  = "HF_TOKEN"
        value = var.hf_token
      }

      env {
        name  = "VLLM_LOGGING_LEVEL"
        value = "INFO"
      }
    }

    labels = {
      managed_by = "terraform"
      workload   = "gemma-deployment"
    }
  }
}

# Allow unauthenticated access if configured
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count    = (var.enable_cloudrun_service && var.allow_unauthenticated) ? 1 : 0
  provider = google-beta

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.gemma_service[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
