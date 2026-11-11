variable "kubeconfig_path" {
  type    = string
  default = "../cluster-local/.state/kubeconfig"
}

variable "namespace" {
  type    = string
  default = "geoscholar"
}

variable "api_image_repository" {
  type        = string
  default     = "ghcr.io/OWNER/geoscholar-api"
  description = "API image repository. Override for a local or real registry."
}

variable "ui_image_repository" {
  type        = string
  default     = "ghcr.io/OWNER/geoscholar-ui"
  description = "UI image repository. Override for a local or real registry."
}

variable "api_image_tag" {
  type    = string
  default = "latest"
}

variable "ui_image_tag" {
  type    = string
  default = "latest"
}

variable "ollama_url" {
  type        = string
  default     = "http://ollama:11434"
  description = "Host-compose Ollama, reachable by DNS name via the shared k3d network."
}

variable "llm_model" {
  type        = string
  default     = "llama3.1:8b"
  description = "Local compose Ollama model; CI overrides to qwen2.5:0.5b."
}
