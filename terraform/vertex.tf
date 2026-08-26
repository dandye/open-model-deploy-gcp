# ------------------------------------------------------------------------------
# Vertex AI Online Prediction Endpoint
# ------------------------------------------------------------------------------

resource "google_vertex_ai_endpoint" "gemma_endpoint" {
  count = var.enable_vertex_endpoint ? 1 : 0

  name         = var.vertex_endpoint_name
  display_name = var.vertex_endpoint_name
  description  = "${var.vertex_endpoint_description} - ${local.display_name} (${local.vertex_accelerator_count}x ${local.vertex_accelerator_type} on ${local.vertex_machine_type})"
  location     = var.region
  project      = var.project_id

  labels = {
    managed_by   = "terraform"
    workload     = "gemma-deployment"
    model_flavor = var.model_flavor
    family       = local.family
  }
}
