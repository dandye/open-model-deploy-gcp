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
# Model Flavor & Runtime Optimization
# ------------------------------------------------------------------------------
variable "model_flavor" {
  description = "Model flavor to deploy from configs/models.json (e.g. gemma-2-9b-it, gemma-3-4b-it, gemma-4-31b-it, qwen3.8-27b, llama-3.2-3b-instruct)."
  type        = string
  default     = "gemma-2-9b-it"

  validation {
    condition = contains([
      "gemma-2-2b-it",
      "gemma-2-9b-it",
      "gemma-2-27b-it",
      "gemma-3-1b-it",
      "gemma-3-4b-it",
      "gemma-3-12b-it",
      "gemma-3-27b-it",
      "gemma-4-31b-it",
      "gemma-4-e2b-it",
      "gemma-4-e4b-it",
      "inkling-small",
      "nemotron-3.5-lightning-bf16",
      "nemotron-3.5-super-vl-nvfp4",
      "nemotron-3.5-super-vl-bf16",
      "qwen3.8-27b",
      "qwen2.5-coder-32b-instruct",
      "ministral-3b-2410",
      "phi-4",
      "deepseek-r1-distill-qwen-32b",
      "qwen3.8-flash-next",
      "qwen3.8-flash-next-fp8",
      "qwen3.8-2.4t-a95b-fp8",
      "glm-5.3-flash",
      "deepseek-v4-pro",
      "kimi-k3",
      "llama-3.2-3b-instruct",
      "llama-guard-3-8b",
      "llama-3.1-nemotron-70b-instruct"
    ], var.model_flavor)
    error_message = "The model_flavor must be one of the dedicated compute models defined in configs/models.json."
  }
}

variable "extra_vllm_flags" {
  description = "Additional runtime flags passed to vLLM (e.g. --quantization=fp8, --speculative-model=[ngram] --num-speculative-tokens=5, --enable-prefix-caching, --enable-chunked-prefill)."
  type        = string
  default     = ""
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
  description = "Whether to deploy the Cloud Run Serverless GPU service (only applies to single-GPU models)."
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
  default     = "Vertex AI Online Prediction Endpoint for open models"
}

# ------------------------------------------------------------------------------
# Cloud Run Configuration
# ------------------------------------------------------------------------------
variable "cloudrun_service_name" {
  description = "Name of the Cloud Run service."
  type        = string
  default     = "gemma-cloudrun-service"
}

variable "cloudrun_container_image" {
  description = "vLLM container image for Cloud Run."
  type        = string
  default     = "vllm/vllm-openai:latest"
}

variable "cloudrun_cpu" {
  description = "Number of vCPUs allocated to Cloud Run container."
  type        = string
  default     = "4"
}

variable "cloudrun_memory" {
  description = "System memory allocated to Cloud Run container."
  type        = string
  default     = "16Gi"
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

variable "hf_token" {
  description = "Hugging Face access token for gated models (e.g. Gemma, Llama)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated public access to Cloud Run service."
  type        = bool
  default     = true
}
