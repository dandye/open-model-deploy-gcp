output "model_flavor" {
  description = "The selected model flavor."
  value       = var.model_flavor
}

output "model_display_name" {
  description = "The display name of the selected model."
  value       = local.display_name
}

output "model_family" {
  description = "The family of the selected model (e.g. gemma2, gemma3, gemma4, qwen, llama)."
  value       = local.family
}

output "model_params" {
  description = "Parameter count / size of the selected model."
  value       = local.params
}

output "hourly_cost_usd" {
  description = "Estimated hourly compute cost in USD for the dedicated GPU VM."
  value       = local.hourly_cost_usd
}

output "vertex_machine_type" {
  description = "The Compute Engine machine type for Vertex AI."
  value       = local.vertex_machine_type
}

output "vertex_accelerator" {
  description = "The accelerator configuration for Vertex AI."
  value       = local.vertex_accelerator_type != null ? "${local.vertex_accelerator_count}x ${local.vertex_accelerator_type}" : "N/A"
}

output "vertex_source_uri" {
  description = "Model weights source URI or OpenModel repository identifier."
  value       = local.vertex_source_uri
}

output "vertex_container_image" {
  description = "The vLLM container image used for Vertex AI serving."
  value       = local.effective_container_image
}

output "vertex_endpoint_id" {
  description = "The ID of the provisioned Vertex AI Endpoint."
  value       = var.enable_vertex_endpoint ? google_vertex_ai_endpoint.gemma_endpoint[0].id : null
}

output "vertex_endpoint_name" {
  description = "The resource name of the provisioned Vertex AI Endpoint."
  value       = var.enable_vertex_endpoint ? google_vertex_ai_endpoint.gemma_endpoint[0].name : null
}

output "cloudrun_supported" {
  description = "Whether the selected model flavor is compatible with Cloud Run (1x GPU limit)."
  value       = local.is_cloudrun_supported
}

output "cloudrun_service_url" {
  description = "The HTTPS URL of the deployed Cloud Run service."
  value       = (var.enable_cloudrun_service && local.is_cloudrun_supported) ? google_cloud_run_v2_service.gemma_service[0].uri : null
}

output "cloudrun_service_name" {
  description = "The name of the Cloud Run service."
  value       = (var.enable_cloudrun_service && local.is_cloudrun_supported) ? google_cloud_run_v2_service.gemma_service[0].name : null
}
