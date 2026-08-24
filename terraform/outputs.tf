output "vertex_endpoint_id" {
  description = "The ID of the provisioned Vertex AI Endpoint."
  value       = var.enable_vertex_endpoint ? google_vertex_ai_endpoint.gemma_endpoint[0].id : null
}

output "vertex_endpoint_name" {
  description = "The resource name of the provisioned Vertex AI Endpoint."
  value       = var.enable_vertex_endpoint ? google_vertex_ai_endpoint.gemma_endpoint[0].name : null
}

output "cloudrun_service_url" {
  description = "The HTTPS URL of the deployed Cloud Run service."
  value       = var.enable_cloudrun_service ? google_cloud_run_v2_service.gemma_service[0].uri : null
}

output "cloudrun_service_name" {
  description = "The name of the Cloud Run service."
  value       = var.enable_cloudrun_service ? google_cloud_run_v2_service.gemma_service[0].name : null
}
