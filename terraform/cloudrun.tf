# ------------------------------------------------------------------------------
# Cloud Run Serverless GPU Service (Scale-to-Zero)
# ------------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "gemma_service" {
  count    = (var.enable_cloudrun_service && local.is_cloudrun_supported) ? 1 : 0
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

      args = local.cloudrun_args

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

      dynamic "env" {
        for_each = var.hf_token != "" ? [var.hf_token] : []
        content {
          name  = "HF_TOKEN"
          value = env.value
        }
      }

      env {
        name  = "MODEL_ID"
        value = local.cloudrun_model_repo
      }

      env {
        name  = "VLLM_LOGGING_LEVEL"
        value = "INFO"
      }
    }

    labels = {
      managed_by   = "terraform"
      workload     = "gemma-deployment"
      model_flavor = var.model_flavor
      family       = local.family
    }
  }
}

# Allow unauthenticated access if configured and Cloud Run service is active
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count    = (var.enable_cloudrun_service && local.is_cloudrun_supported && var.allow_unauthenticated) ? 1 : 0
  provider = google-beta

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.gemma_service[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
