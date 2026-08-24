variable "project_id" {
  description = "The Google Cloud Project ID to deploy resources into."
  type        = string
  default     = "dandye-0324-chronicle"
}

variable "region" {
  description = "The Google Cloud Region for resources."
  type        = string
  default     = "us-central1"
}

# ------------------------------------------------------------------------------
# Feature Flags
# ------------------------------------------------------------------------------
variable "enable_vertex_endpoint" {
  description = "Whether to provision the Vertex AI Endpoint resource."
  type        = bool
  default     = true
}

variable "enable_cloudrun_service" {
  description = "Whether to deploy the Cloud Run Serverless GPU service."
  type        = bool
  default     = true
}

# ------------------------------------------------------------------------------
# Vertex AI Configuration
# ------------------------------------------------------------------------------
variable "vertex_endpoint_name" {
  description = "Display name of the Vertex AI Endpoint."
  type        = string
  default     = "gemma-endpoint"
}

variable "vertex_endpoint_description" {
  description = "Description of the Vertex AI Endpoint."
  type        = string
  default     = "Vertex AI Online Prediction Endpoint for Gemma open models"
}

# ------------------------------------------------------------------------------
# Cloud Run Configuration
# ------------------------------------------------------------------------------
variable "cloudrun_service_name" {
  description = "Name of the Cloud Run service."
  type        = string
  default     = "gemma-cloudrun-service"
}

variable "cloudrun_model_name" {
  description = "Hugging Face / Model identifier to serve in vLLM container."
  type        = string
  default     = "google/gemma-2-9b-it"
}

variable "cloudrun_container_image" {
  description = "vLLM container image for Cloud Run."
  type        = string
  default     = "vllm/vllm-openai:latest"
}

variable "cloudrun_cpu" {
  description = "Number of vCPUs allocated to Cloud Run container."
  type        = string
  default     = "8"
}

variable "cloudrun_memory" {
  description = "System memory allocated to Cloud Run container."
  type        = string
  default     = "32Gi"
}

variable "cloudrun_gpu_count" {
  description = "Number of GPUs attached to each Cloud Run instance."
  type        = string
  default     = "1"
}

variable "cloudrun_gpu_type" {
  description = "Type of GPU for Cloud Run."
  type        = string
  default     = "nvidia-l4"
}

variable "cloudrun_min_instances" {
  description = "Minimum number of instances (0 for scale-to-zero)."
  type        = number
  default     = 0
}

variable "cloudrun_max_instances" {
  description = "Maximum number of instances."
  type        = number
  default     = 1
}

variable "cloudrun_timeout_seconds" {
  description = "Request timeout in seconds (supports cold start weight loading)."
  type        = number
  default     = 900
}

variable "cloudrun_swap_space" {
  description = "vLLM CPU swap space in GiB."
  type        = number
  default     = 4
}

variable "cloudrun_gpu_memory_utilization" {
  description = "vLLM GPU memory utilization fraction."
  type        = number
  default     = 0.90
}

variable "cloudrun_max_model_len" {
  description = "vLLM max model context length."
  type        = number
  default     = 4096
}

variable "hf_token" {
  description = "Hugging Face access token for gated models (e.g. Gemma)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated public access to Cloud Run service."
  type        = bool
  default     = true
}
